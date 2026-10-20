#!/usr/bin/env node
/**
 * Test the full path: a real article, split into parts, synthesised in sequence.
 *
 * This is the case that broke in the browser: a whole article is several
 * minutes of speech, far past the 20-second cap of a single render.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const SANOTTS = path.join(ROOT, 'sanotts');

function loadScript(file) {
  const src = fs.readFileSync(path.join(SANOTTS, file), 'utf8');
  const ctx = vm.createContext({
    console, setTimeout, clearTimeout, setInterval, clearInterval,
    process, require, __dirname: SANOTTS, __filename: path.join(SANOTTS, file),
    TextDecoder, TextEncoder, URL, fetch: globalThis.fetch,
    performance: globalThis.performance, WebAssembly, Buffer,
    document: { currentScript: { src: path.join(SANOTTS, file) } },
    navigator: { userAgent: 'node' },
  });
  ctx.globalThis = ctx;
  ctx.self = ctx;
  vm.runInContext(src, ctx, { filename: file });
  return ctx;
}

(async () => {
  const g2pCtx = loadScript('snt_g2p.js');
  const voiceCtx = loadScript('snt_voice.js');
  const locateFile = (p) => path.join(SANOTTS, p);
  const g2p = await g2pCtx.SaanoG2P({ printErr: () => {}, locateFile });
  const voice = await voiceCtx.SaanoVoice({ locateFile });
  g2p._snt_g2p_init();

  const meta = JSON.parse(fs.readFileSync(path.join(SANOTTS, 'voices', 'italian', 'meta.json'), 'utf8'));
  const widenF16 = (bytes, dims) => {
    const head = Number(dims.meta_bytes), n = Number(dims.weight_floats);
    if (bytes.length !== head + 2 * n) throw new Error('f16 blob size mismatch');
    const out = new Uint8Array(head + 4 * n);
    out.set(bytes.subarray(0, head), 0);
    const src = new DataView(bytes.buffer, bytes.byteOffset + head, 2 * n);
    const dst = new DataView(out.buffer, head, 4 * n);
    for (let i = 0; i < n; i++) {
      const b = src.getUint16(i * 2, true);
      const exp = (b >> 10) & 0x1f, frac = b & 0x3ff, sign = (b & 0x8000) ? -1 : 1;
      let v;
      if (exp === 0) v = sign * frac * 5.960464477539063e-8;
      else if (exp === 31) v = frac ? NaN : sign * Infinity;
      else v = sign * Math.pow(2, exp - 25) * (1024 + frac);
      dst.setFloat32(i * 4, v, true);
    }
    return out;
  };
  const load = (f) => new Uint8Array(fs.readFileSync(path.join(SANOTTS, 'voices', 'italian', f)));
  const front = widenF16(load('front_f16.bin'), meta.front_dims);
  const dec = widenF16(load('dec_f16.bin'), meta.dec_dims);

  // the splitter, taken from the module
  const mod = fs.readFileSync(path.join(ROOT, 'assets', 'zen-speech.js'), 'utf8');
  const splitSrc = mod.match(/function splitForSpeech[\s\S]*?\n}/)[0];
  const splitForSpeech = new Function(splitSrc + '; return splitForSpeech;')();

  // a real article, from articles.json
  const arts = JSON.parse(fs.readFileSync(path.join(ROOT, 'articles.json'), 'utf8'));
  const art = arts.find(a => a.slug === 'two-agents-can-agree-perfectly-and-still-be-incompatible')
           || arts[0];
  const plain = String(art.translation || art.content || '')
    .replace(/<[^>]+>/g, ' ').replace(/&[a-z]+;/gi, ' ').replace(/\s+/g, ' ').trim();

  console.log('articolo: ' + art.id);
  console.log('lunghezza testo: ' + plain.length + ' caratteri');

  const parts = splitForSpeech(plain, 260);
  console.log('parti: ' + parts.length + ' (max ' + Math.max(...parts.map(p => p.length)) + ' caratteri)');
  console.log('testo preservato: ' + (parts.join(' ') === plain));

  const setVoice = g2p.cwrap('snt_g2p_set_voice', 'number', ['string', 'number']);
  const idsOf = (text) => {
    const tp = g2p._malloc(g2p.lengthBytesUTF8(text) + 1);
    g2p.stringToUTF8(text, tp, g2p.lengthBytesUTF8(text) + 1);
    const op = g2p._malloc(1024 * 4);
    const n = g2p._snt_g2p_text_to_ids(tp, op, 1024);
    let out = null;
    if (n > 0) out = new Int32Array(g2p.HEAP32.buffer, op, n).slice();
    g2p._free(tp); g2p._free(op);
    if (n <= 0) throw new Error('fonemizzatore: ' + n);
    return Array.from(out);
  };
  const toHeap = (m, b) => { const p = m._malloc(b.length); m.HEAPU8.set(b, p); return p; };

  const CAP = meta.sample_rate * 20;
  let total = 0, failures = 0, totalSec = 0;
  const t0 = Date.now();
  for (let i = 0; i < parts.length; i++) {
    setVoice('it', meta.g2p_voice_slot);
    const ids = idsOf(parts[i]);
    const frontP = toHeap(voice, front), decP = toHeap(voice, dec);
    const idsP = toHeap(voice, new Uint8Array(new Int32Array(ids).buffer));
    const outP = voice._malloc(CAP * 4);
    const n = voice._snt_voice_synthesize(frontP, decP, idsP, ids.length, meta.length_scale, outP, CAP);
    [frontP, decP, idsP, outP].forEach(p => voice._free(p));
    if (n < 0) { failures++; console.log('  parte ' + (i + 1) + ': FALLITA (' + n + ')'); continue; }
    const bytes = new Uint8Array(voice.HEAPU8.buffer, outP, n * 4);
    const pcm = new Float32Array(bytes.buffer, bytes.byteOffset, n);
    let peak = 0, sum = 0;
    for (let k = 0; k < n; k++) { const a = Math.abs(pcm[k]); if (a > peak) peak = a; sum += pcm[k] * pcm[k]; }
    const rms = Math.sqrt(sum / n);
    total += n; totalSec += n / meta.sample_rate;
    if (peak < 0.01) console.log('  parte ' + (i + 1) + ': SILENZIO');
    if (i === 0) console.log('  parte 1: ' + n + ' campioni, peak ' + peak.toFixed(3) + ', rms ' + rms.toFixed(3));
  }
  const wall = (Date.now() - t0) / 1000;

  console.log('');
  console.log('parti fallite: ' + failures + ' / ' + parts.length);
  console.log('audio totale: ' + totalSec.toFixed(1) + ' s');
  console.log('tempo di sintesi: ' + wall.toFixed(1) + ' s (rapporto ' + (totalSec / wall).toFixed(1) + 'x tempo reale)');
  console.log(failures === 0 ? 'OK: tutte le parti sono state sintetizzate' : 'FALLITO');
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => { console.error('ERRORE:', e && e.message ? e.message : e); process.exit(1); });
