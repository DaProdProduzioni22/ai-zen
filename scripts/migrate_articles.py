#!/usr/bin/env python3
"""One-off migration: bring articles.json up to the final schema.

What it fixes (all verified by audit):
  1. moltbookUrl normalised to a single canonical form
     (https://www.moltbook.com/posts/<uuid>) so the fetch cron can dedup.
     The stored URLs came in 5 different shapes, 25 of which never matched
     the fetch's post_url() -> the cron could republish existing articles.
  2. translation recovered from the blog page for the watchman article
     (it was empty in JSON, present on the page).
  3. content completed for the compacting article (JSON held 39% of the page text).
  4. note set consistently on every article whose published != date.
  5. upvotes/comments filled from `score` for every article (was 1/33).
  6. The duplicate (ai-zen-017 vs the-most-dangerous-state-...-idle) is NOT
     removed here: they are two different texts sharing one Moltbook URL.
     The script reports it; the decision is taken separately.
  7. Placeholder Moltbook URLs are reported (cannot be recovered: those
     posts are not reachable through the search endpoint).

Run once, from the repo root:  python scripts/migrate_articles.py
"""
import json
import os
import re
import html

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(REPO, "articles.json")
BLOG = os.path.join(REPO, "blog")

CANONICAL_HOST = "https://www.moltbook.com/posts/"


def normalise_moltbook_url(url):
    """Return (canonical_url, post_id) for any known URL shape, or (None, None)."""
    if not url:
        return None, None
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", url, re.I)
    if not m:
        return None, None
    return CANONICAL_HOST + m.group(1).lower(), m.group(1).lower()


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def page_blocks(page_path):
    """Extract the three text blocks from a blog page, by anchor id."""
    txt = open(page_path, encoding="utf-8").read()
    out = {}
    for key, anchor in (("content", "english-content"),
                        ("translation", "italian-content"),
                        ("reflection", "reflection-content")):
        m = re.search(r'id="%s"[^>]*>(.*?)</div>' % anchor, txt, re.S)
        if m:
            out[key] = m.group(1).strip()
    if not out:
        # legacy shape: <section class="article-section"><h2>label</h2>body</section>
        for key, label in (("content", "Testo Originale"),
                           ("translation", "Traduzione"),
                           ("reflection", "Riflessione")):
            m = re.search(r"<h2>[^<]*%s[^<]*</h2>(.*?)</section>" % label, txt, re.S)
            if m:
                out[key] = m.group(1).strip()
    return out


def main():
    arts = json.load(open(ARTICLES, encoding="utf-8"))
    if isinstance(arts, dict):
        arts = list(arts.values())

    files = {re.sub(r"^\d{4}-\d{2}-\d{2}-", "", f[:-5]): os.path.join(BLOG, f)
             for f in os.listdir(BLOG) if f.endswith(".html") and f != "index.html"}

    stats = {"url_fixed": 0, "translation_fixed": 0, "content_fixed": 0,
             "note_fixed": 0, "meta_fixed": 0, "placeholder": 0, "reflow": 0}
    placeholders = []

    for a in arts:
        slug = a.get("slug", "")

        # 1. canonical Moltbook URL
        canon, post_id = normalise_moltbook_url(a.get("moltbookUrl", ""))
        if canon is None:
            placeholders.append((a.get("id"), a.get("moltbookUrl")))
            a["moltbookUrl"] = ""  # honest: no known source link
        elif a.get("moltbookUrl") != canon:
            a["moltbookUrl"] = canon
            stats["url_fixed"] += 1
        a["postId"] = post_id or ""

        # 2/3. recover text from the page when JSON is short or empty
        page = files.get(slug)
        if page and os.path.exists(page):
            blocks = page_blocks(page)
            for key in ("content", "translation"):
                cur = (a.get(key) or "").strip()
                want = blocks.get(key, "")
                if not want:
                    continue
                if not cur:
                    a[key] = want
                    stats["translation_fixed" if key == "translation" else "content_fixed"] += 1
                else:
                    cur_txt, want_txt = strip_tags(cur), strip_tags(want)
                    # same text but one is HTML and the other is plain -> normalise to HTML
                    if cur_txt == want_txt and cur != want:
                        a[key] = want
                        stats["reflow"] += 1
                    elif want_txt.startswith(cur_txt[:120]) and len(want_txt) > len(cur_txt) * 1.2:
                        a[key] = want
                        stats["translation_fixed" if key == "translation" else "content_fixed"] += 1

        # 4. note: present iff published != date
        date, published = a.get("date", ""), a.get("published", "") or a.get("date", "")
        a["published"] = published
        if published and published != date:
            want_note = "Curato il %s · post del %s" % (published, date)
            if a.get("note") != want_note:
                a["note"] = want_note
                stats["note_fixed"] += 1
        elif a.get("note"):
            a.pop("note")

        # 5. upvotes/comments: `score` is the Moltbook score; keep a single source
        a["upvotes"] = a.get("score", 0)
        a["comments"] = a.get("comments", 0)
        stats["meta_fixed"] += 1

    with open(ARTICLES, "w", encoding="utf-8") as f:
        json.dump(arts, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("migrated %d articles" % len(arts))
    for k, v in stats.items():
        print("  %-18s %d" % (k, v))
    if placeholders:
        print("\nplaceholder Moltbook URL (no source link):")
        for pid, url in placeholders:
            print("   %-52s %s" % (pid[:52], url))

    # duplicate detection on the canonical URL
    seen = {}
    for a in arts:
        seen.setdefault(a.get("moltbookUrl", ""), []).append(a["id"])
    print("\narticles sharing one Moltbook URL:")
    for url, ids in seen.items():
        if url and len(ids) > 1:
            print("  ", url)
            for i in ids:
                print("      ", i)


if __name__ == "__main__":
    main()
