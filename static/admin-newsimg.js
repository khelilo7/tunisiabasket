// Admin: a Facebook image (PNG) for a news item, drawn in the browser: the label, the headline, a short text, and the player's photo or the club's
// logo when the news is about one. Three sizes (portrait and square for the feed, wide for a link share), French or English, plus the post text.
// Used from the News tab (admin-content.js): NewsImg.mount(element, item, onClose). Nothing is uploaded anywhere.
(function () {
  const K = window.ImgKit; if (!K) return;
  const { C, txt, rr, loadImg } = K;
  const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif';
  const FORMATS = { portrait: [1080, 1350, 'Portrait 1080×1350 (feed)'], square: [1080, 1080, 'Square 1080×1080'], wide: [1200, 630, 'Wide 1200×630 (link size)'] };
  const LBL = { fr: { official: 'OFFICIEL', injury: 'BLESSURE', transfer: 'TRANSFERT', result: 'RÉSULTAT', info: 'INFO', interview: 'INTERVIEW' },
    en: { official: 'OFFICIAL', injury: 'INJURY', transfer: 'TRANSFER', result: 'RESULT', info: 'NEWS', interview: 'INTERVIEW' } };
  const COL = { official: '#3ecf8e', injury: '#ff5d6c', transfer: '#4f93ff', result: '#ff8a1f', info: '#ffb15c', interview: '#c45bf0' };
  const ICON = { official: '📢', injury: '🩹', transfer: '🔁', result: '🏀', info: '📰', interview: '🎙️' };
  const TAGS = '#ProA #BasketballTunisie #TunisiaBasket';

  function wrap(ctx, s, maxW, size, weight) {
    ctx.font = `${weight} ${size}px ${FONT}`;
    const out = []; let cur = '';
    for (const w of String(s).split(/\s+/).filter(Boolean)) { const t = cur ? cur + ' ' + w : w; if (ctx.measureText(t).width > maxW && cur) { out.push(cur); cur = w; } else cur = t; }
    if (cur) out.push(cur);
    return out;
  }
  // The biggest size that keeps the text within maxLines lines and maxH pixels; at the smallest size it is cut with an ellipsis.
  function fit(ctx, s, maxW, maxLines, maxH, from, to, weight, lh) {
    for (let size = from; size >= to; size -= 2) { const l = wrap(ctx, s, maxW, size, weight); if (l.length <= maxLines && l.length * size * lh <= maxH) return { size, lines: l, h: l.length * size * lh }; }
    const l = wrap(ctx, s, maxW, to, weight).slice(0, maxLines); if (l.length) l[l.length - 1] = l[l.length - 1].replace(/[\s.,;:!?]*$/, '') + '…';
    return { size: to, lines: l, h: l.length * to * lh };
  }
  const clip = (s, n) => { s = String(s || '').trim(); return s.length > n ? s.slice(0, n).replace(/\s+\S*$/, '') + '…' : s; };
  const dateText = (iso, lang) => iso ? new Date(iso + 'T12:00').toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric' }) : '';
  const pick = (item, lang) => ({ title: (lang === 'en' && item.title_en) || item.title || '', body: (lang === 'en' && item.body_en) || item.body || '' });

  async function media(ctx, item, cx, cy, d, col) {
    const r = d / 2;
    ctx.beginPath(); ctx.arc(cx, cy, r + 10, 0, 7); ctx.fillStyle = col; ctx.fill();
    ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.fillStyle = '#ffffff'; ctx.fill(); ctx.clip();
    const ph = item.player && item.photo ? await loadImg(item.photo) : null, tl = item.team ? await loadImg(`/img/teams/${item.team}.png`) : null;
    if (ph) { const s = Math.min(ph.width, ph.height); ctx.drawImage(ph, (ph.width - s) / 2, (ph.height - s) * 0.12, s, s, cx - r, cy - r, d, d); }
    else if (tl) { const p = d * 0.16; ctx.drawImage(tl, cx - r + p, cy - r + p, d - 2 * p, d - 2 * p); }
    else { ctx.fillStyle = '#1b2646'; ctx.fillRect(cx - r, cy - r, d, d); txt(ctx, ICON[item.label] || '📰', cx, cy + d * 0.14, { size: d * 0.46, align: 'center' }); }
    ctx.restore();
    if (ph && tl) {                                                // the club's badge on the player's photo
      const b = d * 0.34, bx = cx + r * 0.62, by = cy + r * 0.62;
      ctx.beginPath(); ctx.arc(bx, by, b / 2 + 5, 0, 7); ctx.fillStyle = col; ctx.fill(); ctx.beginPath(); ctx.arc(bx, by, b / 2, 0, 7); ctx.fillStyle = '#fff'; ctx.fill();
      const p = b * 0.12; ctx.drawImage(tl, bx - b / 2 + p, by - b / 2 + p, b - 2 * p, b - 2 * p);
    }
  }

  function pillAt(ctx, label, x, y, col, center) {
    ctx.font = `900 26px ${FONT}`; ctx.letterSpacing = '3px'; const pw = ctx.measureText(label).width + 52; ctx.letterSpacing = '0px';
    const px = center ? x - pw / 2 : x; ctx.fillStyle = col; rr(ctx, px, y, pw, 52, 26); ctx.fill(); txt(ctx, label, px + pw / 2, y + 36, { size: 26, weight: 900, color: '#10131c', align: 'center', space: '3px' });
  }
  // The score card of a game: both clubs, the score, the headline and the game MVP's line
  async function scoreBody(ctx, W, H, item, st, col, title, body) {
    const m = item.match, wide = st.fmt === 'wide', lang = st.lang, hw = m.home_score > m.away_score, sq = st.fmt === 'square', D = wide ? 190 : sq ? 220 : 270;
    const dy = wide ? 0 : sq ? 24 : 120;                                // the block sits in the middle of the page
    pillAt(ctx, `${LBL[lang][item.label] || LBL[lang].result}${m.md ? ' · ' + (lang === 'fr' ? 'J' : 'MD') + m.md : ''}`, W / 2, wide ? 118 : 150 + dy, col, true);
    const ly = wide ? 325 : (sq ? 345 : 390) + dy, lx = wide ? 190 : W * 0.26;
    await K.logo(ctx, m.home, lx - D / 2, ly - D / 2, D); await K.logo(ctx, m.away, W - lx - D / 2, ly - D / 2, D);
    const ny = ly + D / 2 + (wide ? 42 : 46), tw = wide ? 300 : 420;
    txt(ctx, m.home_name, lx, ny, { size: 32, weight: 800, align: 'center', maxW: tw }); txt(ctx, m.away_name, W - lx, ny, { size: 32, weight: 800, align: 'center', maxW: tw });
    const ss = wide ? 150 : sq ? 130 : 170, sb = wide ? 345 : ny + 40 + ss * 0.74;
    txt(ctx, String(m.home_score), W / 2 - 46, sb, { size: ss, weight: 900, color: hw ? C.txt : C.mut, align: 'right' });
    txt(ctx, '–', W / 2, sb - ss * 0.12, { size: ss * 0.5, weight: 700, color: C.mut, align: 'center' });
    txt(ctx, String(m.away_score), W / 2 + 46, sb, { size: ss, weight: 900, color: hw ? C.mut : C.txt });
    ctx.fillStyle = col; const wx = hw ? lx : W - lx; rr(ctx, wx - 70, ly + D / 2 + (wide ? 56 : 62), 140, 6, 3); ctx.fill();   // a bar under the winner
    const cw = wide ? W - 2 * (190 + D / 2 + 40) : W - 140, top = wide ? 390 : sb + 56, bottom = H - 78 - 30;
    const bl = st.text && body ? wrap(ctx, body, cw, 30, 500).slice(0, wide ? 1 : 2) : [], bh = bl.length * 42;
    const head = fit(ctx, title, cw, wide ? 3 : 3, Math.max(100, bottom - top - bh - 18), wide ? 40 : 60, 34, 900, 1.15);
    head.lines.forEach((l, i) => txt(ctx, l, W / 2, top + head.size * (1.15 * i + 0.9), { size: head.size, weight: 900, align: 'center' }));
    bl.forEach((l, i) => txt(ctx, l, W / 2, top + head.h + 18 + 30 + i * 42, { size: 30, weight: 500, color: C.mut, align: 'center' }));
  }

  async function draw(cv, item, st) {
    const [W, H] = FORMATS[st.fmt], wide = st.fmt === 'wide', lang = st.lang, col = COL[item.label] || C.acc, { title, body } = pick(item, lang);
    cv.width = W; cv.height = H; const ctx = cv.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, C.bg2); g.addColorStop(0.5, C.bg1); g.addColorStop(1, '#070b16'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    const glow = ctx.createRadialGradient(W - 60, 40, 10, W - 60, 40, 560); glow.addColorStop(0, col + '47'); glow.addColorStop(1, col + '00'); ctx.fillStyle = glow; ctx.fillRect(0, 0, W, Math.min(H, 640));
    ctx.fillStyle = col; ctx.fillRect(0, 0, W, 10);
    const lg = await loadImg('/img/logo-96.png'); if (lg) ctx.drawImage(lg, 48, 34, 52, 64);
    txt(ctx, 'TUNISIA', 118, 78, { size: 34, weight: 900, color: C.acc, space: '2px' }); ctx.font = `900 34px ${FONT}`; ctx.letterSpacing = '2px';
    const w1 = ctx.measureText('TUNISIA ').width; ctx.letterSpacing = '0px'; txt(ctx, 'BASKET', 118 + w1, 78, { size: 34, weight: 900, space: '2px' });
    txt(ctx, 'PRO A', W - 48, 76, { size: 22, weight: 700, color: C.mut, align: 'right', space: '2px' });
    ctx.fillStyle = C.line; ctx.fillRect(48, H - 78, W - 96, 2);
    txt(ctx, 'tunisiabasket.com', 48, H - 36, { size: 26, weight: 800, color: C.acc });
    txt(ctx, dateText(item.date, lang), W - 48, H - 36, { size: 22, color: C.mut, align: 'right' });

    if (st.style === 'score' && item.match) { await scoreBody(ctx, W, H, item, st, col, title, body); return; }
    // the picture, then the text column (centred under it; to its right on the wide format)
    const D = wide ? 280 : st.fmt === 'square' ? 230 : 320, mcx = wide ? 70 + D / 2 + 10 : W / 2, mcy = wide ? H / 2 + 6 : 130 + D / 2 + 10;
    await media(ctx, item, mcx, mcy, D, col);
    const left = wide ? 70 + D + 70 : 70, tw = wide ? W - left - 60 : W - 140, ax = wide ? 'left' : 'center', x = wide ? left : W / 2;
    const top = wide ? 0 : mcy + D / 2 + 46, bottom = H - 78 - 34;
    ctx.font = `900 26px ${FONT}`; ctx.letterSpacing = '3px'; const label = LBL[lang][item.label] || LBL[lang].info, pw = ctx.measureText(label).width + 52; ctx.letterSpacing = '0px';
    const PH = 52, BS = wide ? 28 : 32, maxBody = wide || st.fmt === 'square' ? 2 : 4;
    let bodyLines = st.text && body ? wrap(ctx, body.trim(), tw, BS, 500) : [];
    if (bodyLines.length > maxBody) { bodyLines = bodyLines.slice(0, maxBody); bodyLines[maxBody - 1] = bodyLines[maxBody - 1].replace(/[\s.,;:!?]*$/, '') + '…'; }
    const bodyH = bodyLines.length * BS * 1.4;
    const gap1 = 30, gap2 = bodyLines.length ? 26 : 0, head = fit(ctx, title, tw, wide ? 4 : st.fmt === 'square' ? 4 : 5, Math.max(120, (wide ? H - 110 - 90 : bottom - top) - PH - gap1 - gap2 - bodyH), wide ? 64 : 84, 40, 900, 1.14);
    const block = PH + gap1 + head.h + gap2 + bodyH;
    let y = wide ? Math.max(104, (104 + bottom - block) / 2) : top;
    const px = ax === 'center' ? x - pw / 2 : x;
    ctx.fillStyle = col; rr(ctx, px, y, pw, PH, PH / 2); ctx.fill();
    txt(ctx, label, px + pw / 2, y + 36, { size: 26, weight: 900, color: '#10131c', align: 'center', space: '3px' });
    y += PH + gap1;
    head.lines.forEach((l, i) => txt(ctx, l, x, y + head.size * (1.14 * i + 0.92), { size: head.size, weight: 900, align: ax }));
    y += head.h + gap2;
    bodyLines.forEach((l, i) => txt(ctx, l, x, y + BS * (1.4 * i + 1), { size: BS, weight: 500, color: C.mut, align: ax }));
  }

  function postText(item, lang) {
    const { title, body } = pick(item, lang), url = lang === 'fr' ? 'https://tunisiabasket.com/actualites' : 'https://tunisiabasket.com/en/news';
    return `${ICON[item.label] || '📰'} ${title}\n\n${body ? clip(body, 300) + '\n\n' : ''}${lang === 'fr' ? '👉 Toute l’actualité de la Pro A' : '👉 All the Pro A news'} : ${url}\n${TAGS}`;
  }

  function mount(el, item, onClose) {
    const st = { fmt: 'portrait', lang: 'fr', text: true, style: item.match ? 'score' : 'headline' }; let busy = false, again = false;
    el.innerHTML = `<div class="card" style="margin:12px 0;border-color:var(--acc)"><div class="row"><b>🖼 Facebook image</b><span class="sp"></span>
        <select id="ni-fmt">${Object.entries(FORMATS).map(([k, v]) => `<option value="${k}">${v[2]}</option>`).join('')}</select>
        ${item.match ? `<select id="ni-style"><option value="score">Score card</option><option value="headline">Headline card</option></select>` : ''}<select id="ni-lang"><option value="fr">Français</option><option value="en">English</option></select>
        <label class="small mut"><input type="checkbox" id="ni-body" checked> show the text</label><button id="ni-close" title="Close">✕</button></div>
      <div class="row" style="margin:10px 0"><button class="primary" id="ni-dl" disabled>⬇ Download PNG</button><span class="mut small">Ready to post. Drawn from the news as it is now.</span><span id="ni-err" class="small" style="color:var(--bad)"></span></div>
      <canvas id="ni-cv" width="1080" height="1350" style="width:100%;max-width:560px;height:auto;border-radius:14px;border:1px solid var(--line);display:block"></canvas>
      <div class="row" style="align-items:flex-start;margin-top:10px;gap:8px"><textarea id="ni-cap" rows="5" style="flex:1;min-width:260px;font:inherit;resize:vertical"></textarea><button id="ni-copy">📋 Copy the post text</button></div></div>`;
    const q = s => el.querySelector(s), cv = q('#ni-cv');
    async function run() {
      if (busy) { again = true; return; } busy = true; q('#ni-dl').disabled = true;
      try { await draw(cv, item, st); q('#ni-err').textContent = ''; q('#ni-dl').disabled = false; } catch (e) { q('#ni-err').textContent = 'Could not draw the image: ' + e.message; }
      busy = false; if (again) { again = false; run(); }
    }
    q('#ni-fmt').onchange = e => { st.fmt = e.target.value; run(); };
    q('#ni-lang').onchange = e => { st.lang = e.target.value; q('#ni-cap').value = postText(item, st.lang); run(); };
    if (q('#ni-style')) q('#ni-style').onchange = e => { st.style = e.target.value; run(); };
    q('#ni-body').onchange = e => { st.text = e.target.checked; run(); };
    q('#ni-close').onclick = () => { el.innerHTML = ''; if (onClose) onClose(); };
    q('#ni-dl').onclick = () => cv.toBlob(b => { const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `tunisia-basket-news-${(item.id || 'draft')}-${st.fmt}.png`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); }, 'image/png');
    q('#ni-copy').onclick = async () => { const c = q('#ni-cap'), b = q('#ni-copy'); try { await navigator.clipboard.writeText(c.value); b.textContent = '✅ Copied'; } catch (x) { c.select(); } setTimeout(() => { b.textContent = '📋 Copy the post text'; }, 1800); };
    q('#ni-cap').value = postText(item, st.lang);
    run();
  }
  window.NewsImg = { mount };
})();
