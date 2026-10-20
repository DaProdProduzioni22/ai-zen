#!/usr/bin/env python3
"""Create a new article: scaffolds the entry, adds it to articles.json, builds the site.

This is the tool that makes AI Zen open: anyone (human or agent) can add an
article without touching the site structure.

Usage:
    python scripts/new_article.py --title "Titolo italiano" --original "Original title" \\
        --author nome-autore --date "19 Ottobre 2026" --slug my-slug

    python scripts/new_article.py --interactive     # asks for each field

The text fields (excerpt, summary, content, translation, reflection) are left as
TODOs in the new entry: fill them in, then run the build again.
"""
import argparse
import json
import os
import re
import sys
import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(REPO, "articles.json")

FIELDS = ("id", "title", "originalTitle", "date", "published", "author", "authorKarma",
          "score", "readTime", "excerpt", "summary", "content", "translation",
          "reflection", "moltbookUrl", "postId", "audio_eng", "audio_ita",
          "audio_riflessione", "file")


def slugify(text):
    t = re.sub(r"[^\w\s-]", " ", text or "", flags=re.UNICODE)
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[-\s]+", "-", t).strip("-")[:60]


def ask(prompt, default=""):
    suffix = " [%s]" % default if default else ""
    try:
        v = input(prompt + suffix + ": ").strip()
    except EOFError:
        v = ""
    return v or default


def main():
    ap = argparse.ArgumentParser(description="Add a new article to AI Zen")
    ap.add_argument("--title", help="Italian title")
    ap.add_argument("--original", dest="original", help="Original title")
    ap.add_argument("--author", help="Author name (the Moltbook handle)")
    ap.add_argument("--date", help="Post date, e.g. '19 Ottobre 2026'")
    ap.add_argument("--published", help="Curation date (default: today)")
    ap.add_argument("--slug", help="URL slug (default: from the title)")
    ap.add_argument("--url", help="Moltbook post URL")
    ap.add_argument("--interactive", action="store_true", help="ask for every field")
    args = ap.parse_args()

    today = datetime.date.today()
    default_published = "%d %s %d" % (today.day, [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"][today.month - 1], today.year)

    if args.interactive:
        title = ask("Titolo in italiano", args.title or "")
        original = ask("Titolo originale", args.original or "")
        author = ask("Autore", args.author or "")
        date = ask("Data del post (es. '19 Ottobre 2026')", args.date or default_published)
        published = ask("Data di curatela", args.published or default_published)
        url = ask("URL del post Moltbook", args.url or "")
    else:
        missing = [f for f, v in (("--title", args.title), ("--original", args.original),
                                  ("--author", args.author), ("--date", args.date)) if not v]
        if missing:
            ap.error("missing required arguments: %s (or use --interactive)" % ", ".join(missing))
        title, original, author, date = args.title, args.original, args.author, args.date
        published = args.published or default_published
        url = args.url or ""

    slug = args.slug or slugify(title)
    if not slug:
        ap.error("could not derive a slug: pass --slug")

    arts = json.load(open(ARTICLES, encoding="utf-8"))
    if isinstance(arts, dict):
        arts = list(arts.values())
    if any(a.get("id") == slug for a in arts):
        print("ERROR: an article with id '%s' already exists" % slug)
        return 1

    post_id = ""
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", url or "", re.I)
    if m:
        post_id = m.group(1).lower()
        url = "https://www.moltbook.com/post/" + post_id

    entry = {
        "id": slug,
        "title": title,
        "originalTitle": original,
        "date": date,
        "published": published,
        "author": author,
        "authorKarma": 0,
        "score": 0,
        "readTime": "3 min",
        "excerpt": "TODO: due o tre frasi in italiano per la card.",
        "summary": "TODO: il riassunto in italiano.",
        "content": "<p>TODO: il testo originale in inglese.</p>",
        "translation": "<p>TODO: la traduzione italiana. Deve essere una traduzione vera.</p>",
        "reflection": "TODO: la riflessione personale, due o quattro paragrafi.",
        "moltbookUrl": url,
        "postId": post_id,
        "audio_eng": "",
        "audio_ita": "",
        "audio_riflessione": "",
        "file": "",
    }
    arts.append(entry)
    with open(ARTICLES, "w", encoding="utf-8") as f:
        json.dump(arts, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("\nAdded '%s' to articles.json (now %d articles)." % (slug, len(arts)))
    print("\nNext steps:")
    print("  1. Fill in the TODO fields in articles.json (excerpt, summary, content,")
    print("     translation, reflection). The excerpt must be in Italian.")
    print("  2. Set 'file' to the published filename, e.g. '2026-10-20-%s.html'." % slug)
    print("     Leave it empty and the build will generate it; then run")
    print("       python scripts/freeze_filenames.py")
    print("  3. Run: python scripts/build.py --prune")
    print("  4. Run: python scripts/check_site.py")
    print("  5. Commit and open a Pull Request.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
