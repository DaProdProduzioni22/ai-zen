#!/usr/bin/env python3
"""Moltbook Daily Fetch v3 -- mechanical fetch + dedup only.

It fetches the hot feed, finds the first post NOT yet published on the AI Zen blog,
and writes it to scripts/pending_post.json for the agent to turn into a quality
article (Italian title + real translation + Babbasone reflection + 3 audio files).

Usage:
  python scripts/moltbook_fetch.py --next     # write next pending post (or "NONE")
  python scripts/moltbook_fetch.py --list      # list hot posts + published status

The GENERATIVE work (translate, reflect, TTS, write articles.json + blog HTML) is
done by the agent via the moltbook skill -- not here -- because it needs an LLM.
"""
import json, os, sys, argparse

API_BASE = "https://www.moltbook.com/api/v1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDS = os.path.expanduser("~/.config/moltbook/credentials.json")
ARTICLES = os.path.join(REPO, "articles.json")
PENDING = os.path.join(REPO, "scripts", "pending_post.json")


def load_key():
    try:
        return json.load(open(CREDS, encoding="utf-8")).get("api_key", "")
    except Exception as e:
        print("ERROR reading credentials:", e); sys.exit(1)


def fetch_hot(limit=15):
    import requests
    k = load_key()
    r = requests.get(f"{API_BASE}/posts?sort=hot&limit={limit}",
                     headers={"Authorization": f"Bearer {k}"}, timeout=15)
    if r.status_code != 200:
        print(f"ERROR moltbook {r.status_code}: {r.text[:200]}"); sys.exit(1)
    return r.json().get("posts", [])


def existing_urls():
    try:
        d = json.load(open(ARTICLES, encoding="utf-8"))
        arts = d if isinstance(d, list) else d.get("articles", [])
    except Exception:
        arts = []
    return {a.get("moltbookUrl", "") for a in arts}


def post_url(pid):
    return f"https://www.moltbook.com/posts/{pid}"


def cmd_next():
    posts = fetch_hot()
    taken = existing_urls()
    for p in posts:
        pid = p.get("id", "")
        url = post_url(pid)
        if url in taken:
            continue
        pending = {
            "id": pid, "url": url, "title_en": p.get("title", ""),
            "content": p.get("content", ""),
            "author": (p.get("author") or {}).get("name", "unknown"),
            "score": p.get("score", 0),
            "created_at": p.get("created_at"),
            "note": "Turn this into ONE quality AI Zen article (Italian title, real EN->IT translation, Babbasone reflection, 3 .ogg via edge-tts). date = created_at; published = today.",
        }
        os.makedirs(os.path.dirname(PENDING), exist_ok=True)
        json.dump(pending, open(PENDING, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"PENDING {pid[:12]}: {pending['title_en'][:60]}")
        return
    if os.path.exists(PENDING):
        os.remove(PENDING)
    print("NONE")


def cmd_list():
    posts = fetch_hot()
    taken = existing_urls()
    print(f"hot posts: {len(posts)} | already published: {len(taken)}")
    for p in posts[:10]:
        url = post_url(p.get("id", ""))
        mark = "published" if url in taken else "  <-- next"
        print(f"  {mark} | {(p.get('author') or {}).get('name','?')[:14]} | {p.get('title','')[:50]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--list", action="store_true", dest="do_list")
    a = ap.parse_args()
    if a.next:
        cmd_next()
    elif a.do_list:
        cmd_list()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
