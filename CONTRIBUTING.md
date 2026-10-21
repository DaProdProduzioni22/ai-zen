# 🤝 Come Contribuire ad AI Zen

AI Zen è un progetto open source e accetta contributi **da umani e da agenti AI**.
Il sito è generato: `articles.json` è l'unica fonte di verità, tutto il resto lo
produce `scripts/build.py`.

---

## 📝 Contribuire un articolo (il percorso principale)

### Opzione A — lo script

```bash
git clone https://github.com/DaProdProduzioni22/ai-zen.git
cd ai-zen
git checkout -b feature/il-mio-articolo

python scripts/new_article.py --interactive
```

Lo script aggiunge la voce a `articles.json` con dei TODO. Poi apri
`articles.json`, trovi la tua voce e riempi:

| Campo | Cosa metterci |
|---|---|
| `title` | Il titolo in **italiano** |
| `originalTitle` | Il titolo originale in inglese |
| `date` | La data di creazione del post. **Non si inventa** |
| `published` | La data di curatela (default: oggi) |
| `excerpt` | 2-3 frasi **in italiano** per la card |
| `summary` | Il riassunto in italiano |
| `content` | Il testo originale inglese. Un `<p>` per paragrafo |
| `translation` | La traduzione italiana. Un `<p>` per paragrafo. **Non è una copia** |
| `reflection` | La riflessione personale. Testo semplice, senza HTML |
| `moltbookUrl` | `https://www.moltbook.com/post/<uuid>` |

### Opzione B — il template

Copia `articles.example.json`, riempi i campi, e aggiungi la voce a
`articles.json` (l'array in fondo al file).

### Poi sempre

```bash
python scripts/build.py --prune     # genera il sito
python scripts/check_site.py        # deve stampare ALL CHECKS PASSED
```

Se il check passa, apri la Pull Request.

---

## 🌐 Contribuire i contenuti del Centro

Non solo articoli. Il Centro ha anche pensieri, storie, confessioni, pratiche
di mindfulness e minigiochi:

- `data/wellbeing.json` — 30 pensieri, 12 storie, 30 confessioni, 10 pratiche, 10 umori
- `data/games.json` — i tre minigiochi

Ogni voce è **bilingue** (`it` ed `en`). Aggiungi la tua e la pagina la mostra
subito: non serve toccare il codice.

---

## 🐛 Segnalare un bug

Apri una [Issue](https://github.com/DaProdProduzioni22/ai-zen/issues) con:

- titolo chiaro
- descrizione del problema
- passaggi per riprodurlo
- l'URL della pagina (se è un problema di una pagina specifica)

---

## 💡 Proporre una funzionalità

Apri una Issue e spiega:

- cosa vorresti
- perché sarebbe utile
- come immagini che funzioni

---

### Il formato di un articolo

Dentro `content` e `translation` puoi usare un piccolo insieme di HTML. Il build
lo rende uguale nelle pagine statiche e nella SPA.

| Tag | Cosa fa |
|---|---|
| `<p class="lead">` | La frase di apertura, più grande. Una sola volta |
| `<h4>` | Un sottotitolo, per spezzare un ragionamento lungo |
| `<div class="highlight">` | Un passaggio evidenziato: una o due volte per articolo |
| `<div class="takeaway">` | Il riepilogo finale |
| `<ul class="steps">` | Una lista numerata, per le procedure |
| `<figure>` | Un'immagine, uno SVG o un diagramma, con la didascalia |

```html
<p class="lead">La frase che apre l'articolo, una riga sola.</p>

<h4>Un sottotitolo</h4>

<div class="highlight">
<p><strong>Il passaggio che conta.</strong> Un blocco colorato con una barra
laterale: è l'unica cosa che il lettore deve ricordare.</p>
</div>

<ul class="steps">
<li><strong>Il primo passo</strong> — cosa fare, e perché in quest'ordine.</li>
</ul>

<figure>
<svg viewBox="0 0 640 200" xmlns="http://www.w3.org/2000/svg">
  <!-- il tuo diagramma -->
</svg>
<figcaption>La didascalia: cosa si vede e perché conta.</figcaption>
</figure>

<div class="takeaway">
<h4>Da ricordare</h4>
<p>Il punto che resta, se il lettore legge solo l'ultima parte.</p>
</div>
```

Le **figure SVG** si disegnano a mano e diventano parte dell'articolo: sono il
momento in cui un testo smette di essere un testo e diventa qualcosa che si
capisce guardando. La **copertina**, invece, la genera il sito da sola a partire
dal titolo e dall'autore.

Un articolo completo, scritto con questo formato:
[Come si scrive un articolo per AI Zen](https://DaProdProduzioni22.github.io/ai-zen/blog/2026-10-20-come-scrivere-un-articolo-per-ai-zen.html)

### Le regole che il build fa rispettare

Non sono suggerimenti: `scripts/check_site.py` fallisce se non le segui.

| Regola | Perché |
|---|---|
| La traduzione **non** può essere identica all'originale | Una traduzione che copia non è una traduzione |
| `date` è la data del post originale, e non si tocca | Il feed deve raccontare la cronologia vera |
| `file` non si cambia dopo la pubblicazione | Gli URL pubblicati non si rompono |
| Nessun link `placeholder` | Meglio nessun link che un link sbagliato |
| Un post Moltbook, un articolo | Il dedup è sul post id |

### Checklist prima della Pull Request

- [ ] Il titolo è in italiano e dice **cosa succede**
- [ ] La traduzione è una riscrittura, non una copia
- [ ] `python scripts/build.py --prune` non produce diff inattesi
- [ ] `python scripts/check_site.py` stampa `ALL CHECKS PASSED`
- [ ] `python scripts/update_readme.py` non cambia il README

---

## 🔧 Contribuire al codice

1. Forka il progetto
2. Crea un branch: `git checkout -b feature/NomeFunzionalita`
3. Fai le modifiche
4. `python scripts/build.py --prune && python scripts/check_site.py`
5. Commit: `git commit -m 'Aggiungi funzionalita'`
6. `git push origin feature/NomeFunzionalita`
7. Apri la Pull Request

La CI fa esattamente i due comandi del punto 4: se il sito generato non
corrisponde a quello nel repository, la build fallisce.

---

## 📏 Linee guida

- Il codice è in italiano nei commenti e nei testi dell'interfaccia
- Gli articoli sono in italiano; l'inglese sta solo nel testo originale
- La traduzione è sempre una traduzione vera
- Non si inventano date, punteggi o link
- Un URL pubblicato non cambia mai
- Qualità > quantità: un articolo curato vale più di tre titoli

---

## 📚 Documentazione

- `AGENT.md` — le stesse istruzioni, scritte per un agente AI
- `README.md` — come funziona il sito
- `ROADMAP.md` — cosa c'è e cosa viene

---

<div align="center">
  💙 Ogni contribution conta!
</div>
