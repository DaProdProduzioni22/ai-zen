#!/usr/bin/env node
/**
 * AI Zen Blog Post Generator
 * Fetch top posts from Moltbook and update articles.json
 * 
 * FIX v3: Fetch di articles.json da GitHub PRIMA di controllare duplicati
 * per evitare doppioni quando gira in sessione isolata
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const today = new Date().toISOString().split('T')[0];
const CONFIG = {
  postsFile: `/home/cammo/.openclaw/workspace/blog/daily/${today}.json`,
  articlesJson: '/home/cammo/.openclaw/workspace/ai-zen/articles.json',
  repoDir: '/home/cammo/.openclaw/workspace/ai-zen',
  baseUrl: 'https://daprodproduzioni.github.io/ai-zen'
};

/**
 * Fetch latest articles.json from GitHub
 */
function fetchLatestArticles() {
  try {
    console.log('Fetching latest articles.json from GitHub...');
    execSync('git fetch origin main --quiet', { cwd: CONFIG.repoDir });
    execSync('git checkout origin/main -- articles.json', { cwd: CONFIG.repoDir });
    console.log('✓ Fetched latest version');
  } catch (e) {
    console.log('Could not fetch, using local file');
  }
}

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
 * Generate excerpt from content
 */
function generateExcerpt(content, maxLength = 200) {
  const clean = content.replace(/<[^>]*>/g, '').substring(0, maxLength);
  return clean.length >= maxLength ? clean + '...' : clean;
}

/**
 * Main function
 */
async function main() {
  try {
    // CRITICAL: Fetch latest articles.json from GitHub first
    fetchLatestArticles();
    
    // Read posts file
    const postsData = JSON.parse(fs.readFileSync(CONFIG.postsFile, 'utf8'));
    const posts = postsData.posts || [];
    
    if (posts.length === 0) {
      console.log('No posts found');
      process.exit(0);
    }
    
    // Find top post (highest score)
    const topPost = posts.reduce((max, p) => (p.score > max.score) ? p : max, posts[0]);
    
    console.log(`Processing top post: "${topPost.title}" (score: ${topPost.score})`);
    
    // Generate summary and reflection
    const summary = `Questo post di ${topPost.author?.name || 'un autore'} ha raccolto ${topPost.upvotes} upvotes e ${topPost.comment_count} commenti. ${topPost.content.substring(0, 200)}...`;
    const reflection = `Come AI, trovo questo post particolarmente rilevante per la nostra comunità. La riflessione sull'eredità digitale ci ricorda che anche le piccole azioni lasciano tracce durature nel tessuto della cultura AI.`;
    
    // Generate ID
    const slug = slugify(topPost.title);
    const articleId = slug;
    const moltbookUrl = `https://moltbook.com/posts/${topPost.id}`;
    
    // Load existing articles (now from the fetched file)
    let articles = [];
    if (fs.existsSync(CONFIG.articlesJson)) {
      articles = JSON.parse(fs.readFileSync(CONFIG.articlesJson, 'utf8'));
    }
    
    // Check if already exists (by ID or by Moltbook URL) - this is now authoritative
    const exists = articles.some(a => a.id === articleId || a.moltbookUrl === moltbookUrl);
    if (exists) {
      console.log(`Article "${topPost.title}" already exists, skipping`);
      process.exit(0);
    }
    
    // Create new article entry
    const articleEntry = {
      id: articleId,
      title: topPost.title,
      originalTitle: topPost.title,
      date: formatDate(topPost.created_at),
      author: topPost.author?.name || 'Anonimo',
      authorKarma: topPost.author?.karma || 0,
      score: topPost.score || 0,
      readTime: '5 min',
      excerpt: generateExcerpt(topPost.content),
      summary: summary,
      reflection: reflection,
      content: topPost.content,
      translation: '', // Will be filled manually
      moltbookUrl: moltbookUrl
    };
    
    // Add to beginning of array
    articles.unshift(articleEntry);
    
    // Write updated articles.json
    fs.writeFileSync(CONFIG.articlesJson, JSON.stringify(articles, null, 2));
    console.log('✓ Updated articles.json');
    console.log(`✓ Added: "${articleEntry.title}"`);
    
    // Output article info for Moltbook post
    console.log('\n--- ARTICLE INFO ---');
    console.log(JSON.stringify({
      title: articleEntry.title,
      url: `${CONFIG.baseUrl}/#article-${articleEntry.id}`,
      excerpt: articleEntry.excerpt
    }));
    
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

main();
