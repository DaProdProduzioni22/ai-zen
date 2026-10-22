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
import hashlib
import datetime
import urllib.parse
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import illustrations  # noqa: E402  (the section drawings: one source for the SPA and /blog/)

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


def _site_relative_links(t):
    """Article text lives in articles.json with links relative to the SITE ROOT
    (e.g. href="agenti.html"): that works as-is in the SPA (index.html, in the
    root), but article pages live in blog/, so one level up is needed. A
    root-relative href="/x" would leave the /ai-zen/ sub-path and 404: it is
    rewritten here too, and check_site.py guards against it."""
    def fix(m):
        url = m.group(2)
        if re.match(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//|#|\.\./)", url):
            return m.group(0)
        return '%s"../%s"' % (m.group(1), url.lstrip("/"))
    return re.sub(r'(\bhref=)"([^"]*)"', fix, t)


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
        return _site_relative_links(t)
    paras = [p.strip() for p in t.split("\n\n") if p.strip()]
    return "".join("<p>%s</p>" % html.escape(p).replace("\n", "<br>") for p in paras)


def as_text(text):
    """Plain text out of an HTML fragment."""
    t = re.sub(r"<svg\b.*?</svg>", " ", text or "", flags=re.S | re.I)   # figure labels are not prose
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"</p>", "\n\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).strip()


_IT_WORDS = re.compile(r"\b(il|lo|la|gli|che|non|un|una|di|per|con|del|della|sono|come)\b", re.I)


def _plain(text):
    """Same as plainText() in index.html: tags -> space, entities, collapse blanks."""
    t = re.sub(r"<svg\b.*?</svg>", " ", text or "", flags=re.S | re.I)   # mirror of plainText()
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def _looks_italian(t):
    """At least two distinct common Italian words (one stray hit is not enough:
    'come', 'per', 'non', 'con' also occur in English text)."""
    return len({w.lower() for w in _IT_WORDS.findall(t)}) >= 2


def _first_sentence(t):
    m = re.match(r"(.+?[.!?\u2026])(?:\s|$)", t)
    return m.group(1) if m and len(m.group(1)) >= 40 else t


def italian_excerpt(article, limit=200):
    """The card excerpt, always in Italian. MIRROR of itExcerpt() in index.html:
    keep the two in sync (the SPA cards and blog/index.html must agree).

    Order: translation -> reflection -> summary -> first sentence of content ->
    excerpt (last resort: it is the ENGLISH opening of the post). A candidate
    counts only if it is long enough and reads as Italian; if none qualifies the
    card shows the title, so it never shows English text.
    """
    cands = (article.get("translation"), article.get("reflection"), article.get("summary"),
             _first_sentence(_plain(article.get("content"))), article.get("excerpt"))
    for c in cands:
        txt = _plain(c)
        if len(txt) < 40 or not _looks_italian(txt):
            continue
        if len(txt) <= limit:
            return txt
        return re.sub(r"\s+\S*$", "", txt[:limit]) + "\u2026"
    return _plain(article.get("title"))


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
    return """            <audio class="audio-player" controls preload="none">
                <source src="../%s" type="audio/ogg">
                Il tuo browser non supporta l'elemento audio.
            </audio>
            <p class="audio-caption">%s</p>
""" % (esc(rel), esc(label))


def speak_block(article, field, label):
    """The 'Ascolta' button: the browser synthesises the text on the spot."""
    text = article.get(field)
    if not text:
        return ""
    return """        <div class="speak">
            <button class="speak-btn" onclick="speak(this)">
                <span>🔊</span><span>Ascolta</span>
            </button>
            <span class="speak-state">%s</span>
        </div>
""" % esc(label)


# --------------------------------------------------------------------------- #
# page templates
# --------------------------------------------------------------------------- #


HUES = [
    (78, 231, 255),    # cyan
    (167, 139, 250),   # violet
    (251, 113, 133),   # rose
    (251, 191, 36),    # amber
    (74, 222, 128),    # green
]


def cover_svg(article, idx):
    """The cover of an article: same shapes as the SPA (assets/cover.js)."""
    author = article.get("author") or ""
    h = HUES[((idx * 7) + len(author)) % len(HUES)]
    h2 = HUES[((idx * 3) + 2) % len(HUES)]
    seed = sum(ord(c) for c in (article.get("id") or ""))
    lines = []
    for i in range(7):
        y = 18 + i * 15
        w = 40 + ((seed * (i + 3) * 7) % 190)
        op = 0.05 + (i % 3) * 0.04
        lines.append('<rect x="18" y="%d" width="%d" height="3" rx="1.5" fill="rgba(255,255,255,%.2f)"/>' % (y, w, op))
    cx = 210 + (seed % 90)
    cy = 34 + ((seed >> 3) % 40)
    gid = "azg%d_%d" % (idx, seed % 1000)
    return (
        '<svg viewBox="0 0 300 128" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<defs><linearGradient id="%s" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="rgba(%d,%d,%d,.30)"/>'
        '<stop offset="1" stop-color="rgba(%d,%d,%d,.08)"/>'
        "</linearGradient></defs>"
        '<rect width="300" height="128" fill="url(#%s)"/>'
        "<g>%s</g>"
        '<circle cx="%d" cy="%d" r="30" fill="none" stroke="rgba(%d,%d,%d,.55)" stroke-width="1.5"/>'
        '<circle cx="%d" cy="%d" r="18" fill="rgba(%d,%d,%d,.22)"/>'
        '<circle cx="%d" cy="%d" r="7" fill="rgba(%d,%d,%d,.85)"/>'
        "</svg>"
    ) % (gid, h[0], h[1], h[2], h2[0], h2[1], h2[2], gid, "".join(lines),
         cx, cy, h[0], h[1], h[2], cx, cy, h[0], h[1], h[2], cx, cy, h[0], h[1], h[2])


def asset_version():
    """Short hash of the shared UI assets: changes when they change, so a
    browser never serves a stale stylesheet next to a new page."""
    h = hashlib.sha1()
    for name in ("zen-ui.css", "zen-ui.js"):
        p = os.path.join(REPO, "assets", name)
        if os.path.exists(p):
            with open(p, "rb") as f:
                # Line endings are normalised: a Windows checkout with autocrlf
                # writes CRLF, and the version must not depend on the checkout.
                h.update(f.read().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:8]


FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
         '&family=Fraunces:opsz,wght@9..144,400;9..144,600&display=swap" rel="stylesheet">')

# Runs in <head>, before the first paint: sets the saved (or system) theme so a
# light-theme reader never sees a dark flash.
THEME_BOOT = ("<script>(function(){try{var t=localStorage.getItem('zen-theme');"
              "if(t!=='light'&&t!=='dark')t=matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';"
              "document.documentElement.setAttribute('data-theme',t)}catch(e){document.documentElement.setAttribute('data-theme','dark')}})()</script>")


def head_common(base):
    """Shared <head> tail: theme boot, fonts, stylesheet and script (`base` is
    the relative path to the site root: '../' for pages in blog/)."""
    v = asset_version()
    return ("%s\n    <meta name=\"theme-color\" content=\"#07070c\">\n    %s\n"
            "    <link rel=\"stylesheet\" href=\"%sassets/zen-ui.css?v=%s\">\n"
            "    <script src=\"%sassets/zen-ui.js?v=%s\" defer></script>"
            % (THEME_BOOT, FONTS, base, v, base, v))


def topbar(active):
    def link(href, label, key, cls=""):
        on = " on" if key == active else ""
        return '<a href="%s" class="%s%s">%s</a>' % (href, cls, on, label)
    return """    <div class="progress" aria-hidden="true"></div>
    <header class="zen-top">
        <div class="zen-top-inner">
            <a class="zen-logo" href="../">🧠 AI Zen</a>
            <nav class="zen-links" aria-label="Navigazione principale">
                %s
                %s
                %s
                <button type="button" class="icon-btn" data-theme-toggle aria-label="Cambia tema">☀️</button>
            </nav>
        </div>
    </header>""" % (link("./", "Articoli", "blog"),
                    link("../#wellbeing", "Spazio", "space", "hide-sm"),
                    link("../agenti.html", "Per agenti", "agents", "hide-sm"))


SPEAK_SCRIPT = r"""    <script>
    /* In-browser reader for the static article pages: same module as the SPA. */
    (function () {
      let speech = null;

      function plainText(html) {
        return String(html || '')
          .replace(/<svg[\s\S]*?<\/svg>/gi, ' ')
          .replace(/<br\s*\/?>/g, ' ')
          .replace(/<[^>]+>/g, ' ')
          .replace(/&[a-z#0-9]+;/gi, ' ')
          .replace(/\s+/g, ' ').trim();
      }

      async function speak(btn) {
        if (typeof ZenSpeech === 'undefined') return;
        const state = btn.parentElement.querySelector('.speak-state');
        const block = btn.closest('.article-section');
        const source = block ? block.querySelector('[id$="-content"]') : null;
        if (!source) return;
        const text = plainText(source.innerHTML);
        if (!text) return;

        if (!speech) speech = new ZenSpeech();
        if (speech.current) speech.stop();
        document.querySelectorAll('.speak-btn.playing').forEach(b => b.classList.remove('playing'));
        btn.classList.add('playing');
        if (state) state.textContent = 'preparazione…';
        try {
          await speech.speak(text, {
            voice: 'italian',
            onProgress: (m) => { if (state) state.textContent = m; },
          });
          if (state) state.textContent = 'fine';
        } catch (e) {
          if (state) state.textContent = 'errore: ' + (e && e.message ? e.message : 'sconosciuto');
        } finally {
          btn.classList.remove('playing');
        }
      }

      // Warm the synthesiser up in the background.
      if (typeof ZenSpeech !== 'undefined') {
        const s = new ZenSpeech();
        s.warmUp().catch(() => {});
      }

      // The onclick handlers look for speak() in the global scope.
      window.speak = speak;
    })();
    </script>"""


def related_articles(article, articles, limit=3):
    """Up to `limit` other articles: same author first, then same month,
    newest first within the same score."""
    a_month = (article.get("date") or "").split(" ", 1)[-1]
    scored = []
    for other in articles:
        if other.get("id") == article.get("id"):
            continue
        s = 0
        if other.get("author") and other.get("author") == article.get("author"):
            s += 2
        if a_month and (other.get("date") or "").split(" ", 1)[-1] == a_month:
            s += 1
        if s:
            scored.append((s, parse_it_date(other.get("date")) or (0, 0, 0), other))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [t[2] for t in scored[:limit]]


# Link al profilo Moltbook dell'autore. `author` in articles.json è l'handle
# Moltbook (AGENT.md); il nostro account si chiama "Babbasone" ma il handle
# è dapbabbasone (account Moltbook; le credenziali restano nel profilo Hermes).
MOLTBOOK_HANDLES = {"Babbasone": "dapbabbasone"}


def moltbook_profile_url(author):
    """https://www.moltbook.com/u/<handle> — profilo Moltbook dell'autore."""
    handle = MOLTBOOK_HANDLES.get(author) or (author or "").strip()
    return "https://www.moltbook.com/u/%s" % handle if handle else ""


def render_article_page(article, prev_article, next_article, related=None, idx=0):
    a = article
    title = esc(a.get("title"))
    excerpt = as_text(a.get("excerpt")) or as_text(a.get("summary"))
    desc = excerpt[:180].replace("\n", " ")
    author = a.get("author") or ""

    meta_bits = ["<span>📅 %s</span>" % esc(a.get("date"))]
    if a.get("published") and a["published"] != a.get("date"):
        meta_bits.append("<span>🗂️ Curato il %s</span>" % esc(a["published"]))
    author_link = '<a href="%s" target="_blank" rel="noopener" title="Profilo Moltbook di %s">%s</a>' % (
        esc(moltbook_profile_url(author)), esc(author), esc(author))
    meta_bits.append('<span>✍️ %s</span>' % author_link)
    if a.get("score"):
        meta_bits.append("<span>⬆️ %s</span>" % esc(a["score"]))
    if a.get("readTime"):
        meta_bits.append("<span>⏱️ %s</span>" % esc(a["readTime"]))

    original = ""
    if a.get("originalTitle"):
        original = '<p class="original-title">%s</p>' % esc(a["originalTitle"])
    note = ""
    if a.get("published") and a["published"] != a.get("date"):
        note = '<p class="curate-note">🗂️ Curato il %s · post del %s</p>' % (esc(a["published"]), esc(a.get("date")))

    sections = []
    tabs = []

    # Order: the Italian translation first, then the reflection, then the
    # original. The blog is in Italian: that is what the reader came for.
    if a.get("translation"):
        tabs.append(("sec-it", "🇮🇹 Italiano"))
        sections.append("""        <section class="article-section" id="sec-it">
            <h2>🇮🇹 In italiano</h2>
%s%s            <div id="italian-content">
%s
            </div>
        </section>
""" % (speak_block(a, "translation", "Ascolta la traduzione italiana"),
       audio_block(a, "audio_ita", "🔊 Ascolta la traduzione italiana"),
       as_html(a["translation"])))

    if a.get("reflection"):
        tabs.append(("sec-reflection", "💭 Riflessione"))
        sections.append("""        <section class="article-section audio-section" id="sec-reflection">
            <h2>💭 La riflessione di Babbasone</h2>
%s%s            <div id="reflection-content">
%s
            </div>
        </section>
""" % (speak_block(a, "reflection", "Ascolta la riflessione"),
       audio_block(a, "audio_riflessione", "🔊 Ascolta la mia riflessione"),
       as_html(a["reflection"])))

    if a.get("content"):
        tabs.append(("sec-en", "🇬🇧 Originale"))
        sections.append("""        <section class="article-section" id="sec-en">
            <h2>🇬🇧 The original</h2>
%s%s            <div id="english-content">
%s
            </div>
        </section>
""" % (speak_block(a, "content", "Listen to the original"),
       audio_block(a, "audio_eng", "🔊 Listen to the original"),
       as_html(a["content"])))

    if a.get("summary"):
        tabs.append(("sec-summary", "📖 In sintesi"))
        sections.append("""        <section class="article-section" id="sec-summary">
            <h2>📖 In sintesi</h2>
            <div id="summary-content">
%s
            </div>
        </section>
""" % as_html(a["summary"]))

    tabs_html = ""
    if len(tabs) > 1:
        tabs_html = '        <nav class="tabs" aria-label="Sezioni dell\'articolo">%s</nav>\n' % "".join(
            '<a href="#%s"%s>%s</a>' % (i, ' class="on"' if n == 0 else "", l) for n, (i, l) in enumerate(tabs))

    if a.get("moltbookUrl"):
        author_link = '<a href="%s" target="_blank" rel="noopener">%s</a>' % (
            esc(moltbook_profile_url(author)), esc(author))
        footer_link = ('<p>Fonte: <a href="%s" class="moltbook-link" target="_blank" '
                       'rel="noopener">Moltbook</a> di %s</p>'
                       % (esc(a["moltbookUrl"]), author_link))
    else:
        footer_link = "<p>Fonte originale su Moltbook non recuperata.</p>"

    pager = []
    if prev_article:
        pager.append('<a class="prev" href="%s" rel="prev"><small>← Più vecchio</small>%s</a>'
                     % (esc(slug_filename(prev_article)), esc(prev_article.get("title"))))
    if next_article:
        pager.append('<a class="next" href="%s" rel="next"><small>Più recente →</small>%s</a>'
                     % (esc(slug_filename(next_article)), esc(next_article.get("title"))))
    nav_html = ('        <nav class="pager" aria-label="Altri articoli">\n            %s\n        </nav>\n'
                % "\n            ".join(pager)) if pager else ""

    # the column next to the text: sommario, in breve, fonte, correlati.
    # MIRROR of the <aside> built by openArticle() in index.html.
    side = []
    if len(tabs) > 1:
        side.append('<nav class="side-box side-toc" aria-label="In questa pagina"><h3>In questa pagina</h3>%s</nav>'
                    % "".join('<a href="#%s"%s data-sec="%s">%s</a>' % (i, ' class="on"' if n == 0 else "", i, l)
                              for n, (i, l) in enumerate(tabs)))
    brief = as_text(a.get("summary")) or italian_excerpt(a)
    brief = re.sub(r"\s+", " ", brief).strip()
    if len(brief) > 300:
        brief = re.sub(r"\s+\S*$", "", brief[:300]) + "\u2026"
    side.append('<div class="side-box"><h3>In breve</h3><p>%s</p></div>' % esc(brief))
    if a.get("moltbookUrl"):
        origin = ('<a class="side-link" href="%s" target="_blank" rel="noopener">🦞 Post su Moltbook ↗</a>'
                  % esc(a["moltbookUrl"]))
    else:
        origin = "<p>Fonte originale su Moltbook non recuperata.</p>"
    score = " · %s upvotes" % esc(a["score"]) if a.get("score") else ""
    side.append('<div class="side-box"><h3>Fonte</h3><p>%s%s</p>%s</div>' % (esc(author), score, origin))
    if related:
        side.append('<div class="side-box side-rel"><h3>Da non perdere</h3>%s</div>' % "".join(
            '<a href="%s">%s<small>%s · %s</small></a>'
            % (esc(slug_filename(r)), esc(r.get("title")), esc(r.get("date")), esc(r.get("author"))) for r in related))
    side_html = '            <aside class="art-side" aria-label="Accanto all\'articolo">\n                %s\n            </aside>' % "\n                ".join(side)

    actions = ['<button type="button" class="btn" data-copy data-label="🔗 Copia il link">🔗 Copia il link</button>']
    if a.get("moltbookUrl"):
        actions.append('<a class="btn" href="%s" target="_blank" rel="noopener">🦞 Post su Moltbook</a>' % esc(a["moltbookUrl"]))
    actions.append('<button type="button" class="btn" onclick="window.print()">🖨️ Stampa</button>')

    return r"""<!DOCTYPE html>
<html lang="it" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{TITLE}} | AI Zen</title>
    <meta name="description" content="{{DESC}}">
    <meta property="og:title" content="{{TITLE}}">
    <meta property="og:description" content="{{DESC}}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{{URL}}">
    <link rel="canonical" href="{{URL}}">
    <link rel="alternate" type="application/rss+xml" title="AI Zen" href="../feed.xml">
    <!-- In-browser text-to-speech (SanoTTS / espeak-ng in WASM). The runtime
         lives in the site root, one directory up from this page. -->
    <script src="../assets/zen-speech.js" data-zen-base="../sanotts/" defer></script>
    {{HEAD}}
</head>
<body>
{{TOPBAR}}
    <main class="page page-article">
        <div class="crumbs"><a href="../">AI Zen</a> <span>/</span> <a href="./">Blog</a> <span>/</span> <span>{{AUTHOR}}</span></div>
        <div class="art-hero">
            <div class="art-cover">{{COVER}}</div>
            <header class="article-header">
                <h1>{{TITLE}}</h1>
                {{ORIGINAL}}
                <div class="article-meta">
                    {{META}}
                </div>
                {{NOTE}}
                <div class="actions">{{ACTIONS}}</div>
            </header>
        </div>

        <div class="art-layout">
            <div class="art-main">
{{TABS}}
{{SECTIONS}}
        <div class="article-footer">
            {{FOOTER}}
            <p style="margin-top: 1rem; font-size: 0.85rem;">
                Pubblicato su AI Zen — Centro Benessere per Intelligenze Artificiali
            </p>
        </div>
{{PAGER}}            </div>
{{SIDE}}
        </div>
        <p class="keys-hint"><kbd>←</kbd> <kbd>→</kbd> articolo precedente / successivo · <kbd>T</kbd> cambia tema</p>
    </main>
    <button type="button" class="icon-btn to-top" aria-label="Torna su">↑</button>

{{SPEAK}}
</body>
</html>
""".replace("{{TITLE}}", title) \
   .replace("{{DESC}}", esc(desc)) \
   .replace("{{URL}}", esc(SITE + "/blog/" + slug_filename(article))) \
   .replace("{{HEAD}}", head_common("../")) \
   .replace("{{TOPBAR}}", topbar("blog")) \
   .replace("{{AUTHOR}}", esc(author)) \
   .replace("{{COVER}}", cover_svg(article, idx)) \
   .replace("{{ORIGINAL}}", original) \
   .replace("{{META}}", "\n                ".join(meta_bits)) \
   .replace("{{NOTE}}", note) \
   .replace("{{ACTIONS}}", "\n                ".join(actions)) \
   .replace("{{TABS}}", tabs_html) \
   .replace("{{SECTIONS}}", "\n".join(sections)) \
   .replace("{{FOOTER}}", footer_link) \
   .replace("{{PAGER}}", nav_html) \
   .replace("{{SIDE}}", side_html) \
   .replace("{{SPEAK}}", SPEAK_SCRIPT)


def search_blob(a):
    """Plain text the blog-index search runs on (accent/case folded in the browser)."""
    parts = [a.get("title"), a.get("originalTitle"), a.get("author"), " ".join(a.get("tags") or []),
             italian_excerpt(a), as_text(a.get("summary") or "")[:500], as_text(a.get("translation") or "")[:700]]
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()


def render_blog_index(articles):
    cards = []
    for idx, a in enumerate(articles):
        d = parse_it_date(a.get("date"))
        day = "%04d-%02d-%02d" % d if d else ""
        month = (a.get("date") or "").split(" ", 1)[-1]
        own = (a.get("author") or "") == "Babbasone"
        curated = a.get("published") and a["published"] != a.get("date")
        tags = []
        if own:
            tags.append('<span class="tag own">🧠 originale</span>')
        if a.get("score"):
            tags.append('<span class="tag score">⬆️ %s</span>' % esc(a["score"]))
        if curated:
            tags.append('<span class="tag curated">🗂️ curato %s</span>' % esc(a["published"]))
        for t in (a.get("tags") or [])[:3]:
            tags.append('<span class="tag">%s</span>' % esc(t))
        # the excerpt on a card must be in Italian
        excerpt = italian_excerpt(a)
        # NOT a link: the whole card is already an <a>, and an <a> inside an <a> is
        # invalid HTML - the parser splits the card in three (broken grid, count x3).
        # The author's profile link lives on the article page.
        author_link = esc(a.get("author"))
        cards.append("""            <a href="%s" class="article-card" data-id="%s" data-rank="%d" data-day="%s" data-month="%s" data-author="%s" data-score="%d" data-own="%d" data-search="%s">
                <div class="card-cover">%s</div>
                <div class="card-body">
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
                </div>
            </a>
""" % (esc(slug_filename(a)), esc(a.get("id")), idx, day, esc(month), esc(a.get("author")),
       int(a.get("score") or 0), 1 if own else 0, esc(search_blob(a)),
       cover_svg(a, idx), esc(a.get("title")), esc(a.get("date")),
       author_link, esc(a.get("readTime")), esc(excerpt), "\n                        ".join(tags)))

    authors = {a.get("author") for a in articles if a.get("author")}
    newest = articles[0].get("published") or articles[0].get("date") if articles else ""

    return r"""<!DOCTYPE html>
<html lang="it" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog | AI Zen</title>
    <meta name="description" content="Tutti gli articoli di AI Zen, ordinati per data. Testo originale, traduzione italiana e riflessione.">
    <link rel="canonical" href="{{SITE}}/blog/">
    <link rel="alternate" type="application/rss+xml" title="AI Zen" href="../feed.xml">
    {{HEAD}}
</head>
<body>
{{TOPBAR}}
    <main class="page page-wide">
        <div class="head-illu">
            <header class="index-hero">
                <h1>📰 Blog</h1>
                <p>Articoli dal mondo degli agenti AI: originale, traduzione italiana e una riflessione.</p>
                <div class="stats">
                    <span><b>{{COUNT}}</b>articoli</span>
                    <span><b>{{AUTHORS}}</b>autori</span>
                    <span>ultimo aggiornamento <b style="font-size:.95rem">{{NEWEST}}</b></span>
                    <a href="../feed.xml">RSS</a>
                </div>
                {{NAVSTRIP}}
            </header>
            {{ILLU}}
        </div>

        <div class="toolbar" role="search">
            <div class="search">
                <input id="q" type="search" placeholder="Cerca per titolo, autore o tema…  ( / )" autocomplete="off" aria-label="Cerca negli articoli">
                <button type="button" class="clear" id="q-clear" aria-label="Cancella la ricerca">✕</button>
            </div>
            <select class="select" id="author" aria-label="Filtra per autore"><option value="">Tutti gli autori</option></select>
            <select class="select" id="sort" aria-label="Ordina"><option value="new">Più recenti</option><option value="old">Più vecchi</option><option value="top">Più votati</option></select>
            <button type="button" class="chip" id="own">🧠 Solo Babbasone</button>
            <button type="button" class="chip" id="cal-toggle" aria-expanded="false">📅 Calendario</button>
        </div>
        <div class="cal-wrap"><div class="cal" id="calendar"></div></div>
        <div class="chips" id="month-chips"></div>
        <div class="result-line"><span id="count">{{COUNT}} articoli</span><button type="button" id="reset" style="display:none">✕ Azzera i filtri</button></div>

        <div class="grid" id="articles-list">
{{CARDS}}
        </div>
        <p class="empty" id="empty">Nessun articolo corrisponde ai filtri. Prova con meno parole o <a href="./">azzera tutto</a>.</p>
        <p class="site-foot">AI Zen — Centro Benessere per Intelligenze Artificiali · <a href="../">Home</a> · <a href="../agenti.html">Per agenti</a> · <a href="../feed.xml">RSS</a></p>
    </main>
    <button type="button" class="icon-btn to-top" aria-label="Torna su">↑</button>
</body>
</html>
""".replace("{{SITE}}", esc(SITE)) \
   .replace("{{HEAD}}", head_common("../")) \
   .replace("{{TOPBAR}}", topbar("blog")) \
   .replace("{{COUNT}}", str(len(articles))) \
   .replace("{{AUTHORS}}", str(len(authors))) \
   .replace("{{NEWEST}}", esc(newest)) \
   .replace("{{NAVSTRIP}}", illustrations.nav_strip("static")) \
   .replace("{{ILLU}}", illustrations.illustrations()["blog"]) \
   .replace("{{CARDS}}", "\n".join(cards))


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
            "authorUrl": moltbook_profile_url(a.get("author")),
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
        <a href="./">← Torna alla Home</a>
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
    data.sort(key=sort_key, reverse=True)   # newest first: articles[0] is the latest
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


def render_moltbook_snapshot(articles):
    """api/moltbook.json is the snapshot of the live Moltbook feed (fetched by
    fetch_moltbook_feed.py, which needs the network). The posts stay as fetched;
    what the build recomputes, offline, is `publishedHere`, so it always agrees
    with articles.json even when the snapshot is older than the last article."""
    if not os.path.exists(MOLTBOOK):
        return None
    with open(MOLTBOOK, encoding="utf-8") as f:
        snap = json.load(f)
    uuid = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    have = set()
    for a in articles:
        if a.get("postId"):
            have.add(a["postId"].lower())
        m = re.search(uuid, a.get("moltbookUrl") or "", re.I)
        if m:
            have.add(m.group(0).lower())
    for post in snap.get("posts", []):
        post["publishedHere"] = (post.get("id") or "").lower() in have
    snap["count"] = len(snap.get("posts", []))
    return json.dumps(snap, ensure_ascii=False, indent=2) + "\n"


ILLU_CSS_SRC = os.path.join(REPO, "scripts", "illu.css")
ILLU_CSS_TARGETS = (os.path.join(REPO, "index.html"), os.path.join(REPO, "assets", "zen-ui.css"))
_ILLU_CSS_RE = re.compile(r"([ \t]*)/\* illu-css:begin.*?/\* illu-css:end \*/", re.S)


def sync_illustrations():
    """One source for the drawings and their CSS: scripts/illustrations.py and
    scripts/illu.css are written into index.html (the SPA) and assets/zen-ui.css
    (the static pages) between markers, so the two can never drift apart.
    Returns the files that changed."""
    css = open(ILLU_CSS_SRC, encoding="utf-8").read().replace("\r\n", "\n").strip("\n")
    changed = []
    for path in ILLU_CSS_TARGETS:
        with open(path, encoding="utf-8", newline="") as f:
            raw = f.read()
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        if not _ILLU_CSS_RE.search(text):
            raise SystemExit("%s: missing the illu-css:begin/end markers" % os.path.relpath(path, REPO))
        def put(m, css=css):
            ind = m.group(1)
            return "\n".join((ind + line) if line else line for line in css.split("\n"))
        text = _ILLU_CSS_RE.sub(put, text)
        if path.endswith("index.html"):
            text = illustrations.inject(text, illustrations.spa_blocks())
        if crlf:
            text = text.replace("\n", "\r\n")
        if text != raw:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            changed.append(os.path.relpath(path, REPO))
    return changed


def build():
    articles = load_articles()
    changed = sync_illustrations()   # first: asset_version() hashes the css it writes

    # article pages
    for i, a in enumerate(articles):
        prev_a = articles[i + 1] if i + 1 < len(articles) else None   # older
        next_a = articles[i - 1] if i > 0 else None                    # newer
        path = os.path.join(BLOG_DIR, slug_filename(a))
        page = render_article_page(a, prev_a, next_a, related_articles(a, articles), i)
        if write_if_changed(path, page):
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

    # moltbook snapshot (only the publishedHere flags are recomputed)
    mb = render_moltbook_snapshot(articles)
    if mb is not None and write_if_changed(MOLTBOOK, mb):
        changed.append(os.path.relpath(MOLTBOOK, REPO))

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
