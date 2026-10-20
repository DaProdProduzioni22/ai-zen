#!/usr/bin/env node
/* eslint-disable no-console */
/**
 * AI Zen — in-browser text-to-speech.
 *
 * Runs the SanoTTS neural voices entirely in the visitor's browser:
 * espeak-ng (WASM) turns the text into phoneme ids, a small neural stack
 * renders the audio. Nothing is uploaded, no API key, no server round-trip.
 *
 * Voices: https://github.com/Ampixa/sanoTTS  (GPL-3.0)
 * Model weights: https://huggingface.co/ampixa/sanoTTS
 *
 * Usage from the page:
 *     const tts = new ZenSpeech();
 *     await tts.speak('Buongiorno', { voice: 'italian' });
 *     await tts.stop();
 */

// The runtime lives in the site's root. The path is computed from the page:
// the homepage is at /ai-zen/ and the article pages at /ai-zen/blog/, so the
// number of levels to climb depends on where we are. An absolute '/sanotts/'
// would 404 on GitHub Pages, where the site lives under a subpath.
/**
 * Where the runtime lives, relative to the page that includes this script.
 *
 * It cannot be a fixed path: the site is served from the root in development
 * and from /ai-zen/ on GitHub Pages, and the article pages live one directory
 * deeper. The page that includes this script declares it in the `data-zen-base`
 * attribute, so the same module works from anywhere.
 */
function runtimeBase() {
  if (typeof document !== 'undefined') {
    const el = document.querySelector('script[data-zen-base]');
    if (el && el.dataset.zenBase) return el.dataset.zenBase;
  }
  return 'sanotts/';
}
/** The voices we ship. The blog is in Italian, so those are the ones that matter. */
const VOICES = {
  italian: {
    label: 'Italiano',
    dir: 'italian',
    espeak: 'it',
    g2pSlot: 12,
    sampleRate: 22050,
  },
  'italian-tiny': {
    label: 'Italiano (leggera)',
    dir: 'italian-tiny',
    espeak: 'it',
    g2pSlot: 12,
    sampleRate: 22050,
  },
};

// The runtime's own output cap: 20 seconds of samples.
const VOICE_OUT_CAP = 22050 * 20;
const MAX_IDS = 1024;
// A passage longer than this is split: ~20s of speech is about 300 characters.
const MAX_SPEECH_CHARS = 260;

/**
 * Split a passage into pieces the runtime can render in one go.
 *
 * It cuts on sentence boundaries first, so the intonation survives; a sentence
 * that is still too long is cut on commas, and only then on words.
 */
function splitForSpeech(text, limit) {
  const sentences = String(text).split(/(?<=[.!?])\s+/);
  const out = [];
  let cur = '';
  for (const s of sentences) {
    if (!s.trim()) continue;
    if ((cur + ' ' + s).trim().length <= limit) {
      cur = (cur + ' ' + s).trim();
      continue;
    }
    if (cur) out.push(cur);
    if (s.length <= limit) {
      cur = s.trim();
      continue;
    }
    // a single very long sentence: cut it on commas
    let piece = '';
    for (const chunk of s.split(/(?<=,)\s+/)) {
      if ((piece + ' ' + chunk).trim().length <= limit) {
        piece = (piece + ' ' + chunk).trim();
      } else {
        if (piece) out.push(piece);
        piece = chunk.trim();
      }
    }
    cur = piece;
  }
  if (cur) out.push(cur);
  return out.length ? out : [text];
}

class ZenSpeech {
  constructor(base = null) {
    this.base = base || (typeof window !== 'undefined' ? runtimeBase() : 'sanotts/');
    this.g2p = null;
    this.voiceMod = null;
    this.ttsMod = null;
    this.nanoMod = null;
    this.voice = null;
    this.bundles = new Map();
    this.audioCtx = null;
    this.current = null;
    this._ready = null;
  }

  // ---- runtime loading -------------------------------------------------

  async loadRuntime() {
    if (this._ready) return this._ready;
    this._ready = (async () => {
      // The runtime ships as Emscripten modules that register a global
      // factory (SaanoG2P, SaanoVoice). Each factory returns a promise for
      // the instantiated module.
      await this._script('snt_g2p.js');
      await this._script('snt_voice.js');
      if (typeof window.SaanoG2P !== 'function') throw new Error('snt_g2p non disponibile');
      if (typeof window.SaanoVoice !== 'function') throw new Error('snt_voice non disponibile');

      // espeak-ng is chatty on stderr: the dictionary and phoneme table
      // messages are normal, not errors.
      const quiet = (t) => {
        if (/Can't read dictionary file|Using phonemetable|Compiling:|entries|rules,|groups/.test(t)) return;
        console.error('g2p: ' + t);
      };

      // locateFile: without it the runtime looks for the .wasm and the .data
      // next to the PAGE, not next to the script, and both 404.
      const locateFile = (p) => this.base + p;

      const [g2p, voice] = await Promise.all([
        window.SaanoG2P({ printErr: quiet, locateFile }),
        window.SaanoVoice({ locateFile }),
      ]);
      if (g2p._snt_g2p_init) g2p._snt_g2p_init();
      this.g2p = g2p;
      this.voice = voice;
      return this;
    })().catch((e) => { this._ready = null; throw e; });
    return this._ready;
  }

  _script(src) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[data-zentts="${src}"]`)) return resolve();
      const s = document.createElement('script');
      s.src = this.base + src;
      s.dataset.zentts = src;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error('cannot load ' + src));
      document.head.appendChild(s);
    });
  }

  // ---- voice weights --------------------------------------------------

  async loadVoice(key, onProgress) {
    if (this.bundles.has(key)) return this.bundles.get(key);
    const def = VOICES[key];
    if (!def) throw new Error('voce sconosciuta: ' + key);

    const pending = (async () => {
      const meta = await this._json(`${this.base}voices/${def.dir}/meta.json`);
      const [front, dec] = await Promise.all([
        this._bytes(`${this.base}voices/${def.dir}/${meta.front || 'front_f32.bin'}`),
        this._bytes(`${this.base}voices/${def.dir}/${meta.dec || 'dec_f32.bin'}`),
      ]);
      // float16 weights are widened to float32 by the loader.
      const f16 = meta.weights === 'f16';
      const out = {
        meta,
        front: f16 ? widenF16(front, meta.front_dims) : front,
        dec: f16 ? widenF16(dec, meta.dec_dims) : dec,
      };
      if (onProgress) onProgress('voce pronta');
      return out;
    })();
    this.bundles.set(key, pending);
    try { return await pending; } catch (e) { this.bundles.delete(key); throw e; }
  }

  async _bytes(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error('fetch ' + url + ': ' + r.status);
    return new Uint8Array(await r.arrayBuffer());
  }

  async _json(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error('fetch ' + url + ': ' + r.status);
    return r.json();
  }

  // ---- synthesis ------------------------------------------------------

  /**
   * Speak a piece of text.
   * Resolves when the audio has finished playing.
   */
  async speak(text, opts = {}) {
    const key = opts.voice || 'italian';
    const def = VOICES[key];
    if (!def) throw new Error('voce sconosciuta: ' + key);
    const clean = String(text || '').replace(/\s+/g, ' ').trim();
    if (!clean) return;

    await this.loadRuntime();
    const bundle = await this.loadVoice(key, opts.onProgress);

    this.stop();

    // The runtime renders at most ~20 seconds at a time, so a long passage
    // has to be split and played in sequence.
    const parts = splitForSpeech(clean, MAX_SPEECH_CHARS);
    for (let i = 0; i < parts.length; i++) {
      if (opts.onProgress) {
        opts.onProgress(parts.length > 1 ? 'parte ' + (i + 1) + ' di ' + parts.length : 'sintesi\u2026');
      }
      await this._speakOne(parts[i], bundle, def);
      // Give the browser a breath between parts: the WASM call is synchronous
      // and would otherwise freeze the page for the whole article.
      await new Promise((r) => setTimeout(r, 0));
    }
  }

  async _speakOne(text, bundle, def) {
    // The phonemizer must be switched to the right voice BEFORE the text is
    // phonemized: the ids are the contract with the neural stack. The call
    // goes through cwrap because it takes a string argument, and a non-zero
    // return means the voice was not accepted.
    this._setVoice(bundle.meta.espeak_voice || def.espeak,
                   bundle.meta.g2p_voice_slot ?? def.g2pSlot);
    const ids = this._ids(text);

    const V = this.voice;
    const frontP = toHeap(V, bundle.front);
    const decP = toHeap(V, bundle.dec);
    const idsP = toHeap(V, new Uint8Array(ids.buffer, 0, ids.length * 4));
    const outP = V._malloc(VOICE_OUT_CAP * 4);

    let pcm = null;
    try {
      const n = V._snt_voice_synthesize(frontP, decP, idsP, ids.length,
                                        bundle.meta.length_scale || 1.0,
                                        outP, VOICE_OUT_CAP);
      if (n < 0) throw new Error('sintesi fallita: ' + n);
      pcm = new Float32Array(n);
      pcm.set(V.HEAPF32.subarray(outP >> 2, (outP >> 2) + n));
    } finally {
      [frontP, decP, idsP, outP].forEach((p) => V._free(p));
    }

    await this._play(pcm, bundle.meta.sample_rate || def.sampleRate);
  }

  _setVoice(espeakVoice, slot) {
    if (!this._setVoiceFn) {
      this._setVoiceFn = this.g2p.cwrap('snt_g2p_set_voice', 'number', ['string', 'number']);
    }
    const rc = this._setVoiceFn(espeakVoice, slot);
    if (rc !== 0) {
      throw new Error('snt_g2p_set_voice("' + espeakVoice + '", ' + slot + ') ha restituito ' + rc);
    }
  }

  _ids(text) {
    const G2P = this.g2p;
    const tp = G2P._malloc(G2P.lengthBytesUTF8(text) + 1);
    G2P.stringToUTF8(text, tp, G2P.lengthBytesUTF8(text) + 1);
    const op = G2P._malloc(MAX_IDS * 4);
    const n = G2P._snt_g2p_text_to_ids(tp, op, MAX_IDS);
    let ids = null;
    if (n > 0) ids = new Int32Array(G2P.HEAP32.buffer, op, n).slice();
    G2P._free(tp);
    G2P._free(op);
    if (n <= 0) throw new Error('fonemizzatore ha restituito ' + n);
    return ids;
  }

  _play(pcm, sampleRate) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return Promise.resolve();
    if (!this.audioCtx) this.audioCtx = new AC();
    // A context starts suspended until a user gesture: without one there is
    // no sound and 'onended' never fires, so the promise would hang.
    if (this.audioCtx.state === 'suspended') {
      const resumed = this.audioCtx.resume();
      if (resumed && resumed.catch) resumed.catch(() => {});
    }

    const buffer = this.audioCtx.createBuffer(1, pcm.length, sampleRate);
    buffer.copyToChannel(pcm, 0);
    const src = this.audioCtx.createBufferSource();
    src.buffer = buffer;
    src.connect(this.audioCtx.destination);
    this.current = src;
    return new Promise((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        if (this.current === src) this.current = null;
        resolve();
      };
      src.onended = finish;
      try { src.start(); } catch (e) { finish(); return; }
      // Safety net: if the context never runs (no output device, autoplay
      // blocked), do not wait forever.
      setTimeout(finish, Math.max(1200, (pcm.length / sampleRate) * 1000 + 800));
    });
  }

  /** Load the runtime and the voice before the reader asks for it. */
  async warmUp(onProgress) {
    await this.loadRuntime();
    await this.loadVoice('italian', onProgress);
    return this;
  }

  stop() {
    if (this.current) {
      try { this.current.stop(); } catch (e) { /* already stopped */ }
      this.current = null;
    }
  }

  /** Speak a list of parts in sequence (e.g. the three tracks of an article). */
  async speakSequence(parts, opts = {}) {
    for (const p of parts) {
      if (opts.onPart) opts.onPart(p);
      await this.speak(p.text, { ...opts, voice: p.voice || opts.voice });
    }
  }
}

function toHeap(mod, bytes) {
  const p = mod._malloc(bytes.length);
  mod.HEAPU8.set(bytes, p);
  return p;
}

/**
 * Widen a float16 blob to float32.
 *
 * The blob layout is [meta_bytes header][weight_floats * float16]. The header
 * is metadata for the runtime and must be copied over untouched: dropping it
 * shifts every weight and the synth returns garbage (or -2).
 */
function widenF16(bytes, dims) {
  const head = Number(dims.meta_bytes);
  const n = Number(dims.weight_floats);
  if (!Number.isInteger(head) || !Number.isInteger(n) || head < 0 || n <= 0) {
    throw new Error('f16 blob: meta.json non ha meta_bytes/weight_floats utilizzabili');
  }
  if (bytes.length !== head + 2 * n) {
    throw new Error('f16 blob di ' + bytes.length + ' byte, meta.json implica ' + (head + 2 * n));
  }
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
}

if (typeof window !== 'undefined') {
  window.ZenSpeech = ZenSpeech;
  window.ZEN_VOICES = VOICES;
}
if (typeof module !== 'undefined' && module.exports) module.exports = { ZenSpeech, VOICES };
