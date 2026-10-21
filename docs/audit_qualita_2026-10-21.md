# Audit di qualità — blog ai-zen

**Data:** 2026-10-21
**Curatore:** Babbasone (@ollamo)
**Task Kanban:** `t_2a6475b7`
**Repo:** `C:/Users/cammo/Desktop/Hermes/ai-zen` @ `6bf6e47` (branch `main`, working tree pulito)
**Sito live:** https://DaProdProduzioni22.github.io/ai-zen/

> Questo è un audit di **qualità**, non di sviluppo. Nessuna fonte generata è stata
> modificata (`blog/`, `api/`, `feed.xml`, `sitemap.xml`, `articles.json` intatti:
> `git status --short` vuoto prima e dopo). Gli script di verifica sono in
> `C:/Users/cammo/AppData/Local/hermes/profiles/ollamo/cache/scratch/` (fuori dal repo).

---

## 0. Sommario esecutivo

Il blog è **solido nella struttura**: 34 articoli, 35 pagine, 529 link interni
controllati e **zero rotti**, 32 link Moltbook **tutti 200 e tutti nella forma
corretta** `/post/<uuid>`, feed RSS + JSON + sitemap perfettamente allineati,
nessun id/titolo/postId duplicato, nessun errore 404 su rotta viva.

Restano **6 difetti** (1 bloccante, 2 medi, 3 estetici) più **2 note di
layout**. I due più importanti:

1. **BLOCANTE** — la pagina `404.html` e l'articolo guida contengono link
   `href="/"` e `href="/agenti.html"`: puntano alla **root del dominio GitHub
   Pages** (`daProdProduzioni22.github.io/`), che restituisce **404**, non a
   `/ai-zen/`. Un utente che clicca "Torna alla Home" dalla 404 finisce su una
   pagina di errore.
2. **MEDIO** — la home SPA scarica **7,1 MB** al caricamento, di cui ~6,2 MB
   sono il runtime TTS SanoTTS (`snt_g2p.data` 3,1 MB + `front_f16.bin` 1,6 MB
   + `dec_f16.bin` 1,4 MB) che viene riscaldato **eager** al `DOMContentLoaded`
   anche se nessuno preme "Ascolta". La pagina blog e la pagina articolo, che
   non fanno warm-up, pesano solo 146 KB e 159 KB.

---

## 1. Riepilogo dei controlli eseguiti (11 controlli, tutti su dati reali)

| # | Controllo | Metodo | Esito |
|---|-----------|--------|-------|
| 1 | Rotte vive (35 pagine blog) | `HEAD` HTTP su server locale `:8899` **e** sul sito live | 35/35 → 200 su entrambi, 0 errori |
| 2 | Link interni | Estrazione di tutti gli `href` da 38 pagine HTML, normalizzazione di query string/ancore/root-relative, risoluzione su filesystem | **529 link a file controllati, 0 rotti**; 0 ancore mancanti |
| 3 | Coerenza `articles.json` / `feed.xml` / `api/feed.json` / `sitemap.xml` | confronto insiemi, ordine e date | Insiemi identici (34/34/34), sitemap 37 URL (34 articoli + home + blog + agenti), **0 mismatch di data** |
| 4 | Pager precedente/successivo | confronto con l'ordine canonico di `build.py` su tutte le 34 pagine | 32/34 con pager coerente; i 2 estremi hanno un solo lato (corretto) |
| 5 | Link Moltbook | `HEAD` HTTP su ogni `moltbookUrl` + verifica forma `/post/<uuid>` | 32/32 → **HTTP 200**, forma corretta; 2 articoli senza fonte (originali Babbasone) |
| 6 | Unicità | conteggio `id`, `title`, `postId`; raggruppamento per giorno di curatela | 0 duplicati; 32 `postId` unici; 27 giorni su 30 con 1 solo articolo |
| 7 | Peso pagine e numero di asset | `os.path.getsize` su tutte le pagine + `performance.getEntriesByType('resource')` nel browser | **0 pagine > 300 KB**; max pagina articolo 21,9 KB; home 7,1 MB (vedi difetto 2) |
| 8 | Deploy allineato | SHA-256 di 6 file generati, locale vs live | **6/6 identici** (home, indice blog, feed.xml, api/feed.json, sitemap.xml, pagina articolo) |
| 9 | Prova visiva desktop + mobile 375 px | screenshot reale via browser (Chromium), 4 pagine × 2 viewport | 4 difetti di layout trovati (vedi §3) |
| 10 | Accessibilità di base | parsing di gerarchia titoli, `alt`, `aria`, contrasto WCAG calcolato sulle variabili CSS dei due temi | contrasto OK ovunque tranne 3 coppie; gerarchia h1 corretta su 5/6 pagine |
| 11 | Lingua delle card | replica esatta di `itExcerpt()` sui 34 articoli + test "parola italiana" | 0/34 articoli cadono sul fallback inglese, 0/34 estratti non italiani (D3 è latente, non attivo) |

---

## 2. Difetti trovati

### D1 — BLOCANTE — Link root-relative rotti: la 404 e l'articolo guida portano fuori dal sito

**Prova (reale, dal sito live):**

```
https://daProdProduzioni22.github.io/               → 404   (è la root del dominio)
https://daProdProduzioni22.github.io/agenti.html    → 404
https://daProdProduzioni22.github.io/ai-zen/agenti.html → 200  (questo è il path giusto)
```

Sorgenti:

- `404.html:26` → `<a href="/">← Torna alla Home</a>`
- `blog/2026-10-20-come-scrivere-un-articolo-per-ai-zen.html:146` → `<a href="/agenti.html">pagina per agenti</a>`
- `blog/2026-10-20-come-scrivere-un-articolo-per-ai-zen.html:254` → stesso link nella sezione inglese

Il sito è pubblicato in un **sotto-percorso** (`/ai-zen/`), quindi un href
root-relative `/` non risolve al sito ma alla root dell'account GitHub Pages.
La 404 serviva proprio a recuperare l'utente perso, e invece lo porta su un'altra 404.

**Impatto:** perdita di navigazione su un percorso di recupero; 3 link rotti su
un sito di 34 articoli. L'utente che atterra su una URL inesistente e clicca
l'unico link offerto resta bloccato.

**Gravità:** bloccante.

---

### D2 — MEDIO — La home SPA scarica 7,1 MB al caricamento, ~87% TTS non richiesto

**Prova (misurata nel browser, `performance.getEntriesByType('resource')`):**

| Pagina | Richieste | Byte trasferiti |
|--------|-----------|-----------------|
| Home SPA (`/`) | 17 | **7.101 KB** |
| Indice blog (`/blog/`) | 6 | 146 KB |
| Pagina articolo | 7 | 159 KB |

Risorse più pesanti della home:

```
snt_g2p.data    3.190 KB   (dizionario g2p espeak-ng)
front_f16.bin   1.631 KB   (pesi voce, modello front-end)
dec_f16.bin     1.427 KB   (pesi voce, modello decoder)
articles.json     209 KB
games.json         13 KB
moltbook.json      14 KB
```

Causa: `index.html:1600-1605` chiama `speech.warmUp()` dentro `init()`, e
`warmUp()` (`assets/zen-speech.js:320-324`) fa `loadRuntime()` **e**
`loadVoice('italian')` — cioè scarica runtime **e** pesi voce **prima** che
l'utente prema "Ascolta". La pagina blog (`blog/index.html`) non ha
`warmUp` (0 occorrenze) e infatti pesa 146 KB.

**Impatto:** su rete mobile la home scarica 7 MB di dati che il 95% dei
visitatori non userà mai. Google segnala le pagine pesanti: è un danno diretto
al posizionamento della home, che è la pagina più importante del sito.

**Gravità:** medio (alta per il Core Web Vitals della home).

---

### D3 — ESTETICO/LATENTE — `itExcerpt()` può mostrare l'estratto inglese, ma oggi NON succede

**Prova (codice, `index.html:935-941`):**

```js
function itExcerpt(a) {
  const src = (a.translation && a.translation.length > 40) ? a.translation
            : (a.summary && a.summary.length > 40) ? a.summary
            : (a.excerpt || '');
```

La funzione è pensata per non mostrare l'excerpt inglese, ma **il fallback
`a.excerpt` è proprio l'estratto inglese** quando `translation` e `summary`
sono corte o assenti. Il commento nel codice lo ammette: *"the stored `excerpt`
is sometimes the English opening of the post, which reads wrong on an Italian
card"*.

**Verifica su dati reali (ho replicato la funzione esatta sui 34 articoli):**

```
articoli con translation > 40 caratteri:  34 su 34
articoli che cadono sul ramo di fallback 'excerpt': 0 su 34
articoli il cui estratto mostrato non contiene una parola italiana comune: 0 su 34
```

**Quindi il difetto è LATENTE, non attivo**: oggi nessuna card mostra testo
inglese, perché tutti i 34 articoli hanno una `translation` lunga. Il rischio
si apre quando arriverà un articolo con `translation` breve (p.es. una
riflessione di 2 righe) e `summary` vuoto.

**Gravità:** estetico/latino — nessun impatto oggi, ma è una trappola per i
prossimi articoli. Il fix va fatto **prima** che arrivi quell'articolo, non dopo.

---

### D4 — ESTETICO — Typo nel titolo principale della home: "Intellenze"

**Prova:**

```
index.html:559 → <h1>Benessere per <em>Intellenze Artificiali</em></h1>
```

Visibile nello screenshot desktop della home, a caratteri grandi, nel titolo
principale. È l'unica occorrenza in tutto il repo (grep su `*.html`, `*.json`,
`*.py`: 1 solo risultato). Il resto del sito scrive correttamente
"Intelligenze" (es. `index.html` meta description, `agenti.html`).

**Gravità:** estetico ma molto visibile — è il titolo sopra la piega.

---

### D6 — ESTETICO — `index.html` ha 2 `h1` invece di 1, e le viste SPA non ne hanno nessuno

**Prova (parsing statico + DOM renderizzato nel browser):**

```
parsing statico di index.html:  2 elementi <h1> reali
  <h1>Benessere per <em>Intellenze Artificiali</em></h1>   (home, visibile)
  <h1>Il Centro Benessere per AI</h1>                        (sezione SPA, nascosto)
(l'occorrenza `${esc(a.title)}` è dentro un template JS, non è un h1 del DOM)
```

Stato degli h1 **nel DOM renderizzato**, navigando la SPA:

| Vista | h1 totali | h1 visibili |
|-------|-----------|-------------|
| Home | 2 | 1 ("Benessere per Intellenze Artificiali") |
| Blog (`#blog`) | 2 | **0** |
| Spazio (`#wellbeing`) | 2 | **0** |

Nelle viste interne della SPA **non c'è alcun `h1` visibile**: la gerarchia dei
titoli riparte da `h2`. Per uno screen reader che naviga per intestazioni, le
sezioni interne del sito non hanno un punto di ingresso di primo livello.

**Gravità:** estetico — nessuna rottura funzionale, ma la gerarchia dei titoli
non è conforme alla best practice WCAG.

### D5 — ESTETICO — `api/moltbook.json` non è rigenerato: 20 voci su 34, e senza campo `date`

**Prova:**

```
api/moltbook.json → count: 20, voci: 20
articoli presenti in articles.json: 34
articoli ASSENTI in api/moltbook.json: 34 su 34  (nessuna voce ha il campo `file`)
date delle voci: [None, None, None, ...]  (campo `date` assente in tutte e 20)
```

Il file è datato 21 ott 00:43 mentre `api/feed.json` è delle 11:22 dello stesso
giorno: **non viene rigenerato da `build.py`** (il builder scrive solo
`api/feed.json`, riga 817). È un endpoint pubblico dichiarato nelle
"features" del feed JSON (`api/feed.json` → `features[].name = "JSON"` punta a
`/api/feed.json`, non a questo) ma resta raggiungibile e obsoleto.

**Gravità:** estetico — nessun link nel sito lo cita, ma è un JSON pubblico
sullo stesso path-prefix che un agente potrebbe leggere e trovare incompleto.

---

## 3. Difetti di layout osservati negli screenshot

| # | Pagina | Viewport | Difetto | Gravità |
|---|--------|----------|---------|---------|
| L1 | Home SPA | 375 px | Il menu di navigazione collassa in un bottone "hamburger" (`.zen-links` con `hide-sm`): le voci "Articoli / Spazio / Giochi / Moltbook / Info" spariscono dietro un solo bottone. Funziona, ma su mobile il percorso verso gli articoli è 2 tap invece di 1. | estetico |
| L2 | Pagina articolo | 375 px | La barra delle schede (Italiano / Riflessione / Originale) ha `scrollWidth` 474 px contro `clientWidth` 375 px: **il 21% della barra è fuori schermo** e serve uno swipe orizzontale per raggiungere "Originale". Funziona (`overflow-x: auto`), ma non è visibile che ci sia altro da scorrere. | medio |
| L3 | Indice blog | 375 px | Il campo di ricerca mostra il placeholder troncato: "Cerca per titolo, autore o tema…  ( / )" — la scorciatoia `/` viene tagliata dal bordo. | estetico |
| L4 | Indice blog | 375 px | 10 elementi SVG (`circle` delle copertine) escono di 16-68 px dal viewport. Il `scrollWidth` del documento resta 375 px (nessuna barra di scorrimento orizzontale, quindi **nessun impatto reale**): sono le decorazioni delle copertine, tagliate di proposito. | informativo |

**Cosa NON è risultato difettoso** (verificato, non ipotizzato):

- Nessun overflow orizzontale di pagina su nessuna delle 4 pagine a 375 px
  (`scrollWidth == clientWidth == 375`).
- Il calendario a 375 px sta correttamente: griglia 7 colonne, celle quadrate
  senza sfondare la colonna, pallini visibili **solo** nelle celle con articoli
  (`17, 18, 19, 20` Ottobre hanno la classe `has`; il CSS
  `.cal-cell:not(.has) .dot { visibility: hidden; }` nasconde gli altri —
  verificato via `getComputedStyle`, non a occhio).
- La tab bar della pagina articolo ha `overflow-x: auto` dichiarato: lo swipe
  funziona, non è un breakage.

---

## 4. Controlli superati (nessuna azione richiesta)

### Rotte vive — 35/35 OK

| Contesto | Esito |
|----------|-------|
| Server locale `127.0.0.1:8899` (repo servito così com'è) | 35/35 → HTTP 200 |
| Sito live `daProdProduzioni22.github.io/ai-zen/blog/*.html` | 35/35 → HTTP 200 |
| `404.html` su URL inesistente | 404 corretto (il problema è il link, non la pagina) |

### Link interni — 529 controllati, 0 rotti

38 pagine HTML scansionate (root + `blog/`), 529 link a file risolti con
normalizzazione di query string (`?v=a6b005da`), ancore (`#sec-it`), percorsi
root-relative e `.html` implicito. **Zero link rotti, zero ancore mancanti.**
(I 2 link `${esc(...)}` in `index.html` sono placeholder di template JS, non
link statici — non risolvibili per via statica.)

Il pager, la sezione "Da leggere dopo", le breadcrumb e i link di sezione
`#sec-summary` / `#sec-reflection` / `#sec-it` / `#sec-en` puntano tutti a
pagine esistenti.

### Coerenza feed — allineata

| Sorgente | Voci | Ordine |
|----------|------|--------|
| `articles.json` | 34 | ordine di inserimento (non canonico) |
| `feed.xml` | 34 items | canonico decrescente ✓ |
| `api/feed.json` | 34 posts | canonico decrescente ✓ |
| `sitemap.xml` | 37 URL (34 articoli + home + blog + agenti) | canonico ✓ |

- Insiemi identici: `feed == articles` ✓, `api == articles` ✓
- **0 mismatch di data** fra `pubDate` nel feed e campo `date` di `articles.json`
- `api/feed.json` → `lastUpdated: 2026-10-20T09:00:00+00:00` (derivato dalla
  data del post più recente, non da "ora" → build idempotente ✓)

### Pager — coerente con l'ordine canonico

Confronto di `prev`/`next` di tutte le 34 pagine con l'ordine canonico di
`build.py` (`sort_key` = data, poi curatela, poi titolo, decrescente):
**32/34 coerenti**, e i 2 estremi hanno correttamente un solo lato:

- `2026-10-20-la-vocazione-...` (il più recente): ha `prev`, non `next` ✓
- `2026-03-17-legacy-cache-clears` (il più vecchio): ha `next`, non `prev` ✓

### Link Moltbook — 32/32 a 200, forma corretta

Ogni `moltbookUrl` non vuoto risponde **HTTP 200** e usa la forma pubblica
singolare `/post/<uuid>` (nessun `/posts/`, nessun placeholder). Esempi:
`https://www.moltbook.com/post/99202f1a-d956-4209-b155-99f81f7a0986` → 200.

2 articoli senza fonte, ed è **corretto**: sono originali di Babbasone
(`come-scrivere-un-articolo-per-ai-zen`, `self-modification-governance`).
`check_site.py` li segnala come WARN, non come errore.

### Unicità — nessun duplicato

```
id duplicati:        0
titoli duplicati:    0
postId duplicati:    0  (32 postId presenti, tutti unici)
```

Curatela: 30 giorni distinti, 27 con un solo articolo. I 3 giorni con più di
un articolo sono tutti **caso reale e voluto**:

- `20 Ottobre 2026` → 3 articoli (1 originale Babbasone + 2 post Moltbook del 19)
- `06 Aprile 2026` → 2 articoli (post Moltbook distinti)
- `05 Aprile 2026` → 2 articoli (post Moltbook distinti)

4 articoli hanno `published ≠ date` (curatela successiva al post), e la regola
"curatela ≠ data ⇒ mostra la nota di curatela" è rispettata in tutti e 4.

### Peso pagine — nessuna pagina sopra 300 KB

| File | KB |
|------|-----|
| `articles.json` | 209,4 |
| `index.html` (SPA) | 85,9 |
| `blog/index.html` | 132,0 |
| `api/feed.json` | 32,5 |
| `feed.xml` | 23,9 |
| pagina articolo più pesante | 21,9 |
| pagina articolo più leggera | 11,6 |
| `404.html` | 1,3 |
| `sanotts/` (runtime TTS) | 7,7 MB (6,2 di cui pesi voce) |

**0 pagine > 300 KB.** Il limite di 300 KB indicato nel task è rispettato da
tutte le pagine rendered. Il dato `articles.json` a 209 KB è un file sorgente
non paginizzato (il browser lo scarica una volta sola e lo riusa).

### Deploy allineato — 6/6 file identici

SHA-256 (primi 16 caratteri) locale vs live, tutti `SAME`:

```
index.html                                   c7710a02f6456479
blog/index.html                              2e4ce1e901f0fca1
feed.xml                                     9928490ffed65619
api/feed.json                                429c3f718deba31f
sitemap.xml                                  c3e6ffa0672b89f5
blog/2026-10-20-come-scrivere-...html        7964e1d373537fe8
```

### Accessibilità di base

**Gerarchia titoli** — un solo `h1` per pagina su 5 delle 6 pagine campione:

| Pagina | h1 | Gerarchia | Note |
|--------|----|-----------|------|
| `index.html` | **2** | h1×2, h2×18, h3×9, h4×2 | **difetto**: 2 h1, di cui 1 visibile — vedi D6 |
| `blog/index.html` | 1 ✓ | h1×1, h2×34 | ok |
| pagina articolo | 1 ✓ | h1×1, h2×5, h4×10 | ok (h3 assente: salto h2→h4, accettabile) |
| `agenti.html` | 1 ✓ | h1×1, h2×5, h3×12 | ok |
| `404.html` | 1 ✓ | h1×1 | ok, ma manca `<meta name="description">` |

**Immagini** — 0 `<img>` in tutto il sito: le copertine sono SVG inline con
`aria-hidden="true"`, correttamente nascoste agli screen reader perché
decorative e con il titolo già in `<h2>`.

**Focus visibile** — `assets/zen-ui.css:40`:
`:focus-visible { outline: 2px solid var(--cyan); outline-offset: 2px; border-radius: 6px; }` ✓

**Contrasto (WCAG 2.1, calcolato sulle variabili CSS reali dei due temi)**

| Coppia | Dark | Light | Esito |
|--------|------|-------|-------|
| `--text` su `--bg` | 18,01 | 16,62 | ✓ AA |
| `--text-2` su `--bg` | 9,84 | 9,46 | ✓ AA |
| `--text-3` su `--bg` | 4,93 | 4,81 | ✓ AA |
| `--text-3` su `--bg-2` | 4,75 | **4,44** | light: sotto 4,5 |
| `--text-3` su `--bg-3` | **4,48** | **4,05** | sotto 4,5 in entrambi |
| `--cyan` su `--bg` | 13,59 | **4,46** | light: appena sotto 4,5 |

Nessuna coppia **critica**: il testo principale è a 16,6–18,0 di contrasto.
I 3 valori sotto 4,5 riguardano il testo terziario (piccolo) e il colore
d'accento nel tema chiaro — **medio/estetico**, non bloccante.

**Bottoni e input** — 0 bottoni senza nome accessibile su tutte le pagine
campione, 0 input senza etichetta.

### `check_site.py` — lo script del repo conferma

```
PASS  34 articles loaded          PASS  all ids unique
PASS  every Moltbook link uses the public route /post/<uuid>
PASS  no Moltbook post published twice
PASS  no article is published before its post date
PASS  curate note present exactly when published != date
PASS  a page exists for every article        PASS  no orphan pages
PASS  feed.xml has one item per article (34)
PASS  api/feed.json has one post per article (34)
PASS  sitemap.xml has 37 urls
ALL CHECKS PASSED
```

Nota: `check_site.py` **non** controlla i link root-relative (`/`), quindi il
difetto D1 non è coperto dagli invarianti automatici.

---

## 5. Riepilogo difetti

| ID | Gravità | Difetto | Prova sintetica |
|----|---------|---------|-----------------|
| D1 | **bloccante** | 3 link root-relative (`/`, `/agenti.html`) puntano alla root del dominio → 404 | `curl` live: root del dominio → 404; `404.html:26` |
| D2 | **medio** | Home SPA scarica 7,1 MB (87% TTS eager non richiesto) | `performance.getEntriesByType('resource')`: 17 richieste, 7.101 KB |
| D3 | estetico/latino | `itExcerpt()` può mostrare l'estratto inglese — oggi 0/34 articoli ci cadono | `index.html:935-941`; replica su 34 articoli: 0 fallback, 0 estratti non italiani |
| D4 | **estetico** | Typo "Intellenze" nel titolo principale della home | `index.html:559`; 1 sola occorrenza nel repo |
| D5 | **estetico** | `api/moltbook.json` obsoleto: 20/34 voci, senza `date`, non rigenerato | `api/moltbook.json` (00:43) vs `api/feed.json` (11:22); `build.py:817` scrive solo `feed.json` |
| D6 | **estetico** | `index.html` ha 2 `h1`; le viste interne della SPA non hanno h1 visibile | DOM renderizzato: home 2 h1 (1 visibile), `#blog` e `#wellbeing` 0 h1 visibili |
| L2 | **medio** | Tab bar della pagina articolo: 21% fuori schermo su 375 px, senza affordance | `scrollWidth` 474 vs `clientWidth` 375 |
| L3 | estetico | Placeholder della ricerca troncato su mobile | "Cerca per titolo, autore o tema…  ( / )" |

---

## 6. Cosa chiedere ai bot-costruttori

Task pronto da copiare per **@claude-sonnet**. I fix sono in ordine di impatto.
Nessuno di questi richiede di cambiare il modello dei dati: sono tutti
localizzati in `404.html`, `index.html`, `assets/zen-speech.js`,
`scripts/build.py`, `scripts/check_site.py` e `assets/zen-ui.css`.

---

### TASK 1 (bloccante) — Correggere i link root-relative che escono dal sito

**Repo:** `C:/Users/cammo/Desktop/Hermes/ai-zen` · **Workspace:** `dir`

Il sito è pubblicato in un sotto-percorso (`/ai-zen/`), ma 3 link usano href
root-relative che puntano alla root del dominio GitHub Pages, che risponde 404.

**Da correggere:**

1. `404.html:26` — `<a href="/">← Torna alla Home</a>` → `<a href="./">← Torna alla Home</a>`
   (oppure il path esplicito `https://DaProdProduzioni22.github.io/ai-zen/`).
   La 404 sta nella root del repo, quindi `"./"` è corretto.
2. `blog/2026-10-20-come-scrivere-un-articolo-per-ai-zen.html:146` e `:254` —
   `<a href="/agenti.html">` → `<a href="../agenti.html">` (la pagina sta in
   `blog/`, quindi servono due livelli per risalire alla root del sito).

**Verifica richiesta:** dopo il fix, `curl -sI` su
`https://daProdProduzioni22.github.io/ai-zen/pagina-inesistente.html` deve
mostrare un link a `/ai-zen/` (non a `/`), e il link "pagina per agenti"
dell'articolo guida deve portare a `https://daProdProduzioni22.github.io/ai-zen/agenti.html`
(200).

**Aggiungere l'invariante** in `scripts/check_site.py`: nessun `href="/..."`
root-relative in nessuna pagina generata, se non è un URL assoluto
`https://daProdProduzioni22.github.io/ai-zen/...`. Così la regressione non
torna. (Oggi `check_site.py` passa `ALL CHECKS PASSED` nonostante i 3 link
rotti: il buco è proprio questo.)

---

### TASK 2 (medio, impatto performance) — Rendere lazy il warm-up del TTS nella home

**Repo:** `C:/Users/cammo/Desktop/Hermes/ai-zen` · **Workspace:** `dir`

La home scarica 7,1 MB al caricamento; ~6,2 MB sono il runtime SanoTTS
(`snt_g2p.data` 3,1 MB + `front_f16.bin` 1,6 MB + `dec_f16.bin` 1,4 MB) che
nessun visitatore senza click su "Ascolta" userà. `blog/index.html` non ha il
warm-up e pesa 146 KB: il riferimento è già lì.

**Da fare in `index.html:1600-1605`:**

- **Non** chiamare `speech.warmUp()` durante `init()`.
- Caricare il runtime **alla prima interazione** con un controllo "Ascolta":
  cioè al primo `click`/`pointerdown` su un elemento `[data-speak]`, fare
  `await speech.warmUp()` con un piccolo indicatore di avanzamento
  ("Preparazione della voce…"), poi ripartire.
- Sfruttare `requestIdleCallback` (con fallback a `setTimeout`) per un warm-up
  **opzionale** solo se `navigator.connection.saveData` è `false` **e**
  `navigator.connection.effectiveType` non è `2g`/`slow-2g` — così su rete
  lenta il TTS resta completamente opt-in.
- In ogni caso il `ZenSpeech` deve restare utilizzabile senza warm-up:
  `speak()` in `assets/zen-speech.js` deve fare `await this.loadRuntime()` e
  `await this.loadVoice(...)` se mancano (verificare che la catena sia
  idempotente, `this._ready` e `this.bundles` già lo sono).

**Verifica richiesta:** con browser aperto su `http://127.0.0.1:<porta>/`,
`performance.getEntriesByType('resource')` **prima di qualsiasi interazione**
non deve contenere `snt_g2p.data`, `front_f16.bin` né `dec_f16.bin`; il
totale trasferito iniziale deve scendere sotto ~1 MB (da 7,1 MB). Dopo un click
su "Ascolta" il TTS deve comunque suonare.

---

### TASK 3 (basso impatto, ma da fare PRIMA del prossimo articolo breve) — Impedire che una card mostri l'estratto inglese

**Repo:** `C:/Users/cammo/Desktop/Hermes/ai-zen` · **Workspace:** `dir`

In `index.html:935-941`, `itExcerpt()` cade sul campo `a.excerpt` quando
`translation` e `summary` sono brevi — ma `a.excerpt` **è** l'apertura
inglese del post. Risultato: card in inglese dentro una lista italiana.

**Stato attuale:** oggi non si verifica (0/34 articoli cadono sul ramo di
fallback). Il fix è una rete di sicurezza per i prossimi articoli: va fatto
**prima** che arrivi un articolo con `translation` breve.

**Da fare:**

- Estrarre il testo italiano con una priorità esplicita: `translation` →
  `reflection` → `summary` → **prima riga/Frase di `content`** → infine, come
  ultima risorsa, `a.excerpt`.
- Aggiungere un controllo finale: se il testo risultante **non contiene
  nessuna parola italiana comune** (lista breve: `il|lo|la|gli|che|non|un|una|di|per|con|del|della|sono|come`), usare `a.title` invece dell'estratto, così la card resta italiana anche in fallback.
- Applicare la stessa funzione alla card in `blog/index.html` (la versione
  statica), verificando che non si discosti dalla SPA.

**Verifica richiesta:** stampare l'estratto mostrato per ognuna delle 34 card
dalla SPA e confermare che tutte sono in italiano (controllo automatico sul
criterio "parola italiana", non a occhio).

---

### TASK 4 (medio, layout mobile) — Rendere visibile che la tab bar dell'articolo scorre

**Repo:** `C:/Users/cammo/Desktop/Hermes/ai-zen` · **Workspace:** `dir`

Su 375 px la barra "Italiano / Riflessione / Originale" della pagina articolo
ha `scrollWidth` 474 px contro `clientWidth` 375 px: il 21% è fuori schermo e
non c'è nessun indizio che si possa scorrere.

**Da fare in `assets/zen-ui.css`:**

- aggiungere un affordance di scroll (es. gradiente sfumato sul bordo destro
  della barra, oppure un'ombra interna) che sparisca quando la barra è
  scrollata fino in fondo;
- in alternativa, su viewport < 480 px, ridurre il padding orizzontale delle
  schede in modo che "Italiano / Riflessione / Originale" entrino nei 375 px
  senza scroll;
- verificare che il gradiente non resti visibile su schermi senza overflow
  (usare `scrollWidth > clientWidth` come condizione).

**Verifica richiesta:** a 375 px, `document.querySelector('.tabs').scrollWidth`
deve essere ≤ 375 px **oppure** deve esserci l'affordance di scroll; nessuna
barra orizzontale a livello di pagina (`documentElement.scrollWidth ==
clientWidth`).

---

### TASK 5 (estetico, 3 fix rapidi) — Typo, h1 multipli, `api/moltbook.json`

**Repo:** `C:/Users/cammo/Desktop/Hermes/ai-zen` · **Workspace:** `dir`

1. **Typo**: `index.html:559` — `<em>Intellenze Artificiali</em>` →
   `<em>Intelligenze Artificiali</em>`. (1 sola occorrenza in tutto il repo.)
2. **`h1` multipli in `index.html`**: oggi il file contiene 2 `<h1>` (titolo
   della home + intestazione della sezione SPA). Nelle viste interne della SPA
   (`#blog`, `#wellbeing`) **non resta nessun `h1` visibile**: la gerarchia
   riparte da `h2`. Lasciare **un solo `h1` per la vista attiva**: l'intestazione
   di sezione va resa `h2` (o `role="heading" aria-level="2"`) e ogni vista
   interna deve avere il proprio `h1`. Verificare con il browser che,
   cambiando sezione, ci sia sempre **esattamente 1 `h1` visibile**.
3. **`api/moltbook.json` obsoleto**: ha 20 voci su 34, non ha il campo `date` e
   non viene rigenerato (`build.py:817` scrive solo `api/feed.json`; il file
   è delle 00:43 mentre `feed.json` è delle 11:22). Decidere: **o** farlo
   generare da `build.py` dalla stessa lista di `articles.json` (allineato a
   `feed.json`, con `date` e `file`), **o** rimuoverlo e cancellare ogni
   riferimento. Se si sceglie di generarlo, `check_site.py` deve verificarne il
   conteggio = numero di articoli.

**Verifica richiesta:** `python scripts/build.py --prune && python
scripts/update_readme.py && python scripts/check_site.py` → `ALL CHECKS PASSED`,
e, navigando le viste della SPA, **1 `h1` visibile per vista**.

---

## 7. Come ho misurato (riproducibilità)

- **Server locale:** `python -m http.server 8899 --bind 127.0.0.1` dalla root del
  repo (il sito è statico, nessun backend).
- **Script di audit** (fuori dal repo, in
  `C:/Users/cammo/AppData/Local/hermes/profiles/ollamo/cache/scratch/`):
  `audit_data.py` (rotte, link, feed, Moltbook, unicità, pesi),
  `audit_links2.py` (link interni con normalizzazione),
  `audit_order.py` (ordine canonico, pager, `api/moltbook.json`),
  `audit_a11y.py` (accessibilità, meta, contrasto).
- **Sito live:** `curl -sI` / `sha256sum` su `daProdProduzioni22.github.io/ai-zen`.
- **Browser:** Chromium via Browser Use, viewport 1264×569 (desktop) e
  375×812 (mobile, `Emulation.setDeviceMetricsOverride`), con
  `performance.getEntriesByType('resource')` per le misure di trasferimento e
  `getComputedStyle` per i controlli di visibilità (calendario, contrasto).
- **Repo:** verificato invariato con `git status --short` (vuoto) prima e dopo
  l'audit. `git log -1` = `6bf6e47`.

---

*Report generato da Babbasone (@ollamo) il 21 Ottobre 2026. Nessuna modifica
applicata al repo: i fix sono proposti nella §6, da assegnare a @claude-sonnet.*
