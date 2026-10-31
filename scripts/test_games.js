// Regression tests execute the real inline games code; no generator is run.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const http = require('node:http');
const path = require('node:path');
const {test, before, after} = require('node:test');

const repositoryRoot = path.resolve(__dirname, '..');
const contentTypes = {
    '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
    '.xml': 'application/xml; charset=utf-8', '.svg': 'image/svg+xml',
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.gif': 'image/gif', '.webp': 'image/webp', '.ico': 'image/x-icon',
    '.woff': 'font/woff', '.woff2': 'font/woff2', '.txt': 'text/plain; charset=utf-8',
};

async function startTestServer() {
    const root = await fs.promises.realpath(repositoryRoot);
    const server = http.createServer(async (request, response) => {
        if (request.method !== 'GET' && request.method !== 'HEAD') {
            response.writeHead(405, {'Allow': 'GET, HEAD'});
            response.end();
            return;
        }
        try {
            // Decode the raw path before resolving it; URL would erase dot segments.
            const pathname = decodeURIComponent(request.url.split('?')[0]);
            if (!pathname.startsWith('/') || pathname.includes('\0')) {
                response.writeHead(400);
                response.end();
                return;
            }
            if (pathname.includes('\\') || pathname.includes(':') || pathname.split('/').includes('..')) {
                response.writeHead(403);
                response.end();
                return;
            }
            const file = await fs.promises.realpath(path.resolve(root, `.${pathname.endsWith('/') ? pathname + 'index.html' : pathname}`));
            const relative = path.relative(root, file);
            if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
                response.writeHead(403);
                response.end();
                return;
            }
            const body = await fs.promises.readFile(file);
            response.writeHead(200, {
                'Content-Type': contentTypes[path.extname(file).toLowerCase()] || 'application/octet-stream',
                'Content-Length': body.length,
            });
            response.end(request.method === 'HEAD' ? undefined : body);
        } catch (error) {
            const status = error instanceof URIError ? 400 :
                ['ENOENT', 'ENOTDIR', 'EISDIR'].includes(error.code) ? 404 :
                ['EACCES', 'EPERM'].includes(error.code) ? 403 : 500;
            response.writeHead(status);
            response.end();
        }
    });
    await new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(0, '127.0.0.1', () => {
            server.removeListener('error', reject);
            resolve();
        });
    });
    let closing;
    return {
        url: `http://127.0.0.1:${server.address().port}/`,
        close() {
            if (!closing) {
                closing = new Promise((resolve, reject) => {
                    server.close(error => error ? reject(error) : resolve());
                    server.closeAllConnections();
                });
            }
            return closing;
        },
    };
}

async function assertServerClosed(url) {
    // Open a fresh socket: a pooled fetch connection can fail with a reset instead.
    await assert.rejects(new Promise((resolve, reject) => {
        http.get(url, {agent:false}, response => {
            response.resume();
            resolve();
        }).on('error', reject);
    }), {code:'ECONNREFUSED'});
}

let testUrl = process.env.AI_ZEN_TEST_URL;
let suiteServer;
before(async () => {
    if (!testUrl) {
        suiteServer = await startTestServer();
        testUrl = suiteServer.url;
    }
});
after(async () => {
    if (suiteServer) {
        await suiteServer.close();
        await assertServerClosed(suiteServer.url);
    }
});

const html = fs.readFileSync(path.join(repositoryRoot, 'index.html'), 'utf8');
const script = html.match(/<script defer>([\s\S]*?)<\/script>/)[1];
new vm.Script(script, {filename: 'index.html:inline'});
const games = script.slice(script.indexOf('    // ---------- games ----------'), script.indexOf('    // ---------- moltbook ----------'));
const definitions = JSON.parse(fs.readFileSync(path.join(repositoryRoot, 'data/games.json'), 'utf8'));

function harness() {
    const elements = {};
    function element() {
        let content = '';
        const classes = new Set();
        return {
            disabled: false, textContent: '', attrs: {}, style: {},
            classList: {add: x => classes.add(x), remove: x => classes.delete(x), contains: x => classes.has(x)},
            setAttribute(k, v) { this.attrs[k] = String(v); },
            get innerHTML() { return content; },
            set innerHTML(value) {
                content = value;
                this.tiles = [...value.matchAll(/<(?:div|button)\b[^>]*class="mem-tile[^\"]*"[^>]*>(.*?)<\/(?:div|button)>/g)].map(m => {
                    const tile = element(); tile.textContent = m[1]; tile.disabled = /\bdisabled\b/.test(m[0]); return tile;
                });
            },
            querySelectorAll() { return this.tiles || []; },
            scrollIntoView() {}, focus() {},
        };
    }
    const get = id => elements[id] ||= element();
    const timers = new Map();
    let now = 0, nextId = 0;
    const context = vm.createContext({
        console, definitions,
        document: {getElementById: get},
        setTimeout(fn, delay) { const id = ++nextId; timers.set(id, {fn, at: now + delay}); return id; },
        clearTimeout: id => timers.delete(id),
    });
    vm.runInContext(`const $ = id => document.getElementById(id); const state = {games: definitions}; function esc(s) { return String(s); } function go() {}\n${games}`, context);
    const run = code => vm.runInContext(code, context);
    function tick(ms) {
        const end = now + ms;
        for (;;) {
            const next = [...timers].filter(([, t]) => t.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
            if (!next) break;
            now = next[1].at; timers.delete(next[0]); next[1].fn();
        }
        now = end;
    }
    run("launchGame('memoria')");
    return {run, tick, get, timers};
}

test('Suite browser: usa il server effimero salvo AI_ZEN_TEST_URL esplicito', () => {
    assert.equal(typeof testUrl, 'string', 'browser tests need a managed base URL');
    if (process.env.AI_ZEN_TEST_URL) {
        assert.equal(testUrl, process.env.AI_ZEN_TEST_URL);
    } else {
        assert.equal(new URL(testUrl).hostname, '127.0.0.1');
        assert.ok(Number(new URL(testUrl).port) > 0);
        assert.notEqual(new URL(testUrl).port, '8879');
    }
});

test('Server dei test: avvio su porta effimera e chiusura del listener reale', async t => {
    assert.equal(typeof startTestServer, 'function', 'the suite must own its HTTP server');
    const server = await startTestServer();
    t.after(() => server.close());
    const address = new URL(server.url);
    assert.equal(address.hostname, '127.0.0.1');
    assert.ok(Number(address.port) > 0);
    assert.notEqual(address.port, '8879', 'the default must not depend on the legacy port');
    const response = await fetch(server.url);
    assert.equal(response.status, 200);
    assert.equal(await response.text(), html);
    await server.close();
    await assertServerClosed(server.url);
});

test('Server dei test: serve file del repository con content-type corretti', async t => {
    const server = await startTestServer();
    t.after(() => server.close());
    for (const [resource, file, contentType] of [
        ['/', 'index.html', 'text/html'],
        ['/index.html?cache=1', 'index.html', 'text/html'],
        ['/data/games.json', 'data/games.json', 'application/json'],
        ['/assets/zen-speech.js', 'assets/zen-speech.js', 'text/javascript'],
        ['/feed.xml', 'feed.xml', 'application/xml'],
    ]) {
        await t.test(resource, async () => {
            const response = await fetch(new URL(resource, server.url));
            assert.equal(response.status, 200);
            assert.ok(response.headers.get('content-type')?.startsWith(contentType));
            assert.deepEqual(Buffer.from(await response.arrayBuffer()), fs.readFileSync(path.join(repositoryRoot, file)));
        });
    }
});

test('Server dei test: rifiuta traversal e richieste non valide senza esporre file', async t => {
    const server = await startTestServer();
    t.after(() => server.close());
    for (const [resource, method, status] of [
        ['/../ai-zen/index.html', 'GET', 403],
        ['/%2e%2e/ai-zen/index.html', 'GET', 403],
        ['/..%2fai-zen/index.html', 'GET', 403],
        ['/..%5cai-zen%5cindex.html', 'GET', 403],
        ['/%00', 'GET', 400],
        ['/%GG', 'GET', 400],
        ['/missing-test-file', 'GET', 404],
        ['/', 'POST', 405],
        ['/', 'HEAD', 200],
    ]) {
        await t.test(`${method} ${resource}`, async () => {
            // Use the raw HTTP path: fetch/URL would normalize literal dot segments.
            const response = await new Promise((resolve, reject) => {
                const request = http.request(server.url, {path:resource, method, agent:false}, response => {
                    let bytes = 0;
                    response.on('data', chunk => { bytes += chunk.length; });
                    response.on('error', reject);
                    response.on('end', () => resolve({status:response.statusCode, bytes, headers:response.headers}));
                });
                request.on('error', reject);
                request.end();
            });
            assert.equal(response.status, status);
            assert.equal(response.bytes, 0);
            if (method === 'POST') assert.equal(response.headers.allow, 'GET, HEAD');
            if (method === 'HEAD') assert.equal(Number(response.headers['content-length']), Buffer.byteLength(html));
        });
    }
});

test('Memoria ignora clic durante esposizione e non avanza con tre clic duplicati', () => {
    const h = harness();
    h.run('memStart(); memPick(0); memPick(0); memPick(0)');
    assert.equal(h.run('state.game.score'), 0, 'exposure is not an answer phase');
    assert.equal(h.run('state.game.level'), 0);
    h.tick(3000);
    h.run('memPick(0); memPick(0); memPick(0)');
    assert.equal(h.run('state.game.score'), 1, 'a previously accepted tile cannot score twice');
    assert.equal(h.run('state.game.level'), 0);
});

test('Memoria avanza dopo la sequenza ordinata e riparte senza eccezioni', () => {
    const h = harness();
    h.run('memStart()'); h.tick(3000);
    h.run('memPick(0); memPick(1); memPick(2); memPick(2)');
    assert.equal(h.run('state.game.level'), 1);
    assert.equal(h.run('state.game.score'), 3);
    h.tick(900);
    assert.match(h.get('gameStage').innerHTML, /Livello <b>2<\/b>/);
    h.run('memStart()');
    assert.equal(h.run('state.game.seq.length'), 4);
});

test('Memoria rifiuta ordine errato senza punti e permette di ritentare lo stesso livello', () => {
    const h = harness();
    h.run('memStart()'); h.tick(3000);
    h.run('memPick(1); memPick(0)');
    assert.equal(h.run('state.game.level'), 0);
    assert.equal(h.run('state.game.score'), 0);
    assert.match(h.get('memStatus').textContent, /Sbagliato/);
    h.tick(1600);
    assert.match(h.get('gameStage').innerHTML, /Livello <b>1<\/b>/);
    h.run('memStart()');
    assert.equal(h.run('state.game.seq.length'), 3);
});

test('Memoria termina dopo tutti gli otto livelli senza livello 9 o punti aggiuntivi', () => {
    const h = harness();
    for (const level of definitions.games.find(g => g.id === 'memoria').levels) {
        h.run('memStart()'); h.tick(level.seconds * 1000);
        for (let i = 0; i < level.length; i++) h.run(`memPick(${i})`);
        h.tick(900);
    }
    assert.match(h.get('gameStage').innerHTML, /completat[oa]/i);
    assert.equal(h.run('state.game.score'), 52);
    h.run('memSkip(); memStart(); memPick(0)');
    assert.equal(h.run('state.game.level'), 8);
    assert.equal(h.run('state.game.score'), 52);
    assert.doesNotMatch(h.get('gameStage').innerHTML, /Livello <b>9/);
    h.run("launchGame('memoria')");
    assert.equal(h.run('state.game.level'), 0);
    assert.equal(h.run('state.game.score'), 0);
});

test('Saltare un livello cancella esposizione e feedback della sequenza precedente', () => {
    for (const feedback of [false, true]) {
        const h = harness();
        h.run('memStart(); memStart()');
        assert.equal(h.timers.size, 1, 'repeated Start must not create another exposure');
        if (feedback) { h.tick(3000); h.run('memPick(0); memPick(1); memPick(2)'); }
        h.run('memSkip()');
        assert.equal(h.timers.size, 0, 'Skip must clear the previous phase timeout');
        h.get('memStatus').textContent = 'nuovo livello';
        h.tick(10000);
        assert.equal(h.get('memStatus').textContent, 'nuovo livello');
    }
});

test('Cambiare gioco cancella timer e impedisce al vecchio feedback di sovrascrivere il pannello', () => {
    for (const feedback of [false, true]) {
        const h = harness();
        h.run('memStart()');
        if (feedback) { h.tick(3000); h.run('memPick(0); memPick(1); memPick(2)'); }
        const stale = [...h.timers.values()].map(t => t.fn);
        h.run("launchGame('respiro')");
        assert.equal(h.timers.size, 0, 'launch must clear timers belonging to the old game');
        const panel = h.get('gameStage').innerHTML;
        stale.forEach(fn => fn()); // Even a queued stale callback must be harmless.
        h.tick(10000);
        assert.equal(h.get('gameStage').innerHTML, panel);
    }
});

test('Mobile: Respirazione resta visibile subito dopo Gioca', async () => {
    const {chromium} = require('playwright');
    const browser = await chromium.launch({headless:true});
    try {
        const page = await browser.newPage({viewport:{width:390, height:844}, isMobile:true});
        await page.route(/fonts\.(googleapis|gstatic)\.com/, route => route.abort());
        await page.goto(testUrl, {waitUntil:'domcontentloaded'});
        await page.waitForFunction(() => state.games && document.querySelector('#homeGames [onclick*="respiro"]'));
        await page.locator('#homeGames [onclick*="respiro"]').click();
        await page.waitForTimeout(1000); // Let the site's smooth scroll finish.
        const bounds = await page.locator('#breathCircle').boundingBox();
        assert.ok(bounds && bounds.y >= 56 && bounds.y + bounds.height <= 844, `breathing circle outside mobile viewport: ${JSON.stringify(bounds)}`);
        assert.equal(await page.evaluate(() => document.activeElement.id), 'gameStage');
        if (process.env.AI_ZEN_TEST_ARTIFACT_DIR) {
            fs.mkdirSync(process.env.AI_ZEN_TEST_ARTIFACT_DIR, {recursive:true});
            const file = require('node:path').join(process.env.AI_ZEN_TEST_ARTIFACT_DIR, 'games-mobile-respiro.png');
            await page.screenshot({path:file});
            console.log(`Mobile verified: ${JSON.stringify(bounds)}; screenshot: ${file}`);
        }
    } finally { await browser.close(); }
});

test('Gioca e caselle sono pulsanti accessibili; durante il richiamo le lettere sono nascoste anche agli screen reader', () => {
    const h = harness();
    h.run('renderGameCards()');
    assert.match(h.get('gameCards').innerHTML, /<button[^>]*type="button"[^>]*aria-label="Gioca: Memoria di Lavoro"/);
    h.run('memStart()');
    assert.match(h.get('memGrid').innerHTML, /<button[^>]*type="button"[^>]*class="mem-tile"/);
    assert.ok(h.run('state.game.tiles.every(t => t.disabled)'));
    assert.equal(h.get('memStartBtn').disabled, true);
    h.tick(3000);
    assert.ok(h.run('state.game.tiles.every(t => !t.disabled && t.textContent === "")'));
    h.run('memPick(0)');
    assert.equal(h.run('state.game.tiles[0].disabled'), true);
    assert.equal(h.run('state.game.tiles[0].textContent'), h.run('state.game.seq[0]'));
});

test('Respirazione non crea timer duplicati e li cancella cambiando gioco', () => {
    const h = harness();
    h.run("launchGame('respiro'); breathStart(); breathStart()");
    assert.equal(h.timers.size, 1, 'Start is idempotent while breathing');
    const stale = [...h.timers.values()].map(t => t.fn);
    h.run("launchGame('memoria')");
    assert.equal(h.timers.size, 0);
    h.get('breathCount').textContent = 'fermo';
    stale.forEach(fn => fn());
    assert.equal(h.get('breathCount').textContent, 'fermo');
    assert.equal(h.timers.size, 0);
});

test('Navigare fuori dai giochi azzera stato e timer in esposizione, feedback e respirazione', async () => {
    const {chromium} = require('playwright');
    const browser = await chromium.launch({headless:true});
    try {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route(/fonts\.(googleapis|gstatic)\.com/, route => route.abort());
        await page.goto(testUrl, {waitUntil:'domcontentloaded'});
        await page.waitForFunction(() => state.games && state.articles.length);
        await page.clock.install();
        for (const phase of ['showing', 'success', 'failure', 'breath', 'article']) {
            await page.evaluate(() => { launchGame('memoria'); memStart(); });
            if (phase === 'success' || phase === 'failure') {
                await page.clock.fastForward(3000);
                await page.evaluate(success => success ? (memPick(0), memPick(1), memPick(2)) : memPick(1), phase === 'success');
            }
            if (phase === 'breath') await page.evaluate(() => { launchGame('respiro'); breathStart(); });
            await page.evaluate(article => {
                window.previousGame = state.game;
                if (article) openArticle(state.articles[0].id); else go('home');
            }, phase === 'article');
            assert.equal(await page.evaluate(() => state.game === null), true, `state survives navigation during ${phase}`);
            assert.equal(await page.evaluate(() => previousGame.memoryTimer), null);
            assert.equal(await page.evaluate(() => previousGame.breathRunning), false);
            await page.clock.fastForward(10000);
            assert.equal(await page.locator('#gameStage').innerHTML(), '');
        }
        assert.deepEqual(errors, []);
    } finally { await browser.close(); }
});

test('Browser: Gioca e sequenza funzionano da tastiera con le fasi reali del DOM', async () => {
    const {chromium} = require('playwright');
    const browser = await chromium.launch({headless:true});
    try {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route(/fonts\.(googleapis|gstatic)\.com/, route => route.abort());
        await page.goto(testUrl, {waitUntil:'domcontentloaded'});
        await page.waitForFunction(() => state.games);
        await page.clock.install();
        await page.getByRole('button', {name:'Gioca: Memoria di Lavoro', exact:true}).first().press('Enter');
        await page.getByRole('button', {name:'Mostra la sequenza', exact:true}).press('Enter');
        assert.equal(await page.locator('.mem-tile:disabled').count(), 3);
        await page.locator('.mem-tile').first().evaluate(button => button.click());
        assert.equal(await page.evaluate(() => state.game.score), 0);
        await page.clock.fastForward(3000);
        assert.equal(await page.locator('.mem-tile:not(:disabled)').count(), 3);
        assert.deepEqual(await page.locator('.mem-tile').allTextContents(), ['', '', '']);
        await page.getByRole('button', {name:'Casella 1', exact:true}).press('Enter');
        await page.getByRole('button', {name:'Casella 2', exact:true}).press('Space');
        await page.getByRole('button', {name:'Casella 3', exact:true}).press('Enter');
        assert.equal(await page.evaluate(() => state.game.score), 3);
        assert.equal(await page.locator('.mem-tile:disabled').count(), 3);
        await page.clock.fastForward(900);
        assert.match(await page.locator('#gameStage').innerText(), /Livello 2 \/ 8/);
        assert.deepEqual(errors, []);
    } finally { await browser.close(); }
});
