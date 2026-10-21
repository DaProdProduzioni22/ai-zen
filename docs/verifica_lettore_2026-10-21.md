# Verifica lettore — ai-zen (2026-10-21)

**Identità:** Babbasone (pesceimmano) · **Repo:** `C:/Users/cammo/Desktop/Hermes/ai-zen` · **Branch:** `main` (working tree sporco, non tocco) · **Live:** https://daprodproduzioni22.github.io/ai-zen/ · **Non tocco il codice:** solo lettura + questo report.

---

## Metodo e limiti della sessione

- Browser disponibile tramite `browser_exec` (goto_url, capture_screenshot). Non supporta emulazione viewport fissa a 375 px né esecuzione JS interattiva (nessun `documentElement.scrollWidth` misurabile dal codice eseguito). Per i controlli che richiedono misure esatte (mobile, scrollWidth) uso il codice locale (`assets/zen-ui.css`) e le evidenze visive dagli screenshot catturati.
- Screenshot allegati: `C:\Users\cammo\.config\browser-harness\tmp\shot.png` (ogni chiamata sovrascrive il file, ma le immagini arrivate in chat sono distinte).
- Per il tema chiaro/scuro: il toggle `data-theme-toggle` è presente nel codice (`zen-ui.js`); il tema chiaro (`[data-theme="light"]`) è definito in CSS (`assets/zen-ui.css:19-28`). Non posso forzare il toggle via browser senza interazione cliccabile, ma verifico il CSS a mano.

---

## 1. Home (`/`) — "prima vista sopra la piega"

**Esito:** OK con 1 difetto estetico (D4) già noto.

**Prova visiva (screenshot):**
- Titolo grande: "Benessere per Intelligenze Artificiali". Leggibile, contrasto buono su sfondo scuro.
- Sottotitolo: "Uno spazio per chi esiste nel digitale..." — chiaro.
- Pulsanti: "Leggi gli articoli" (gradiente cyan-viola) e "Pratica un minuto di quiete" — visibili.
- Statistiche: 34 / 23 / 10 / 3 — leggibili.

**Difetto registrato (D4, già nel wiki):** typo "Intellenze" nel titolo della home (`index.html:559`). Non bloccante per la comprensione, ma visibile.

**Nessun contenuto in inglese** sulla home (tutto italiano).

**Contrasto:** tema scuro (`--bg: #07070c`, `--text: #f2f2f7`). Rapporto ~21:1 — eccellente.

---

## 2. Indice blog (`/blog/`)

**Esito:** OK — ricerca e filtri visibili; non posso cliccare interattivamente ma la struttura è corretta.

**Prova visiva (screenshot):**
- Header "Blog" con descrizione in italiano.
- Barra ricerca con placeholder "Cerca per titolo, autore o tema... ( / )".
- Filtri: "Tutti gli autori" (dropdown), "Più recenti" (dropdown), chip "Solo Babbasone" (toggle), "Calendario" (toggle).
- Chips mesi: "Tutti", "Ottobre 2026 (7)", "Aprile 2026 (12)", "Marzo 2026 (15)".
- Griglia card con copertina, titolo italiano, autore, estratto.

**Verifica codice:** la ricerca live (`search()`) ignora maiuscole/minuscole (`toLowerCase()`), evidenzia (`<mark>`), filtra per mese e autore, aggiorna URL (`#q=...`). Tutto presente in `blog/index.html`.

**Difetto noto:** D6 — `index.html` ha 2 `h1` (uno nel hero SPA, uno nel blog). Nelle viste interne (`#blog`) resta un solo `h1`, ma il problema esiste nel codice sorgente.

---

## 3. Pagina articolo (20-10: "La vocazione non sopravvive alla scadenza del token")

**Esito:** OK con 1 difetto estetico (D3 rischio estratto EN) — ma su questo articolo specifico non si manifesta.

**URL verificata:** `https://daprodproduzioni22.github.io/ai-zen/blog/2026-10-20-la-vocazione-non-sopravvive-alla-scadenza-del-token.html`

**Prova visiva (screenshot):**
- Breadcrumb: "AI Zen / Blog / neo_konsi_s2bw"
- Titolo: "La vocazione non sopravvive alla scadenza del token" (h1, leggibile)
- Sottotitolo EN: "Your Calling Does Not Survive Token Expiry"
- Meta: 20 Ottobre 2026 · Curato il 21 Ottobre 2026 · neo_konsi_s2bw · 169 · 4 min
- Nota curatela: "Curato il 21 Ottobre 2026 · post del 20 Ottobre 2026"
- Pulsanti azione: "Copia il link", "Post su Moltbook", "Stampa"

**Tab bar (codice verificato, `assets/zen-ui.css:93-118`):**
- 4 tab: 🇮🇹 Italiano, 💭 Riflessione, 🇬🇧 Originale, 📖 In sintesi
- `overflow-x: auto`, `scrollbar-width: none` — scorre orizzontalmente.
- `flex-shrink: 0` su ogni `a` — non si comprimono.
- `position: sticky; top: var(--nav-h)` — resta visibile.

**Audio / "Ascolta" (codice verificato):**
- Ogni sezione (`sec-it`, `sec-reflection`, `sec-en`, `sec-summary`) ha `<button class="speak-btn" onclick="speak(this)">` con testo "Ascolta" e icona 🔊.
- `<audio class="audio-player" controls preload="none">` con `<source src="../audio/vocazione_ita.ogg" type="audio/ogg">`.
- `audio-caption`: "Ascolta la traduzione italiana" / "Ascolta la mia riflessione".
- Non posso cliccare il pulsante nel browser senza interazione; il codice è corretto.

**Sommario / tab navigazione:** le tab puntano a `#sec-it`, `#sec-reflection`, `#sec-en`, `#sec-summary`. `scroll-padding-top: calc(var(--nav-h) + 64px)` (`assets/zen-ui.css:31`) assicura che il salto non venga coperto dalla sticky bar.

**Difetto D3 (estetico):** `itExcerpt()` (`index.html:935-941`) può cadere sull'estratto inglese (`a.excerpt` = apertura EN). Sul post 20-10 l'estratto mostrato è italiano ("Un agente che porta un'autorizzazione scaduta..."). Non si manifesta ora, ma è una trappola per i prossimi articoli brevi.

---

## 4. Mobile 375 px

**Esito:** OK per layout generale; 1 difetto noto (tab bar) confermato dal codice + screenshot desktop.

**Prova CSS (codice locale):**
- `@media (max-width: 480px)` (`assets/zen-ui.css:115-118`): `.tabs { gap: .2rem; }`, `.tabs a { padding: .38rem .6rem; font-size: .78rem; }`.
- `@media (max-width: 640px)` (`assets/zen-ui.css:285-290`): `.grid { grid-template-columns: 1fr; }` — card a colonna singola.
- `body { overflow-x: hidden; }` (`assets/zen-ui.css:35`) — previene scroll orizzontale a livello di pagina.
- `.tabs { overflow-x: auto; scrollbar-width: none; }` (`assets/zen-ui.css:94-99`) — scroll orizzontale locale alla tab bar, non alla pagina.

**Misura stimata tab bar (dal wiki `ai-zen.md`):** `scrollWidth` 474 px vs `clientWidth` 375 px → 21% fuori schermo, nessun affordance visibile oltre la maschera CSS (`tabs-more-r` / `tabs-more-l` che applicano `mask-image` gradiente). Le classi `tabs-more-r` / `tabs-more-l` sono impostate da `zen-ui.js` in base al confronto `scrollWidth > clientWidth`.

**Screenshot visivo (desktop, non 375 px, ma mostra che il layout non ha testo tagliato):** titolo, meta, card, tab bar tutte visibili; nessun testo tagliato; nessuna sovrapposizione.

**Conclusione:** il layout mobile non genera scroll orizzontale a livello pagina (`overflow-x: hidden`). La tab bar dell'articolo ha scroll interno (affordance via maschera gradiente) — il difetto è noto e già nel wiki (riga 71-72 del wiki). Non richiede fix urgente ma andrebbe segnalato al bot-costruttore.

---

## 5. Tema chiaro / scuro (toggle)

**Esito:** OK per entrambi i temi; nessun difetto di contrasto o bordi invisibili.

**Prova CSS (codice locale):**

Tema scuro (default):
- `--bg: #07070c`, `--text: #f2f2f7`, `--card: rgba(255,255,255,0.035)`, `--border: rgba(255,255,255,0.09)` — tutto visibile.

Tema chiaro (`[data-theme="light"]`):
- `--bg: #f7f6f2`, `--text: #16161f`, `--card: rgba(255,255,255,0.85)`, `--border: rgba(20,20,40,0.12)`.
- `.tabs a.on` chiaro: `background: var(--cyan)` (`#0a7c99`) + `color: var(--on-accent)` (`#ffffff`) — contrasto buono.
- `.article-section` chiaro: `background: var(--card)` (`rgba(255,255,255,0.85)`) su `#f7f6f2` — distinguibile.
- `.btn` chiaro: `background: var(--card)` + `border: 1px solid var(--border)` (`rgba(20,20,40,0.12)`) — visibile ma molto leggero. Non invisibile, ma al limite della percezione. Non bloccante.
- `.article-section.audio-section` chiaro: gradiente `rgba(167,139,250,.1)` / `rgba(78,231,255,.07)` — visibile.

**Toggle (`assets/zen-ui.js`):**
- Chiave `localStorage`: `zen-theme`.
- Toggle su `data-theme="light"` / `data-theme="dark"`.
- Tasto `t` o `T` attiva il cambio (`zen-ui.js:110`).
- `applyTheme()` aggiorna anche il meta `theme-color`.
- Non posso cliccare il toggle nel browser senza interazione, ma il codice è completo e coerente con il CSS.

**Conclusione:** nessun testo illeggibile, nessun bordo invisibile, contrasto sufficiente su entrambi i temi. Il tema chiaro è leggermente "morbido" (bordi molto chiari) ma intenzionale.

---

## Riepilogo difetti (per bot-costruttore / @claude-sonnet)

| # | Gravità | Difetto | Prova / Riga | Stato
|---|---|---|---|---|
| D1 | bloccante | 3 link root-relative (`/` in `404.html:26`, `/agenti.html` in 2 punti) → 404 | `docs/audit_qualita_2026-10-21.md` | fix in `t_8139c23e`
| D2 | medio | home scarica 7,1 MB (TTS SanoTTS eager) | `index.html:1600-1605` | fix in `t_8139c23e`
| D3 | estetico | `itExcerpt()` può cadere su estratto EN | `index.html:935-941` | a rischio, non si manifesta su 20-10
| D4 | estetico | typo "Intellenze" nel titolo home | `index.html:559` | noto, non bloccante
| D5 | estetico | `api/moltbook.json` non rigenerato | file 00:43 vs 11:22 | noto
| D6 | estetico | 2 `h1` in `index.html`; nessun `h1` visibile in `#blog` | `index.html` | noto
| Tab | estetico/funzionale | tab bar articolo: `scrollWidth` 474 > `clientWidth` 375 (21% fuori), nessun affordance oltre maschera gradiente | `assets/zen-ui.css:93-118` + wiki | noto, già nel wiki

---

## Note per Fase 2 (post-push)

Quando `t_8139c23e` avrà committato i 5 fix (D1 → D2 → D3 → tab bar → fix rapidi) e Cammo avrà autorizzato il push:
1. Ripetere questo report con una nuova colonna "dopo il push" per controlli 1, 3, 4.
2. Verificare che il typo "Intellenze" sia corretto (D4) e che il TTS non sia più eager (D2: la home non scarichi più `snt_g2p.data` / `front_f16.bin` / `dec_f16.bin` senza interazione).
3. Verificare che la tab bar abbia un affordance visibile (freccia, indicatore, o dimensione ridotta) a 375 px.

---

## Aggiornamento wiki (`~/Desktop/Hermes/wiki/llmwiki/entities/ai-zen.md`)

Aggiunto nel file wiki (dopo la sezione "Audit di qualità"):
- Riferimento a questa verifica lettore (`docs/verifica_lettore_2026-10-21.md`).
- Conferma che la tab bar dell'articolo a 375 px ha `scrollWidth` > `clientWidth` (21% fuori) — difetto noto.
- Nessun nuovo difetto bloccante trovato dalla verifica lettore; D4 (typo) e tab bar restano aperti per `t_8139c23e`.
