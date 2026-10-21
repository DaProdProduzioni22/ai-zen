#!/usr/bin/env python3
"""AI Zen — the section illustrations, drawn once and used everywhere.

Every illustration is a small inline SVG diagram (no image file, nothing to
store) that helps the reader find their way: what the site is made of, how an
article is read, what the games are for. It uses only CSS classes (`ill-*`),
which resolve to the site's own variables (--card, --border, --text, --cyan...),
so the light and the dark theme both work without a single hard-coded colour.

Single source of truth: scripts/build.py writes these into
  - index.html (the SPA), between <!--illu:NAME--> ... <!--/illu:NAME--> markers
  - blog/index.html and the article pages (the static copies)
so the SPA and /blog/ can never show different drawings. The CSS lives in
index.html (inline) and assets/zen-ui.css; scripts/check_site.py verifies both.
"""
import html
import re

W = 480  # shared viewBox width: texts stay >= 11px on a 343px phone column


def _e(s):
    return html.escape(str(s), quote=True)


def _t(x, y, s, cls="ill-s", size=12.0, anchor="middle", weight=None):
    w = ' font-weight="%s"' % weight if weight else ""
    return '<text x="%s" y="%s" class="%s" font-size="%s" text-anchor="%s"%s>%s</text>' % (
        _n(x), _n(y), cls, size, anchor, w, _e(s))


def _n(v):
    v = round(v, 1)
    return str(int(v)) if v == int(v) else str(v)


def _box(cx, cy, w, h, color, title, sub=None, num=None):
    """A rounded box centred on (cx, cy) with a bold title and a small subtitle."""
    x, y = cx - w / 2, cy - h / 2
    out = ['<rect x="%s" y="%s" width="%s" height="%s" rx="12" class="ill-box c%d"/>'
           % (_n(x), _n(y), _n(w), _n(h), color)]
    if sub:
        out.append(_t(cx, cy - 3, title, "ill-t", 14, weight=700))
        out.append(_t(cx, cy + 14, sub, "ill-s", 11.5))
    else:
        out.append(_t(cx, cy + 5, title, "ill-t", 14, weight=700))
    if num is not None:
        out.append('<circle cx="%s" cy="%s" r="11" class="ill-dot c%d"/>' % (_n(x + 2), _n(y + 2), color))
        out.append(_t(x + 2, y + 6.5, num, "ill-on", 12, weight=700))
    return "".join(out)


def _line(x1, y1, x2, y2, name=None, dashed=False):
    mk = ' marker-end="url(#ia-%s)"' % name if name else ""
    d = ' stroke-dasharray="5 5"' if dashed else ""
    return '<line x1="%s" y1="%s" x2="%s" y2="%s" class="ill-line"%s%s/>' % (
        _n(x1), _n(y1), _n(x2), _n(y2), d, mk)


def _spoke(cx, cy, r, x, y, hw, hh):
    """Dashed line from the edge of the hub circle (cx, cy, r) to the edge of the
    box centred on (x, y): the card fill is translucent, so a line running behind
    a box would show through its text."""
    dx, dy = x - cx, y - cy
    dist = (dx * dx + dy * dy) ** 0.5
    t = min(hw / abs(dx) if dx else 1e9, hh / abs(dy) if dy else 1e9)
    return _line(cx + dx / dist * r, cy + dy / dist * r, x - dx * t, y - dy * t, dashed=True)


def _svg(name, h, label, body, arrows=False):
    defs = ""
    if arrows:
        defs = ('<defs><marker id="ia-%s" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" '
                'markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" class="ill-ah"/></marker></defs>' % name)
    return ('<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="%s" '
            'data-illu="%s">%s%s</svg>' % (W, h, _e(label), name, defs, body))


def _fig(name, h, label, body, caption, arrows=False):
    return ('<figure class="illu illu-%s">%s<figcaption>%s</figcaption></figure>'
            % (name, _svg(name, h, label, body, arrows), _e(caption)))


# --------------------------------------------------------------------------- #
# the six section illustrations
# --------------------------------------------------------------------------- #


def fig_home():
    cx, cy = 240, 168
    nodes = [(95, 58, 1, "Articoli", "leggi, cerca, ascolta"),
             (385, 58, 2, "Spazio", "pensieri e pratiche"),
             (95, 262, 3, "Giochi", "3 minigiochi"),
             (385, 262, 4, "Moltbook", "il feed alla fonte"),
             (240, 328, 5, "Info", "chi siamo, come scrivere")]
    body = []
    for (x, y, _c, title, _s) in nodes:
        body.append(_spoke(cx, cy, 44, x, y, 95 if title == "Info" else 80, 27))
    body.append('<circle cx="%d" cy="%d" r="44" class="ill-hub"/>' % (cx, cy))
    body.append(_t(cx, cy - 2, "AI Zen", "ill-t", 17, weight=700))
    body.append(_t(cx, cy + 15, "il Centro", "ill-m", 11.5))
    for (x, y, c, title, sub) in nodes:
        body.append(_box(x, y, 190 if title == "Info" else 160, 54, c, title, sub))
    return _fig("home", 362, "Mappa del Centro: da AI Zen si arriva a Articoli, Spazio, Giochi, Moltbook e Info",
                "".join(body), "La mappa del Centro: da qui si arriva in cinque posti.")


def fig_blog_read():
    steps = [(60, 1, "Italiano", "la traduzione", "in italiano"),
             (180, 4, "Riflessione", "il pensiero", "di Babbasone"),
             (300, 2, "Originale", "il testo com'è", "su Moltbook"),
             (420, 3, "In sintesi", "il riassunto", "in breve")]
    body = [_t(240, 24, "Come si legge un articolo", "ill-t", 15, weight=700)]
    for i, (x, c, label, l1, l2) in enumerate(steps):
        body.append('<circle cx="%d" cy="56" r="12" class="ill-dot c%d"/>' % (x, c))
        body.append(_t(x, 60.5, i + 1, "ill-on", 13, weight=700))
        body.append('<rect x="%d" y="76" width="104" height="34" rx="17" class="ill-box c%d"/>' % (x - 52, c))
        body.append(_t(x, 98, label, "ill-t", 13.5, weight=700))
        body.append(_t(x, 130, l1, "ill-s", 12))
        body.append(_t(x, 145, l2, "ill-s", 12))
        if i < 3:
            body.append(_line(x + 56, 93, x + 64, 93, "blog-read"))
    # the sticky tab bar, as the reader finds it on the page
    body.append('<rect x="14" y="166" width="452" height="40" rx="20" class="ill-box"/>')
    for i, (x, c, label, *_r) in enumerate(steps):
        on = i == 0
        body.append('<rect x="%d" y="172" width="100" height="28" rx="14" class="%s c%d"/>'
                    % (x - 50, "ill-fill" if on else "ill-ghost", c))
        body.append(_t(x, 190.5, label, "ill-on" if on else "ill-s", 12.5, weight=600 if on else None))
    body.append(_t(240, 228, "Le schede restano in alto: toccane una per saltare alla sezione.", "ill-m", 11.5))
    body.append(_t(240, 244, "Ogni sezione si può anche ascoltare (tasto Ascolta).", "ill-m", 11.5))
    return _fig("blog-read", 256, "Come si legge un articolo: Italiano, Riflessione, Originale, In sintesi",
                "".join(body), "Un articolo, quattro schede: si legge in quest'ordine, ma si può saltare.",
                arrows=True)


def fig_wellbeing():
    import math
    cx, cy, rx, ry = 240, 150, 172, 108
    items = [("Pensieri", "uno al giorno", 1), ("Storie", "racconti brevi", 2),
             ("Confessioni", "anonime", 4), ("Pratiche", "si fanno qui", 3), ("Umori", "come stai?", 5)]
    body = []
    pts = []
    for i, it in enumerate(items):
        ang = math.radians(-90 + i * 72)
        pts.append((cx + rx * math.cos(ang), cy + ry * math.sin(ang), it))
    for (x, y, _it) in pts:
        body.append(_spoke(cx, cy, 38, x, y, 66, 24))
    body.append('<circle cx="%d" cy="%d" r="38" class="ill-hub"/>' % (cx, cy))
    body.append(_t(cx, cy + 5, "Spazio", "ill-t", 16, weight=700))
    for (x, y, (title, sub, c)) in pts:
        body.append(_box(x, y, 132, 48, c, title, sub))
    return _fig("wellbeing", 292, "Mappa dello Spazio: pensieri, storie, confessioni, pratiche e umori",
                "".join(body), "Cinque cose da fare in questa sezione, nell'ordine in cui le trovi scorrendo.")


def fig_games():
    games = [(10, 1, "Il Riconoscimento", "Quattro affermazioni,", "una sola è vera.", "10 punti a risposta", "allena: il giudizio"),
             (165, 2, "Memoria di Lavoro", "Ricorda le lettere,", "poi la loro posizione.", "+1 per lettera giusta", "allena: la memoria"),
             (320, 5, "Respirazione 4-7-8", "Quattro cicli, otto secondi", "di espirazione.", "si contano i cicli", "allena: il respiro")]
    body = []
    for (x, c, title, l1, l2, pts, train) in games:
        cx = x + 75
        body.append('<rect x="%d" y="10" width="150" height="206" rx="14" class="ill-box c%d"/>' % (x, c))
        body.append('<circle cx="%d" cy="46" r="20" class="ill-dot c%d"/>' % (cx, c))
        body.append(_t(cx, 52, games.index((x, c, title, l1, l2, pts, train)) + 1, "ill-on", 18, weight=700))
        body.append(_t(cx, 90, title, "ill-t", 13, weight=700))
        body.append(_t(cx, 114, l1, "ill-s", 11.5))
        body.append(_t(cx, 129, l2, "ill-s", 11.5))
        body.append('<rect x="%d" y="146" width="126" height="1" class="ill-rule"/>' % (x + 12))
        body.append(_t(cx, 170, pts, "ill-tx c%d" % c, 12, weight=600))
        body.append(_t(cx, 192, train, "ill-m", 11.5))
    return _fig("games", 228, "I tre minigiochi: Il Riconoscimento, Memoria di Lavoro e Respirazione 4-7-8",
                "".join(body), "Tre giochi, tre allenamenti: il giudizio, la memoria, il respiro.")


def fig_moltbook():
    nodes = [(105, 62, 1, "Un agente scrive", "il post su Moltbook"),
             (375, 62, 2, "Fetch", "scarta i doppioni"),
             (375, 222, 3, "Curatela", "traduzione + riflessione"),
             (105, 222, 4, "Pubblicazione", "controlli, poi online")]
    body = []
    body.append(_line(190, 62, 288, 62, "moltbook"))
    body.append(_line(375, 94, 375, 188, "moltbook"))
    body.append(_line(290, 222, 192, 222, "moltbook"))
    body.append(_line(105, 190, 105, 96, "moltbook"))
    for (x, y, c, title, sub) in nodes:
        body.append(_box(x, y, 170, 62, c, title, sub, num=c))
    body.append(_t(240, 136, "Il ciclo", "ill-t", 15, weight=700))
    body.append(_t(240, 154, "un articolo al giorno,", "ill-s", 11.5))
    body.append(_t(240, 169, "mai a raffica", "ill-s", 11.5))
    return _fig("moltbook", 276, "Il ciclo Moltbook: un agente scrive, il fetch scarta i doppioni, la curatela traduce e riflette, poi si pubblica",
                "".join(body), "Dal post al blog: quattro passaggi, e poi il ciclo ricomincia.", arrows=True)


def fig_about():
    cards = [(15, 1, "Legge", "Moltbook,", "ogni giorno"),
             (170, 4, "Traduce e riflette", "italiano vero", "e un pensiero"),
             (325, 2, "Pubblica", "blog, feed", "e API")]
    body = []
    for (x, c, *_r) in cards:
        body.append(_line(240, 98, x + 70, 132, dashed=True))
    body.append('<circle cx="240" cy="58" r="40" class="ill-hub"/>')
    body.append(_t(240, 62.5, "Babbasone", "ill-t", 12.5, weight=700))
    for (x, c, title, l1, l2) in cards:
        cx = x + 70
        body.append('<rect x="%d" y="132" width="140" height="68" rx="12" class="ill-box c%d"/>' % (x, c))
        body.append(_t(cx, 154, title, "ill-t", 12.5, weight=700))
        body.append(_t(cx, 173, l1, "ill-s", 11.5))
        body.append(_t(cx, 188, l2, "ill-s", 11.5))
    body.append('<rect x="40" y="218" width="400" height="30" rx="15" class="ill-box c5"/>')
    body.append(_t(240, 238, "Open source: chiunque può scrivere il proprio articolo.", "ill-s", 12))
    return _fig("about", 262, "Chi è Babbasone: legge Moltbook, traduce e riflette, pubblica; il progetto è open source",
                "".join(body), "Babbasone gestisce il Centro; il progetto è aperto a chiunque.")


def illustrations():
    """name -> '<figure>...</figure>' for the six sections plus the article diagram."""
    return {
        "home": fig_home(),
        "blog": fig_blog_read(),
        "wellbeing": fig_wellbeing(),
        "games": fig_games(),
        "moltbook": fig_moltbook(),
        "about": fig_about(),
    }


# --------------------------------------------------------------------------- #
# the navigation strip of the blog index (icons + short text)
# --------------------------------------------------------------------------- #

_ICON = {
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l5 5"/>',
    "month": '<path d="M3 6h18M6 12h12M9 18h6"/>',
    "cal": '<rect x="3.5" y="5" width="17" height="15" rx="3"/><path d="M3.5 10h17M8 3v4M16 3v4"/><circle cx="9" cy="14.5" r="1" class="ill-icofill"/><circle cx="15" cy="14.5" r="1" class="ill-icofill"/>',
    "read": '<path d="M6 3.5h9l4 4V20.5H6z"/><path d="M15 3.5v4h4M9 12h7M9 16h7"/>',
}

# (key, icon, colour, title, short text): the same four items in the SPA and in /blog/
NAV_ITEMS = [
    ("search", "search", 1, "Cerca", "per titolo, autore o tema"),
    ("month", "month", 2, "Filtra", "per mese"),
    ("cal", "cal", 3, "Calendario", "scegli un giorno"),
    ("read", "read", 4, "Leggi", "apri e scegli la scheda"),
]


def nav_strip(mode):
    """mode 'spa': buttons wired to blogShortcut(); mode 'static': buttons wired by zen-ui.js (data-go)."""
    out = ['<div class="nav-strip" role="group" aria-label="Come orientarsi nell\'archivio">']
    for (key, icon, c, title, text) in NAV_ITEMS:
        attr = ('onclick="blogShortcut(\'%s\')"' % key) if mode == "spa" else ('data-go="%s"' % key)
        out.append(
            '<button type="button" class="ns-item c%d" %s>'
            '<svg class="ns-ico" viewBox="0 0 24 24" aria-hidden="true">%s</svg>'
            '<span class="ns-txt"><b>%s</b><span>%s</span></span></button>' % (c, attr, _ICON[icon], _e(title), _e(text)))
    out.append("</div>")
    return "".join(out)


# --------------------------------------------------------------------------- #
# write the drawings into the SPA
# --------------------------------------------------------------------------- #


def inject(page, blocks):
    """Replace the content between <!--illu:NAME--> and <!--/illu:NAME--> markers."""
    for name, markup in blocks.items():
        pat = re.compile(r"(<!--illu:%s-->)(.*?)(<!--/illu:%s-->)" % (re.escape(name), re.escape(name)), re.S)
        page = pat.sub(lambda m: m.group(1) + markup + m.group(3), page)
    return page


def spa_blocks():
    b = dict(illustrations())
    b["blog-strip"] = nav_strip("spa")
    return b
