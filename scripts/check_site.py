#!/usr/bin/env python3
"""Self-check for the AI Zen site: run after every change to articles.json or build.py.

Verifies the invariants that were silently broken before:
  - articles.json and the generated blog pages agree (one page per article)
  - no article text is empty or truncated
  - no leftover placeholder Moltbook URLs, no duplicate post ids
  - the feeds contain every article
  - the generated pages are valid enough (no unescaped tags leaking as text)

Usage:  python scripts/check_site.py
Exit code 0 = all good.
"""
import json
import os
import re
import sys
import html

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(REPO, "articles.json")
BLOG = os.path.join(REPO, "blog")
AUDIO = os.path.join(REPO, "audio")

problems = []


def fail(msg):
    problems.append(msg)
    print("  FAIL  " + msg)


def ok(msg):
    print("  PASS  " + msg)


def strip_tags(s):
    s = re.sub(r"<br\s*/?>", " ", s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def main():
    data = json.load(open(ARTICLES, encoding="utf-8"))
    arts = data if isinstance(data, list) else list(data.values())

    print("\n=== articles.json ===")
    if arts:
        ok("%d articles loaded" % len(arts))
    else:
        fail("articles.json is empty")
        return 1

    # unique ids
    ids = [a.get("id", "") for a in arts]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        fail("duplicate ids: %s" % dupes)
    else:
        ok("all ids unique")

    # required fields. `score` and `authorKarma` may legitimately be 0 (an
    # original article, not a curated Moltbook post), so only None/missing counts.
    required = ("id", "title", "originalTitle", "date", "published", "author",
                "readTime", "excerpt", "summary", "reflection",
                "content", "translation", "slug", "file")
    missing = [(a.get("id"), f) for a in arts for f in required if not a.get(f)]
    if missing:
        for aid, f in missing:
            fail("%s: missing/empty '%s'" % (aid, f))
    else:
        ok("all required fields present on every article")

    for a in arts:
        for f in ("score", "authorKarma"):
            if a.get(f) is None:
                fail("%s: '%s' is null (0 is a valid value)" % (a.get("id"), f))

    # The Moltbook link may be empty when the original post could not be
    # retrieved; that is documented, not a bug. A placeholder URL is a bug.
    no_source = [a["id"] for a in arts if not a.get("moltbookUrl")]
    if no_source:
        print("  WARN  %d article(s) have no Moltbook source link (not retrievable): %s"
              % (len(no_source), no_source))
    else:
        ok("every article links to its Moltbook source")

    # translation must not be a copy of the english content
    copies = [a["id"] for a in arts
              if strip_tags(a.get("content")) and strip_tags(a.get("content")) == strip_tags(a.get("translation"))]
    if copies:
        fail("translation is a copy of the original: %s" % copies)
    else:
        ok("no article has the translation copied from the original")

    # placeholder / broken Moltbook URLs
    bad_urls = [a["id"] for a in arts
                if a.get("moltbookUrl") and ("placeholder" in a["moltbookUrl"]
                                             or not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}", a["moltbookUrl"]))]
    if bad_urls:
        fail("placeholder Moltbook URL: %s" % bad_urls)
    else:
        ok("no placeholder Moltbook URLs")

    # duplicate Moltbook post ids (the same post published twice)
    post_ids = [a.get("postId") for a in arts if a.get("postId")]
    dup_posts = {p for p in post_ids if post_ids.count(p) > 1}
    if dup_posts:
        fail("the same Moltbook post is published twice: %s" % dup_posts)
    else:
        ok("no Moltbook post published twice")

    # dates
    MON = {"Gennaio": 1, "Febbraio": 2, "Marzo": 3, "Aprile": 4, "Maggio": 5, "Giugno": 6,
           "Luglio": 7, "Agosto": 8, "Settembre": 9, "Ottobre": 10, "Novembre": 11, "Dicembre": 12}

    def parse(s):
        m = re.match(r"(\d+)\s+(\w+)\s+(\d+)", s or "")
        return (int(m.group(3)), MON.get(m.group(2), 0), int(m.group(1))) if m else None

    bad_dates = [a["id"] for a in arts if not parse(a.get("date")) or not parse(a.get("published"))]
    if bad_dates:
        fail("unparseable date: %s" % bad_dates)
    else:
        ok("all dates parse")

    backwards = [a["id"] for a in arts
                 if parse(a.get("published")) and parse(a.get("date"))
                 and parse(a["published"]) < parse(a["date"])]
    if backwards:
        fail("published before the post date: %s" % backwards)
    else:
        ok("no article is published before its post date")

    # the curate note must be present exactly when published != date
    bad_note = []
    for a in arts:
        has = bool(a.get("note"))
        should = a.get("published") != a.get("date")
        if has != should:
            bad_note.append(a["id"])
    if bad_note:
        fail("curate note missing or spurious: %s" % bad_note)
    else:
        ok("curate note present exactly when published != date")

    # audio files referenced must exist
    missing_audio = []
    for a in arts:
        for f in ("audio_eng", "audio_ita", "audio_riflessione"):
            if a.get(f) and not os.path.exists(os.path.join(REPO, a[f])):
                missing_audio.append("%s:%s" % (a["id"], f))
    if missing_audio:
        fail("missing audio file: %s" % missing_audio)
    else:
        ok("every referenced audio file exists")

    print("\n=== generated pages ===")
    pages = {f for f in os.listdir(BLOG) if f.endswith(".html") and f != "index.html"}
    expected = {a["file"] for a in arts}
    if expected - pages:
        fail("article page not generated: %s" % sorted(expected - pages))
    else:
        ok("a page exists for every article")

    orphans = pages - expected
    if orphans:
        fail("orphan pages (run build.py --prune): %s" % sorted(orphans))
    else:
        ok("no orphan pages")

    # every page must contain the article's text
    not_in_page = []
    for a in arts:
        page = open(os.path.join(BLOG, a["file"]), encoding="utf-8").read()
        body = strip_tags(page)
        for field in ("content", "translation", "reflection"):
            t = strip_tags(a.get(field))
            if t and t not in body:
                not_in_page.append("%s:%s" % (a["id"], field))
    if not_in_page:
        fail("text missing from the generated page: %s" % not_in_page)
    else:
        ok("every article's text is in its page")

    # no HTML leaking as visible text
    leaks = []
    for a in arts:
        page = open(os.path.join(BLOG, a["file"]), encoding="utf-8").read()
        for m in re.finditer(r'<div id="(english|italian|reflection)-content">(.*?)</div>', page, re.S):
            if re.search(r"&lt;/p&gt;|\b</p>\b", strip_tags(m.group(2))):
                leaks.append("%s:%s" % (a["id"], m.group(1)))
    if leaks:
        fail("HTML tag visible as text: %s" % leaks)
    else:
        ok("no HTML tag leaks as visible text")

    # the published filename must be stable
    unstable = [a["id"] for a in arts if a["file"] != re.sub(r"^\d{4}-\d{2}-\d{2}-", "", a["file"][:-5]) + ".html"
                and not a["file"].endswith(".html")]
    if unstable:
        fail("bad filename: %s" % unstable)
    else:
        ok("filenames are well formed")

    print("\n=== feeds ===")
    feed = open(os.path.join(REPO, "feed.xml"), encoding="utf-8").read()
    n_items = feed.count("<item>")
    if n_items != len(arts):
        fail("feed.xml has %d items, expected %d" % (n_items, len(arts)))
    else:
        ok("feed.xml has one item per article (%d)" % n_items)
    if "daprodproduzioni.github.io" in feed:
        fail("feed.xml points at the wrong GitHub org")
    else:
        ok("feed.xml points at DaProdProduzioni22")

    api = json.load(open(os.path.join(REPO, "api", "feed.json"), encoding="utf-8"))
    if api.get("count") != len(arts) or len(api.get("posts", [])) != len(arts):
        fail("api/feed.json has %s posts, expected %d" % (len(api.get("posts", [])), len(arts)))
    else:
        ok("api/feed.json has one post per article (%d)" % len(arts))

    sitemap = open(os.path.join(REPO, "sitemap.xml"), encoding="utf-8").read()
    n_urls = sitemap.count("<url>")
    if n_urls < len(arts) + 3:
        fail("sitemap.xml has %d urls, expected at least %d" % (n_urls, len(arts) + 3))
    else:
        ok("sitemap.xml has %d urls" % n_urls)

    print("\n" + ("=" * 50))
    if problems:
        print("FAILED: %d problem(s)" % len(problems))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
