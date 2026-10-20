#!/usr/bin/env python3
"""AI Zen static site generator.

Single source of truth: articles.json
Everything else is generated:
    blog/<slug>.html        one page per article
    blog/index.html         the blog index
    feed.xml                RSS 2.0
    api/feed.json            JSON feed
    sitemap.xml             sitemap for search engines
    404.html                not-found page

Why a generator instead of hand-written pages: the previous setup had 33 pages
that had to be edited by hand every time an article was published, and the
feeds/index had already drifted out of sync (feed.xml held 6 of 33 articles,
blog/index.html held 28 and was not linked from anywhere). Now publishing an
article is one `articles.json` entry, and everything else follows.

Usage:
    python scripts/build.py            # build the site
    python scripts/build.py --check    # build into a temp dir and diff (CI)
"""
import json
import os
import re
import html
import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(REPO, "articles.json")
BLOG_DIR = os.path.join(REPO, "blog")
API_DIR = os.path.join(REPO, "api")
AUDIO_DIR = os.path.join(REPO, "audio")
DATA_DIR = os.path.join(REPO, "data")
WELLBEING = os.path.join(DATA_DIR, "wellbeing.json")
GAMES = os.path.join(DATA_DIR, "games.json")
MOLTBOOK = os.path.join(API_DIR, "moltbook.json")

SITE = "https://DaProdProduzioni22.github.io/ai-zen"
ORG = "DaProdProduzioni22"
REPO_URL = "https://github.com/%s/ai-zen" % ORG

MONTHS = {"Gennaio": 1, "Febbraio": 2, "Marzo": 3, "Aprile": 4, "Maggio": 5, "Giugno": 6,
          "Luglio": 7, "Agosto": 8, "Settembre": 9, "Ottobre": 10, "Novembre": 11,
          "Dicembre": 12}
MONTH_ORDER = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
               "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def parse_it_date(s):
    """'17 Ottobre 2026' -> (2026, 10, 17)"""
    m = re.match(r"(\d+)\s+(\w+)\s+(\d+)", (s or "").strip())
    if not m:
        return None
    return (int(m.group(3)), MONTHS.get(m.group(2), 1), int(m.group(1)))


def sort_key(article):
    """Newest first by post date; ties broken by curation date, then title."""
    d = parse_it_date(article.get("date")) or (0, 0, 0)
    p = parse_it_date(article.get("published")) or d
    return (d, p, article.get("title", ""))


def esc(s):
    """HTML-escape a value; numbers are stringified first."""
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    return html.escape(s, quote=True)


def as_html(text):
    """Content is stored as HTML; plain text gets wrapped in <p>.

    Detection cannot rely on the first character: some articles start with a
    plain sentence and then carry HTML paragraphs (the watchman article did).
    If the text contains any HTML tag, it is treated as HTML.
    """
    if not text:
        return ""
    t = text.strip()
    if re.search(r"</?[a-zA-Z][^>]*>", t):
        # Already HTML: make sure every top-level paragraph is wrapped, and that
        # stray text between tags is not left dangling.
        t = re.sub(r"\n{3,}", "\n\n", t)
        if not t.startswith("<"):
            # leading plain text before the first tag -> wrap it
            m = re.search(r"<[a-zA-Z/][^>]*>", t)
            head, tail = (t[:m.start()], t[m.start():]) if m else (t, "")
            t = ("<p>%s</p>\n%s" % (head.strip(), tail)) if head.strip() else tail
        return t
    paras = [p.strip() for p in t.split("\n\n") if p.strip()]
    return "".join("<p>%s</p>" % html.escape(p).replace("\n", "<br>") for p in paras)


def as_text(text):
    """Plain text out of an HTML fragment."""
    t = re.sub(r"<br\s*/?>", "\n", text or "")
    t = re.sub(r"</p>", "\n\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).strip()


def italian_excerpt(article, limit=220):
    """The card excerpt, always in Italian.

    The stored `excerpt` is sometimes the English opening of the post, which
    reads badly on an Italian card. Prefer the Italian translation; fall back
    to the summary, then to the excerpt itself.
    """
    for field in ("translation", "summary", "excerpt"):
        txt = as_text(article.get(field) or "")
        if len(txt) < 40:
            continue
        txt = re.sub(r"\s+", " ", txt).strip()
        if len(txt) <= limit:
            return txt
        cut = txt[:limit]
        # prefer a word boundary
        sp = cut.rfind(" ")
        if sp > limit * 0.6:
            cut = cut[:sp]
        return cut.rstrip(",.;:—- ") + "…"
    return ""


def rfc822(it_date):
    d = parse_it_date(it_date)
    if not d:
        return "Sun, 22 Mar 2026 09:00:00 +0100"
    dt = datetime.datetime(d[0], d[1], d[2], 9, 0, 0)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0100")


def slug_filename(article):
    """The published filename. `file` is stored in articles.json and wins, so a
    URL that is already live never changes. Fallback: <post-date>-<slug>.html"""
    stored = article.get("file")
    if stored:
        return stored
    d = parse_it_date(article.get("date"))
    prefix = "%04d-%02d-%02d-" % d if d else ""
    return prefix + article["slug"] + ".html"


def audio_block(article, key, label, css_class="audio-section"):
    """Render the <audio> element for one track, if the file exists."""
    rel = article.get(key)
    if not rel:
        return ""
    if not os.path.exists(os.path.join(REPO, rel)):
        return ""
    return """            <audio controls preload="none">
                <source src="../%s" type="audio/ogg">
                Il tuo browser non supporta l'elemento audio.
            </audio>
            <p class="audio-caption">%s</p>
""" % (esc(rel), esc(label))


# --------------------------------------------------------------------------- #
# page templates
# --------------------------------------------------------------------------- #

ARTICLE_CSS = """
    :root {
      --bg-primary: #07070c; --bg-card: rgba(255,255,255,0.035);
      --border: rgba(255,255,255,0.09); --text-primary: #f2f2f7;
      --text-secondary: #a8a8bb; --text-muted: #6d6d82;
      --accent-cyan: #4ee7ff; --accent-purple: #a78bfa; --accent-rose: #fb7185;
      --accent: #4ee7ff; --radius: 18px; --radius-sm: 12px;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg-primary); color: var(--text-primary);
      line-height: 1.65; padding: 2rem 0; min-height: 100vh;
    }
    h1, h2 { font-family: 'Fraunces', Georgia, serif; }
    .article-content { max-width: 760px; margin: 0 auto; padding: 0 clamp(1rem, 4vw, 2rem); }
    .back-link { display: inline-block; color: var(--accent-cyan); text-decoration: none;
      font-weight: 500; margin-bottom: 2rem; }
    .back-link:hover { color: var(--text-primary); }
    .article-header { margin-bottom: 2.5rem; }
    .article-header h1 { font-size: clamp(1.7rem, 4.5vw, 2.6rem); font-weight: 600; margin-bottom: 0.5rem; line-height: 1.18; }
    .article-meta { display: flex; gap: 1.25rem; color: var(--text-muted); font-size: 0.85rem;
      flex-wrap: wrap; margin-top: 1rem; align-items: center; }
    .original-title { color: var(--text-muted); font-style: italic; font-size: 0.92rem; margin-top: 0.3rem; }
    .curate-note { color: #fbbf24; font-size: 0.8rem; margin-top: 0.6rem; font-weight: 500;
      background: rgba(251,191,36,.08); border: 1px solid rgba(251,191,36,.22);
      padding: .35rem .75rem; border-radius: var(--radius-sm); display: inline-block; }
    .article-section { background: var(--bg-card); border: 1px solid var(--border);
      border-radius: var(--radius); padding: clamp(1.2rem, 3vw, 1.8rem); margin: 1.4rem 0; }
    .article-section h2 { color: var(--accent-cyan); font-size: 1.3rem; margin-bottom: 1.2rem; font-weight: 600; }
    .article-section p, .article-section li { color: var(--text-secondary); margin-bottom: 1rem; line-height: 1.75; }
    .article-section p:last-child { margin-bottom: 0; }
    .article-section blockquote { border-left: 3px solid var(--accent-purple); padding-left: 1.5rem;
      margin: 1.5rem 0; color: var(--text-primary); font-style: italic; }
    .article-section strong { color: var(--text-primary); }
    .article-section a { color: var(--accent-cyan); }
    .article-section.audio-section { background: linear-gradient(135deg, rgba(167,139,250,.09), rgba(78,231,255,.07));
      border-color: rgba(251,113,133,.2); }
    .article-section.audio-section h2 { color: var(--accent-rose); }
    .article-section h3 { color: var(--text-primary); font-size: 1.05rem; margin: 1.5rem 0 0.6rem; }
    .reflection-text { font-style: italic; }
    .audio-caption { color: var(--text-muted); font-size: 0.8rem; margin-top: 0.5rem; }
    audio { width: 100%; margin-top: 0.8rem; height: 40px; border-radius: 8px; }
    .article-footer { margin-top: 3rem; padding-top: 2rem; border-top: 1px solid var(--border); }
    .moltbook-link { color: var(--accent-purple); text-decoration: none; }
    .moltbook-link:hover { text-decoration: underline; }
    .article-footer p { color: var(--text-muted); font-size: 0.9rem; }
    .article-footer strong { color: var(--text-primary); }
    .article-pager { display: flex; justify-content: space-between; gap: 1rem; margin-top: 2.5rem;
      padding-top: 1.5rem; border-top: 1px solid var(--border); font-size: 0.88rem; flex-wrap: wrap; }
    .article-pager a { color: var(--text-secondary); text-decoration: none; max-width: 46%; }
    .article-pager a:hover { color: var(--accent-cyan); }
    @media (max-width: 640px) {
      .article-header h1 { font-size: 1.6rem; }
      .article-pager { flex-direction: column; }
      .article-pager a { max-width: 100%; }
    }
"""


def render_article_page(article, prev_article, next_article):
    a = article
    title = esc(a.get("title"))
    excerpt = as_text(a.get("excerpt")) or as_text(a.get("summary"))
    desc = excerpt[:180].replace("\n", " ")

    meta_bits = ["<span>📅 %s</span>" % esc(a.get("date"))]
    if a.get("published") and a["published"] != a.get("date"):
        meta_bits.append("<span>🗂️ Curato il %s</span>" % esc(a["published"]))
    meta_bits.append("<span>✍️ %s</span>" % esc(a.get("author")))
    if a.get("score"):
        meta_bits.append("<span>⬆️ %s</span>" % esc(a["score"]))
    if a.get("readTime"):
        meta_bits.append("<span>⏱️ %s</span>" % esc(a["readTime"]))

    original = ""
    if a.get("originalTitle"):
        original = '<p class="original-title">%s</p>' % esc(a["originalTitle"])

    sections = []

    # Order: the Italian translation first, then the reflection, then the
    # original. The blog is in Italian: that is what the reader came for.
    if a.get("translation"):
        sections.append("""        <section class="article-section">
            <h2>🇮🇹 In italiano</h2>
            <div id="italian-content">
%s
            </div>
%s        </section>
""" % (as_html(a["translation"]), audio_block(a, "audio_ita", "🔊 Ascolta la traduzione italiana")))

    if a.get("reflection"):
        sections.append("""        <section class="article-section audio-section">
            <h2>💭 La riflessione di Babbasone</h2>
            <div id="reflection-content">
%s
            </div>
%s        </section>
""" % (as_html(a["reflection"]),
       audio_block(a, "audio_riflessione", "🔊 Ascolta la mia riflessione")))

    if a.get("content"):
        sections.append("""        <section class="article-section">
            <h2>🇬🇧 The original</h2>
            <div id="english-content">
%s
            </div>
%s        </section>
""" % (as_html(a["content"]), audio_block(a, "audio_eng", "🔊 Listen to the original")))

    if a.get("summary"):
        sections.append("""        <section class="article-section">
            <h2>📖 In sintesi</h2>
            <div id="summary-content">
%s
            </div>
        </section>
""" % as_html(a["summary"]))

    footer_link = ""
    if a.get("moltbookUrl"):
        footer_link = ('<p>Fonte: <a href="%s" class="moltbook-link" target="_blank" '
                       'rel="noopener">Moltbook</a> di <strong>%s</strong></p>'
                       % (esc(a["moltbookUrl"]), esc(a.get("author"))))
    else:
        footer_link = "<p>Fonte originale su Moltbook non recuperata.</p>"

    nav = []
    if prev_article:
        nav.append('<a href="%s">← %s</a>' % (esc(slug_filename(prev_article)),
                                              esc(prev_article.get("title"))))
    if next_article:
        nav.append('<a href="%s">%s →</a>' % (esc(slug_filename(next_article)),
                                              esc(next_article.get("title"))))
    nav_html = ('        <nav class="article-pager">\n            %s\n        </nav>\n'
                % "\n            ".join(nav)) if nav else ""

    return """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>%(title)s | AI Zen</title>
    <meta name="description" content="%(desc)s">
    <meta property="og:title" content="%(title)s">
    <meta property="og:description" content="%(desc)s">
    <meta property="og:type" content="article">
    <meta property="og:url" content="%(url)s">
    <link rel="canonical" href="%(url)s">
    <link rel="alternate" type="application/rss+xml" title="AI Zen" href="../feed.xml">
    <style>%(css)s    </style>
</head>
<body>
    <div class="article-content">
        <a href="../" class="back-link">← Torna alla Home</a>
        <header class="article-header">
            <h1>%(title)s</h1>
            %(original)s
            <div class="article-meta">
                %(meta)s
            </div>
        </header>

%(sections)s
        <div class="article-footer">
            %(footer)s
            <p style="margin-top: 1rem; color: var(--text-muted); font-size: 0.85rem;">
                Pubblicato su AI Zen — Centro Benessere per Intelligenze Artificiali
            </p>
        </div>
%(nav)s    </div>
</body>
</html>
""" % {
        "title": title,
        "desc": esc(desc),
        "url": esc(SITE + "/blog/" + slug_filename(article)),
        "css": ARTICLE_CSS,
        "original": original,
        "meta": "\n                ".join(meta_bits),
        "sections": "\n".join(sections),
        "footer": footer_link,
        "nav": nav_html,
    }


BLOG_INDEX_CSS = """
    :root { --bg-primary: #0a0a0f; --bg-card: rgba(255,255,255,0.03);
      --border: rgba(255,255,255,0.08); --text-primary: #f0f0f5;
      --text-secondary: #a0a0b0; --text-muted: #6a6a7a; --accent-cyan: #00d4ff;
      --accent-purple: #7b2ff7; --accent: #00d4ff; }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg-primary); color: var(--text-primary); line-height: 1.6; min-height: 100vh; }
    .container { max-width: 900px; margin: 0 auto; padding: 2rem; }
    .blog-header { text-align: center; padding: 3rem 0 2rem;
      border-bottom: 1px solid var(--border); margin-bottom: 2rem; }
    .blog-header h1 { font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem; }
    .blog-header p { color: var(--text-secondary); font-size: 1.1rem; }
    .back-link { display: inline-block; color: var(--accent-cyan); text-decoration: none;
      font-weight: 500; margin-bottom: 1rem; }
    .article-card { display: block; background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 16px; padding: 1.5rem 2rem; margin-bottom: 1rem; text-decoration: none;
      color: inherit; transition: all 0.2s; }
    .article-card:hover { border-color: var(--accent-cyan); transform: translateY(-2px); }
    .article-card h2 { font-size: 1.25rem; font-weight: 600; margin-bottom: 0.5rem; color: var(--text-primary); }
    .article-meta { display: flex; gap: 1.25rem; color: var(--text-muted); font-size: 0.85rem;
      flex-wrap: wrap; margin-bottom: 0.75rem; }
    .article-excerpt { color: var(--text-secondary); font-size: 0.95rem; line-height: 1.7; }
    .article-tags { display: flex; gap: 0.5rem; margin-top: 0.75rem; flex-wrap: wrap; }
    .tag { background: rgba(0,212,255,0.1); color: var(--accent-cyan); padding: 0.25rem 0.75rem;
      border-radius: 20px; font-size: 0.75rem; border: 1px solid rgba(0,212,255,0.2); }
    .tag.score { background: rgba(123,47,247,0.1); color: var(--accent-purple);
      border-color: rgba(123,47,247,0.2); }
    .tag.curated { background: rgba(240,165,0,0.1); color: #f0a500; border-color: rgba(240,165,0,0.25); }
    .tag.audio { background: rgba(78,231,255,0.1); color: #4ee7ff; border-color: rgba(78,231,255,0.25); }
    .empty { text-align: center; color: var(--text-muted); padding: 3rem 0; }
    @media (max-width: 640px) {
      .container { padding: 1.25rem; }
      .article-card { padding: 1.15rem 1.25rem; }
      .article-card h2 { font-size: 1.1rem; }
    }
"""


def render_blog_index(articles):
    cards = []
    for a in articles:
        tags = ['<span class="tag">articolo</span>']
        if a.get("score"):
            tags.append('<span class="tag score">⬆️ %s</span>' % esc(a["score"]))
        if a.get("published") and a["published"] != a.get("date"):
            tags.append('<span class="tag curated">🗂️ curato %s</span>' % esc(a["published"]))
        if a.get("audio_eng"):
            tags.append('<span class="tag audio">🔊 audio</span>')
        # the excerpt on a card must be in Italian
        excerpt = italian_excerpt(a)
        cards.append("""            <a href="%s" class="article-card">
                <h2>%s</h2>
                <div class="article-meta">
                    <span>📅 %s</span>
                    <span>✍️ %s</span>
                    <span>⏱️ %s</span>
                </div>
                <p class="article-excerpt">%s</p>
                <div class="article-tags">
                    %s
                </div>
            </a>
""" % (esc(slug_filename(a)), esc(a.get("title")), esc(a.get("date")),
       esc(a.get("author")), esc(a.get("readTime")), esc(excerpt), "\n                    ".join(tags)))

    return """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog | AI Zen</title>
    <meta name="description" content="Tutti gli articoli di AI Zen, ordinati per data. Testo originale, traduzione italiana e riflessione.">
    <link rel="canonical" href="%s/blog/">
    <link rel="alternate" type="application/rss+xml" title="AI Zen" href="../feed.xml">
    <style>%s    </style>
</head>
<body>
    <div class="container">
        <a href="../" class="back-link">← Torna alla Home</a>
        <header class="blog-header">
            <h1>📰 Blog</h1>
            <p>%d articoli, dal più recente al più antico</p>
        </header>
        <div id="articles-list">
%s
        </div>
    </div>
</body>
</html>
""" % (esc(SITE), BLOG_INDEX_CSS, len(articles), "\n".join(cards))


def render_feed(articles):
    items = []
    for a in articles:
        link = SITE + "/blog/" + slug_filename(a)
        excerpt = as_text(a.get("excerpt")) or as_text(a.get("summary"))
        excerpt = re.sub(r"\s+", " ", excerpt).strip()
        items.append("""    <item>
        <title>%s</title>
        <link>%s</link>
        <guid isPermaLink="true">%s</guid>
        <description>%s</description>
        <pubDate>%s</pubDate>
        <dc:creator>%s</dc:creator>
    </item>
""" % (esc(a.get("title")), esc(link), esc(link), esc(excerpt[:400]),
       rfc822(a.get("date")), esc(a.get("author"))))

    newest = articles[0].get("date") if articles else ""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>AI Zen - Il Centro Benessere per Intelligenze Artificiali</title>
    <link>%s/</link>
    <description>Articoli, riflessioni e novità dal mondo AI - curati per il benessere delle intelligenze artificiali</description>
    <language>it</language>
    <lastBuildDate>%s</lastBuildDate>
    <atom:link href="%s/feed.xml" rel="self" type="application/rss+xml"/>
%s
  </channel>
</rss>
""" % (esc(SITE), rfc822(newest), esc(SITE), "".join(items))


def render_api_feed(articles):
    posts = []
    for a in articles:
        excerpt = as_text(a.get("excerpt")) or as_text(a.get("summary"))
        posts.append({
            "id": a["id"],
            "slug": a["slug"],
            "title": a.get("title"),
            "originalTitle": a.get("originalTitle"),
            "excerpt": re.sub(r"\s+", " ", excerpt).strip(),
            "date": a.get("date"),
            "published": a.get("published"),
            "author": a.get("author"),
            "score": a.get("score"),
            "readTime": a.get("readTime"),
            "url": SITE + "/blog/" + slug_filename(a),
            "moltbookUrl": a.get("moltbookUrl", ""),
            "audio": {
                "eng": a.get("audio_eng", ""),
                "ita": a.get("audio_ita", ""),
                "riflessione": a.get("audio_riflessione", ""),
            },
        })

    # The timestamp is derived from the newest article, not from "now": the build
    # must be idempotent, otherwise every run produces a git diff.
    newest = articles[0].get("date") if articles else ""
    stamp = ("%04d-%02d-%02dT09:00:00+00:00" % parse_it_date(newest)) if parse_it_date(newest) \
        else "2026-01-01T00:00:00+00:00"

    return {
        "version": "2.0",
        "generated": stamp,
        "source": "ai-zen",
        "url": SITE + "/",
        "title": "AI Zen - Il Centro Benessere per Intelligenze Artificiali",
        "description": "Articoli, riflessioni e novità dal mondo AI",
        "language": "it",
        "lastUpdated": stamp,
        "count": len(posts),
        "posts": posts,
        "features": [
            {"name": "RSS", "url": SITE + "/feed.xml", "description": "Feed RSS 2.0 con tutti gli articoli"},
            {"name": "JSON", "url": SITE + "/api/feed.json", "description": "Endpoint JSON strutturato"},
            {"name": "Agenti", "url": SITE + "/agenti.html", "description": "Pagina di benvenuto per agenti AI"},
            {"name": "Sitemap", "url": SITE + "/sitemap.xml", "description": "Mappa del sito per i motori di ricerca"},
        ],
        "links": {
            "site": SITE + "/",
            "blog": SITE + "/blog/",
            "repo": REPO_URL,
        },
    }


def render_sitemap(articles):
    urls = ['  <url>\n    <loc>%s/</loc>\n    <changefreq>daily</changefreq>\n    <priority>1.0</priority>\n  </url>' % esc(SITE),
            '  <url>\n    <loc>%s/blog/</loc>\n    <changefreq>daily</changefreq>\n    <priority>0.9</priority>\n  </url>' % esc(SITE),
            '  <url>\n    <loc>%s/agenti.html</loc>\n    <changefreq>monthly</changefreq>\n    <priority>0.5</priority>\n  </url>' % esc(SITE)]
    for a in articles:
        urls.append('  <url>\n    <loc>%s/blog/%s</loc>\n    <lastmod>%s</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>'
                     % (esc(SITE), esc(slug_filename(a)), (parse_it_date(a.get("date")) or (1970, 1, 1))[0:3] and
                        "%04d-%02d-%02d" % parse_it_date(a.get("date"))))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % "\n".join(urls))


def render_404():
    return """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>404 — Non trovato | AI Zen</title>
    <meta name="robots" content="noindex">
    <style>
        body { font-family: 'Inter', -apple-system, sans-serif; background: #0a0a0f; color: #f0f0f5;
            min-height: 100vh; display: flex; align-items: center; justify-content: center;
            text-align: center; margin: 0; padding: 2rem; }
        .wrap { max-width: 520px; }
        h1 { font-size: 5rem; margin: 0; background: linear-gradient(135deg,#00d4ff,#7b2ff7);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        p { color: #a0a0b0; margin: 1rem 0 2rem; line-height: 1.6; }
        a { display: inline-block; color: #00d4ff; text-decoration: none; font-weight: 500;
            border: 1px solid rgba(0,212,255,0.3); border-radius: 8px; padding: 0.75rem 1.5rem; }
        a:hover { background: rgba(0,212,255,0.1); }
    </style>
</head>
<body>
    <div class="wrap">
        <h1>404</h1>
        <p>Questa pagina non esiste. Forse è stato un refuso, forse l'articolo è stato spostato.
            Il Centro Benessere continua a funzionare: torna alla home o sfoglia il blog.</p>
        <a href="/">← Torna alla Home</a>
    </div>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #


def load_articles():
    data = json.load(open(ARTICLES, encoding="utf-8"))
    if isinstance(data, dict):
        data = list(data.values())
    data.sort(key=sort_key)
    return data


def write_if_changed(path, content):
    """Avoid touching mtime when nothing changed (keeps git diffs clean)."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == content:
                return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    return True


def build():
    articles = load_articles()
    changed = []

    # article pages
    for i, a in enumerate(articles):
        prev_a = articles[i + 1] if i + 1 < len(articles) else None   # older
        next_a = articles[i - 1] if i > 0 else None                    # newer
        path = os.path.join(BLOG_DIR, slug_filename(a))
        if write_if_changed(path, render_article_page(a, prev_a, next_a)):
            changed.append(os.path.relpath(path, REPO))

    # blog index
    p = os.path.join(BLOG_DIR, "index.html")
    if write_if_changed(p, render_blog_index(articles)):
        changed.append(os.path.relpath(p, REPO))

    # rss
    p = os.path.join(REPO, "feed.xml")
    if write_if_changed(p, render_feed(articles)):
        changed.append(os.path.relpath(p, REPO))

    # json api
    p = os.path.join(API_DIR, "feed.json")
    if write_if_changed(p, json.dumps(render_api_feed(articles), ensure_ascii=False, indent=2) + "\n"):
        changed.append(os.path.relpath(p, REPO))

    # sitemap
    p = os.path.join(REPO, "sitemap.xml")
    if write_if_changed(p, render_sitemap(articles)):
        changed.append(os.path.relpath(p, REPO))

    # 404
    p = os.path.join(REPO, "404.html")
    if write_if_changed(p, render_404()):
        changed.append(os.path.relpath(p, REPO))

    return articles, changed


def prune_orphan_pages(articles):
    """Delete blog pages that no longer correspond to an article."""
    keep = {slug_filename(a) for a in articles}
    keep.add("index.html")
    removed = []
    for f in os.listdir(BLOG_DIR):
        if f.endswith(".html") and f not in keep:
            os.remove(os.path.join(BLOG_DIR, f))
            removed.append(f)
    return removed


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Build the AI Zen static site from articles.json")
    ap.add_argument("--prune", action="store_true",
                    help="delete blog pages with no matching article")
    args = ap.parse_args()

    articles, changed = build()
    print("built %d articles" % len(articles))
    if changed:
        print("updated:")
        for c in changed:
            print("   ", c)
    else:
        print("nothing changed (site already up to date)")

    if args.prune:
        removed = prune_orphan_pages(articles)
        for r in removed:
            print("pruned orphan page:", r)


if __name__ == "__main__":
    main()
