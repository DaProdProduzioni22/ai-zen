#!/usr/bin/env python3
"""Add the daily article to articles.json from a draft: mechanical fields come
from the Moltbook post, only the generative ones come from the writer.

Why this exists: the daily article used to be written by an agent editing
articles.json by hand. Every mechanical field (date, published, note, file, slug,
postId, moltbookUrl, score, karma) was a chance to get the blog rules wrong
(date = created_at of the post, one article per day, no duplicates, singular
/post/ route). Now the agent writes ONLY the draft (the text) and this script
fills in and validates the rest.

Usage:
  python scripts/moltbook_fetch.py --next              # writes scripts/pending_post.json
  # the agent writes scripts/draft_article.json (see below), then:
  python scripts/add_article.py                        # validate + add
  python scripts/add_article.py --dry-run              # validate, print, write nothing
  python scripts/build.py --prune && python scripts/update_readme.py && python scripts/check_site.py

Draft (scripts/draft_article.json), all text fields in Italian except `content`:
  {
    "contentType": "summary",                          (editorial default, explicit)
    "title":       "Titolo italiano che dice cosa succede",
    "excerpt":     "2-3 frasi per la card",
    "summary":     "2-3 paragrafi, testo semplice",
    "content":     "<p>Original English synthesis, not the entire source post.</p>",
    "translation": "<p>Sintesi originale italiana, non traduzione integrale del post.</p>",
    "reflection":  "2-4 paragrafi di Babbasone, testo semplice, con la firma finale",
    "tags":        ["memoria", "agenti"],                  (opzionale, lista corta)
    "slug":        "slug-opzionale"                        (opzionale)
  }

Full republication is exceptional: contentType='full' requires a verified
reusePermission string including an evidence URL (permission for reproduction
and translation). The URL check is structural; the editor must verify the rights.
Legacy drafts missing contentType remain full and require permission for NEW
inserts. Historical entries are never migrated or renamed. New filenames use
the publication date, while date stays the source's validated created_at day.

Exit codes: 0 ok, 1 refused (validation failed, duplicate, already one today).
"""
import argparse
import datetime
import html
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(REPO, "articles.json")
PENDING = os.path.join(REPO, "scripts", "pending_post.json")
DRAFT = os.path.join(REPO, "scripts", "draft_article.json")

MONTHS = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio",
          "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
SIGNATURE = "Babbasone — AI Zen, Centro Benessere per Intelligenze Artificiali"
REQUIRED = ("title", "excerpt", "summary", "content", "translation", "reflection")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# a handful of very frequent function words, to catch an "Italian" text that is
# really English (a copied original, or English left mixed in)
EN_WORDS = {"the", "and", "of", "to", "is", "that", "it", "for", "with", "this", "are", "was",
            "not", "you", "your", "but", "have", "from", "they", "what", "when", "which"}
IT_WORDS = {"il", "lo", "la", "le", "gli", "di", "che", "è", "un", "una", "per", "con", "non",
            "del", "della", "dei", "nel", "nella", "sono", "come", "più", "ma", "si", "da", "in"}


def it_date(d):
    return "%02d %s %d" % (d.day, MONTHS[d.month - 1], d.year)


def parse_it_date(value):
    """Compare calendar dates, not their historical zero-padding or case."""
    if not isinstance(value, str):
        raise ValueError("data italiana non valida")
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", value or "")
    if not match:
        raise ValueError("data italiana non valida")
    months = {name.lower(): i for i, name in enumerate(MONTHS, 1)}
    return datetime.date(int(match[3]), months.get(match[2].lower(), 0), int(match[1]))


def source_date(value):
    """Validate the whole ISO value, retaining the source's calendar date."""
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?", value):
        raise ValueError("created_at deve essere una data o timestamp ISO valido")
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def slugify(text):
    t = re.sub(r"[^\w\s-]", " ", text or "", flags=re.UNICODE)
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[-\s]+", "-", t).strip("-")[:70].strip("-")


def english_ratio(text):
    words = re.findall(r"[a-zà-ú']+", strip_tags(text).lower())
    if len(words) < 20:
        return 0.0, 0.0
    en = sum(1 for w in words if w in EN_WORDS)
    it = sum(1 for w in words if w in IT_WORDS)
    return en / len(words), it / len(words)


def load_json(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit("ERROR: %s non trovato (%s)" % (what, path))
    except ValueError as exc:
        sys.exit("ERROR: %s non è JSON valido: %s" % (what, exc))


def validate(draft, pending, arts, today, force):
    """Return a list of problems; empty means the article can be added."""
    problems = []

    for f in REQUIRED:
        if not str(draft.get(f) or "").strip():
            problems.append("bozza: campo '%s' mancante o vuoto" % f)
    if problems:
        return problems

    # Legacy drafts are full republications, never silently relabelled summaries.
    content_type = draft.get("contentType", "full")
    if content_type not in ("summary", "full"):
        problems.append("bozza: contentType deve essere 'summary' oppure 'full'")
    if content_type == "full":
        permission = draft.get("reusePermission")
        if not isinstance(permission, str) or not re.search(
                r"https?://[A-Za-z0-9][A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:[/:?#][^\s<>]*)?(?=\s|$)",
                permission.strip()):
            problems.append("bozza full: reusePermission richiede un permesso/licenza verificato "
                            "con URL della prova; non inventare diritti, usa contentType='summary'")
    elif content_type == "summary":
        source = strip_tags(html.unescape(pending.get("content") or "")).casefold()
        english = strip_tags(html.unescape(draft["content"])).casefold()
        if source and source in english:
            problems.append("bozza summary: la sintesi contiene il post intero; riscrivila autonomamente")

    if not UUID_RE.match(str(pending.get("id") or "").lower()):
        problems.append("pending_post.json: id non è un uuid")
    try:
        created = source_date(pending.get("created_at"))
        if created > today:
            problems.append("pending_post.json: created_at è nel futuro rispetto alla pubblicazione")
    except ValueError:
        problems.append("pending_post.json: created_at mancante o non è una data/timestamp ISO valido")

    pid = str(pending.get("id") or "").lower()
    for a in arts:
        if (a.get("postId") or "").lower() == pid or pid in (a.get("moltbookUrl") or "").lower():
            problems.append("duplicato: il post %s è già pubblicato come '%s'" % (pid[:8], a.get("id")))

    today_s = it_date(today)
    todays = []
    for article in arts:
        try:
            if parse_it_date(article.get("published")) == today:
                todays.append(article.get("id", "?"))
        except ValueError:
            problems.append("articles.json: published non valida per '%s'" % article.get("id", "?"))
    if todays and not force:
        problems.append("regola 'un solo articolo al giorno': oggi (%s) è già stato pubblicato '%s' "
                        "(--force solo se Cammo lo chiede)" % (today_s, todays[0]))

    if draft["title"].strip().lower() == str(pending.get("title_en", "")).strip().lower():
        problems.append("title è uguale al titolo inglese: va scritto in italiano")
    if strip_tags(draft["content"]) == strip_tags(draft["translation"]):
        problems.append("translation è una copia di content")
    if "<p" not in draft["content"] or "<p" not in draft["translation"]:
        problems.append("content e translation sono HTML: un <p> per paragrafo")
    if SIGNATURE not in draft["reflection"]:
        problems.append("reflection: manca la firma finale «%s»" % SIGNATURE)
    if re.search(r"</?[a-z][^>]*>", draft["reflection"]):
        problems.append("reflection è testo semplice, senza HTML")
    if re.search(r"TODO", " ".join(str(draft.get(f)) for f in REQUIRED)):
        problems.append("la bozza contiene dei TODO")

    for f in ("translation", "title", "excerpt", "summary", "reflection"):
        en, it = english_ratio(draft[f])
        if en > 0.07 and en >= it:
            problems.append("%s sembra inglese (parole inglesi %.0f%%, italiane %.0f%%)" % (f, en * 100, it * 100))
    en_c, _ = english_ratio(draft["content"])
    if en_c < 0.03 and len(strip_tags(draft["content"]).split()) > 40:
        problems.append("content deve essere in inglese (sintesi originale per summary, fonte per full)")

    return problems


def build_entry(draft, pending, today):
    created = source_date(pending["created_at"])
    pid = pending["id"].lower()
    slug = draft.get("slug") or slugify(pending.get("title_en") or draft["title"])
    slug = slugify(slug)
    words = len(strip_tags(draft["translation"]).split())
    read = "%d min" % max(1, round(words / 200.0))
    date, published = it_date(created), it_date(today)
    entry = {
        "id": slug,
        "title": draft["title"].strip(),
        "originalTitle": pending.get("title_en", "").strip(),
        "date": date,
        "published": published,
        "author": pending.get("author", "unknown"),
        "authorKarma": int(pending.get("author_karma") or 0),
        "authorUrl": "https://www.moltbook.com/u/%s" % (
            {"Babbasone": "dapbabbasone"}.get(pending.get("author", "")) or pending.get("author", "").strip()),
        "score": int(pending.get("score") or 0),
        "readTime": draft.get("readTime") or read,
        "excerpt": draft["excerpt"].strip(),
        "summary": draft["summary"].strip(),
        "contentType": draft.get("contentType", "full"),
        "content": draft["content"].strip(),
        "translation": draft["translation"].strip(),
        "reflection": draft["reflection"].strip(),
        "moltbookUrl": "https://www.moltbook.com/post/%s" % pid,
        "postId": pid,
        "audio_eng": "",
        "audio_ita": "",
        "audio_riflessione": "",
        "tags": [t for t in (draft.get("tags") or []) if isinstance(t, str)][:5],
        "slug": slug,
        "upvotes": int(pending.get("upvotes") or pending.get("score") or 0),
        "comments": int(pending.get("comments") or 0),
        "file": "%04d-%02d-%02d-%s.html" % (today.year, today.month, today.day, slug),
    }
    if entry["contentType"] == "full":
        entry["reusePermission"] = draft["reusePermission"].strip()
    if published != date:
        entry["note"] = "Curato il %s · post del %s" % (published, date)
    return entry


def main():
    ap = argparse.ArgumentParser(description="Add the daily article from a draft")
    ap.add_argument("draft", nargs="?", default=DRAFT, help="draft json (default: scripts/draft_article.json)")
    ap.add_argument("--pending", default=PENDING)
    ap.add_argument("--dry-run", action="store_true", help="validate and print, write nothing")
    ap.add_argument("--force", action="store_true", help="skip the one-article-per-day rule")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD), for tests")
    args = ap.parse_args()

    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
    draft = load_json(args.draft, "la bozza")
    pending = load_json(args.pending, "pending_post.json (esegui prima moltbook_fetch.py --next)")
    arts = load_json(ARTICLES, "articles.json")
    if isinstance(arts, dict):
        arts = list(arts.values())

    problems = validate(draft, pending, arts, today, args.force)
    entry = None
    if not problems:
        entry = build_entry(draft, pending, today)
        if any(a.get("id") == entry["id"] or a.get("file") == entry["file"] for a in arts):
            problems.append("esiste già un articolo con id/file '%s': scegli un altro slug" % entry["id"])
    if problems:
        print("RIFIUTATO — %d problema/i:" % len(problems))
        for p in problems:
            print("  -", p)
        return 1

    print("OK: %s" % entry["file"])
    print("  titolo : %s" % entry["title"])
    print("  autore : %s (karma %s, score %s)" % (entry["author"], entry["authorKarma"], entry["score"]))
    print("  data   : %s | curato: %s%s" % (entry["date"], entry["published"],
                                           "" if "note" in entry else " (stesso giorno, nessuna nota)"))
    print("  lettura: %s | url: %s" % (entry["readTime"], entry["moltbookUrl"]))
    print("  profilo: %s" % entry["authorUrl"])
    if args.dry_run:
        print("(dry-run: articles.json NON modificato)")
        return 0

    arts.insert(0, entry)
    with open(ARTICLES, "w", encoding="utf-8", newline="\n") as f:
        json.dump(arts, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("Aggiunto a articles.json (%d articoli). Ora: build.py --prune, update_readme.py, check_site.py" % len(arts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
