# scripts/legacy

Script **una-tantum** usati per riparare e migrare il modello dati (ottobre 2026).
Nessun cron, nessuna CI e nessun altro script li chiama più. Restano qui, e non
cancellati, perché documentano come si è arrivati a `articles.json` com'è oggi.

| Script | Cosa ha fatto |
|---|---|
| `migrate_articles.py` | portò `articles.json` allo schema finale (`moltbookUrl` canonico, traduzione recuperata) |
| `fix_blog_data.py` | aggiunse `slug` e `published` (data di curatela) a ogni articolo |
| `normalize_content.py` | normalizzò l'HTML di `content` dell'articolo del watchman (testo misto a tag) |
| `recover_moltbook_ids.py` | applicò i `postId` Moltbook recuperati e tolse un articolo duplicato |

**Non rilanciarli** sull'`articles.json` attuale: assumono la forma di quello di allora
e calcolano i percorsi da `scripts/`, non da `scripts/legacy/`.
