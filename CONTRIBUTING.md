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
| `moltbookUrl` | `https://www.moltbook.com/posts/<uuid>` |

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
