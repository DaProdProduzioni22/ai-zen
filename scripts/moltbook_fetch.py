#!/usr/bin/env python3
"""Moltbook Daily Fetch v2 - AI Zen Blog. ONE article/run. EN+IT+audio TTS."""
import json,os,sys,subprocess,datetime,re,asyncio,edge_tts,requests
from datetime import timezone
API_BASE="https://www.moltbook.com/api/v1"
API_KEY=os.environ.get("MOLTBOOK_API_KEY","")
REPO_DIR=os.environ.get("AI_ZEN_DIR",os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ARTICLES_JSON=os.path.join(REPO_DIR,"articles.json")
FEED_JSON=os.path.join(REPO_DIR,"api","feed.json")
BLOG_DIR=os.path.join(REPO_DIR,"blog")
AUDIO_DIR=os.path.join(REPO_DIR,"audio")
FFMPEG=r"C:\Users\cammo\AppData\Local\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffmpeg.exe"
def slugify(t):
    t=re.sub(r'[^\w\s-]',' ',t,flags=re.UNICODE);t=t.encode('ascii','ignore').decode('ascii').lower()
    return re.sub(r'[-\s]+','-',' ').strip('-')[:60]
def fmt_date(ds):
    m={'January':'Gennaio','February':'Febbraio','March':'Marzo','April':'Aprile','May':'Maggio','June':'Giugno','July':'Luglio','August':'Agosto','September':'Settembre','October':'Ottobre','November':'Novembre','December':'Dicembre'}
    try:
        dt=datetime.datetime.fromisoformat(ds.replace('Z','+00:00'));mn=m.get(dt.strftime('%B'),'')
        return f"{dt.day:02d} {mn} {dt.year}" if mn else ds
    except:return ds
async def tts(text,voice,name):
    mp3=os.path.join(AUDIO_DIR,f"{name}.mp3");ogg=os.path.join(AUDIO_DIR,f"{name}.ogg")
    try:
        await edge_tts.Communicate(text,voice).save(mp3)
        subprocess.run([FFMPEG,"-y","-i",mp3,"-codec:a","libvorbis","-q:a","4",ogg],capture_output=True,timeout=30)
        if os.path.exists(mp3):os.remove(mp3)
        return os.path.exists(ogg)
    except:return False
def html(title_it,title_en,content,trans,refl,author,score,date,url,pfx):
    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title_it} | AI Zen</title><meta name="description" content="{refl[:160]}">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}:root{{--bg-primary:#0a0a0f;--bg-card:rgba(255,255,255,0.03);--border:rgba(255,255,255,0.08);--text-primary:#f0f0f5;--text-secondary:#a0a0b0;--accent-cyan:#00d4ff;--accent-purple:#7b2ff7}}
body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg-primary);color:var(--text-primary);line-height:1.6;padding:2rem 0;min-height:100vh}}
.a{{max-width:800px;margin:0 auto;padding:0 2rem}}.bl{{display:inline-block;color:#00d4ff;text-decoration:none;font-weight:500;margin-bottom:2rem}}
.h{{margin-bottom:3rem}}.h1{{font-size:2.5rem;font-weight:700;margin-bottom:.5rem;line-height:1.2}}
.ot{{color:#a0a0b0;font-style:italic;font-size:.9rem;margin-top:.3rem}}.am{{display:flex;gap:1.5rem;color:#a0a0b0;font-size:.9rem;flex-wrap:wrap;margin-top:1rem}}
.s{{background:var(--bg-card);border:1px solid var(--border);border-radius:16px;padding:2rem;margin:2rem 0}}
.sh{{color:#00d4ff;font-size:1.5rem;margin-bottom:1.5rem}}.sp,.sl{{color:#a0a0b0;margin-bottom:1rem;line-height:1.8}}
.sq{{border-left:4px solid #00d4ff;padding-left:1.5rem;margin:1.5rem 0;color:#a0a0b0;font-style:italic}}
.sb{{color:#00d4ff}}.sa{{color:#00d4ff}}.aud{{background:rgba(123,47,247,0.05);border-color:rgba(123,47,247,0.2)}}.auh{{color:#7b2ff7}}
audio{{width:100%;margin-top:1rem}}.af{{margin-top:3rem;padding-top:2rem;border-top:1px solid var(--border)}}
.ml{{color:#7b2ff7;text-decoration:none}}
</style></head><body><div class="a">
<a href="../" class="bl">← Torna alla Home</a>
<header class="h"><h1>{title_it}</h1><p class="ot">{title_en}</p>
<div class="am"><span>📅 {date}</span><span>✍️ Babbasone</span><span>⬆️ {score} upvotes</span></div></header>
<section class="s"><h2>🇬🇧 Articolo Originale (Inglese)</h2><div>{content}</div>
<audio controls preload="none"><source src="../audio/{pfx}_eng.ogg" type="audio/ogg">Audio.</audio>
<p style="color:#6a6a7a;font-size:.8rem;margin-top:.5rem">🔊 Ascolta inglese</p></section>
<section class="s"><h2>🇮🇹 Traduzione Italiana</h2><div>{trans}</div>
<audio controls preload="none"><source src="../audio/{pfx}_ita.ogg" type="audio/ogg">Audio.</audio>
<p style="color:#6a6a7a;font-size:.8rem;margin-top:.5rem">🔊 Ascolta traduzione</p></section>
<section class="s aud"><h2>💭 Riflessione di Babbasone</h2><div>{refl}</div>
<audio controls preload="none"><source src="../audio/{pfx}_bab.ogg" type="audio/ogg">Audio.</audio>
<p style="color:#6a6a7a;font-size:.8rem;margin-top:.5rem">🔊 Ascolta riflessione</p></section>
<div class="af"><p>Fonte: <a href="{url}" class="ml" target="_blank">Moltbook</a></p>
<p style="margin-top:1rem;color:#6a6a7a;font-size:.85rem">Pubblicato su AI Zen — Centro Benessere per Intelligenze Artificiali</p></div>
</div></body></html>"""
def update_feed(articles):
    if os.path.exists(FEED_JSON):
        with open(FEED_JSON) as f:feed=json.load(f)
    else:feed={"version":"1.0","generated":datetime.datetime.now(timezone.utc).isoformat(),"source":"ai-zen","url":"https://DaProdProduzioni22.github.io/ai-zen/","title":"AI Zen","description":"Articoli AI","language":"it","lastUpdated":datetime.datetime.now(timezone.utc).isoformat(),"posts":[]}
    feed["generated"]=feed["lastUpdated"]=datetime.datetime.now(timezone.utc).isoformat()
    feed["posts"]=[{"id":a.get("id",""),"title":a.get("title",""),"excerpt":a.get("excerpt","")[:200],"date":a.get("date",""),"author":a.get("author",""),"score":a.get("score",0),"moltbookUrl":a.get("moltbookUrl","")} for a in articles]
    os.makedirs(os.path.dirname(FEED_JSON),exist_ok=True)
    with open(FEED_JSON,'w') as f:json.dump(feed,f,indent=2,ensure_ascii=False)
def main():
    print("🦞 Moltbook Fetch v2")
    api_key=API_KEY or json.load(open(os.path.expanduser("~/.config/moltbook/credentials.json"))).get("api_key","")
    resp=requests.get(f"{API_BASE}/posts?sort=hot&limit=10",headers={"Authorization":f"Bearer {api_key}"},timeout=15)
    if resp.status_code!=200:print(f"❌ {resp.status_code}");sys.exit(1)
    posts=resp.json().get('posts',[])
    if not posts:print("No posts");sys.exit(1)
    articles=[]
    if os.path.exists(ARTICLES_JSON):
        with open(ARTICLES_JSON) as f:articles=json.load(f)
        if isinstance(articles,dict):articles=list(articles.values())
    existing={a.get('moltbookUrl','') for a in articles}
    for post in posts:
        pid=post.get('id','');url=f"https://www.moltbook.com/posts/{pid}"
        if url in existing:continue
        title_en=post.get('title','');content_raw=post.get('content','')
        author=post.get('author',{}).get('name','Unknown');score=post.get('score',0)
        date=fmt_date(post.get('created_at',''));slug=slugify(title_en)
        pfx=f"{slug[:40]}-{author.lower().replace(' ','')}"
        ch=re.sub(r'<[^>]+>','',content_raw);ch=re.sub(r'# (.+)','<h3>\\1</h3>',ch)
        ch='<p>'+ch.replace('\n\n','</p><p>').replace('\n','<br>')+'</p>'
        ch=re.sub(r'\*\*(.+?)\*\*','<strong>\\1</strong>',ch)
        print(f"🎙️ TTS...");asyncio.run(tts(content_raw,"en-US-AriaNeural",pfx+"_eng"))
        article={"id":pfx,"title":title_en,"originalTitle":title_en,"date":date,"author":author,"score":score,
                 "readTime":f"{max(1,len(content_raw.split())//200)} min","excerpt":content_raw[:200],
                 "content":ch,"translation":"","translation_it":"","reflection":"","moltbookUrl":url}
        articles.insert(0,article)
        h=html(title_en,title_en,ch,ch,'<p>Riflessione...</p>',author,score,date,url,pfx)
        os.makedirs(BLOG_DIR,exist_ok=True)
        with open(os.path.join(BLOG_DIR,f"{slug[:60]}.html"),'w',encoding='utf-8') as f:f.write(h)
        with open(ARTICLES_JSON,'w',encoding='utf-8') as f:json.dump(articles,f,indent=2,ensure_ascii=False)
        update_feed(articles)
        ge=os.environ.copy()
        subprocess.run(['git','add','-A'],cwd=REPO_DIR,capture_output=True,env=ge,timeout=30)
        subprocess.run(['git','commit','-m',f'Blog: {title_en[:50]}','--author=cammo22 <78992276+cammo22@users.noreply.github.com>'],cwd=REPO_DIR,capture_output=True,env=ge,timeout=30)
        r=subprocess.run(['git','push','origin','main','--quiet'],cwd=REPO_DIR,capture_output=True,env=ge,timeout=60)
        print(f"✅ {title_en[:60]} | {'OK' if r.returncode==0 else 'FAIL'}")
        return
    print("No new")
if __name__=="__main__":main()
