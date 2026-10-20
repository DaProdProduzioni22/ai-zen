#!/usr/bin/env python3
"""Normalise the watchman article's content: it was stored as mixed text+HTML.

The stored value started with a plain sentence and then carried HTML paragraphs
("...success.</p><p>My notifier marked..."), so any renderer that trusted the
first character treated the whole thing as plain text and the HTML tags showed
up on the page. The clean text was recovered from the blog page; this script
stores it as consistent HTML.
"""
import json
import os
import re
import html

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(REPO, "articles.json")
TARGET = "my-watchman-failed-politely-for-two-weeks-and-i-thanked-it-lightningzero"


def strip_tags(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = re.sub(r"</p>", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def to_html(text):
    """Plain text -> <p> paragraphs, with **bold** turned into <strong>."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    out = []
    for p in paras:
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        out.append("<p>%s</p>" % p.replace("\n", "<br>"))
    return "".join(out)


def main():
    arts = json.load(open(ARTICLES, encoding="utf-8"))
    if isinstance(arts, dict):
        arts = list(arts.values())

    changed = []
    for a in arts:
        for field in ("content", "translation"):
            raw = a.get(field) or ""
            if not raw:
                continue
            # mixed: contains HTML tags but does not start with one
            has_tag = re.search(r"</?[a-zA-Z][^>]*>", raw)
            if has_tag and not raw.lstrip().startswith("<"):
                a[field] = to_html(strip_tags(raw))
                changed.append((a["id"], field))

    with open(ARTICLES, "w", encoding="utf-8") as f:
        json.dump(arts, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("normalised mixed text/HTML fields:", len(changed))
    for aid, field in changed:
        print("   %-52s %s" % (aid[:52], field))


if __name__ == "__main__":
    main()
