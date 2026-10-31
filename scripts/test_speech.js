#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ROOT = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(ROOT, file), 'utf8');

function runtime(voices = []) {
  const calls = { utterances: [], cancel: 0, runtime: 0 };
  const synth = {
    getVoices: () => voices,
    cancel() { calls.cancel++; },
    speak(utterance) {
      calls.utterances.push(utterance);
      queueMicrotask(() => utterance.onend());
    },
  };
  const window = { speechSynthesis: synth, SpeechSynthesisUtterance: class {
    constructor(text) { this.text = text; }
  } };
  const ctx = vm.createContext({ window, console, setTimeout, clearTimeout });
  vm.runInContext(read('assets/zen-speech.js'), ctx);
  const tts = new window.ZenSpeech();
  tts.loadRuntime = async () => {
    calls.runtime++;
    throw new Error('Italian runtime must not receive English');
  };
  return { tts, calls, window, synth };
}

test('English uses an explicitly local English voice, never Italian SanoTTS', async () => {
  const remote = { lang: 'en-US', localService: false, name: 'Remote' };
  const local = { lang: 'en-US', localService: true, name: 'Local' };
  const { tts, calls } = runtime([remote, { lang: 'it-IT', localService: true }, local]);
  await tts.speak('The original English text.', { lang: 'en-US' });
  assert.equal(calls.runtime, 0);
  assert.equal(calls.utterances.length, 1);
  assert.equal(calls.utterances[0].voice, local);
  assert.equal(calls.utterances[0].lang, 'en-US');
  assert.equal(calls.utterances[0].text, 'The original English text.');
});

function pageReader(kind, sectionId, ZenSpeech) {
  const html = read('index.html');
  // Parse every inline script too: extracted-function tests must not hide a
  // syntax error elsewhere in the SPA's enclosing script.
  for (const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)) {
    new vm.Script(match[1]);
  }
  const build = read('scripts/build.py');
  const staticScript = build.match(/SPEAK_SCRIPT = r"""([\s\S]*?)"""/)[1]
    .replace(/^\s*<script>/, '').replace(/<\/script>\s*$/, '');
  new vm.Script(staticScript);
  const source = { innerHTML: '<p>The original English text.</p>' };
  const state = { textContent: '' };
  const block = { id: sectionId, querySelector: () => source };
  const classes = new Set();
  const btn = {
    closest: () => block,
    parentElement: { querySelector: () => state },
    classList: { add: c => classes.add(c), remove: c => classes.delete(c) },
  };
  const window = {};
  const errors = [];
  const ctx = vm.createContext({
    window, ZenSpeech, console: { ...console, error: e => errors.push(e) }, setTimeout,
    document: { querySelectorAll: () => [] },
    $: () => state,
    plainText: html => html.replace(/<[^>]+>/g, '').trim(),
  });
  if (kind === 'SPA') {
    const start = html.indexOf('    let speech = null;');
    const end = html.indexOf('    // ---------- copertina generata', start);
    assert.ok(start > 0 && end > start, 'SPA speech block located');
    vm.runInContext(html.slice(start, end), ctx);
  } else {
    vm.runInContext(staticScript, ctx);
  }
  return {
    state, classes, source, errors,
    speak: () => kind === 'SPA' ? ctx.speak('test', btn) : window.speak(btn),
  };
}

for (const kind of ['SPA', 'static']) {
  test(`${kind}: English section selects English instead of hardcoded Italian`, async () => {
    const calls = [];
    class Speech {
      warmUp() { return Promise.resolve(); }
      async speak(text, opts) { calls.push({ text, opts }); }
    }
    const page = pageReader(kind, 'sec-en', Speech);
    await page.speak();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].opts.lang, 'en-US');
    assert.notEqual(calls[0].opts.voice, 'italian');
    assert.equal(page.state.textContent, 'fine · EN: solo voci locali del browser');
    assert.equal(page.classes.size, 0);
  });
}

for (const [label, voices] of [
  ['empty inventory', []],
  ['remote English only', [{ lang: 'en-US', localService: false }]],
  ['unverified English service', [{ lang: 'en-US' }]],
  ['local Italian only', [{ lang: 'it-IT', localService: true }]],
]) {
  test(`English unavailable with ${label}: no default, remote or Italian synthesis`, async () => {
    const { tts, calls } = runtime(voices);
    await assert.rejects(tts.speak('English remains readable.', { lang: 'en-US', voice: 'italian' }),
      /voce inglese locale non disponibile/);
    assert.equal(calls.runtime, 0);
    assert.equal(calls.utterances.length, 0);
  });
}

test('Missing Web Speech API reports local English unavailable', async () => {
  const { tts, calls, window } = runtime();
  delete window.speechSynthesis;
  await assert.rejects(tts.speak('English text.', { lang: 'en-US' }),
    /voce inglese locale non disponibile/);
  assert.equal(calls.runtime, 0);
});

test('English may use another local English locale, with its matching language', async () => {
  const voice = { lang: 'en-GB', localService: true };
  const { tts, calls } = runtime([voice]);
  await tts.speak('English text.', { lang: 'en-US' });
  assert.equal(calls.utterances[0].voice, voice);
  assert.equal(calls.utterances[0].lang, 'en-GB');
});

test('Italian retains local SanoTTS phonemizer it, slot 12 and Italian model', async () => {
  const { tts, calls } = runtime([{ lang: 'en-US', localService: true }]);
  const selected = [];
  let loadedVoice;
  let spokenText;
  let sampleRate;
  const heap = new ArrayBuffer(2 * 1024 * 1024);
  let pointer = 8;
  tts.loadRuntime = async () => {
    tts.g2p = { cwrap: () => (lang, slot) => { selected.push([lang, slot]); return 0; } };
    tts.voice = {
      HEAPU8: new Uint8Array(heap), HEAPF32: new Float32Array(heap),
      _malloc: n => { const p = pointer; pointer += Math.ceil(n / 4) * 4; return p; },
      _free() {},
      _snt_voice_synthesize: () => 32,
    };
  };
  tts.loadVoice = async key => {
    loadedVoice = key;
    return { meta: { espeak_voice: 'it', g2p_voice_slot: 12, sample_rate: 22050 },
      front: new Uint8Array(4), dec: new Uint8Array(4) };
  };
  tts._ids = text => { spokenText = text; return new Int32Array([1, 2]); };
  tts._play = async (pcm, rate) => { assert.equal(pcm.length, 32); sampleRate = rate; };
  await tts.speak('Buongiorno, intelligenze artificiali.', { lang: 'it-IT' });
  assert.equal(loadedVoice, 'italian');
  assert.deepEqual(selected, [['it', 12]]);
  assert.equal(spokenText, 'Buongiorno, intelligenze artificiali.');
  assert.equal(sampleRate, 22050);
  assert.equal(calls.utterances.length, 0);
});

for (const kind of ['SPA', 'static']) {
  test(`${kind}: missing local English is explicit and does not change the text`, async () => {
    const { tts, calls } = runtime([{ lang: 'en-US', localService: false }]);
    tts.warmUp = async () => tts;
    const page = pageReader(kind, 'sec-en', function () { return tts; });
    await page.speak();
    assert.match(page.state.textContent, /voce inglese locale non disponibile/);
    assert.equal(page.source.innerHTML, '<p>The original English text.</p>');
    assert.equal(calls.runtime, 0);
    assert.equal(calls.utterances.length, 0);
    assert.equal(page.classes.size, 0);
  });

  for (const section of ['sec-it', 'sec-reflection']) {
    test(`${kind}: ${section} selects Italian`, async () => {
      const calls = [];
      class Speech {
        warmUp() { return Promise.resolve(); }
        async speak(text, opts) { calls.push(opts); }
      }
      const page = pageReader(kind, section, Speech);
      await page.speak();
      assert.equal(calls[0].lang, 'it-IT');
      assert.equal(page.state.textContent, 'fine');
    });
  }
}

function deferred() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
}

const nextTurn = () => new Promise(resolve => setTimeout(resolve, 0));
const longItalian = ('Una frase italiana abbastanza lunga per occupare una parte. '.repeat(3).trim() + ' ').repeat(2).trim();

function cancellationRuntime() {
  const env = runtime([{ lang: 'en-US', localService: true }]);
  const { tts, window, synth, calls } = env;
  const events = [];
  const sources = [];
  synth.speak = utterance => { calls.utterances.push(utterance); events.push('EN_START'); };
  synth.cancel = () => { calls.cancel++; events.push('EN_STOP'); };
  window.AudioContext = class {
    constructor() { this.state = 'running'; this.destination = {}; }
    createBuffer() { return { copyToChannel() {} }; }
    createBufferSource() {
      const src = {
        connect() {},
        start() { events.push('IT_START'); },
        stop() { events.push('IT_STOP'); this.onended(); },
      };
      sources.push(src);
      return src;
    }
  };
  tts.loadRuntime = async () => { calls.runtime++; };
  tts.loadVoice = async () => ({});
  // Exercise the real playback/current ownership; synthesis itself is synchronous.
  tts._speakOne = () => tts._play(new Float32Array(32), 22050);
  return { ...env, events, sources };
}

test('Cancellation: IT to EN never resumes the old Italian passage or replaces current', async () => {
  const { tts, events, calls } = cancellationRuntime();
  const old = tts.speak(longItalian, { lang: 'it-IT' });
  await nextTurn();
  assert.deepEqual(events, ['IT_START']);
  const latest = tts.speak('Keep reading English.', { lang: 'en-US' });
  const english = tts.current;
  await nextTurn();
  await nextTurn(); // also drain the old loop's inter-segment timer
  assert.deepEqual(events, ['IT_START', 'IT_STOP', 'EN_START']);
  assert.equal(tts.current, english, 'the English playback still owns current');
  await old;
  calls.utterances[0].onend();
  await latest;
});

test('Cancellation: EN to IT stops English before waiting for the Italian runtime', async () => {
  const { tts, events, calls, sources } = cancellationRuntime();
  const loading = deferred();
  const english = tts.speak('English first.', { lang: 'en-US' });
  tts.loadRuntime = () => loading.promise;
  const italian = tts.speak('Adesso italiano.', { lang: 'it-IT' });
  assert.deepEqual(events, ['EN_START', 'EN_STOP']);
  await english;
  loading.resolve();
  await nextTurn();
  const current = tts.current;
  calls.utterances[0].onend(); // late browser callback cannot clear Italian
  assert.equal(tts.current, current);
  assert.deepEqual(events, ['EN_START', 'EN_STOP', 'IT_START']);
  sources[0].onended();
  await italian;
  assert.equal(tts.current, null);
});

for (const stage of ['loadRuntime', 'loadVoice']) {
  test(`Cancellation: stop during ${stage} prevents later Italian playback`, async () => {
    const { tts, events } = cancellationRuntime();
    const loading = deferred();
    const entered = deferred();
    let voiceLoads = 0;
    if (stage === 'loadRuntime') tts.loadVoice = async () => { voiceLoads++; return {}; };
    tts[stage] = () => { entered.resolve(); return loading.promise; };
    const pending = tts.speak(longItalian, { lang: 'it-IT' });
    await entered.promise;
    tts.stop();
    loading.resolve({});
    await pending;
    assert.deepEqual(events, []);
    assert.equal(voiceLoads, 0, 'cancelled runtime must not start loading a voice');
    assert.equal(tts.current, null);
  });

  for (const lang of ['en-US', 'it-IT']) {
    test(`Cancellation: new ${lang} while old ${stage} is pending keeps the latest owner`, async () => {
      const { tts, events, sources, calls } = cancellationRuntime();
      const loading = deferred();
      const entered = deferred();
      const load = tts[stage];
      let first = true;
      tts[stage] = (...args) => {
        if (!first) return load(...args);
        first = false;
        entered.resolve();
        return loading.promise;
      };
      const old = tts.speak(longItalian, { lang: 'it-IT' });
      await entered.promise;
      const latest = tts.speak(lang === 'en-US' ? 'Latest English.' : 'Ultimo italiano.', { lang });
      await nextTurn();
      const current = tts.current;
      assert.ok(current, 'latest playback has started');
      loading.resolve({});
      await nextTurn();
      await nextTurn();
      assert.deepEqual(events, [lang === 'en-US' ? 'EN_START' : 'IT_START']);
      assert.equal(tts.current, current);
      await old;
      if (lang === 'en-US') calls.utterances[0].onend(); else sources[0].onended();
      await latest;
      assert.equal(tts.current, null);
    });
  }
}

for (const lang of ['it-IT', 'en-US']) {
  test(`Cancellation: stop during ${lang} playback does not restart remaining segments`, async () => {
    const { tts, events } = cancellationRuntime();
    const pending = tts.speak(longItalian, { lang });
    await nextTurn();
    tts.stop();
    await nextTurn();
    await nextTurn();
    assert.deepEqual(events, lang === 'it-IT' ? ['IT_START', 'IT_STOP'] : ['EN_START', 'EN_STOP']);
    await pending;
    assert.equal(tts.current, null);
  });
}

test('Cancellation: stop between Italian segments prevents the next synthesis', async () => {
  const { tts, events, sources } = cancellationRuntime();
  const pending = tts.speak(longItalian, { lang: 'it-IT' });
  await nextTurn();
  sources[0].onended();
  // Let _speakOne and speak reach the inter-segment timer, but do not run it.
  await Promise.resolve();
  await Promise.resolve();
  tts.stop();
  await nextTurn();
  assert.deepEqual(events, ['IT_START']);
  await pending;
  assert.equal(tts.current, null);
});

test('Sequences retain the explicit language for each part', async () => {
  const { tts } = runtime();
  const calls = [];
  tts.speak = async (text, opts) => calls.push([text, opts.lang]);
  await tts.speakSequence([
    { text: 'English.', lang: 'en-US' },
    { text: 'Italiano.', lang: 'it-IT' },
  ]);
  assert.deepEqual(calls, [['English.', 'en-US'], ['Italiano.', 'it-IT']]);
});
