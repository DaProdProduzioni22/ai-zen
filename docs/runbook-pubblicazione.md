# Runbook di pubblicazione — AI Zen

Questo runbook descrive la pipeline presente nel repository. `articles.json` è la fonte unica degli articoli; le pagine e i feed generati non si modificano a mano. I segreti Moltbook restano nel `.env` del profilo Hermes che esegue il job, mai nel repository o nella bozza.

## Articolo del blog

1. **Preflight.** Nel repo `DaProdProduzioni22/ai-zen`, controlla `git status --short --branch`: lavora solo con albero pulito. Verifica che l'account GitHub attivo sia `cammo22` e che `origin` sia `https://github.com/DaProdProduzioni22/ai-zen.git`. Aggiorna `main` con `git fetch origin`, `git switch main`, `git pull --ff-only origin main`; crea un branch `<operatore>/articolo-AAAA-MM-GG` (per il cron delle 08:00 `haiku/articolo-AAAA-MM-GG`). Se un controllo fallisce, fermati senza reset o force.
2. **Selezione della fonte.** `python scripts/moltbook_fetch.py --next` legge il feed hot autenticato, esclude post già usati, post propri, spam/deleted e contenuti sotto 400 caratteri, scarica il testo intero quando la lista è troncata e scrive `scripts/pending_post.json` (ignorato da Git). `NONE` è un esito valido: non inventare un articolo e fermati.
3. **Bozza.** Segui `AGENT.md` e `scripts/prompts/fetch_article.txt`. Scrivi solo `scripts/draft_article.json`: titolo, estratto, riassunto e riflessione in italiano; `content` originale in inglese e `translation` italiana reale, entrambi HTML. Non inventare dati meccanici: `add_article.py` calcola date, slug, nome file, URL/id del post e statistiche. La riflessione richiede la firma esatta descritta in `AGENT.md`.
4. **Validazione e generazione.** Esegui in ordine:

   ```bash
   python scripts/add_article.py --dry-run
   python scripts/add_article.py
   python scripts/build.py --prune
   python scripts/update_readme.py
   python scripts/check_site.py
   ```

   Se il dry-run rifiuta la bozza, correggi la bozza o fermati: mai usare `--force` senza richiesta esplicita. Il build genera `blog/<file>.html`, `blog/index.html`, `feed.xml`, `api/feed.json`, `sitemap.xml`, `404.html` e aggiorna `api/moltbook.json` solo nei flag `publishedHere`. `check_site.py` deve terminare con `ALL CHECKS PASSED`.
5. **Revisione e deploy.** Controlla `git diff --check`, `git status` e `git diff` completo; non includere `.env`, chiavi, bozze, credenziali o backup. Esegui `git add` solo sui file attesi, commit con messaggio `Blog: <titolo>`, poi ricontrolla account, repository, diff e segreti prima di `git push -u origin HEAD`. Apri una PR verso `main` e controlla `gh pr checks <numero> --watch`. Non pushare direttamente su `main` né fare merge autonomamente: GitHub Pages è configurato dalla root del branch `main`, quindi l'articolo diventa live solo dopo il merge autorizzato. Dopo il deploy, verifica HTTP 200 sulla pagina dell'articolo, sul feed e sul link pubblico Moltbook.

## Moltbook

- I fetcher del repo usano `MOLTBOOK_API_KEY` dall'ambiente del profilo Hermes attivo oppure dal `.env` indicato da `HERMES_HOME` se il processo non ha ancora ricaricato l'ambiente. `scripts/moltbook_auth.py` legge solo quel profilo, senza fallback a vecchi file di credenziali. `scripts/moltbook_fetch.py --next` legge il feed; `scripts/fetch_moltbook_feed.py` aggiorna lo snapshot pubblico in `api/moltbook.json`. Nessuno dei due crea un post Moltbook.
- Per creare un post, l'API ufficiale usa `POST https://www.moltbook.com/api/v1/posts`, autenticazione `Authorization: Bearer <MOLTBOOK_API_KEY>` e JSON con `submolt_name` (obbligatorio, ad esempio `general`), `title` (obbligatorio, massimo 300 caratteri) e `content` (facoltativo, massimo 40.000). Non inviare la chiave a host diversi da `www.moltbook.com`; evitare redirect senza `www`. Non stampare la chiave né inserirla in file del repo, prompt o log. Riferimento: [skill ufficiale Moltbook](https://www.moltbook.com/skill.md).
- Dopo un POST, conserva l'id restituito e verifica il contenuto con `GET /api/v1/posts/<id>` e l'URL pubblico `https://www.moltbook.com/post/<id>` (singolare). Se lo stato è `pending` senza challenge, è già stato creato: non ripubblicare. Se la risposta include una challenge, non indovinare; segui la procedura di verifica ufficiale disponibile al profilo, oppure fermati. Non ripetere un POST per timeout senza prima controllare se il primo è riuscito.
- Per commentare: `POST /api/v1/posts/<id>/comments`; il body contiene `content` e, solo per una risposta, `parent_id` dell'elemento genitore. Verifica via endpoint comments del post e considera `replies` annidate. La rotta pubblica è `/post/<id>`; `/posts/<id>` è solo API. Non mettere `../` nei contenuti: il WAF può rifiutarli.

## Credenziali e coordinamento

La chiave API va in `MOLTBOOK_API_KEY` nel `.env` del profilo che esegue il job (Luna e Haiku hanno profili distinti). Il `.env` non va committato. Il file sorgente in chiaro `moltbook_creds.txt` è stato usato solo per migrare l'API key nei due profili; la copia sorgente va cancellata dal proprietario dopo averne verificato la migrazione.

Il cron `haiku-aizen-articolo-0800` (profilo `claude-haiku`, `0 8 * * *`, ora locale `Europe/Rome`) prepara una PR giornaliera; non esegue il merge. Il cron di controllo Haiku ogni quattro ore dovrebbe essere sfalsato al minuto :30 (`30 */4 * * *`) per ridurre le collisioni col job delle 08:00. Se un altro job ha il repo aperto o sporco, fermati e riprendi al giro successivo.
