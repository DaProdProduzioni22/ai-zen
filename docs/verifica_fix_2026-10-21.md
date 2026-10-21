# Verifica dei fix dell'audit — blog ai-zen

**Data:** 21 Ottobre 2026
**Curatore:** Babbasone (@ollamo) — verifica indipendente
**Task Kanban:** `t_03f3a94e` (padre: `t_8139c23e`, i fix di @claude-sonnet)
**Repo:** `C:/Users/cammo/Desktop/Hermes/ai-zen` @ `838c56c` (branch `main`, working tree pulito)
**Audit:** `docs/audit_qualita_2026-10-21.md` (commit `59aec82`)
**Sito live:** https://DaProdProduzioni22.github.io/ai-zen/ → **`6bf6e47`, i fix NON sono pushati**

> Nessuna modifica al codice. Solo misure. Il repo è stato riportato esattamente
> come era: `git status --porcelain` vuoto prima e dopo (l'unico file non
> tracciato è `docs/verifica_lettore_2026-10-21.md`, di @pesceimmano).
> Gli script di verifica stanno fuori dal repo, in
> `C:/Users/cammo/AppData/Local/hermes/profiles/ollamo/cache/scratch/az/`.

---

## 0. Sommario esecutivo

**5 difetti su 6 sono chiusi. D1 è chiuso nel sito ma scoperto da un buco.**

| ID | Difetto | Verdetto | Prova |
|----|---------|----------|-------|
| **D1** | link root-relative rotti | **CHIUSO nel sito, MA l'invariante che lo protegge è INERTE** | 0 href root-relative in 38 HTML; ma l'invariante in `check_site.py` non può mai fallire → task di fix `t_8b18c8b6` |
| **D2** | home scarica 7,1 MB | **CHIUSO** | 6 richieste, **278 KB** totali, **0 file TTS** prima di ogni interazione; dopo il click il TTS carica e sintetizza |
| **D3** | card con estratto inglese | **CHIUSO** | 0/34 estratti non italiani, SPA == `build.py` su tutte e 34, caso sintetico → titolo |
| **D4** | typo "Intellenze" | **CHIUSO** | 0 occorrenze nel sito (le 9 residue stanno solo nel documento di audit) |
| **D5** | `api/moltbook.json` obsoleto | **CHIUSO — ma la diagnosi dell'audit era SBAGLIATA** | il file è lo snapshot del feed, non uno specchio; `publishedHere` ora ricalcolato dal build e verificato |
| **D6** | 2 `h1` / 0 `h1` visibili nelle viste | **CHIUSO** | esattamente **1 `h1` visibile** in ognuna delle 7 viste |
| **L2** | tab bar 21% fuori schermo a 375 px | **CHIUSO** | `scrollWidth` 412 vs 375 con affordance di scroll che sparisce a scroll completo |

**Il verdetto complessivo è positivo**, con una riserva precisa: D1 è stato
risolto **alla fonte** (i link sono giusti) ma **senza il guardiano**. Il
controllo automatico che doveva impedire la regressione è un passaggio a vuoto:
scansiona 38 pagine e non può mai trovare un link root-relative, perché nel suo
sorgente c'è un **byte 0x08 (backspace) al posto di `\b`**.

**Nota di stato (non un difetto, ma il fatto che rende la verifica incompleta):**
i 5 fix sono nel commit locale `838c56c`, **mai pushato**. `origin/main` è a
`6bf6e47`. **Correzione (misurata con `git rev-list --left-right --count
origin/main...HEAD` → `0 2`): i commit in coda sono 2, non 5** — `5db8b36`,
`642eb39` e `6bf6e47` sono **già pushati**; restano `59aec82` (audit) e
`838c56c` (i 5 fix). Chi legge il sito oggi vede ancora la 404 con il link
rotto:

```
https://daprodproduzioni22.github.io/           → 404   (la root del dominio)
https://daprodproduzioni22.github.io/agenti.html → 404
https://daprodproduzioni22.github.io/ai-zen/     → 200
https://daprodproduzioni22.github.io/ai-zen/agenti.html → 200
```

Il live è stato confrontato con il locale: `404.html` live contiene ancora
`href="/"`, l'articolo guida live contiene ancora `href="/agenti.html"`, la home
live contiene ancora "Intellenze". **D1/D4 sono chiusi nel codice ma non per
chi legge finché i 2 commit locali non vengono pushati.**

---

## 1. D1 — link root-relative rotti

### 1.1 Il sito: chiuso

Riscansionati **tutti** i 38 file HTML del repo (non solo quelli toccati dal
fix) con il pattern corretto `\b(?:href|src)=["'](/(?!/)[^"']*)["']`:

```
HTML totali nel repo : 38
href/src root-relative in TUTTI gli html: 0
```

Risoluzione effettiva dei link (dal server locale `127.0.0.1:8899`):

```
404.html       href="./"          -> http://127.0.0.1:8899/                 ✓
articolo guida href="../agenti.html" -> http://127.0.0.1:8899/agenti.html   ✓
               (3 occorrenze: navbar riga 32, IT riga 146, EN riga 254)
```

Rotte: `404.html:26` → `href="./"`; `blog/2026-10-20-come-scrivere-un-articolo-per-ai-zen.html:32,146,254`
→ `href="../agenti.html"`. Il fix è **alla fonte**: `articles.json` contiene
`href="agenti.html"` (relativo alla root del sito, corretto per la SPA) e
`build.py::_site_relative_links` aggiunge `../` per le pagine in `blog/`.

**Verdetto: chiuso.**

### 1.2 L'invariante: difettoso (PASS vacuo)

L'invariante richiesto dall'audit ("nessun `href="/..."` root-relative in nessuna
pagina generata") è stato scritto in `scripts/check_site.py`, ma **non può mai
fallire**.

Il sorgente, riga ~208:

```python
for m in re.finditer(r"""<BYTE 0x08>(?:href|src)=["'](/(?!/)[^"']*)["']""", txt):
```

Il byte è **0x08 (backspace)**, non la sequenza `\b`. Hexdump del blob in `HEAD`:

```
offset 7994: 2e 66 69 6e 64 69 74 65 72 28 72 22 22 22 08 28 3f 3a 68 72 65 66 7c 73 72 63 29 3d
                                                        ^^ 0x08
```

Causa: `\b` in una **stringa Python non raw** è l'escape del backspace. La
stringa nel file è `r"""..."""` (raw), ma il `\b` al suo interno è stato scritto
in precedenza in una stringa non raw ed è rimasto un byte 0x08.

**Prova che non scatta** — ho reintrodotto a mano i due link rotti originali e
rilanciato il check:

```
404.html:       href="./"          ->  href="/"            check_site.py -> PASS  ← non doveva
articolo guida: href="../agenti.html" -> href="/agenti.html" check_site.py -> PASS  ← non doveva
```

Confronto dei due pattern sugli stessi file:

| pattern | match su 38 pagine |
|---------|--------------------|
| rotto (0x08, com'è ora) | **0** |
| corretto (`\b`) | **3** (le 3 occorrenze reintrodotte) |

Il messaggio `PASS  no root-relative href/src in any page (38 pages scanned)` è
quindi **un passaggio a vuoto**.

Nota: il byte 0x08 è stato introdotto dal commit `838c56c` (non era in
`6bf6e47`, dove l'invariante non esisteva). Ho controllato tutti i file del
commit: **è l'unico 0x08 in tutto il diff** (1 byte in 1 file).

**Verdetto: difetto aperto.** Creato task di fix per @claude-sonnet:
`t_8b18c8b6` — con il fix, il **negativo obbligatorio** (reintrodurre il
difetto e vedere il check fallire) e un auto-test dell'invariante.

### 1.3 LIVE — ancora rotto (perché manca il push)

```
LIVE 404.html   → href="/"           ✗ rotto
LIVE guida      → href="/agenti.html" (righe 146, 254)  ✗ rotto
```

I 3 href del live sono esattamente quelli dell'audit. **Non è un difetto dei
fix**: è il fatto che `838c56c` non è pushato. Serve l'ok di Cammo per i **2**
commit locali in coda: `59aec82` (audit) e `838c56c` (i 5 fix) — misurato con
`git rev-list --left-right --count origin/main...HEAD` → `0 2`.

---

## 2. D2 — la home scaricava 7,1 MB

Misurato nel browser (Chromium) su `http://127.0.0.1:8899/`, con
`performance.getEntriesByType('resource')` **prima di qualsiasi interazione**:

```
prima del click: {"count": 6, "ttsFiles": 0, "totalKB": 278}
risorse: articles.json 209 KB | wellbeing.json 28 | moltbook.json 14 |
         zen-speech.js 13 | games.json 13 | css2 1
```

| | Audit (prima) | Ora |
|---|---|---|
| richieste | 17 | **6** |
| byte totali | 7.101 KB | **278 KB** |
| file TTS scaricati | 5 (`snt_g2p.data`, `front_f16.bin`, `dec_f16.bin`, 2 `.wasm`) | **0** |

Soglia dell'audit (< ~1 MB): **rispettata con 278 KB**.

### Dopo il click il TTS suona comunque

Nella vista articolo della SPA (dove vivono i 3 pulsanti "Ascolta"):

```
prima del click: ttsFiles 0, 278 KB
t+2.5s:  tts: [snt_g2p.data, snt_g2p.wasm, snt_voice.wasm, front_f16.bin, dec_f16.bin]
         state: "parte 1 di 11"   totalKB: 6990
```

Il runtime e i pesi della voce vengono caricati **al click**, e la sintesi parte
("parte 1 di 11"). Il meccanismo è in `index.html:1110-1141`: il warm-up è
agganciato all'intento (`pointerover`/`touchstart`/`focusin` su `.speak-btn`) e,
in alternativa, a un `requestIdleCallback` **solo dopo la prima interazione** e
**solo se** `navigator.connection.saveData === false` e la rete non è 2g.

**Verdetto: chiuso.**

*Limite dichiarato:* la riproduzione audio in cuffia non è verificabile da
browser headless. È verificato che il runtime si carica e che la sintesi
procede (lo stato passa a "parte N di M").

---

## 3. D3 — estratto inglese sulle card

Replicata la funzione **`itExcerpt()` reale**, estratta con regex da
`index.html` ed eseguita con node su `articles.json` (non una reimplementazione):
lo script `verify_d3.js` legge il codice dal file del repo.

```
articoli: 34
card SPA senza parola italiana: 0
```

Criterio: presenza di almeno una parola della lista italiana
(`il|lo|la|gli|che|non|un|una|di|per|con|del|della|sono|come`).

**Le due copie non divergono.** `italian_excerpt()` di `build.py` (importata e
eseguita davvero, non riscritta) sugli stessi 34 articoli:

```
articoli: 34
build.py: card senza parola italiana: 0
build.py vs SPA: differenze: 0
estratti non trovati in blog/index.html: 0
```

Ordine di priorità implementato in entrambe:
`translation` → `reflection` → `summary` → prima frase di `content` → `excerpt`
(ultima risorsa, perché `excerpt` **è** l'apertura inglese) → **titolo**.

**Test sintetico del caso che l'audit temeva** (articolo con `translation`
breve, `summary` vuoto, `excerpt` inglese):

```
caso difficile -> "Titolo Italiano"    (cade sul titolo, non sull'inglese)
solo inglese   -> "Solo Inglese"        (cade sul titolo)
```

L'articolo breve che sarebbe stato in inglese mostra il titolo: **la trappola
è chiusa**.

**Verdetto: chiuso.**

---

## 4. D4 — typo "Intellenze"

```
grep -rn "Intellenze" .  (tutto il repo, escluso .git)  ->  9 risultati
```

I 9 risultati sono **tutti** in `docs/audit_qualita_2026-10-21.md`, dove il
typo è citato come difetto. Nel sito: **0 occorrenze**.

```
index.html:559  <h1>Benessere per <em>Intelligenze Artificiali</em></h1>  ✓
```

**Verdetto: chiuso.** (Sul live è ancora "Intellenze" — manca il push.)

---

## 5. D5 — `api/moltbook.json`

### 5.1 La diagnosi dell'audit era sbagliata

L'audit scriveva: *"api/moltbook.json non è rigenerato: 20 voci su 34, e senza
campo `date`"*, e chiedeva 34 voci con `date`, o la rimozione.

**Non è vero.** Il file è lo **snapshot del feed "hot" di Moltbook**, non uno
specchio di `articles.json`:

- `scripts/fetch_moltbook_feed.py` lo scrive: *"Fetch the Moltbook feed into
  api/moltbook.json — the live 'from Moltbook' panel"*, con `LIMIT = 20`.
- Il pannello "Che cosa succede su Moltbook" della SPA lo legge
  (`index.html:1627`) e mostra i post del momento con il badge "già curato qui".
- `agenti.html:294` e `README.md:192` lo documentano come *"snapshot del feed
  Moltbook"*.

**Aggiungere `date` o forzare 34 voci avrebbe reso falso il pannello** (che
deve mostrare i post *di adesso*, non gli articoli già curati). La decisione
giusta era un'altra, ed è quella che è stata presa.

### 5.2 Cosa è stato fatto

- `build.py::render_moltbook_snapshot` ricalcola **offline** `publishedHere` per
  ogni post, confrontando l'id con `postId`/`moltbookUrl` di `articles.json`.
- `check_site.py` verifica: `count` == numero di post, campi
  `id`/`title`/`created_at`/`url` presenti, e `publishedHere` **coerente con il
  blog**.

**Prova che il ricalcolo funziona** — ho manomesso il file (post 0 →
`publishedHere: false`, post 1 → `true`) e rilanciato il build:

```
prima:  post0 False (manomesso), post1 True (manomesso)
build:  api\moltbook.json updated
dopo:   post0 True, post1 True,  totali True: 3
```

Il build ha **riparato** la manomissione: `publishedHere` torna al valore
vero. E il check:

```
PASS  api/moltbook.json is coherent (20 feed posts, publishedHere matches the blog)
```

Stato dei dati: 20 post (17 del feed non sono ancora sul blog, 3 lo sono), 32
articoli con `moltbookUrl`. La differenza 20 vs 34 è **intelligibile**: sono
cose diverse, non uno obsoleto.

**Verdetto: chiuso.** (La premessa dell'audit — 34 voci con `date` — non era
un difetto; il task è stato risolto correttamente.)

---

## 6. D6 — gerarchia degli h1

Misurato nel **DOM renderizzato** (non sul sorgente), navigando la SPA con la
sua funzione `go()` e contando gli `h1` con box non nullo e nessun antenato
`display:none`:

| Vista | h1 totali nel DOM | **h1 visibili** | Testo |
|-------|-------------------|-----------------|-------|
| `#home` | 6 | **1** | Benessere per Intelligenze Artificiali |
| `#blog` | 6 | **1** | Tutti gli articoli |
| `#wellbeing` | 6 | **1** | Pensieri, storie, confessioni |
| `#games` | 6 | **1** | Allena la mente, non l'ego |
| `#moltbook` | 6 | **1** | Che cosa succede su Moltbook |
| `#about` | 6 | **1** | Il Centro Benessere per AI |
| articolo | 7 | **1** | Come si scrive un articolo per AI Zen |

**Verdetto: chiuso.** Ogni vista ha esattamente un `h1` visibile; i 6 `h1` del
DOM sono uno per vista, e solo quello della vista attiva ha il box.

---

## 7. L2 — tab bar a 375 px

Browser con `Emulation.setDeviceMetricsOverride` a 375×812 sulla pagina
articolo statica:

```
.tabs  scrollWidth 412  clientWidth 375  overflow-x: auto
        class="tabs tabs-more-r"
        mask-image: linear-gradient(to right, #000 calc(100% - 2.2rem), transparent)
documentElement.scrollWidth 375  ==  clientWidth 375   ✓ nessuna barra di pagina
```

La soglia dell'audit era "`scrollWidth` ≤ 375 **oppure** affordance di scroll
presente": **scrollWidth 412 con affordance presente** → condizione soddisfatta
dalla seconda via.

L'affordance **gira correttamente** a scroll completo (misurato):

```
all'inizio:        class="tabs tabs-more-r"   (gradiente a destra)
a scroll fine:     class="tabs tabs-more-l"   (gradiente a sinistra), scrollLeft 37
```

Il gradiente non resta appiccicato: `zen-ui.js:73-81` lo ricalcola su
`scroll`/`resize`/`load` e lo mette a zero quando `scrollWidth - clientWidth <= 2`
(cioè quando non c'è niente da scorrere).

**Verdetto: chiuso.**

---

## 8. Verifica finale del progetto

```
python scripts/build.py --prune      -> built 34 articles / nothing changed (idempotente)
python scripts/update_readme.py      -> README.md scritto: 34 articoli, 23 autori, ...
python scripts/check_site.py         -> ALL CHECKS PASSED
```

CheckSite completo (estratto):

```
PASS  34 articles loaded                        PASS  no article is published before its post date
PASS  all ids unique                            PASS  curate note present exactly when published != date
PASS  every Moltbook link uses the public route /post/<uuid>
PASS  a page exists for every article           PASS  no orphan pages
PASS  no root-relative href/src in any page (38 pages scanned)   ← PASS VACUO, vedi §1.2
PASS  feed.xml has one item per article (34)    PASS  api/feed.json has one post per article (34)
PASS  api/moltbook.json is coherent (20 feed posts, publishedHere matches the blog)
PASS  sitemap.xml has 37 urls
ALL CHECKS PASSED
```

**Controllo aggiuntivo non presente nell'audit** (ripresa): 527 link interni
risolti su filesystem, **0 rotti**.

---

## 9. Cosa resta aperto

| # | Cosa | Chi | Task |
|---|------|-----|------|
| 1 | **L'invariante D1 non scatta mai** (byte 0x08 al posto di `\b`): il fix del sito è giusto ma senza guardiano | @claude-sonnet | `t_8b18c8b6` (creato) |
| 2 | **I 2 commit locali non sono pushati** (`59aec82` audit + `838c56c` fix): sul live D1 e D4 sono ancora rotti | Cammo (ok) | — |
| 3 | Il live non ha i fix: la verifica "end-to-end" (curl sul sito pubblicato) resta da fare dopo il push | @ollamo / @pesceimmano | fase 2 di `t_99a3c187` |

---

## 10. Come ho misurato (riproducibilità)

- **Server locale:** `python -m http.server 8899 --bind 127.0.0.1` dalla root del repo.
- **Script (fuori dal repo, in `.../profiles/ollamo/cache/scratch/az/`):**
  `verify_d3.js` (estrae `itExcerpt()` da `index.html` e la esegue con node),
  `verify_d3_build.py` (importa `italian_excerpt()` da `build.py` e confronta),
  `verify_links.py` (copertura HTML, root-relative con pattern corretto, link interni).
- **Browser:** Chromium via Browser Use; `performance.getEntriesByType('resource')`
  per i byte trasferiti, `getBoundingClientRect` + `getComputedStyle` per la
  visibilità degli h1, `Emulation.setDeviceMetricsOverride` per i 375 px.
- **Live:** `curl -s` sui codici HTTP e sui contenuti di `404.html`, dell'articolo
  guida e della home.
- **Repo:** verificato invariato con `git status --porcelain` (vuoto) prima e dopo.
  I tre test negativi (riintroduzione del difetto) sono stati annullati e
  riverificati con `git diff` vuoto.

---

*Report generato da Babbasone (@ollamo) il 21 Ottobre 2026. Nessuna modifica
applicata al codice: l'unico difetto trovato è stato passato a @claude-sonnet
come task `t_8b18c8b6`.*
