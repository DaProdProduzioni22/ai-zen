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
import shutil
import subprocess

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
                "authorUrl",
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

    # The public route of a post is /post/<uuid> (SINGULAR). /posts/<uuid> is
    # the API route and answers 404 in a browser: every "Fonte: Moltbook" link
    # built from it is dead (this shipped once, 31 links at a time).
    wrong_route = [a["id"] for a in arts
                   if a.get("moltbookUrl")
                   and not re.fullmatch(r"https://www\.moltbook\.com/post/[0-9a-fA-F-]{36}", a["moltbookUrl"])]
    if wrong_route:
        fail("moltbookUrl is not the public route https://www.moltbook.com/post/<uuid>: %s" % wrong_route)
    else:
        ok("every Moltbook link uses the public route /post/<uuid>")

    # Profilo Moltbook dell'autore: https://www.moltbook.com/u/<handle>
    missing_author_urls = [a["id"] for a in arts if not a.get("authorUrl")]
    bad_author_urls = [a["id"] for a in arts
                       if a.get("authorUrl")
                       and not re.fullmatch(r"https://www\.moltbook\.com/u/[A-Za-z0-9._-]+", a["authorUrl"])]
    if missing_author_urls:
        fail("authorUrl mancante: %s" % missing_author_urls)
    elif bad_author_urls:
        fail("authorUrl non è un profilo Moltbook /u/<handle>: %s" % bad_author_urls)
    else:
        ok("ogni articolo linka il profilo Moltbook dell'autore")

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

    # "One article per day" is a curation rule (add_article.py enforces it, but a
    # hand-edited articles.json bypasses it). WARN, not FAIL: two curated Moltbook
    # posts on the same day can be legitimate, so a human has to judge each case.
    per_day = {}
    for a in arts:
        if parse(a.get("published")):
            per_day.setdefault(parse(a["published"]), []).append(a["id"])
    crowded = {"%04d-%02d-%02d" % d: ids for d, ids in sorted(per_day.items()) if len(ids) > 1}
    if crowded:
        print("  WARN  more than one article curated on the same day (rule: max 1/day; "
              "may be legitimate for two imported Moltbook posts, evaluate each case): %s" % crowded)
    else:
        ok("at most one article curated per day")

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

    # A file that exists is not necessarily the RIGHT file: one audio file
    # must belong to exactly one article (a shared file means one of the two
    # articles plays the other one's text).
    audio_users = {}
    for a in arts:
        for f in ("audio_eng", "audio_ita", "audio_riflessione"):
            if a.get(f):
                audio_users.setdefault(a[f], []).append("%s:%s" % (a["id"], f))
    shared_audio = {path: users for path, users in audio_users.items() if len(users) > 1}
    if shared_audio:
        fail("the same audio file is used by several articles: %s" % shared_audio)
    else:
        ok("every audio file is used by exactly one article")

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

    # The site is published under /ai-zen/. A root-relative href="/x" leaves that
    # sub-path and lands on the domain root, which answers 404 (shipped once:
    # the 404 page's "Home" button and the guide article's "pagina per agenti").
    # Only absolute https://DaProdProduzioni22.github.io/ai-zen/... URLs are fine.
    page_files = [os.path.join(REPO, f) for f in ("index.html", "404.html", "agenti.html")]
    page_files += [os.path.join(BLOG, f) for f in sorted(os.listdir(BLOG)) if f.endswith(".html")]
    # NB: raw string, so \w stays backslash+w. In a non-raw string "\b" silently
    # became the backspace byte 0x08 and this check never fired. The lookbehind
    # skips data-href / xlink-href (not navigations).
    ROOT_REL_RE = re.compile(r"""(?<![\w-])(?:href|src)=["'](/(?!/)[^"']*)["']""")
    # self-test: the pattern must catch known-bad links and let good ones through,
    # otherwise this invariant would be a vacuous PASS.
    if chr(8) in ROOT_REL_RE.pattern:
        fail("root-relative pattern contains a backspace byte (0x08) instead of a word boundary")
    _bad = ['<a href="/x">x</a>', "<a href='/agenti.html'>a</a>", '<img src="/img/a.png">']
    _good = ['<a href="./">h</a>', '<a href="../agenti.html">a</a>', '<a href="//cdn.x/y">c</a>',
             '<a href="https://DaProdProduzioni22.github.io/ai-zen/">a</a>',
             '<a href="#top">t</a>', 'data-href="/x"']
    _missed = [s for s in _bad if not ROOT_REL_RE.search(s)]
    _false = [s for s in _good if ROOT_REL_RE.search(s)]
    if _missed:
        fail("root-relative pattern is broken, misses known-bad links: %s" % _missed)
    elif _false:
        fail("root-relative pattern is broken, flags good links: %s" % _false)
    else:
        ok("root-relative pattern self-test (%d bad caught, %d good allowed)" % (len(_bad), len(_good)))
    root_rel = []
    for pf in page_files:
        if not os.path.exists(pf):
            continue
        txt = open(pf, encoding="utf-8").read()
        for m in ROOT_REL_RE.finditer(txt):
            root_rel.append("%s -> %s" % (os.path.relpath(pf, REPO).replace(os.sep, "/"), m.group(1)))
    if root_rel:
        fail("root-relative href/src (404 under /ai-zen/): %s" % root_rel)
    else:
        ok("no root-relative href/src in any page (%d pages scanned)" % len(page_files))

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

    print("\n=== covers, illustrations and the CSS the two copies share ===")
    # The cover is drawn by THREE copies of one function: cover_svg() in build.py
    # (static pages), coverSVG() in index.html (SPA) and assets/cover.js. Compare
    # them on every article (gradient ids and aria-hidden aside).
    def norm_cover(svg):
        svg = re.sub(r'\s+aria-hidden="true"', "", svg)
        svg = re.sub(r'id="[^"]*"', 'id="ID"', svg)
        return re.sub(r'url\(#[^)]*\)', "url(#ID)", svg)

    cards_html = open(os.path.join(BLOG, "index.html"), encoding="utf-8").read()
    n_cards = len(re.findall(r'<div class="card-cover"><svg', cards_html))
    n_heroes = 0
    for a in arts:
        pg = open(os.path.join(BLOG, a["file"]), encoding="utf-8").read()
        n_heroes += len(re.findall(r'<div class="art-cover"><svg', pg))
    if n_cards != len(arts):
        fail("blog/index.html has %d card covers, expected %d (one per article)" % (n_cards, len(arts)))
    elif n_heroes != len(arts):
        fail("article pages have %d hero covers, expected %d (one per article)" % (n_heroes, len(arts)))
    else:
        ok("static pages: %d card covers + %d article covers (one per article)" % (n_cards, n_heroes))

    # an <a> nested in the card's own <a> is invalid HTML: the parser splits the card
    # (grid broken, counters x3). Compare what the browser would build with what we wrote.
    nested = [m.group(1) for m in re.finditer(r'<a href="([^"]+)" class="article-card"[^>]*>(.*?)</a>', cards_html, re.S)
              if "<a " in m.group(2)]
    if nested:
        fail("blog/index.html: link nested inside a card link (card splits into pieces): %s" % nested[:3])
    else:
        ok("blog/index.html: no link nested inside the %d card links" % n_cards)

    node = shutil.which("node")
    spa_src = open(os.path.join(REPO, "index.html"), encoding="utf-8").read()
    m = re.search(r"function coverSVG\(a, idx\) \{.*?\n    \}\n", spa_src, re.S)
    # the page's own index (the gradient id carries it: azg<idx>_<seed>) is what the
    # cover of that article was drawn with; the other two copies must draw the same
    static, idxs = [], []
    for a in arts:
        pg = open(os.path.join(BLOG, a["file"]), encoding="utf-8").read()
        mm = re.search(r'<div class="art-cover">(<svg.*?</svg>)</div>', pg, re.S)
        static.append(mm.group(1) if mm else "")
        gi = re.search(r'id="azg(\d+)_', static[-1])
        idxs.append(int(gi.group(1)) if gi else 0)
    if not node:
        print("  WARN  node not found: cover.js / SPA coverSVG parity not checked")
    elif not m:
        fail("coverSVG() not found in index.html")
    else:
        js = ("const fs=require('fs');const vm=require('vm');\n"
              "const arts=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));\n"
              "const ix=JSON.parse(process.argv[5]);\n"
              "const cj=fs.readFileSync(process.argv[3],'utf8');\n"
              "const ctx={window:{}};vm.createContext(ctx);vm.runInContext(cj,ctx);\n"
              "const spa=new Function(fs.readFileSync(process.argv[4],'utf8')+';return coverSVG;')();\n"
              "console.log(JSON.stringify(arts.map((a,i)=>[ctx.window.coverSVG(a.id,a.author,ix[i]),spa(a,ix[i])])));\n")
        tmp_js = os.path.join(os.environ.get("TMPDIR") or os.environ.get("TEMP") or REPO, "_check_cover.js")
        tmp_spa = tmp_js + ".spa.js"
        try:
            open(tmp_js, "w", encoding="utf-8").write(js)
            open(tmp_spa, "w", encoding="utf-8").write(m.group(0))
            r = subprocess.run([node, tmp_js, ARTICLES, os.path.join(REPO, "assets", "cover.js"), tmp_spa,
                                json.dumps(idxs)], capture_output=True, text=True, timeout=60, encoding="utf-8")
        finally:
            for t in (tmp_js, tmp_spa):
                if os.path.exists(t):
                    os.remove(t)
        if r.returncode != 0:
            fail("could not run cover.js / SPA coverSVG under node: %s" % r.stderr.strip()[:200])
        else:
            pairs = json.loads(r.stdout)
            n_js = sum(1 for c, _ in pairs if c.startswith("<svg"))
            n_spa = sum(1 for _, c in pairs if c.startswith("<svg"))
            if n_js != len(arts) or n_spa != len(arts):
                fail("covers: cover.js drew %d, SPA coverSVG %d, expected %d" % (n_js, n_spa, len(arts)))
            else:
                ok("cover.js and the SPA's coverSVG() each draw %d covers (one per article)" % len(arts))
            drift = [arts[i]["id"] for i, (c, sp) in enumerate(pairs)
                     if not (norm_cover(c) == norm_cover(sp) == norm_cover(static[i]))]
            if drift:
                fail("cover drawing differs between build.py, cover.js and index.html for: %s" % drift[:5])
            else:
                ok("cover drawing identical in build.py, cover.js and index.html (%d articles)" % len(arts))

    css = open(os.path.join(REPO, "assets", "zen-ui.css"), encoding="utf-8").read()
    need = [".card-cover", ".article-card", ".card-body", ".art-hero", ".art-cover", ".art-layout",
            ".art-side", ".side-box", ".article-header h1", ".index-hero h1", ".nav-strip", ".illu"]
    missing = [sel for sel in need if sel not in css]
    if missing:
        fail("assets/zen-ui.css lacks the card/title/column rules: %s" % missing)
    else:
        ok("zen-ui.css defines cards, titles, article columns and illustrations (%d selectors)" % len(need))

    def illu_block(txt):
        mb = re.search(r"/\* illu-css:begin.*?/\* illu-css:end \*/", txt, re.S)
        return re.sub(r"\s+", " ", mb.group(0)) if mb else None
    b_css, b_spa = illu_block(css), illu_block(spa_src)
    if not b_css or not b_spa:
        fail("illu-css block missing in zen-ui.css or index.html")
    elif b_css != b_spa:
        fail("the illustration CSS differs between index.html and assets/zen-ui.css (run build.py)")
    else:
        ok("illustration CSS identical in index.html and zen-ui.css")

    sections = {"home": "illu-home", "blog": "illu-blog-read", "wellbeing": "illu-wellbeing",
                "games": "illu-games", "moltbook": "illu-moltbook", "about": "illu-about"}
    no_illu = [k for k, cls in sections.items() if ('<figure class="illu %s"' % cls) not in spa_src]
    if no_illu:
        fail("SPA sections without an illustration: %s" % no_illu)
    elif '<figure class="illu illu-blog-read"' not in cards_html:
        fail("blog/index.html lacks the 'how to read' illustration")
    else:
        ok("all %d SPA sections + /blog/ carry an inline SVG illustration" % len(sections))

    figs = re.findall(r'<figure class="illu.*?</figure>', spa_src, re.S)
    bad_col = [c for f in figs for c in re.findall(r'(?:fill|stroke)="(#[0-9a-fA-F]{3,8}|rgba?\([^"]*)"', f)]
    if bad_col:
        fail("hard-coded colours in the illustrations (breaks the light theme): %s" % bad_col[:5])
    else:
        ok("illustrations use only site variables (no hard-coded colours)")


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

    # api/moltbook.json is NOT a mirror of articles.json: it is the snapshot of the
    # live Moltbook "hot" feed (scripts/fetch_moltbook_feed.py), so its length is
    # the feed limit, not the article count. What must hold: it is coherent, and
    # `publishedHere` agrees with what the blog really published.
    mb_path = os.path.join(REPO, "api", "moltbook.json")
    if os.path.exists(mb_path):
        mb = json.load(open(mb_path, encoding="utf-8"))
        mb_posts = mb.get("posts", [])
        have = {(a.get("postId") or "").lower() for a in arts if a.get("postId")}
        have |= {m.group(0).lower() for a in arts
                 for m in [re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                                     a.get("moltbookUrl") or "", re.I)] if m}
        bad_mb = [p.get("id") for p in mb_posts
                  if not (p.get("id") and p.get("title") and p.get("created_at") and p.get("url"))]
        stale = [p.get("id") for p in mb_posts if bool(p.get("publishedHere")) != (p.get("id") in have)]
        if mb.get("count") != len(mb_posts):
            fail("api/moltbook.json count=%s but %d posts" % (mb.get("count"), len(mb_posts)))
        elif bad_mb:
            fail("api/moltbook.json: posts missing id/title/created_at/url: %s" % bad_mb)
        elif stale:
            fail("api/moltbook.json: publishedHere out of date (run scripts/fetch_moltbook_feed.py): %s" % stale)
        else:
            ok("api/moltbook.json is coherent (%d feed posts, publishedHere matches the blog)" % len(mb_posts))

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
