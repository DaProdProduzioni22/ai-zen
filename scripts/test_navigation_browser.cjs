// Focused navigation/freshness E2E; no build, external server or live API needed.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require('playwright');
const repo = path.resolve(__dirname, '..');
const mime = {'.html':'text/html', '.js':'text/javascript', '.json':'application/json', '.svg':'image/svg+xml'};
(async () => {
    let browser;
    const server = http.createServer(async (req, res) => {
        try {
            const pathname = new URL(req.url, 'http://localhost').pathname;
            const file = path.resolve(repo, '.' + pathname, pathname.endsWith('/') ? 'index.html' : '');
            if (!file.startsWith(repo + path.sep)) {res.writeHead(403).end(); return;}
            res.writeHead(200, {'Content-Type':mime[path.extname(file)] || 'application/octet-stream'}).end(await fs.readFile(file));
        } catch {res.writeHead(404).end();}
    });
    try {
        await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
        const base = `http://127.0.0.1:${server.address().port}/`;
        const snapshot = JSON.parse(await fs.readFile(path.join(repo, 'api/moltbook.json'), 'utf8'));
        browser = await chromium.launch({headless:true});
        for (const width of [1440, 390]) {
            const page = await browser.newPage({viewport:{width, height:1000}});
            const errors = [];
            let snapshotRequests = 0;
            page.on('pageerror', e => errors.push(e.message));
            page.on('request', req => {if (req.url().endsWith('/api/moltbook.json')) snapshotRequests++;});
            await page.goto(base + '#home');
            await page.waitForFunction(() => state.articles.length > 0);
            const initialHistory = await page.evaluate(() => history.length);
            if (width < 600) await page.locator('#navToggle').click();
            await page.locator('#nav-blog').focus();
            await page.keyboard.press('Enter');
            await page.waitForSelector('#blog-section.active');
            await page.locator('#blogGrid .card').first().focus();
            await page.keyboard.press('Enter');
            await page.waitForSelector('#article-view.active');
            assert.equal(await page.evaluate(() => history.length), initialHistory + 2);
            const articleHash = await page.evaluate(() => location.hash);
            await page.locator((width < 600 ? '.art-tabs' : '.side-toc') + ' a[data-sec="sec-reflection"]').focus();
            await page.keyboard.press('Enter');
            await page.waitForFunction(() => document.activeElement.id === 'sec-reflection');
            assert.equal(await page.evaluate(() => location.hash), articleHash + '/sec-reflection');
            assert.ok((await page.locator('#sec-reflection .spoken-text').innerText()).trim());
            assert.equal(await page.locator('#sec-reflection .spoken-text .speak-btn').count(), 0);
            await page.goBack();
            await page.waitForFunction(() => !location.hash.includes('/sec-'));
            await page.goBack();
            await page.waitForSelector('#blog-section.active');
            await page.goBack();
            await page.waitForSelector('#home-section.active');
            await page.goForward();
            await page.waitForSelector('#blog-section.active');
            await page.goto(base + articleHash + '/sec-reflection');
            await page.waitForFunction(() => document.activeElement.id === 'sec-reflection');
            await page.evaluate(() => go('moltbook'));
            assert.equal(await page.locator('#moltbookFreshness time').getAttribute('datetime'), snapshot.generatedAt || snapshot.generated);
            assert.match(await page.locator('#moltbook-section').innerText(), /snapshot statico, non un feed in tempo reale/);
            assert.equal(await page.locator('#moltbookFreshness').getAttribute('role'), 'status');
            const requestsBeforeRevisit = snapshotRequests;
            await page.evaluate(() => {go('home'); go('moltbook');});
            assert.equal(snapshotRequests, requestsBeforeRevisit, 'a section visit does not pretend to fetch a live feed');
            await page.evaluate(() => {state.moltbook.generatedAt = '2026-10-20T22:43:39.026670+00:00'; renderMoltbook();});
            assert.match(await page.locator('#moltbookFreshness').innerText(), /non aggiornato/);
            assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'snapshot timestamp wraps on mobile');
            assert.deepEqual(errors, []);
            console.log(`PASS navigation ${width}px: Enter, exact history entries, Back/Forward, section deep link/focus, reflection source, snapshot timestamp/stale/no fake refresh`);
            await page.close();
        }
    } finally {
        if (browser) await browser.close();
        await new Promise(resolve => server.close(resolve));
    }
})().catch(error => {console.error(error); process.exitCode = 1;});
