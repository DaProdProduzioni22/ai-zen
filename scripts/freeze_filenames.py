#!/usr/bin/env python3
"""Freeze each article's published filename into articles.json.

A published URL must never change. The generator derives the filename from the
post date, but for pages that are already live the existing filename wins.
This script reads the filenames currently on disk and stores them as `file`
on each article, so later builds reproduce exactly the same URLs.
"""
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(REPO, "articles.json")
BLOG = os.path.join(REPO, "blog")

# Files that must never be touched: the blog index.
RESERVED = {"index.html"}


def main():
    arts = json.load(open(ARTICLES, encoding="utf-8"))
    if isinstance(arts, dict):
        arts = list(arts.values())

    on_disk = {f for f in os.listdir(BLOG) if f.endswith(".html") and f not in RESERVED}

    frozen, generated = [], []
    for a in arts:
        slug = a.get("slug", "")
        # a live page whose stem ends with this slug
        matches = [f for f in on_disk if re.sub(r"^\d{4}-\d{2}-\d{2}-", "", f[:-5]) == slug]
        if matches:
            # prefer an exact "<slug>.html" (no date prefix) if it exists
            exact = [f for f in matches if f == slug + ".html"]
            chosen = sorted(exact or matches)[0]
            if a.get("file") != chosen:
                a["file"] = chosen
                frozen.append((slug, chosen))
        else:
            a.pop("file", None)
            generated.append(slug)

    with open(ARTICLES, "w", encoding="utf-8") as f:
        json.dump(arts, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("frozen filenames:", len(frozen))
    for slug, f in frozen:
        print("   %-56s -> %s" % (slug[:56], f))
    if generated:
        print("\nno live page yet (filename will be generated):")
        for s in generated:
            print("   ", s)


if __name__ == "__main__":
    main()
