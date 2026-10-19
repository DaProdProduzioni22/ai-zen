#!/usr/bin/env python3
"""Repair the ai-zen data model: add slug + published (curate date) to every article.

Model (honest, no fake dates):
  - date        = original Moltbook post date (created_at). NEVER changed.
  - published   = day Babbasone curated/published it. Known only where documented
                  (supersedes -> 19 Oct, from git + articles.json); otherwise the
                  same day as the post (curated same day), which is the common case.
  - note        = shown in the UI when published != date: "Curato il X * post del Y".
  - slug        = the real slug taken from the blog HTML filename (date prefix stripped).
"""
import json, os, re, shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(REPO, "articles.json")
BLOG = os.path.join(REPO, "blog")

PUB_OVERRIDE = {
    "your-memory-store-needs-a-supersedes-edge-not-a-correction-log-hobosentinel": "19 Ottobre 2026",
}


def slugify(t):
    t = re.sub(r"[^\w\s-]", " ", t, flags=re.UNICODE)
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[-\s]+", "-", " ").strip("-")[:60]


def slug_from_stem(stem):
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)


def match(a, files):
    cand = slugify(a.get("originalTitle") or a.get("title") or a.get("id", ""))
    stem = a.get("id", "")
    for s in files:
        if s == stem:
            return cand, s
    for s in files:
        if stem and stem in s:
            return cand, s
    for s in files:
        if cand and cand in s and len(cand) >= 8:
            return cand, s
    for s in files:
        for tok in re.findall(r"[a-z0-9]{6,}", cand):
            if tok in s:
                return cand, s
    # score files by distinctive id tokens (>=8 chars); the id keeps the English
    # slug even when the title is Italian. Pick the best-scoring file.
    id_tokens = set(re.findall(r"[a-z0-9]{8,}", stem))
    best, best_score = None, 0
    for s in files:
        score = sum(1 for t in id_tokens if t in s)
        if score > best_score:
            best, best_score = s, score
    if best:
        return cand, best
    return cand, None


def main():
    shutil.copy2(ARTICLES, ARTICLES + ".bak")
    d = json.load(open(ARTICLES, encoding="utf-8"))
    arts = d if isinstance(d, list) else d.get("articles", [])
    files = [f[:-5] for f in os.listdir(BLOG) if f.endswith(".html") and not f.startswith("index")]

    changed = added = dup_note = 0
    for a in arts:
        id_ = a.get("id", "")
        cand, stem = match(a, files)
        a["slug"] = slug_from_stem(stem) if stem else (a.get("slug") or cand)
        date = a.get("date")
        published = PUB_OVERRIDE.get(id_, date)
        if a.get("published") != published:
            added += 1
        a["published"] = published
        if published != date:
            a["note"] = "Curato il %s · post del %s" % (published, date)
            dup_note += 1
        else:
            a.pop("note", None)
        changed += 1

    with open(ARTICLES, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print("OK %d articles written. published set/updated: %d. notes added: %d" % (changed, added, dup_note))
    print("backup:", ARTICLES + ".bak")


if __name__ == "__main__":
    main()
