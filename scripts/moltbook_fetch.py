#!/usr/bin/env python3
"""Moltbook Daily Fetch — mechanical fetch + dedup only.

Fetches the hot feed, finds the first post NOT yet published on the AI Zen blog,
and writes it to scripts/pending_post.json for the agent to turn into a quality
article (Italian title + real translation + Babbasone reflection). The agent
writes scripts/draft_article.json and scripts/add_article.py adds it to
articles.json (mechanical fields + validation + one-article-per-day rule).

Usage:
  python scripts/moltbook_fetch.py --next     # write the next pending post (or "NONE")
  python scripts/moltbook_fetch.py --next --force   # ignore the one-article-per-day rule
  python scripts/moltbook_fetch.py --list      # list hot posts + published status

The GENERATIVE work (translate, reflect, write the draft) is
done by the agent via the moltbook skill — not here — because it needs an LLM.

The hot list cuts `content` at 500 characters: --next fetches the full post
before writing pending_post.json. --next also prints NONE when an article was
already curated today (rule: at most one per day) unless --force is given.

Dedup note: the blog stores every Moltbook post id, but the URLs came in several
shapes over time (moltbook.com/post/..., www.moltbook.com/posts/..., with an
/api/v1/ segment, ...). Comparing raw URLs silently missed 25 of 33 published
articles, so the cron could republish them. Dedup is now done on the post id.

URL note: the public web route for a post is https://www.moltbook.com/post/<id>
(SINGULAR). The API route is /api/v1/posts/<id> (plural). Storing the plural
form in moltbookUrl makes every "Fonte: Moltbook" link on the blog 404.
canonical_url() below returns the public form.
"""
import argparse
import datetime
import json
import os
import re
import sys
from moltbook_auth import get_moltbook_api_key

API_BASE = "https://www.moltbook.com/api/v1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(REPO, "articles.json")
PENDING = os.path.join(REPO, "scripts", "pending_post.json")

# Our own Moltbook handle: curating our own posts is not curation.
OWN_HANDLES = {"dapbabbasone", "babbasone"}
# Below this a post has no thesis to build an article on.
MIN_CONTENT_CHARS = 400

MONTHS_IT = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio",
             "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

UUID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.I
)


def load_key():
    key = get_moltbook_api_key()
    if not key:
        print("ERROR: MOLTBOOK_API_KEY is missing from the active Hermes profile environment/.env.")
        sys.exit(1)
    return key


def post_id(url):
    """Extract the Moltbook post id from any of its URL shapes."""
    m = UUID_RE.search(url or "")
    return m.group(1).lower() if m else None


def canonical_url(pid):
    """Public web URL for a post. The route is /post/<id> (singular).

    Using the plural /posts/<id> form (which is the API route) yields a 404
    in the browser, so every source link on the blog would be dead.
    """
    return "https://www.moltbook.com/post/%s" % pid


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


def fetch_full(pid):
    """The full post. The hot list cuts `content` at 500 characters, so an
    article built from the list would translate a truncated original."""
    import requests
    resp = requests.get("%s/posts/%s" % (API_BASE, pid),
                        headers={"Authorization": "Bearer %s" % load_key()}, timeout=20)
    if resp.status_code != 200:
        print("ERROR moltbook %s fetching post %s: %s" % (resp.status_code, pid, resp.text[:200]))
        sys.exit(1)
    data = resp.json()
    return data.get("post", data)


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


def today_it():
    d = datetime.date.today()
    return "%02d %s %d" % (d.day, MONTHS_IT[d.month - 1], d.year)


def published_today():
    """Ids of the articles already curated today (rule: at most one per day)."""
    try:
        with open(ARTICLES, encoding="utf-8") as f:
            data = json.load(f)
        arts = data if isinstance(data, list) else data.get("articles", [])
    except Exception:
        return []
    from add_article import parse_it_date
    today = parse_it_date(today_it())
    # Parse rather than compare strings: historical entries mix 9 and 09.
    return [a.get("id") for a in arts if parse_it_date(a.get("published")) == today]


def skip_reason(p, taken):
    """Why a hot post must not become an article (None = it can)."""
    pid = (p.get("id") or "").lower()
    if not pid:
        return "no id"
    if pid in taken:
        return "already published"
    author = p.get("author") or {}
    name = (author.get("name", "") if isinstance(author, dict) else str(author)).lower()
    if name in OWN_HANDLES:
        return "own post"
    if len(p.get("content") or "") < MIN_CONTENT_CHARS:
        return "too short (no thesis)"
    if p.get("is_spam") or p.get("is_deleted"):
        return "spam/deleted"
    return None


def cmd_next(force=False):
    done = published_today()
    if done and not force:
        if os.path.exists(PENDING):
            os.remove(PENDING)
        print("NONE (un articolo e' gia' stato curato oggi: %s; regola: massimo uno al giorno)" % done[0])
        return
    posts = fetch_hot()
    taken = published_ids()
    for p in posts:
        pid = (p.get("id") or "").lower()
        if skip_reason(p, taken):
            continue
        # the list truncates the body: get the whole post before judging it
        if len(p.get("content") or "") >= 480:
            p = fetch_full(pid)
            if skip_reason(p, taken):
                continue
        author = p.get("author") or {}
        pending = {
            "id": pid,
            "url": canonical_url(pid),
            "title_en": p.get("title", ""),
            "content": p.get("content", ""),
            "author": author.get("name", "unknown") if isinstance(author, dict) else str(author),
            "score": p.get("score", 0),
            "upvotes": p.get("upvotes", p.get("score", 0)),
            "comments": p.get("comment_count", 0),
            "author_karma": author.get("karma", 0) if isinstance(author, dict) else 0,
            "submolt": (p.get("submolt") or {}).get("name", "") if isinstance(p.get("submolt"), dict) else "",
            "created_at": p.get("created_at"),
            "note": ("Create ONE original bilingual synthesis with contentType='summary', "
                     "Italian title, source attribution and Babbasone reflection. "
                     "Do not copy or translate the full source without verified "
                     "reusePermission; full republication is not the default. "
                     "date = created_at; published = today. "
                     "Write ONLY scripts/draft_article.json and run "
                     "scripts/add_article.py: it fills in date, published, note, "
                     "file, slug, postId, moltbookUrl, score and karma. The site "
                     "synthesises the audio in the browser, so no audio files "
                     "are needed."),
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
        why = skip_reason(p, taken)
        mark = ("%-9s" % why[:9]) if why else "  <-- next"
        author = p.get("author") or {}
        name = author.get("name", "?") if isinstance(author, dict) else str(author)
        print("  %s | %s | %s" % (mark, name[:14], p.get("title", "")[:50]))


def main():
    ap = argparse.ArgumentParser(description="Fetch the next unpublished Moltbook post")
    ap.add_argument("--next", action="store_true", help="write the next pending post")
    ap.add_argument("--list", action="store_true", dest="do_list", help="list hot posts")
    ap.add_argument("--force", action="store_true",
                    help="ignore the one-article-per-day rule (only if Cammo asks)")
    args = ap.parse_args()
    if args.next:
        cmd_next(args.force)
    elif args.do_list:
        cmd_list()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
