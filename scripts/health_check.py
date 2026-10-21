#!/usr/bin/env python3
"""AI Zen sentinel: is the *published* site healthy, seen from outside?

Read-only. Meant to run from cron WITHOUT an LLM (hermes cron --no-agent):
stdout is delivered verbatim, and EMPTY stdout means "all good, say nothing".

What it checks (each one is a thing that has already broken at least once):
  1. the latest GitHub Actions run on main is green (README/generated files
     out of date, check_site failures)
  2. the live site answers: home, feed.xml, api/feed.json, sitemap, every page
  3. the live feed has as many articles as articles.json (deploy is not stale)
  4. every "Fonte: Moltbook" link answers 200 (the /posts/ vs /post/ 404 bug)
  5. local repo: nothing unpushed, nothing left uncommitted
  6. the daily article: one was curated today (the 07:00 cron ran and produced it).
     Skipped with --no-daily, e.g. when the check runs before the morning job.

Usage:
  python scripts/health_check.py             # silent when healthy
  python scripts/health_check.py --verbose   # always print a summary
  python scripts/health_check.py --no-moltbook   # skip the 34 external links
  python scripts/health_check.py --no-daily      # skip the "article published today" check

Exit code: 0 healthy, 1 problems found.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://DaProdProduzioni22.github.io/ai-zen/"
GH_REPO = "DaProdProduzioni22/ai-zen"
UA = {"User-Agent": "Mozilla/5.0 (AI-Zen health check)"}


def http(url, timeout=20):
    """Return (status, body). Status 0 means the network failed."""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def run(cmd):
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return p.returncode, p.stdout.strip()
    except Exception as exc:
        return 1, str(exc)


def load_articles():
    with open(os.path.join(REPO, "articles.json"), encoding="utf-8") as f:
        data = json.load(f)
    return data["articles"] if isinstance(data, dict) else data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-moltbook", action="store_true")
    ap.add_argument("--no-daily", action="store_true")
    args = ap.parse_args()

    problems, notes = [], []
    arts = load_articles()

    # 1. CI on main
    code, out = run(["gh", "run", "list", "--repo", GH_REPO, "--branch", "main",
                     "--workflow", "Build & check", "--limit", "1",
                     "--json", "conclusion,status,displayTitle,url"])
    if code == 0 and out:
        runs = json.loads(out)
        if runs:
            r = runs[0]
            if r["status"] == "completed" and r["conclusion"] != "success":
                problems.append("CI rossa su main: «%s» (%s) — %s"
                                % (r["displayTitle"], r["conclusion"], r["url"]))
            else:
                notes.append("CI: %s" % (r["conclusion"] or r["status"]))
    else:
        notes.append("CI: gh non disponibile, controllo saltato")

    # 2. live pages
    for path in ("", "feed.xml", "api/feed.json", "sitemap.xml", "blog/"):
        st, _ = http(SITE + path)
        if st != 200:
            problems.append("sito: %s%s risponde %s" % (SITE, path, st or "nessuna risposta"))
    st, sm = http(SITE + "sitemap.xml")
    pages = re.findall(r"<loc>([^<]+)</loc>", sm) if st == 200 else []
    dead_pages = []
    for url in pages:
        st, _ = http(url)
        if st != 200:
            dead_pages.append("%s [%s]" % (url, st or "-"))
    if dead_pages:
        problems.append("pagine del sitemap non raggiungibili:\n    " + "\n    ".join(dead_pages))
    notes.append("pagine live: %d verificate" % len(pages))

    # 3. deploy is not stale
    st, feed = http(SITE + "api/feed.json")
    if st == 200:
        try:
            live = json.loads(feed)
            live_n = len(live.get("posts", live if isinstance(live, list) else []))
            if live_n != len(arts):
                problems.append("deploy non allineato: articles.json ha %d articoli, il feed live %d"
                                % (len(arts), live_n))
        except ValueError:
            problems.append("api/feed.json live non è JSON valido")

    # 4. Moltbook source links
    if not args.no_moltbook:
        dead = []
        urls = [a["moltbookUrl"] for a in arts if a.get("moltbookUrl")]
        for url in urls:
            st, _ = http(url)
            if st == 429:          # rate limited: not evidence of a dead link
                time.sleep(5)
                st, _ = http(url)
            if st not in (200, 429):
                dead.append("%s [%s]" % (url, st or "-"))
            time.sleep(0.4)
        if dead:
            problems.append("link «Fonte: Moltbook» morti:\n    " + "\n    ".join(dead))
        notes.append("link Moltbook: %d verificati" % len(urls))

    # 6. the daily article (the one-per-day rule makes "none today" a real signal)
    if not args.no_daily:
        months = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio",
                  "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
        t = datetime.date.today()
        today_it = "%02d %s %d" % (t.day, months[t.month - 1], t.year)
        if any(a.get("published") == today_it for a in arts):
            notes.append("articolo di oggi presente")
        else:
            problems.append("nessun articolo curato oggi (%s): il job delle 07:00 non ha pubblicato. "
                            "Controlla `hermes cron` e scripts/moltbook_fetch.py --next" % today_it)

    # 5. local repo
    run(["git", "fetch", "--quiet", "origin"])
    code, ahead = run(["git", "rev-list", "--count", "origin/main..HEAD"])
    if code == 0 and ahead.isdigit() and int(ahead) > 0:
        problems.append("%s commit locali non pushati" % ahead)
    code, dirty = run(["git", "status", "--porcelain", "--untracked-files=no"])
    if dirty:
        problems.append("modifiche non committate nel repo:\n    " + dirty.replace("\n", "\n    "))

    if problems:
        print("⚠️ AI Zen — controllo di salute: %d problema/i" % len(problems))
        for p in problems:
            print("• " + p)
        return 1
    if args.verbose:
        print("✅ AI Zen in salute — " + " · ".join(notes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
