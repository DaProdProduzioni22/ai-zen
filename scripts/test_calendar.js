// Exercise the actual homepage calendar functions with a minimal DOM.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('index.html', 'utf8');
const script = html.match(/<script defer>([\s\S]*?)<\/script>/)[1];
// Always parse the entire script: extracted-function tests must not hide syntax errors.
new vm.Script(script, {filename: 'index.html:inline'});
const utils = script.slice(script.indexOf('    const MONTHS ='), script.indexOf('    function toast('));
const calendar = script.slice(script.indexOf('    const calState ='), script.indexOf('    // ---------- wellbeing ----------'));
const elements = Object.fromEntries(['calendar', 'dayList', 'blogGrid'].map(id => [id, {innerHTML: '', scrollIntoView() {}}]));
const context = vm.createContext({document: {getElementById: id => elements[id], querySelectorAll: () => [], querySelector: () => null}, console});
vm.runInContext(`const $ = id => document.getElementById(id); const state = {articles: [], filtered: [], month: 'all', query: ''}; function renderCards() {}\n${utils}\n${calendar}`, context);
const allArticles = JSON.parse(fs.readFileSync('articles.json', 'utf8'));
const real = allArticles.find(a => a.id === 'a-gzip-member-boundary-is-not-the-end-of-a-tool-result');
assert.ok(real, 'real regression article exists');
vm.runInContext(script.slice(script.indexOf('    function applyFilters()'), script.indexOf('    function blogShortcut(')) + script.slice(script.indexOf('    function buildMonthFilters()'), script.indexOf('    function openArticle(')), context);
context.real = real;
const articleCards = script.slice(script.indexOf('    function sortArticles('), script.indexOf('    function renderCards('));
const plainText = script.slice(script.indexOf('    function plainText('), script.indexOf('    // ---------- navigation ----------'));
vm.runInContext(`${plainText}\n${articleCards}\nfunction coverSVG() { return ''; }`, context);
// Exact user symptom: picking 27 October must not show an unlabelled 25 October card.
const card = vm.runInContext('cardHTML(real, 0)', context);
assert.match(card, /Su AI Zen: <time datetime="2026-10-27">27 Ottobre 2026<\/time>/);
assert.match(card, /Post originale: <time datetime="2026-10-25">25 Ottobre 2026<\/time>/);
vm.runInContext(`state.articles = [real, {id:'fallback', date:'31 Dicembre 2026'}, {id:'cross', date:'31 Dicembre 2026', published:'1 Gennaio 2027'}]; calState.year = 2026; calState.month = 9; renderCalendar();`, context);
assert.match(elements.calendar.innerHTML, /class="cal-cell has[^\"]*" data-key="2026-10-27"/);
assert.doesNotMatch(elements.calendar.innerHTML, /class="cal-cell has[^\"]*" data-key="2026-10-25"/);
vm.runInContext("pickDay('2026-10-27')", context);
assert.match(elements.dayList.innerHTML, /Un risultato gzip incompleto/);
assert.equal(vm.runInContext('state.filtered[0].id', context), real.id);
vm.runInContext('calMove(2)', context);
assert.match(elements.calendar.innerHTML, /data-key="2026-12-31" onclick=/);
vm.runInContext("pickDay('2026-12-31')", context);
assert.equal(vm.runInContext('state.filtered[0].id', context), 'fallback');
assert.equal(vm.runInContext('state.filtered.length', context), 1);
vm.runInContext('calMove(1)', context);
assert.match(elements.calendar.innerHTML, /Gennaio 2027/);
assert.match(elements.calendar.innerHTML, /data-key="2027-01-01" onclick=/);
assert.equal(vm.runInContext('calState.day', context), null);
vm.runInContext("pickDay('2027-01-01')", context);
assert.equal(vm.runInContext('state.filtered[0].id', context), 'cross');
// Month filters use the same AI Zen editorial timeline, including year crossings.
const filters = script.slice(script.indexOf('    function applyFilters()'), script.indexOf('    function blogShortcut(')) + script.slice(script.indexOf('    function buildMonthFilters()'), script.indexOf('    function setMonth('));
elements.monthFilters = {innerHTML: ''};
vm.runInContext(filters, context);
vm.runInContext("calState.day = null; state.query = ''; state.month = 'Dicembre 2026'; buildMonthFilters(); applyFilters()", context);
assert.match(elements.monthFilters.innerHTML, /Dicembre 2026 \(1\)/);
assert.equal(vm.runInContext('state.filtered.length', context), 1);
vm.runInContext("state.month = 'Gennaio 2027'; applyFilters()", context);
assert.equal(vm.runInContext('state.filtered.length', context), 1);
assert.equal(vm.runInContext('state.filtered[0].id', context), 'cross');
context.reversed = [{id:'new', date:'2 Dicembre 2026', published:'1 Gennaio 2027'}, {id:'old', date:'31 Dicembre 2026'}];
assert.equal(vm.runInContext('reversed.sort(sortArticles)[0].id', context), 'new');
// Exercise the real SPA article renderer, not a duplicate date formatter.
for (const id of ['article-view', 'nav-blog', 'articleContainer']) elements[id] = {innerHTML:'', classList:{add(){}, remove(){}}};
context.window = {scrollTo(){}};
vm.runInContext("function setHash() {} function watchSections() {}", context);
vm.runInContext(script.slice(script.indexOf('    function openArticle('), script.indexOf('    // Jump to a section')), context);
vm.runInContext('state.articles = [real]; openArticle(real.id)', context);
assert.match(elements.articleContainer.innerHTML, /Su AI Zen: <time datetime="2026-10-27">27 Ottobre 2026<\/time>/);
assert.match(elements.articleContainer.innerHTML, /Post originale: <time datetime="2026-10-25">25 Ottobre 2026<\/time>/);
// Selected day and search are intersected; month selection explicitly clears the day.
vm.runInContext(script.slice(script.indexOf('    function renderCards('), script.indexOf('    function blogShortcut(')) + script.slice(script.indexOf('    function setMonth('), script.indexOf('    function openArticle(')), context);
vm.runInContext("state.articles = [real]; state.query = 'nessuna corrispondenza'; state.month = 'all'; calState.year = 2026; calState.month = 9; calState.day = null; pickDay('2026-10-27')", context);
assert.equal(vm.runInContext('state.filtered.length', context), 0, 'calendar must not silently ignore the active search');
assert.ok(!elements.dayList.innerHTML.includes(real.title), 'day list and card grid must agree when a search hides the article');
vm.runInContext("state.query = 'gzip'; applyFilters()", context);
assert.equal(vm.runInContext('state.filtered[0].id', context), real.id);
assert.match(elements.blogGrid.innerHTML, /Su AI Zen: <time datetime="2026-10-27">/);
assert.match(elements.calendar.innerHTML, /data-key="2026-10-27"[^>]*aria-pressed="true"/);
assert.match(elements.calendar.innerHTML, /aria-label="27 Ottobre 2026: 1 articolo su AI Zen"/);
assert.match(elements.calendar.innerHTML, /data-key="2026-10-25"[^>]*disabled/);
assert.match(elements.dayList.innerHTML, /Su AI Zen: <time datetime="2026-10-27">/);
vm.runInContext("setMonth('Ottobre 2026', null)", context);
assert.equal(vm.runInContext('calState.day', context), null);
assert.equal(vm.runInContext('state.filtered.length', context), 1);
vm.runInContext("pickDay('2026-10-27'); calMove(1)", context);
assert.equal(vm.runInContext('state.query', context), 'gzip');
assert.equal(vm.runInContext('calState.day', context), null);
assert.equal(vm.runInContext('state.filtered.length', context), 1);
// Month controls expose their active state consistently with the selected day.
vm.runInContext("buildMonthFilters()", context);
assert.match(elements.monthFilters.innerHTML, /data-month="all"[^>]*aria-pressed="true"/);
// Summary posts must not be presented as the source author's full text.
context.summaryArticle = {...real, contentType:'summary'};
vm.runInContext('state.articles = [summaryArticle]; openArticle(summaryArticle.id)', context);
assert.ok(elements.articleContainer.innerHTML.includes('Sintesi EN'));
assert.ok(elements.articleContainer.innerHTML.includes('Sintesi IT'));
assert.ok(elements.articleContainer.innerHTML.includes('Sintesi originale di Babbasone, basata sul post di ' + real.author + ', non traduzione integrale'));
assert.ok(!elements.articleContainer.innerHTML.includes('The original'));
assert.ok(!elements.articleContainer.innerHTML.includes('Ascolta la traduzione italiana'));
// Real reported dates, plus any newly added summary on the 29th.
context.allArticles = allArticles;
vm.runInContext("state.articles = allArticles.slice().sort(sortArticles); state.query = ''; state.month = 'all'; calState.year = 2026; calState.month = 9", context);
for (const day of [27, 28, 29]) {
    const expected = allArticles.filter(a => (a.published || a.date) === `${day} Ottobre 2026`);
    if (day !== 29) assert.ok(expected.length, `real regression fixture for ${day} October exists`);
    if (!expected.length) continue;
    context.key = `2026-10-${day}`;
    vm.runInContext('calState.day = null; pickDay(key)', context);
    assert.deepEqual(Array.from(vm.runInContext('state.filtered.map(a => a.id).sort()', context)), expected.map(a => a.id).sort());
    assert.ok(elements.blogGrid.innerHTML.includes(`Su AI Zen: <time datetime="2026-10-${day}">${day} Ottobre 2026</time>`));
    for (const article of expected) {
        context.articleId = article.id;
        vm.runInContext('openArticle(articleId)', context);
        assert.ok(elements.articleContainer.innerHTML.includes(`Su AI Zen: <time datetime="2026-10-${day}">${day} Ottobre 2026</time>`));
        assert.ok(elements.articleContainer.innerHTML.includes(article.date));
    }
}
console.log('Calendar, archive filters, order, article dates and summary labels passed');
