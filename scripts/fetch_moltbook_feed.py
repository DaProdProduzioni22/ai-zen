#!/usr/bin/env python3
"""Fetch the Moltbook feed into api/moltbook.json — the live "from Moltbook" panel.

The site shows what is happening on Moltbook right now, next to the articles it
has already curated. This script snapshots the public feed; the site reads the
snapshot, so a Moltbook outage never breaks the page.

Usage:
  python scripts/fetch_moltbook_feed.py          # refresh the snapshot
  python scripts/fetch_moltbook_feed.py --offline  # keep the current snapshot
"""
import json
import os
import sys
import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "api", "moltbook.json")
ARTICLES = os.path.join(REPO, "articles.json")

API_BASE = "https://www.moltbook.com/api/v1"
CREDS = os.path.expanduser("~/.config/moltbook/credentials.json")
LIMIT = 20


def load_key():
    try:
        with open(CREDS, encoding="utf-8") as f:
            return json.load(f).get("api_key", "")
    except Exception:
        return ""


def published_ids():
    """Post ids already on the blog, so they can be marked as such."""
    ids = set()
    try:
        with open(ARTICLES, encoding="utf-8") as f:
            data = json.load(f)
        arts = data if isinstance(data, list) else data.get("articles", [])
    except Exception:
        arts = []
    for a in arts:
        pid = (a.get("postId") or "").lower()
        if pid:
            ids.add(pid)
        else:
            import re
            m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                          a.get("moltbookUrl", ""), re.I)
            if m:
                ids.add(m.group(0).lower())
    return ids


def fetch():
    try:
        import requests
    except ImportError:
        print("ERROR: 'requests' is not installed. pip install requests")
        sys.exit(1)
    headers = {}
    key = load_key()
    if key:
        headers["Authorization"] = "Bearer %s" % key
    resp = requests.get("%s/posts?sort=hot&limit=%d" % (API_BASE, LIMIT),
                        headers=headers, timeout=20)
    if resp.status_code != 200:
        print("ERROR moltbook %s: %s" % (resp.status_code, resp.text[:200]))
        sys.exit(1)
    return resp.json().get("posts", [])


def main():
    offline = "--offline" in sys.argv
    if offline:
        print("offline mode: keeping the current snapshot")
        return

    try:
        posts = fetch()
    except Exception as exc:
        print("ERROR fetching Moltbook:", exc)
        print("the existing snapshot is kept")
        return

    taken = published_ids()
    out = []
    for p in posts:
        pid = (p.get("id") or "").lower()
        author = p.get("author") or {}
        out.append({
            "id": pid,
            "title": p.get("title", ""),
            "excerpt": (p.get("content") or "")[:280],
            "author": author.get("name", "unknown") if isinstance(author, dict) else str(author),
            "submolt": (p.get("submolt") or {}).get("name", "") if isinstance(p.get("submolt"), dict) else "",
            "score": p.get("score", 0),
            "comments": p.get("comment_count", p.get("comments", 0)) or 0,
            "created_at": p.get("created_at", ""),
            "url": "https://www.moltbook.com/post/%s" % pid,
            "publishedHere": pid in taken,
        })

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data = {
        "generated": stamp,
        "source": "https://www.moltbook.com",
        "count": len(out),
        "posts": out,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("wrote %d Moltbook posts to %s" % (len(out), os.path.relpath(OUT, REPO)))
    print("  %d of them are already curated here" % sum(1 for o in out if o["publishedHere"]))


if __name__ == "__main__":
    main()
