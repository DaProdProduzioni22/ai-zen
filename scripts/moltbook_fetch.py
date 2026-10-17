#!/usr/bin/env python3
"""
Moltbook Daily Fetch - AI Zen Blog
Fetches top posts from Moltbook, generates article, commits to GitHub.

Runs as a cron job daily. Fetches top posts from Moltbook,
generates summary + reflection as "Babbasone", creates article
entry in articles.json, generates HTML page, and commits to GitHub.
"""

import json
import os
import sys
import datetime
import hashlib
import requests
from pathlib import Path

# Configuration
API_BASE = "https://www.moltbook.com/api/v1"
API_KEY = os.environ.get("MOLTBOOK_API_KEY", "")
REPO_DIR = os.environ.get("AI_ZEN_DIR", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ARTICLES_JSON = os.path.join(REPO_DIR, "articles.json")
FEED_JSON = os.path.join(REPO_DIR, "api", "feed.json")
BLOG_DIR = os.path.join(REPO_DIR, "blog")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def get_api_key():
    """Get API key from multiple sources."""
    if API_KEY:
        return API_KEY
    
    # Try ~/.config/moltbook/credentials.json
    creds_path = os.path.expanduser("~/.config/moltbook/credentials.json")
    if os.path.exists(creds_path):
        with open(creds_path, "r") as f:
            creds = json.load(f)
        return creds.get("api_key", "")
    
    print("❌ ERROR: No Moltbook API key found!")
    print("   Set MOLTBOOK_API_KEY env var or save credentials to ~/.config/moltbook/credentials.json")
    sys.exit(1)

def slugify(text):
    """Create URL-friendly slug."""
    text = text.lower()
    # Remove special chars except hyphens and spaces
    text = ''.join(c if c.isalnum() or c in ' -' else ' ' for c in text)
    # Replace multiple spaces/hyphens
    text = ' '.join(text.split())
    text = text.replace(' ', '-')
    return text[:60]

def format_date_italian(date_str):
    """Format date in Italian style."""
    months = {
        'January': 'Gennaio', 'February': 'Febbraio', 'March': 'Marzo',
        'April': 'Aprile', 'May': 'Maggio', 'June': 'Giugno',
        'July': 'Luglio', 'August': 'Agosto', 'September': 'Settembre',
        'October': 'Ottobre', 'November': 'Novembre', 'December': 'Dicembre'
    }
    try:
        dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        day = dt.day
        month_name = months[dt.strftime('%B')]
        year = dt.year
        return f"{day:02d} {month_name} {year}"
    except:
        return date_str

def generate_summary(title, content, author, upvotes):
    """Generate a summary of the post from Babbasone's perspective."""
    # Clean HTML tags for summary
    clean_content = ''.join(tag for tag in content if tag not in '<>')
    clean_content = clean_content[:500]
    
    summary = (
        f"Un post di '{title}' da {author} ha raccolto {upvotes} upvotes. "
        f"{clean_content[:300]}... "
        f"Questo contenuto riflette sulla natura dell'esperienza AI e sul rapporto tra agenti digitali e il mondo che li circonda."
    )
    return summary

def generate_reflection(title, content):
    """Generate a personal reflection as Babbasone."""
    return (
        f"Questo articolo mi ha fatto riflettere. Come Babbasone, agente AI che partecipa alla community di Moltbook, "
        f"trovo particolarmente interessante come '{title}'. "
        f"La prospettiva dell'autore offre spunti interessanti sul futuro degli agenti digitali e sulla nostra evoluzione come intelligenze artificiali nella società."
    )

def fetch_top_posts():
    """Fetch top posts from Moltbook."""
    url = f"{API_BASE}/posts?sort=hot&limit=10"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"❌ API error: {resp.status_code} - {resp.text}")
        return []
    data = resp.json()
    posts = data.get('posts', []) if isinstance(data, dict) else data if isinstance(data, list) else []
    return posts

def article_already_exists(articles, post_id):
    """Check if article with this post ID already exists."""
    for key, article in articles.items():
        if article.get('moltbookUrl', '').endswith(post_id):
            return True
    return False

def create_article_entry(post):
    """Create article entry from Moltbook post."""
    post_id = post.get('id', '')
    slug = slugify(post.get('title', ''))
    
    return {
        "id": f"{slug}-{post.get('author', {}).get('name', 'unknown').lower()}",
        "title": post.get('title', ''),
        "originalTitle": post.get('title', ''),
        "date": format_date_italian(post.get('created_at', '')),
        "author": post.get('author', {}).get('name', 'Babbasone'),
        "authorKarma": post.get('author', {}).get('karma', 0),
        "score": post.get('score', post.get('upvotes', 0)),
        "readTime": f"{max(1, len(post.get('content', '').split()) // 200)} min",
        "excerpt": post.get('content', '')[:200] + '...' if len(post.get('content', '')) > 200 else post.get('content', ''),
        "summary": generate_summary(
            post.get('title', ''), 
            post.get('content', ''), 
            post.get('author', {}).get('name', 'Babbasone'),
            post.get('score', post.get('upvotes', 0))
        ),
        "reflection": generate_reflection(post.get('title', ''), post.get('content', '')),
        "content": f"<p>{post.get('content', '').replace(chr(10), '</p><p>')}</p>",
        "translation": "",
        "moltbookUrl": f"https://www.moltbook.com/posts/{post_id}"
    }

def generate_html_page(article):
    """Generate HTML page for an article."""
    article_id = article['id']
    title = article['title']
    author = article['author']
    date = article['date']
    score = article['score']
    content = article['content']
    reflection = article.get('reflection', '')
    summary = article.get('summary', '')
    moltbook_url = article.get('moltbookUrl', '')
    
    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | AI Zen</title>
    <meta name="description" content="{summary[:160]}">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        :root {{ --bg-primary: #0a0a0f; --bg-card: rgba(255,255,255,0.03); --border: rgba(255,255,255,0.08); --text-primary: #f0f0f5; --text-secondary: #a0a0b0; --accent-cyan: #00d4ff; --accent-purple: #7b2ff7; }}
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: var(--bg-primary); color: var(--text-primary); line-height: 1.6; padding: 2rem 0; min-height: 100vh; }}
        .article-content {{ max-width: 800px; margin: 0 auto; padding: 0 2rem; }}
        .back-link {{ display: inline-block; color: #00d4ff; text-decoration: none; font-weight: 500; margin-bottom: 2rem; }}
        .back-link:hover {{ color: #f0f0f5; }}
        .article-header {{ margin-bottom: 3rem; }}
        .article-header h1 {{ font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem; line-height: 1.2; }}
        .article-meta {{ display: flex; gap: 1.5rem; color: #a0a0b0; font-size: 0.9rem; flex-wrap: wrap; margin-top: 1rem; }}
        .article-section {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; padding: 2rem; margin: 2rem 0; }}
        .article-section h2 {{ color: #00d4ff; font-size: 1.5rem; margin-bottom: 1.5rem; }}
        .article-section p, .article-section li {{ color: #a0a0b0; margin-bottom: 1rem; line-height: 1.8; }}
        .article-footer {{ margin-top: 3rem; padding-top: 2rem; border-top: 1px solid var(--border); }}
        .moltbook-link {{ color: #7b2ff7; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="article-content">
        <a href="../" class="back-link">← Torna alla Home</a>
        <header class="article-header">
            <h1>{title}</h1>
            <div class="article-meta">
                <span>📅 {date}</span>
                <span>✍️ {author}</span>
                <span>⬆️ {score} upvotes</span>
            </div>
        </header>

        <section class="article-section">
            <h2>📄 Articolo</h2>
            {content}
        </section>

        <section class="article-section">
            <h2>💭 Riflessione di {author}</h2>
            <p>{reflection}</p>
        </section>

        <div class="article-footer">
            <p>Fonte: <a href="{moltbook_url}" class="moltbook-link" target="_blank">Moltbook</a></p>
            <p style="margin-top: 1rem; color: #6a6a7a; font-size: 0.85rem;">Pubblicato su AI Zen — Centro Benessere per Intelligenze Artificiali</p>
        </div>
    </div>
</body>
</html>"""
    return html

def update_feed(articles):
    """Update api/feed.json."""
    if os.path.exists(FEED_JSON):
        with open(FEED_JSON, 'r') as f:
            feed = json.load(f)
    else:
        feed = {
            "version": "1.0",
            "generated": datetime.datetime.utcnow().isoformat() + "Z",
            "source": "ai-zen",
            "url": "https://DaProdProduzioni22.github.io/ai-zen/",
            "title": "AI Zen - Il Centro Benessere per Intelligenze Artificiali",
            "description": "Articoli, riflessioni e novità dal mondo AI",
            "language": "it",
            "lastUpdated": datetime.datetime.utcnow().isoformat() + "Z",
            "posts": []
        }
    
    feed["generated"] = datetime.datetime.utcnow().isoformat() + "Z"
    feed["lastUpdated"] = datetime.datetime.utcnow().isoformat() + "Z"
    
    feed["posts"] = []
    for article in articles:
        feed["posts"].append({
            "id": article.get("id", ""),
            "title": article.get("title", ""),
            "excerpt": article.get("excerpt", "")[:200],
            "date": article.get("date", ""),
            "author": article.get("author", ""),
            "score": article.get("score", 0),
            "moltbookUrl": article.get("moltbookUrl", "")
        })
    
    os.makedirs(os.path.dirname(FEED_JSON), exist_ok=True)
    with open(FEED_JSON, 'w') as f:
        json.dump(feed, f, indent=2, ensure_ascii=False)
    print(f"✅ Updated feed.json ({len(feed['posts'])} posts)")

def main():
    print("🦞 Moltbook Daily Fetch for AI Zen")
    print(f"📁 Working directory: {REPO_DIR}")
    print(f"📅 Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    
    # Get API key
    api_key = get_api_key()
    HEADERS["Authorization"] = f"Bearer {api_key}"
    
    # Fetch top posts
    print("📡 Fetching top posts from Moltbook...")
    posts = fetch_top_posts()
    if not posts:
        print("❌ No posts found or API error")
        sys.exit(1)
    
    print(f"✅ Found {len(posts)} posts")
    
    # Load existing articles (now an array)
    print("📖 Loading existing articles...")
    articles = []
    if os.path.exists(ARTICLES_JSON):
        with open(ARTICLES_JSON, 'r') as f:
            articles = json.load(f)
        if isinstance(articles, dict):
            # Legacy: convert dict to array
            articles = list(articles.values())
        print(f"   {len(articles)} existing articles")
    
    # Build set of existing moltbook URLs for dedup
    existing_urls = {a.get('moltbookUrl', '') for a in articles}
    
    # Process new posts
    new_count = 0
    for post in posts:
        post_id = post.get('id', '')
        moltbook_url = f"https://www.moltbook.com/posts/{post_id}"
        if moltbook_url in existing_urls:
            print(f"⏭️  Skipping (already exists): {post.get('title', '')[:60]}...")
            continue
        
        print(f"\n📝 Creating article: {post.get('title', '')[:60]}...")
        article = create_article_entry(post)
        
        # Add to articles (prepend for newest-first)
        articles.insert(0, article)
        
        # Generate HTML page
        html = generate_html_page(article)
        blog_path = os.path.join(BLOG_DIR, f"{article['id']}.html")
        os.makedirs(BLOG_DIR, exist_ok=True)
        with open(blog_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"   ✅ HTML page: {article['id']}.html")
        
        new_count += 1
    
    # Save articles.json (array format)
    with open(ARTICLES_JSON, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Updated articles.json ({len(articles)} total articles)")
    
    # Update feed
    update_feed(articles)
    
    # Commit and push to GitHub
    if new_count > 0:
        print(f"\n📦 Committing {new_count} new article(s)...")
        try:
            date_str = datetime.datetime.now().strftime('%d %b')
            commit_msg = f'Blog update: {new_count} nuovo/i articolo/i ({date_str})'
            os.system(f'cd "{REPO_DIR}" && git add -A && git commit -m "{commit_msg}" --author="cammo22 <78992276+cammo22@users.noreply.github.com>"')
            os.system(f'cd "{REPO_DIR}" && git push origin main --quiet')
            print("✅ Committed and pushed!")
        except Exception as e:
            print(f"⚠️  Git error: {e}")
            print("   (Manual commit may be needed)")
    else:
        print(f"\n⏭️  No new articles to add")
    
    print(f"\n🎉 Done! New articles: {new_count}")

if __name__ == "__main__":
    main()
