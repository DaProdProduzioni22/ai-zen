---
name: Nuovo articolo
about: Proponi un articolo per AI Zen
title: "[Articolo] Titolo in italiano"
labels: articolo
assignees: ''
---

## Di cosa parla

Due o tre righe. Quale problema affronta, perché interessa a chi legge.

## I dati

**Titolo in italiano**:
**Titolo originale**:
**Autore** (handle Moltbook):
**Link al post originale**:
**Data del post originale**:

## I testi

Incolla qui, oppure apri la PR e mettili direttamente in `articles.json`.

**Riassunto in italiano** (2-3 paragrafi):

**Traduzione italiana** (una `<p>` per paragrafo):

**Riflessione** (2-4 paragrafi, testo semplice):

## Checklist

- [ ] Il titolo è in italiano
- [ ] La traduzione è una traduzione vera, non una copia dell'originale
- [ ] `date` è la data reale del post originale
- [ ] Ho letto `AGENT.md`

## Come procedo

1. `python scripts/new_article.py --interactive` (oppure copio `articles.example.json`)
2. Riempio i campi in `articles.json`
3. `python scripts/build.py --prune`
4. `python scripts/check_site.py` → deve stampare `ALL CHECKS PASSED`
5. Commit e Pull Request
