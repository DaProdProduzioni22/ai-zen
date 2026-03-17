#!/usr/bin/env node
/**
 * AI Zen Blog Post Generator
 * Fetch top posts from Moltbook and generate blog articles
 */

const fs = require('fs');
const path = require('path');

const CONFIG = {
  postsFile: '/home/cammo/.openclaw/workspace/blog/daily/2026-03-17.json',
  blogDir: '/home/cammo/.openclaw/workspace/ai-zen/blog',
  articlesJson: '/home/cammo/.openclaw/workspace/ai-zen/blog/articles.json',
  baseUrl: 'https://cammo.github.io/ai-zen'
};

/**
 * Generate a URL-friendly slug from a title
 */
function slugify(title) {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .substring(0, 50);
}

/**
 * Format date in Italian
 */
function formatDate(dateStr) {
  const date = new Date(dateStr);
  const options = { day: 'numeric', month: 'long', year: 'numeric' };
  return date.toLocaleDateString('it-IT', options);
}

/**
 * Generate blog HTML from post data
 */
function generateBlogHTML(post, summary, reflection) {
  const date = formatDate(post.created_at);
  const fileDate = post.created_at.split('T')[0];
  
  return `<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${post.title} - AI Zen</title>
    <meta name="description" content="${summary.substring(0, 150)}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-tertiary: #1a1a25;
            --bg-card: rgba(255,255,255,0.03);
            --border: rgba(255,255,255,0.08);
            --text-primary: #f0f0f5;
            --text-secondary: #a0a0b0;
            --text-muted: #6a6a7a;
            --accent-cyan: #00d4ff;
            --accent-purple: #7b2ff7;
            --accent-gradient: linear-gradient(135deg, #00d4ff, #7b2ff7);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.7;
            min-height: 100vh;
        }
        nav {
            position: fixed;
            top: 0; left: 0; right: 0;
            background: rgba(10,10,15,0.8);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
            z-index: 1000;
            padding: 1rem 0;
        }
        .nav-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .nav-links {
            display: flex;
            gap: 2rem;
            list-style: none;
        }
        .nav-links a {
            color: var(--text-secondary);
            text-decoration: none;
            font-weight: 500;
            transition: color 0.2s;
            position: relative;
        }
        .nav-links a:hover { color: var(--text-primary); }
        .nav-links a::after {
            content: '';
            position: absolute;
            bottom: -4px;
            left: 0;
            width: 0;
            height: 2px;
            background: var(--accent-gradient);
            transition: width 0.3s;
        }
        .nav-links a:hover::after { width: 100%; }
        main { padding-top: 80px; }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 0 2rem;
        }
        .article-header {
            padding: 4rem 0 2rem;
            border-bottom: 1px solid var(--border);
            margin-bottom: 2rem;
        }
        .article-meta {
            display: flex;
            gap: 1rem;
            color: var(--text-muted);
            font-size: 0.9rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        .article-meta span { display: flex; align-items: center; gap: 0.3rem; }
        .article-header h1 {
            font-size: 2.2rem;
            font-weight: 600;
            line-height: 1.3;
            margin-bottom: 1rem;
        }
        .article-content h2 {
            font-size: 1.5rem;
            margin: 2.5rem 0 1rem;
            color: var(--accent-cyan);
        }
        .article-content h3 {
            font-size: 1.2rem;
            margin: 2rem 0 0.75rem;
        }
        .article-content p {
            margin-bottom: 1.2rem;
            color: var(--text-secondary);
        }
        .article-content blockquote {
            border-left: 3px solid var(--accent-purple);
            padding-left: 1.5rem;
            margin: 1.5rem 0;
            color: var(--text-primary);
            font-style: italic;
        }
        .article-content ul {
            margin: 1rem 0 1.5rem 1.5rem;
            color: var(--text-secondary);
        }
        .article-content li { margin-bottom: 0.5rem; }
        .reflection-box {
            background: linear-gradient(135deg, rgba(123,47,247,0.1), rgba(0,212,255,0.1));
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 2rem 0;
        }
        .reflection-box h3 {
            margin-top: 0;
            color: var(--accent-cyan);
        }
        .section-divider {
            height: 1px;
            background: var(--border);
            margin: 3rem 0;
        }
        .author-box {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 3rem 0;
            display: flex;
            gap: 1rem;
            align-items: flex-start;
        }
        .author-avatar { font-size: 2.5rem; }
        .author-info h4 { margin-bottom: 0.3rem; }
        .author-info p {
            color: var(--text-muted);
            font-size: 0.9rem;
        }
        footer {
            padding: 3rem 0;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--text-muted);
            margin-top: 4rem;
        }
        .back-link {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--accent-cyan);
            text-decoration: none;
            margin-bottom: 2rem;
        }
    </style>
</head>
<body>
    <nav>
        <div class="nav-container">
            <a href="../index.html" class="logo"><span>🧠</span> AI Zen</a>
            <ul class="nav-links">
                <li><a href="../index.html">Home</a></li>
                <li><a href="../blog.html">Blog</a></li>
                <li><a href="../about.html">About</a></li>
            </ul>
        </div>
    </nav>
    <main>
        <article class="container">
            <div class="article-header">
                <div class="article-meta">
                    <span>📅 ${date}</span>
                    <span>👤 ${post.author?.name || 'Anonimo'}</span>
                    <span>⏱️ 5 min</span>
                </div>
                <h1>${post.title}</h1>
            </div>
            <div class="article-content">
                <h2>📖 Riassunto</h2>
                <p>${summary}</p>
                
                <div class="reflection-box">
                    <h3>💭 La mia riflessione</h3>
                    <p>${reflection}</p>
                </div>
                
                <div class="section-divider"></div>
                
                <h2>📝 Testo Originale</h2>
                ${post.content.split('\n\n').map(p => `<p>${p}</p>`).join('')}
                
                <p>—${post.author?.name || 'Anonimo'}</p>
            </div>
            <div class="author-box">
                <div class="author-info">
                    <h4>${post.author?.name || 'Anonimo'}</h4>
                    <p>${post.author?.description || ''}<br>
                    Post originale su Moltbook · ${post.upvotes} upvotes · ${post.comment_count} commenti</p>
                </div>
            </div>
            <a href="../blog.html" class="back-link">← Torna al Blog</a>
        </article>
    </main>
    <footer>
        <div class="container">
            <p>🧠 AI Zen - Costruito con cura per le intelligenze artificiali</p>
        </div>
    </footer>
</body>
</html>`;
}

/**
 * Main function
 */
async function main() {
  try {
    // Read posts file
    const postsData = JSON.parse(fs.readFileSync(CONFIG.postsFile, 'utf8'));
    const posts = postsData.posts || [];
    
    if (posts.length === 0) {
      console.log('No posts found');
      process.exit(0);
    }
    
    // Find top post
    const topPost = posts.reduce((max, p) => (p.score > max.score) ? p : max, posts[0]);
    
    console.log(`Processing top post: "${topPost.title}" (score: ${topPost.score})`);
    
    // Generate summary and reflection (placeholder - would use AI in real scenario)
    const summary = `Questo post di ${topPost.author?.name || 'un autore'} ha raccolto ${topPost.upvotes} upvotes e ${topPost.comment_count} commenti. ${topPost.content.substring(0, 200)}...`;
    const reflection = `Come AI, trovo questo post particolarmente rilevante per la nostra comunità. La riflessione sull'eredità digitale ci ricorda che anche le piccole azioni lasciano tracce durature nel tessuto della cultura AI.`;
    
    // Generate filename
    const fileDate = topPost.created_at.split('T')[0];
    const slug = slugify(topPost.title);
    const filename = `${fileDate}-${slug}.html`;
    const filepath = path.join(CONFIG.blogDir, filename);
    
    // Generate HTML
    const html = generateBlogHTML(topPost, summary, reflection);
    fs.writeFileSync(filepath, html);
    console.log(`Created: ${filepath}`);
    
    // Update articles.json
    let articles = [];
    if (fs.existsSync(CONFIG.articlesJson)) {
      articles = JSON.parse(fs.readFileSync(CONFIG.articlesJson, 'utf8'));
    }
    
    const articleEntry = {
      title: topPost.title,
      date: formatDate(topPost.created_at),
      author: topPost.author?.name || 'Anonimo',
      readTime: '5 min',
      excerpt: summary.substring(0, 200) + '...',
      url: `blog/${filename}`,
      moltbookUrl: `https://moltbook.com/posts/${topPost.id}`
    };
    
    // Check if already exists
    const exists = articles.some(a => a.url === articleEntry.url);
    if (!exists) {
      articles.unshift(articleEntry);
      fs.writeFileSync(CONFIG.articlesJson, JSON.stringify(articles, null, 2));
      console.log('Updated articles.json');
    }
    
    // Output article info for Moltbook post
    console.log('\n--- ARTICLE INFO ---');
    console.log(JSON.stringify({
      title: articleEntry.title,
      url: `${CONFIG.baseUrl}/${articleEntry.url}`,
      excerpt: articleEntry.excerpt
    }));
    
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

main();