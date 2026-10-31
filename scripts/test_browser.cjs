// End-to-end checks against the built site (or a supplied live base URL).
// npm ci && npx playwright install chromium && npm run test:browser
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');
const repo = path.resolve(__dirname, '..');
const mime = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.json':'application/json', '.svg':'image/svg+xml', '.wasm':'application/wasm'};

async function serve() {
  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      const rel = decodeURIComponent(url.pathname).replace(/^\/ai-zen\//, '');
      const file = path.resolve(repo, rel.replace(/^\//, ''), url.pathname.endsWith('/') ? 'index.html' : '');
      if (!file.startsWith(repo + path.sep)) { res.writeHead(403).end(); return; }
      const data = await fs.readFile(file);
      res.writeHead(200, {'Content-Type':mime[path.extname(file)] || 'application/octet-stream'}).end(data);
    } catch { res.writeHead(404).end('Not found'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return [server, `http://127.0.0.1:${server.address().port}/ai-zen/`];
}

(async () => {
  let server, browser;
  try {
    let base = process.argv[2];
    if (!base) [server, base] = await serve();
    base = base.endsWith('/') ? base : base + '/';
    const articles = await (await fetch(base + 'articles.json')).json();
    assert.ok(articles.some(a => a.published === '29 Ottobre 2026'), 'articolo del 29 ottobre presente');
    browser = await chromium.launch({headless:true});
    for (const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
      const page = await browser.newPage({viewport});
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(base + '#home');
      await page.waitForFunction(() => typeof state !== 'undefined' && state.articles.length > 0);
      for (const id of ['nav-home','nav-blog','nav-wellbeing','nav-games','nav-moltbook','nav-about']) {
        assert.ok((await page.locator('#' + id).getAttribute('href') || '').startsWith('#'), `${id} link nativo`);
      }
      if (viewport.width < 600) await page.locator('#navToggle').click();
      await page.locator('#nav-blog').focus();
      await page.keyboard.press('Enter');
      await page.waitForSelector('#blogGrid .card');
      await page.locator('#blogGrid .card').first().focus();
      await page.keyboard.press('Enter');
      await page.waitForSelector('#article-view.active h1');
      await page.goBack();
      await page.waitForSelector('#blog-section.active');
      await page.goBack();
      await page.waitForSelector('#home-section.active');
      await page.goForward();
      await page.waitForSelector('#blog-section.active');
      await page.evaluate(() => { calState.year=2026; calState.month=9; renderCalendar(); });
      assert.equal(await page.locator('#calendar .cal-cell:disabled .dot').count(), 0, 'il pallino segnala solo giorni con articoli');
      assert.ok(await page.evaluate(() => {
        const blank = document.querySelector('#calendar .cal-cell.empty');
        const day = document.querySelector('#calendar button.cal-cell');
        return !blank || Math.abs(blank.getBoundingClientRect().height - day.getBoundingClientRect().height) < 1;
      }), 'celle vuote alte quanto i giorni: nessuna riga dilatata');
      for (const day of [27,28,29,31]) {
        const expected = articles.filter(a => (a.published || a.date).replace(/^0/, '') === `${day} Ottobre 2026`);
        assert.ok(expected.length, `articolo del ${day} ottobre disponibile`);
        await page.locator(`[data-key="2026-10-${day}"]`).click();
        await page.waitForFunction(n => document.querySelectorAll('#blogGrid .card').length === n, expected.length);
        const cards = await page.locator('#blogGrid .card').allTextContents();
        for (const a of expected) assert.ok(cards.some(t => t.includes(a.title) && t.includes(`${day} Ottobre 2026`)), `calendario/card coerenti ${day}`);
        await page.locator('#blogGrid .card').first().click();
        await page.waitForSelector('#article-view.active h1');
        assert.equal(await page.locator('#articleContainer h1').textContent(), expected[0].title);
        assert.match(await page.locator('#articleContainer .article-meta').innerText(), new RegExp(`${day} Ottobre 2026`));
        assert.equal(await page.locator('#sec-reflection .spoken-text').count(), 1, 'riflessione disponibile al lettore');
        assert.ok(await page.locator('#articleContainer .art-tabs a[href]').count() >= 3, 'tabs raggiungibili da tastiera');
        await page.evaluate(async () => {
          window.__readText = '';
          speech = { current:null, stop(){}, warmUp(){return Promise.resolve();}, async speak(text){window.__readText=text;} };
          const button = document.querySelector('#sec-reflection .speak-btn');
          await speak(button.id, button);
        });
        assert.match(await page.evaluate(() => window.__readText), /Babbasone/, 'il lettore riceve il testo della riflessione');
        if (expected[0].contentType === 'summary') {
          assert.match(await page.locator('#articleContainer').innerText(), /Sintesi EN/);
          assert.match(await page.locator('#articleContainer').innerText(), /non (?:è una )?traduzione integrale|non una traduzione integrale/i);
        }
        await page.locator('#article-view .back-btn').click();
      }
      await page.evaluate(() => blogShortcut('all'));
      assert.equal(await page.locator('#blogGrid .card').count(), articles.length, 'Tutti azzera i filtri');
      await page.locator('#searchBox').fill('nessun-risultato-unique-42');
      await page.waitForFunction(() => document.querySelectorAll('#blogGrid .card').length === 0);
      await page.locator('#searchBox').fill('');
      await page.waitForFunction(n => document.querySelectorAll('#blogGrid .card').length === n, articles.length);
      for (const section of ['home','blog','wellbeing','games','moltbook','about']) {
        await page.evaluate(s => go(s), section);
        assert.ok(await page.locator(`#${section}-section`).isVisible(), `sezione ${section}`);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `nessun overflow ${section} ${viewport.width}`);
      }
      await page.goto(base + 'blog/' + articles[0].file);
      await page.waitForSelector('h1');
      assert.equal(await page.locator('h1').textContent(), articles[0].title);
      assert.doesNotMatch(await page.locator('body').innerText(), /\{\{(?:IT|EN)_HEADING\}\}/, 'nessun segnaposto nei titoli statici');
      if (articles[0].contentType === 'summary') {
        assert.match(await page.locator('#sec-it h2').innerText(), /Sintesi IT/);
        assert.match(await page.locator('#sec-en h2').innerText(), /Sintesi EN/);
      }
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `nessun overflow pagina statica ${viewport.width}`);
      assert.deepEqual(errors, [], 'nessun errore JavaScript');
      console.log(`PASS browser ${viewport.width}px: calendario 27/28/29/31, lettore, ricerca, reset, 6 sezioni, pagina statica`);
      await page.close();
    }
  } finally {
    if (browser) await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
  }
})().catch(e => { console.error(e); process.exitCode=1; });
