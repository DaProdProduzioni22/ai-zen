// Run the real inline SPA functions with deterministic DOM/history boundaries.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');
const html = fs.readFileSync('index.html', 'utf8');
const script = html.match(/<script defer>([\s\S]*?)<\/script>/)[1];
new vm.Script(script, {filename: 'index.html:inline'});
const slice = (start, end) => script.slice(script.indexOf(start), script.indexOf(end));
function setup(hash = '#home') {
    const nodes = {};
    const node = id => nodes[id] ||= {innerHTML:'', textContent:'', style:{}, attrs:{},
        classList:{add(){}, remove(){}, toggle(){}},
        setAttribute(key, value) {this.attrs[key] = value;},
        getAttribute(key) {return this.attrs[key];},
        scrollIntoView() {this.scrolled = true;}, focus() {this.focused = true;}};
    const location = {hash};
    const writes = [];
    const history = Object.fromEntries(['pushState', 'replaceState'].map(method => [method, (_state, _title, url) => {writes.push([method, url]); location.hash = url;} ]));
    const document = {getElementById:node, documentElement:node('html'), querySelector:() => null, querySelectorAll:() => []};
    const context = vm.createContext({document, location, history, console, window:{scrollTo(){}}, setTimeout, clearTimeout});
    vm.runInContext(`const $ = id => document.getElementById(id); const state = {articles:[], articleId:null}; function coverSVG(){return '';}\n${slice('    const MONTHS =', '    function toast(')}\n${slice('    function plainText(', '    // ---------- navigation ----------')}\n${slice('    // ---------- navigation ----------', '    // ---------- articles ----------')}\n${slice('    function sortArticles(', '    function renderCards(')}\n${slice('    function openArticle(', '    // Jump to a section')}\n${slice('    // Jump to a section', '    // ---------- ascolto')}\nfunction toast(message){ document.getElementById('toast').textContent = message; }`, context);
    const articles = [
        {id:'first', title:'Primo', date:'20 Ottobre 2026', published:'29 Ottobre 2026', author:'Test', translation:'<p>Il testo italiano.</p>', content:'<p>The English text.</p>', reflection:'Una riflessione & un <dettaglio>.', summary:'<p>In breve.</p>'},
        {id:'second', title:'Secondo', date:'19 Ottobre 2026', author:'Test'}
    ];
    context.articles = articles;
    vm.runInContext('state.articles = articles', context);
    return {context, node, writes, location, run: code => vm.runInContext(code, context)};
}

test('user navigation pushes once; hash routing and initial deep links never push', () => {
    const app = setup();
    app.run("go('blog')");
    assert.deepEqual(app.writes, [['pushState', '#blog']]);
    app.run('routeFromHash()');
    assert.equal(app.writes.length, 1, 'routing a changed hash cannot add history');
    app.run("openArticle('first')");
    assert.deepEqual(app.writes[1], ['pushState', '#article-first']);
    app.location.hash = '#blog'; // Browser Back changes the URL before hashchange.
    app.run('routeFromHash()');
    assert.equal(app.writes.length, 2, 'Back must not create or replace an entry');
    const deep = setup('#article-first');
    deep.run('routeFromHash()');
    assert.equal(deep.writes.length, 0, 'initial article rendering preserves history');
    assert.match(deep.node('articleContainer').innerHTML, /<h1>Primo<\/h1>/);
    deep.run("openArticle('first')");
    assert.equal(deep.writes.length, 0, 'same destination does not duplicate history');
});

test('navigation and article links have real destinations without double click handlers', () => {
    const staticLinks = html.match(/<a\b[^>]*(?:class="logo"|id="nav-[^"]+")[^>]*>/g);
    assert.equal(staticLinks.length, 7);
    for (const link of staticLinks) {
        assert.match(link, /href="#(?:home|blog|wellbeing|games|moltbook|about)"/);
        assert.doesNotMatch(link, /onclick=/, 'native hash navigation must have one event path');
    }
    const app = setup();
    const card = app.run('cardHTML(articles[0], 0)');
    assert.match(card, /<a class="card" href="#article-first">/);
    app.run("openArticle('first')");
    const article = app.node('articleContainer').innerHTML;
    for (const anchor of article.match(/<a\b[^>]*>/g)) {
        assert.match(anchor, /href="(?:#article-|https?:)/, 'all article links remain focusable and shareable');
        assert.doesNotMatch(anchor, /onclick=/);
    }
    assert.match(article, /href="#article-first\/sec-reflection"[^>]*data-sec="sec-reflection"/);
    assert.doesNotMatch(html, /<a\b[^>]*onclick="(?:go|openArticle)\(/, 'footer and calendar use the same native link contract');
});

test('article section deep links stay in the article and move keyboard focus', () => {
    const app = setup('#article-first/sec-reflection');
    app.run('routeFromHash()');
    assert.match(app.node('articleContainer').innerHTML, /<h1>Primo<\/h1>/);
    assert.equal(app.node('sec-reflection').scrolled, true);
    assert.equal(app.node('sec-reflection').focused, true);
    assert.equal(app.writes.length, 0);
    // A second section link must not recreate the audio controls or article DOM.
    app.node('articleContainer').innerHTML = 'retained article DOM';
    app.location.hash = '#article-first/sec-en';
    app.run('routeFromHash()');
    assert.equal(app.node('articleContainer').innerHTML, 'retained article DOM');
    assert.equal(app.node('sec-en').focused, true);
    assert.equal(app.writes.length, 0);
});

test('reflection provides the same spoken text source as the other article sections', () => {
    const app = setup();
    app.run("openArticle('first')");
    const reflection = app.node('articleContainer').innerHTML.match(/<section[^>]*id="sec-reflection">([\s\S]*?)<\/section>/)[1];
    assert.match(reflection, /<div class="spoken-text"><p>Una riflessione &amp; un &lt;dettaglio&gt;\.<\/p><\/div>/);
    assert.match(reflection, /onclick="speak\(/);
});

test('Moltbook exposes the real snapshot timestamp, age and explicit stale status', () => {
    const app = setup();
    app.run(slice('    // ---------- moltbook ----------', '    // ---------- contribute ----------'));
    app.run("Date.now = () => Date.parse('2026-10-29T12:00:00Z')");
    // Historical regression fixture must stay stale even when the real snapshot updates.
    app.context.snapshot = {generated:'2026-10-20T22:43:39.026670+00:00', posts:[{title:'Post nello snapshot', author:'Test', score:1, url:'https://www.moltbook.com'}]};
    app.run('state.moltbook = snapshot; renderMoltbook()');
    const status = app.node('moltbookFreshness').innerHTML;
    assert.ok(status.includes(app.context.snapshot.generated), 'preserve the exact timestamp, including timezone and precision');
    assert.match(status, /<time datetime="2026-10-20T22:43:39\.026670\+00:00">/);
    assert.match(status, /8 giorni, 13 ore/);
    assert.match(status, /non aggiornato/i);
    assert.match(status, /24 ore/);
    assert.match(html, /id="moltbookFreshness"[^>]*role="status"/);
    assert.match(html, /snapshot statico, non un feed in tempo reale/);
    assert.doesNotMatch(html, /Ecco il feed in tempo reale/);
    assert.equal(app.node('moltbookEmpty').style.display, 'none');
    assert.match(app.node('moltbookGrid').innerHTML, /Post nello snapshot/);
});

test('snapshot freshness handles generatedAt, missing, invalid and future dates honestly', () => {
    const app = setup();
    app.run(slice('    // ---------- moltbook ----------', '    // ---------- contribute ----------'));
    app.run("Date.now = () => Date.parse('2026-10-29T12:00:00Z')");
    for (const snapshot of [null, {}, {generated:'invalid'}, {generated:''}]) {
        app.context.snapshot = snapshot;
        app.run('state.moltbook = snapshot; renderMoltbook()');
        assert.match(app.node('moltbookFreshness').innerHTML, /non verificabile/);
        assert.doesNotMatch(app.node('moltbookFreshness').innerHTML, /NaN|Snapshot recente/);
        assert.equal(app.node('moltbookEmpty').style.display, 'block');
    }
    app.run("state.moltbook = {generatedAt:'2026-10-29T11:00:00Z', posts:[]}; renderMoltbook()");
    assert.match(app.node('moltbookFreshness').innerHTML, /Età: 1 ora, 0 min/);
    assert.match(app.node('moltbookFreshness').innerHTML, /non live/);
    app.run("state.moltbook = {generated:'2026-10-30T12:00:00Z', posts:[]}; renderMoltbook()");
    assert.match(app.node('moltbookFreshness').innerHTML, /Data futura/);
    assert.doesNotMatch(app.node('moltbookFreshness').innerHTML, /Età: -/);
    app.run("state.moltbook = {generated:'2026-10-28T12:00:00Z', posts:[]}; renderMoltbook()");
    assert.match(app.node('moltbookFreshness').innerHTML, /non aggiornato/);
    // Re-entering the section updates age from the device clock, without fetching posts.
    app.run("state.moltbook = {generated:'2026-10-29T11:00:00Z', posts:[]}; Date.now = () => Date.parse('2026-10-30T12:00:00Z'); go('moltbook')");
    assert.match(app.node('moltbookFreshness').innerHTML, /Età: 1 giorno, 1 ora/);
    assert.match(app.node('moltbookFreshness').innerHTML, /non aggiornato/);
});

test('real checked-in snapshot retains its current source timestamp in the renderer', () => {
    const app = setup();
    app.run(slice('    // ---------- moltbook ----------', '    // ---------- contribute ----------'));
    app.context.snapshot = JSON.parse(fs.readFileSync('api/moltbook.json', 'utf8'));
    app.run('state.moltbook = snapshot; renderMoltbook()');
    assert.ok(app.node('moltbookFreshness').innerHTML.includes(app.context.snapshot.generatedAt || app.context.snapshot.generated));
});
