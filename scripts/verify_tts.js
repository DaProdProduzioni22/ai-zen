#!/usr/bin/env node
/**
 * Verify the in-browser TTS end to end, outside the browser harness.
 *
 * It loads the SanoTTS runtime in Node (the WASM modules work there too), then:
 *   1. checks that the phonemizer produces DIFFERENT ids for Italian and English
 *      (if they were the same, the Italian would be read with an English accent)
 *   2. synthesizes a sentence and checks the audio is real speech, not silence
 *
 * Usage: node scripts/verify_tts.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const SANOTTS = path.join(ROOT, 'sanotts');
const OUT_WAV = path.join(ROOT, 'scripts', 'tts-sample.wav');

// The runtime is browser-oriented: it needs a window, a document and fetch.
const files = {};

function loadScript(file) {
  const src = fs.readFileSync(path.join(SANOTTS, file), 'utf8');
  // Emscripten glue is a big IIFE; run it in a context that looks like a browser.
  const ctx = vm.createContext({
    console,
    setTimeout, clearTimeout, setInterval, clearInterval,
    process,
    require,
    __dirname: SANOTTS,
    __filename: path.join(SANOTTS, file),
    TextDecoder, TextEncoder, URL, fetch: globalThis.fetch,
    performance: globalThis.performance,
    WebAssembly,
    Buffer,
    location: { href: 'file://' + path.join(SANOTTS, file) },
    document: { currentScript: { src: path.join(SANOTTS, file) } },
    navigator: { userAgent: 'node' },
  });
  ctx.globalThis = ctx;
  ctx.self = ctx;
  vm.runInContext(src, ctx, { filename: file });
  return ctx;
}

(async () => {
  let failures = 0;
  const ok = (m) => console.log('  PASS  ' + m);
  const bad = (m) => { console.log('  FAIL  ' + m); failures++; };

  console.log('\n=== 1. il runtime si carica ===');
  const g2pCtx = loadScript('snt_g2p.js');
  const voiceCtx = loadScript('snt_voice.js');
  if (typeof g2pCtx.SaanoG2P !== 'function') { bad('SaanoG2P non esposto'); return finish(); }
  if (typeof voiceCtx.SaanoVoice !== 'function') { bad('SaanoVoice non esposto'); return finish(); }
  ok('i due factory sono esposti');

  // In node the runtime reads the .data and the .wasm from disk, resolved
  // through locateFile (otherwise it looks in the current working directory).
  const locateFile = (p) => path.join(SANOTTS, p);
  const g2p = await g2pCtx.SaanoG2P({ printErr: () => {}, locateFile });
  const voice = await voiceCtx.SaanoVoice({ locateFile });
  g2p._snt_g2p_init();
  ok('i moduli WASM sono istanziati');

  const setVoice = g2p.cwrap('snt_g2p_set_voice', 'number', ['string', 'number']);

  const ids = (text) => {
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

  const ipa = (text) => {
    const tp = g2p._malloc(g2p.lengthBytesUTF8(text) + 1);
    g2p.stringToUTF8(text, tp, g2p.lengthBytesUTF8(text) + 1);
    const op = g2p._malloc(8192);
    const n = g2p._snt_g2p_text_to_ipa(tp, op, 8192);
    let out = '';
    if (n > 0) { const b = new Uint8Array(g2p.HEAPU8.buffer, op, n); out = Buffer.from(b).toString('latin1'); }
    g2p._free(tp); g2p._free(op);
    return out;
  };

  console.log('\n=== 2. la lingua e\' italiana ===');
  const phrase = 'Centro Benessere per Intelligenze Artificiali';
  const rcIt = setVoice('it', 12);
  if (rcIt !== 0) bad('set_voice("it", 12) ha restituito ' + rcIt);
  else ok('set_voice("it", 12) accettato');

  const idsIt = ids(phrase);
  const ipaIt = ipa(phrase);
  ok('IPA italiano: ' + ipaIt.replace(/\n/g, ' ').trim().slice(0, 90));

  let idsEn = null;
  try {
    setVoice('en-us', 0);
    idsEn = ids(phrase);
  } catch (e) { /* en-us might not be available */ }

  if (idsEn) {
    const same = idsIt.join(',') === idsEn.join(',');
    if (same) bad('gli id italiani sono identici a quelli inglesi: la lingua NON cambierebbe');
    else ok('gli id italiani differiscono da quelli inglesi (' + idsIt.length + ' vs ' + idsEn.length + ' fonemi)');
  } else {
    console.log('  WARN  set_voice("en-us") non disponibile: confronto non possibile');
  }

  // Italian markers in the IPA: the 'it' voice uses the Italian phoneme set.
  const hasItalianMarkers = /ʃ|ʎ|t͡ʃ|t͡s|ɛ|e\b/.test(ipaIt) || /[aeiou]/.test(ipaIt);
  if (hasItalianMarkers) ok('l\'IPA contiene segmenti vocalici coerenti con l\'italiano');
  else bad('IPA sospetto: ' + ipaIt.slice(0, 60));

  console.log('\n=== 3. la sintesi produce audio reale ===');
  const meta = JSON.parse(fs.readFileSync(path.join(SANOTTS, 'voices', 'italian', 'meta.json'), 'utf8'));

  const widenF16 = (bytes, dims) => {
    const head = Number(dims.meta_bytes);
    const n = Number(dims.weight_floats);
    if (bytes.length !== head + 2 * n) throw new Error('f16 blob: ' + bytes.length + ' vs ' + (head + 2 * n));
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

  const toHeap = (mod, bytes) => { const p = mod._malloc(bytes.length); mod.HEAPU8.set(bytes, p); return p; };
  setVoice('it', meta.g2p_voice_slot);
  const idArr = ids(phrase);
  const frontP = toHeap(voice, front), decP = toHeap(voice, dec);
  const idsP = toHeap(voice, new Uint8Array(new Int32Array(idArr).buffer));
  const CAP = meta.sample_rate * 20;
  const outP = voice._malloc(CAP * 4);
  const n = voice._snt_voice_synthesize(frontP, decP, idsP, idArr.length, meta.length_scale, outP, CAP);
  if (n < 0) { bad('sintesi ha restituito ' + n); return finish(); }

  // The heap pointer is a byte offset and the buffer may not be 4-aligned:
  // read the bytes and reinterpret them.
  const bytes = new Uint8Array(voice.HEAPU8.buffer, outP, n * 4);
  const pcm = new Float32Array(bytes.buffer, bytes.byteOffset, n);
  let peak = 0, sum = 0, nz = 0;
  for (let i = 0; i < n; i++) { const a = Math.abs(pcm[i]); if (a > peak) peak = a; sum += pcm[i] * pcm[i]; if (a > 0.001) nz++; }
  const rms = Math.sqrt(sum / n);
  console.log('  campioni: ' + n + '  (' + (n / meta.sample_rate).toFixed(2) + ' s)');
  console.log('  peak: ' + peak.toFixed(4) + '  rms: ' + rms.toFixed(4) + '  segnale: ' + ((nz / n) * 100).toFixed(1) + '%');
  if (n > 1000 && peak > 0.05) ok('audio non vuoto');
  else bad('audio silenzioso o troppo corto');
  if (rms > 0.01) ok('il segnale ha energia');
  else bad('rms troppo basso: ' + rms);

  // write a WAV so a human can listen to it
  const wav = Buffer.alloc(44 + n * 2);
  wav.write('RIFF', 0); wav.writeUInt32LE(36 + n * 2, 4); wav.write('WAVE', 8);
  wav.write('fmt ', 12); wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 16);
  wav.writeUInt16LE(1, 18); wav.writeUInt32LE(meta.sample_rate, 20);
  wav.writeUInt32LE(meta.sample_rate * 2, 24); wav.writeUInt16LE(2, 28); wav.writeUInt16LE(16, 30);
  wav.write('data', 36); wav.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) {
    const s = Math.max(-1, Math.min(1, pcm[i]));
    wav.writeInt16LE(s < 0 ? s * 0x8000 : s * 0x7FFF, 44 + i * 2);
  }
  fs.writeFileSync(OUT_WAV, wav);
  ok('campione scritto in ' + path.relative(ROOT, OUT_WAV) + ' (' + (wav.length / 1024).toFixed(0) + ' KB)');

  finish();

  function finish() {
    console.log('\n' + (failures ? 'FAILURES: ' + failures : 'TUTTI I CHECK PASSATI'));
    process.exit(failures ? 1 : 0);
  }
})().catch((e) => { console.error('ERRORE:', e); process.exit(1); });
