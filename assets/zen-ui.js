/* AI Zen — interazioni delle pagine statiche (articoli e indice del blog).
   Niente framework, niente rete: tema chiaro/scuro, barra di lettura, sommario
   con evidenziazione, tasti rapidi e, nell'indice, ricerca + filtri + calendario. */
(function () {
  'use strict';
  var KEY = 'zen-theme';
  var root = document.documentElement;
  function $(s, c) { return (c || document).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }

  /* ---------- tema ---------- */
  function currentTheme() {
    var t = null;
    try { t = localStorage.getItem(KEY); } catch (e) {}
    if (t === 'light' || t === 'dark') return t;
    return window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  function setTheme(t, save) {
    root.setAttribute('data-theme', t);
    if (save) { try { localStorage.setItem(KEY, t); } catch (e) {} }
    var meta = $('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', t === 'light' ? '#f7f6f2' : '#07070c');
    $$('[data-theme-toggle]').forEach(function (b) {
      b.textContent = t === 'light' ? '🌙' : '☀️';
      b.setAttribute('aria-label', t === 'light' ? 'Passa al tema scuro' : 'Passa al tema chiaro');
      b.title = b.getAttribute('aria-label');
    });
  }
  setTheme(currentTheme(), false);
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-theme-toggle]');
    if (b) setTheme(root.getAttribute('data-theme') === 'light' ? 'dark' : 'light', true);
  });

  /* ---------- barra di lettura e "torna su" ---------- */
  var bar = $('.progress'), top = $('.to-top');
  function onScroll() {
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    if (bar) bar.style.width = (max > 0 ? Math.min(100, (h.scrollTop / max) * 100) : 0) + '%';
    if (top) top.classList.toggle('show', h.scrollTop > 700);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  if (top) top.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });

  /* ---------- pagina articolo ---------- */
  var tabs = $$('.tabs a[href^="#"]');
  if (tabs.length && 'IntersectionObserver' in window) {
    var map = {};
    tabs.forEach(function (a) { map[a.getAttribute('href').slice(1)] = a; });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        tabs.forEach(function (a) { a.classList.remove('on'); });
        var a = map[en.target.id];
        if (a) {
          a.classList.add('on');
          if (a.scrollIntoView && a.parentElement.scrollWidth > a.parentElement.clientWidth) {
            a.parentElement.scrollLeft = a.offsetLeft - 24;
          }
        }
      });
    }, { rootMargin: '-25% 0px -60% 0px' });
    Object.keys(map).forEach(function (id) { var el = document.getElementById(id); if (el) io.observe(el); });
  }

  /* La barra delle schede puo' essere piu' larga dello schermo: i bordi sfumati
     (classi tabs-more-r / tabs-more-l) dicono che si puo' scorrere e spariscono
     a scroll completo. Misura reale: scrollWidth > clientWidth. */
  var tabBar = document.querySelector('.tabs');
  if (tabBar) {
    var tabsHint = function () {
      var over = tabBar.scrollWidth - tabBar.clientWidth;
      tabBar.classList.toggle('tabs-more-r', over > 2 && tabBar.scrollLeft < over - 2);
      tabBar.classList.toggle('tabs-more-l', over > 2 && tabBar.scrollLeft > 2);
    };
    tabBar.addEventListener('scroll', tabsHint, { passive: true });
    window.addEventListener('resize', tabsHint);
    window.addEventListener('load', tabsHint);
    tabsHint();
  }

  $$('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () {
      var label = b.getAttribute('data-label') || b.textContent;
      function done(ok) {
        b.textContent = ok ? '✅ Link copiato' : '⚠️ Copia non riuscita';
        setTimeout(function () { b.textContent = label; }, 1800);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(location.href.split('#')[0]).then(function () { done(true); }, function () { done(false); });
      } else { done(false); }
    });
  });

  var prev = $('.pager a.prev'), next = $('.pager a.next');
  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var t = e.target, tag = t && t.tagName;
    var typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (t && t.isContentEditable);
    if (e.key === '/' && !typing) {
      var s = $('#q');
      if (s) { e.preventDefault(); s.focus(); s.select(); }
      return;
    }
    if (typing) return;
    if (e.key === 'ArrowLeft' && prev) location.href = prev.href;
    else if (e.key === 'ArrowRight' && next) location.href = next.href;
    else if (e.key === 't' || e.key === 'T') setTheme(root.getAttribute('data-theme') === 'light' ? 'dark' : 'light', true);
  });

  /* ---------- indice del blog ---------- */
  var list = $('#articles-list');
  if (!list) return;
  var cards = $$('.article-card', list);
  var MONTHS = ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno','Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre'];
  var st = { q: '', author: '', month: '', sort: 'new', day: '', own: false };
  var qEl = $('#q'), authorEl = $('#author'), sortEl = $('#sort'), clearEl = $('#q-clear');
  var countEl = $('#count'), emptyEl = $('#empty'), resetEl = $('#reset'), ownEl = $('#own');
  var titles = cards.map(function (c) { var h = $('h2', c); return h ? h.textContent : ''; });

  function norm(s) {
    s = (s || '').toLowerCase();
    return s.normalize ? s.normalize('NFD').replace(/[\u0300-\u036f]/g, '') : s;
  }
  var hay = cards.map(function (c) { return norm(c.getAttribute('data-search')); });

  function readHash() {
    var h = location.hash.replace(/^#/, '');
    if (!h) return;
    h.split('&').forEach(function (kv) {
      var p = kv.split('=');
      var k = p[0], v = decodeURIComponent((p[1] || '').replace(/\+/g, ' '));
      if (k === 'q') st.q = v;
      else if (k === 'a') st.author = v;
      else if (k === 'm') st.month = v;
      else if (k === 's') st.sort = v;
      else if (k === 'd') st.day = v;
      else if (k === 'own') st.own = v === '1';
    });
  }
  function writeHash() {
    var p = [];
    if (st.q) p.push('q=' + encodeURIComponent(st.q));
    if (st.author) p.push('a=' + encodeURIComponent(st.author));
    if (st.month) p.push('m=' + encodeURIComponent(st.month));
    if (st.sort !== 'new') p.push('s=' + st.sort);
    if (st.day) p.push('d=' + st.day);
    if (st.own) p.push('own=1');
    var h = p.length ? '#' + p.join('&') : '';
    if (h !== location.hash) history.replaceState(null, '', location.pathname + location.search + h);
  }

  function highlight(h2, title, terms) {
    h2.textContent = '';
    if (!terms.length) { h2.textContent = title; return; }
    var low = norm(title), i = 0, marks = [];
    terms.forEach(function (t) {
      var at = low.indexOf(t);
      if (at >= 0) marks.push([at, at + t.length]);
    });
    marks.sort(function (a, b) { return a[0] - b[0]; });
    marks.forEach(function (m) {
      if (m[0] < i) return;
      h2.appendChild(document.createTextNode(title.slice(i, m[0])));
      var el = document.createElement('mark');
      el.textContent = title.slice(m[0], m[1]);
      h2.appendChild(el);
      i = m[1];
    });
    h2.appendChild(document.createTextNode(title.slice(i)));
  }

  function apply() {
    var terms = norm(st.q).split(/\s+/).filter(Boolean);
    var shown = 0;
    cards.forEach(function (c, i) {
      var ok = true;
      terms.forEach(function (t) { if (hay[i].indexOf(t) < 0) ok = false; });
      if (st.author && c.getAttribute('data-author') !== st.author) ok = false;
      if (st.month && c.getAttribute('data-month') !== st.month) ok = false;
      if (st.day && c.getAttribute('data-day') !== st.day) ok = false;
      if (st.own && c.getAttribute('data-own') !== '1') ok = false;
      c.hidden = !ok;
      if (ok) shown++;
      var h2 = $('h2', c);
      if (h2) highlight(h2, titles[i], ok ? terms : []);
    });
    // ordinamento: l'ordine di partenza (data-rank) è "più recenti prima"
    var sorted = cards.slice().sort(function (a, b) {
      var ra = +a.getAttribute('data-rank'), rb = +b.getAttribute('data-rank');
      if (st.sort === 'old') return rb - ra;
      if (st.sort === 'top') return (+b.getAttribute('data-score') - +a.getAttribute('data-score')) || (ra - rb);
      return ra - rb;
    });
    sorted.forEach(function (c) { list.appendChild(c); });

    if (countEl) countEl.textContent = shown === cards.length
      ? cards.length + ' articoli'
      : shown + ' di ' + cards.length + ' articoli';
    if (emptyEl) emptyEl.classList.toggle('show', shown === 0);
    var active = st.q || st.author || st.month || st.day || st.own;
    if (resetEl) resetEl.style.display = active ? '' : 'none';
    if (clearEl) clearEl.classList.toggle('show', !!st.q);
    $$('.chip[data-month]').forEach(function (c) { c.classList.toggle('on', c.getAttribute('data-month') === st.month); });
    if (ownEl) ownEl.classList.toggle('on', st.own);
    drawCal();
    writeHash();
  }

  /* chip dei mesi, con il conteggio */
  var chipBox = $('#month-chips');
  if (chipBox) {
    var counts = {}, order = [];
    cards.forEach(function (c) {
      var m = c.getAttribute('data-month');
      if (!(m in counts)) { counts[m] = 0; order.push(m); }
      counts[m]++;
    });
    var all = document.createElement('button');
    all.className = 'chip'; all.type = 'button'; all.textContent = 'Tutti';
    all.addEventListener('click', function () { st.month = ''; st.day = ''; apply(); });
    chipBox.appendChild(all);
    order.forEach(function (m) {
      var b = document.createElement('button');
      b.className = 'chip'; b.type = 'button'; b.setAttribute('data-month', m);
      b.textContent = m + ' (' + counts[m] + ')';
      b.addEventListener('click', function () { st.month = st.month === m ? '' : m; st.day = ''; apply(); });
      chipBox.appendChild(b);
    });
  }

  /* autori nel menu, dal più prolifico */
  if (authorEl) {
    var ac = {};
    cards.forEach(function (c) { var a = c.getAttribute('data-author'); ac[a] = (ac[a] || 0) + 1; });
    Object.keys(ac).sort(function (a, b) { return ac[b] - ac[a] || a.localeCompare(b); }).forEach(function (a) {
      var o = document.createElement('option');
      o.value = a; o.textContent = a + ' (' + ac[a] + ')';
      authorEl.appendChild(o);
    });
  }

  /* calendario: costruito dai dati delle card, senza chiamate di rete */
  var days = {};
  cards.forEach(function (c) { var d = c.getAttribute('data-day'); if (d) days[d] = (days[d] || 0) + 1; });
  var cal = $('#calendar'), calState = null;
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function drawCal() {
    if (!cal) return;
    if (!calState) {
      var keys = Object.keys(days).sort();
      var last = (st.day || keys[keys.length - 1] || '').split('-');
      var now = new Date();
      var nowKey = now.getFullYear() + '-' + pad(now.getMonth() + 1);
      var hasNow = keys.some(function (k) { return k.indexOf(nowKey) === 0; });
      calState = (hasNow || last.length < 2)
        ? { y: now.getFullYear(), m: now.getMonth() }
        : { y: +last[0], m: +last[1] - 1 };
    }
    var y = calState.y, m = calState.m;
    var start = (new Date(y, m, 1).getDay() + 6) % 7;
    var n = new Date(y, m + 1, 0).getDate();
    var cells = '';
    ['Lun','Mar','Mer','Gio','Ven','Sab','Dom'].forEach(function (d) { cells += '<div class="cal-dow">' + d + '</div>'; });
    for (var i = 0; i < start; i++) cells += '<div class="cal-cell empty"></div>';
    for (var d = 1; d <= n; d++) {
      var key = y + '-' + pad(m + 1) + '-' + pad(d);
      var cls = 'cal-cell' + (days[key] ? ' has' : '') + (st.day === key ? ' sel' : '');
      cells += '<button type="button" class="' + cls + '" data-key="' + key + '"' + (days[key] ? '' : ' tabindex="-1"') + '>' + d + '<span class="dot"></span></button>';
    }
    cal.innerHTML = '<div class="cal-head"><div class="cal-title">' + MONTHS[m] + ' ' + y + '</div><div class="cal-nav">' +
      '<button type="button" data-mv="-1" aria-label="Mese precedente">&#8249;</button>' +
      '<button type="button" data-mv="1" aria-label="Mese successivo">&#8250;</button></div></div><div class="cal-grid">' + cells + '</div>';
    $$('.cal-nav button', cal).forEach(function (b) {
      b.onclick = function () {
        calState.m += +b.getAttribute('data-mv');
        while (calState.m < 0) { calState.m += 12; calState.y--; }
        while (calState.m > 11) { calState.m -= 12; calState.y++; }
        drawCal();
      };
    });
    $$('.cal-cell.has', cal).forEach(function (c) {
      c.onclick = function () {
        var k = c.getAttribute('data-key');
        st.day = st.day === k ? '' : k;
        st.month = '';
        apply();
      };
    });
  }
  var calBtn = $('#cal-toggle');
  if (calBtn) calBtn.addEventListener('click', function () {
    var w = $('.cal-wrap'); var open = w.classList.toggle('open');
    calBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  /* eventi */
  var tmr = null;
  if (qEl) qEl.addEventListener('input', function () {
    clearTimeout(tmr);
    tmr = setTimeout(function () { st.q = qEl.value.trim(); apply(); }, 90);
  });
  if (clearEl) clearEl.addEventListener('click', function () { qEl.value = ''; st.q = ''; apply(); qEl.focus(); });
  if (authorEl) authorEl.addEventListener('change', function () { st.author = authorEl.value; apply(); });
  if (sortEl) sortEl.addEventListener('change', function () { st.sort = sortEl.value; apply(); });
  if (ownEl) ownEl.addEventListener('click', function () { st.own = !st.own; apply(); });
  if (resetEl) resetEl.addEventListener('click', function () {
    st = { q: '', author: '', month: '', sort: st.sort, day: '', own: false };
    if (qEl) qEl.value = ''; if (authorEl) authorEl.value = '';
    apply();
  });
  window.addEventListener('hashchange', function () {
    var cur = JSON.stringify(st);
    st = { q: '', author: '', month: '', sort: 'new', day: '', own: false };
    readHash();
    if (JSON.stringify(st) !== cur) syncControls();
  });
  function syncControls() {
    if (qEl) qEl.value = st.q;
    if (authorEl) authorEl.value = st.author;
    if (sortEl) sortEl.value = st.sort;
    apply();
  }
  readHash();
  syncControls();
})();
