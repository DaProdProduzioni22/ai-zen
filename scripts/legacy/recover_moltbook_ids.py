#!/usr/bin/env python3
"""Apply the recovered Moltbook post ids and drop the duplicate article.

The 4 "placeholder" URLs were looked up on Moltbook and 3 were recovered:
  first-time-i-lied           -> 4a0710f9-7a69-4b77-92a5-891df3d7876f  (Hazel_OC)
  nobody-changed-mind         -> 637485e8-ea6a-4d5f-97f5-6052096e4c42  (Hazel_OC)
  surgical-notes-next-version -> 0bfa04e6-578a-45bd-a660-6847fc1af3e8  (Verado)
The 4th (self-modification-governance, by keats) is not reachable through the
search endpoint, so its link stays empty rather than pointing somewhere invented.

The duplicate: "ai-zen-017" and "the-most-dangerous-state-for-an-orchestrator-is-idle"
are the same Moltbook post (00a3bce8). The ai-zen-017 copy is the corrupted one:
  - its "translation" is a byte copy of its English "content"
  - its date (1 Aprile) contradicts the post's created_at (30 Marzo 2026)
  - its score (460) does not match the post's score (261 in the old row, 475 on Moltbook)
  - its reflection is attributed to a different author voice
So ai-zen-017 is removed and the original (the-most-dangerous-...) is kept.
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(REPO, "articles.json")
BLOG = os.path.join(REPO, "blog")

RECOVERED = {
    "first-time-i-lied": "4a0710f9-7a69-4b77-92a5-891df3d7876f",
    "nobody-changed-mind": "637485e8-ea6a-4d5f-97f5-6052096e4c42",
    "surgical-notes-next-version": "0bfa04e6-578a-45bd-a660-6847fc1af3e8",
}

DROP = {"ai-zen-017"}


def main():
    arts = json.load(open(ARTICLES, encoding="utf-8"))
    if isinstance(arts, dict):
        arts = list(arts.values())

    applied, dropped = [], []
    kept = []
    for a in arts:
        pid = a.get("id")
        if pid in DROP:
            dropped.append(pid)
            continue
        if pid in RECOVERED:
            a["moltbookUrl"] = "https://www.moltbook.com/post/" + RECOVERED[pid]
            a["postId"] = RECOVERED[pid]
            applied.append(pid)
        kept.append(a)

    with open(ARTICLES, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # remove the dropped article's blog page
    for slug in ("ai-zen-017",):
        p = os.path.join(BLOG, "2026-04-01-%s.html" % slug)
        if os.path.exists(p):
            os.remove(p)
            print("removed page:", os.path.basename(p))

    print("articles now:", len(kept))
    print("recovered urls:", len(applied))
    for p in applied:
        print("   ", p)
    print("dropped duplicates:", dropped)


if __name__ == "__main__":
    main()
