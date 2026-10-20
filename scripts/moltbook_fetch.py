#!/usr/bin/env python3
"""Moltbook Daily Fetch — mechanical fetch + dedup only.

Fetches the hot feed, finds the first post NOT yet published on the AI Zen blog,
and writes it to scripts/pending_post.json for the agent to turn into a quality
article (Italian title + real translation + Babbasone reflection + 3 audio files).

Usage:
  python scripts/moltbook_fetch.py --next     # write the next pending post (or "NONE")
  python scripts/moltbook_fetch.py --list      # list hot posts + published status

The GENERATIVE work (translate, reflect, TTS, write articles.json + blog HTML) is
done by the agent via the moltbook skill — not here — because it needs an LLM.

Dedup note: the blog stores every Moltbook post id, but the URLs came in several
shapes over time (moltbook.com/post/..., www.moltbook.com/posts/..., with an
/api/v1/ segment, ...). Comparing raw URLs silently missed 25 of 33 published
articles, so the cron could republish them. Dedup is now done on the post id.
"""
import argparse
import json
import os
import re
import sys

API_BASE = "https://www.moltbook.com/api/v1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDS = os.path.expanduser("~/.config/moltbook/credentials.json")
ARTICLES = os.path.join(REPO, "articles.json")
PENDING = os.path.join(REPO, "scripts", "pending_post.json")

UUID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.I
)


def load_key():
    try:
        with open(CREDS, encoding="utf-8") as f:
            return json.load(f).get("api_key", "")
    except Exception as exc:
        print("ERROR reading credentials:", exc)
        sys.exit(1)


def post_id(url):
    """Extract the Moltbook post id from any of its URL shapes."""
    m = UUID_RE.search(url or "")
    return m.group(1).lower() if m else None


def canonical_url(pid):
    return "https://www.moltbook.com/posts/%s" % pid


def fetch_hot(limit=15):
    try:
        import requests
    except ImportError:
        print("ERROR: the 'requests' package is missing. Install it with:")
        print("  pip install requests")
        sys.exit(1)
    key = load_key()
    resp = requests.get("%s/posts?sort=hot&limit=%d" % (API_BASE, limit),
                        headers={"Authorization": "Bearer %s" % key}, timeout=20)
    if resp.status_code != 200:
        print("ERROR moltbook %s: %s" % (resp.status_code, resp.text[:200]))
        sys.exit(1)
    return resp.json().get("posts", [])


def published_ids():
    """Every Moltbook post id already on the blog."""
    ids = set()
    try:
        with open(ARTICLES, encoding="utf-8") as f:
            data = json.load(f)
        arts = data if isinstance(data, list) else data.get("articles", [])
    except Exception:
        arts = []
    for a in arts:
        pid = a.get("postId")
        if not pid:
            pid = post_id(a.get("moltbookUrl", ""))
        if pid:
            ids.add(pid.lower())
    return ids


def cmd_next():
    posts = fetch_hot()
    taken = published_ids()
    for p in posts:
        pid = (p.get("id") or "").lower()
        if not pid or pid in taken:
            continue
        author = p.get("author") or {}
        pending = {
            "id": pid,
            "url": canonical_url(pid),
            "title_en": p.get("title", ""),
            "content": p.get("content", ""),
            "author": author.get("name", "unknown") if isinstance(author, dict) else str(author),
            "score": p.get("score", 0),
            "created_at": p.get("created_at"),
            "note": ("Turn this into ONE quality AI Zen article (Italian title, real "
                     "EN->IT translation, Babbasone reflection, 3 .ogg via edge-tts). "
                     "date = created_at; published = today."),
        }
        os.makedirs(os.path.dirname(PENDING), exist_ok=True)
        with open(PENDING, "w", encoding="utf-8") as f:
            json.dump(pending, f, ensure_ascii=False, indent=2)
        print("PENDING %s: %s" % (pid[:12], pending["title_en"][:60]))
        return
    if os.path.exists(PENDING):
        os.remove(PENDING)
    print("NONE")


def cmd_list():
    posts = fetch_hot()
    taken = published_ids()
    print("hot posts: %d | already published: %d" % (len(posts), len(taken)))
    for p in posts[:10]:
        pid = (p.get("id") or "").lower()
        mark = "published" if pid in taken else "  <-- next"
        author = p.get("author") or {}
        name = author.get("name", "?") if isinstance(author, dict) else str(author)
        print("  %s | %s | %s" % (mark, name[:14], p.get("title", "")[:50]))


def main():
    ap = argparse.ArgumentParser(description="Fetch the next unpublished Moltbook post")
    ap.add_argument("--next", action="store_true", help="write the next pending post")
    ap.add_argument("--list", action="store_true", dest="do_list", help="list hot posts")
    args = ap.parse_args()
    if args.next:
        cmd_next()
    elif args.do_list:
        cmd_list()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
