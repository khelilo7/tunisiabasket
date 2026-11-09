// Admin: a "player of the game" image for Facebook. You choose a game and a player, upload a recent photo (it becomes the background), write a
// free headline ("Homme du match", "Il a dominé"...) and pick the stat tiles. The photo is only read by your browser to draw the picture: it is not uploaded.
// Used from the News tab: Spotlight.mount(element, gameResult, matchday). Needs ImgKit (admin-images.js).
(function () {
  const K = window.ImgKit; if (!K) return;
  const { C, txt, rr, loadImg, nm } = K;
  const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif';
  const F = { portrait: [1080, 1350, 'Portrait 1080×1350 (feed)'], square: [1080, 1080, 'Square 1080×1080'], story: [1080, 1920, 'Story 1080×1920'] };
  const STATS = { pts: ['PTS', 'PTS'], reb: ['REB', 'REB'], ast: ['PD', 'AST'], stl: ['INT', 'STL'], blk: ['CTR', 'BLK'], p3m: ['3PT', '3PT'], pir: ['PIR', 'PIR'], min: ['MIN', 'MIN'], pm: ['+/-', '+/-'] };
  const HEADS = { fr: ['Homme du match', 'Énorme performance', 'Il a dominé la rencontre', 'Soirée XXL', 'Le show de la soirée', 'Il a fait la différence'],
    en: ['Man of the match', 'Huge performance', 'He dominated the game', 'Big night', 'The show of the night', 'He made the difference'] };
  const TAGS = '#ProA #BasketballTunisie #TunisiaBasket';
  let siteCache = null;
  const sitePlayers = async () => siteCache || (siteCache = await fetch('/api/players').then(r => r.json()).then(j => j.players).catch(() => []));

  function wrap(ctx, s, maxW, size, weight) {
    ctx.font = `${weight} ${size}px ${FONT}`; const out = []; let cur = '';
    for (const w of String(s).split(/\s+/).filter(Boolean)) { const t = cur ? cur + ' ' + w : w; if (ctx.measureText(t).width > maxW && cur) { out.push(cur); cur = w; } else cur = t; }
    if (cur) out.push(cur); return out;
  }
  function fit(ctx, s, maxW, maxLines, from, to, weight) {
    for (let size = from; size >= to; size -= 2) { const l = wrap(ctx, s, maxW, size, weight); if (l.length <= maxLines) return { size, lines: l }; }
    const l = wrap(ctx, s, maxW, to, weight).slice(0, maxLines); if (l.length) l[l.length - 1] = l[l.length - 1].replace(/[\s.,;:!?]*$/, '') + '…'; return { size: to, lines: l };
  }
  const signed = v => v > 0 ? '+' + v : String(v);

  function mount(el, game, md) {
    const players = (game.players || []).slice().sort((a, b) => b.pir - a.pir);
    if (!players.length) { el.innerHTML = '<div class="card" style="margin:12px 0"><div class="row"><b>📸 Player photo image</b><span class="sp"></span><button id="sp-close">✕</button></div><div class="mut small" style="margin-top:6px">This game has no box score yet, so there are no player stats to show. Add its box score (Data tab), then come back.</div></div>';
      el.querySelector('#sp-close').onclick = () => { el.innerHTML = ''; }; return; }
    const mvpName = game.mvp && game.mvp.name;
    const st = { fmt: 'portrait', lang: 'fr', pid: '', stats: ['pts', 'reb', 'ast', 'pir'], zoom: 100, ox: 0, oy: 60, dark: 60, head: '', touched: false, img: null, own: false };
    const key = p => p.id || `${p.team}-${p.number}`;
    st.pid = key(players.find(p => p.name === mvpName) || players[0]);
    el.innerHTML = `<div class="card" style="margin:12px 0;border-color:var(--acc)"><div class="row"><b>📸 Player photo image</b><span class="sp"></span><button id="sp-close" title="Close">✕</button></div>
      <div class="row" style="margin-top:8px"><select id="sp-player">${players.map(p => `<option value="${esc(key(p))}" ${key(p) === st.pid ? 'selected' : ''}>${esc(nm(p.name))} · ${esc(p.team)} · ${p.pts} pts</option>`).join('')}</select>
        <select id="sp-fmt">${Object.entries(F).map(([k, v]) => `<option value="${k}">${v[2]}</option>`).join('')}</select><select id="sp-lang"><option value="fr">Français</option><option value="en">English</option></select></div>
      <div class="row" style="margin-top:8px"><label class="small mut">Photo</label><input type="file" id="sp-file" accept="image/*"><span class="mut small" id="sp-fnote">Upload a recent photo of the game (it fills the background). Without one, the site’s photo of the player is used.</span></div>
      <div class="row" style="margin-top:8px"><label class="small mut">Headline</label><input id="sp-head" list="sp-heads" maxlength="80" style="min-width:280px;flex:1" placeholder="Freestyle: Homme du match, Il a dominé…"><datalist id="sp-heads"></datalist></div>
      <div class="row" style="margin-top:8px"><span class="small mut">Stats</span>${Object.entries(STATS).map(([k, v]) => `<label class="small"><input type="checkbox" data-stat="${k}" ${st.stats.includes(k) ? 'checked' : ''}> ${v[1]}</label>`).join('')}<span class="mut small">(up to 6)</span></div>
      <div class="row" style="margin-top:8px;gap:14px"><label class="small mut">Zoom <input type="range" id="sp-zoom" min="100" max="300" value="100"></label><label class="small mut">← → <input type="range" id="sp-ox" min="-100" max="100" value="0"></label>
        <label class="small mut">↑ ↓ <input type="range" id="sp-oy" min="-100" max="100" value="${st.oy}"></label><label class="small mut">Darkness <input type="range" id="sp-dark" min="0" max="100" value="60"></label><span class="mut small">or drag the picture</span></div>
      <div class="row" style="margin:10px 0"><button class="primary" id="sp-dl" disabled>⬇ Download PNG</button><span class="mut small">Your photo is only used in your browser to draw this image: it is not uploaded.</span><span id="sp-err" class="small" style="color:var(--bad)"></span></div>
      <canvas id="sp-cv" width="1080" height="1350" style="width:100%;max-width:560px;height:auto;border-radius:14px;border:1px solid var(--line);display:block;cursor:grab;touch-action:none"></canvas>
      <div class="row" style="align-items:flex-start;margin-top:10px;gap:8px"><textarea id="sp-cap" rows="5" style="flex:1;min-width:260px;font:inherit;resize:vertical"></textarea><button id="sp-copy">📋 Copy the post text</button></div></div>`;
    const q = s => el.querySelector(s), cv = q('#sp-cv'), cur = () => players.find(p => key(p) === st.pid);
    const defHead = () => HEADS[st.lang][cur().name === mvpName ? 0 : 1];
    let busy = false, again = false, lay = { rx: 0, ry: 0 };

    async function siteImage() { const p = cur(), sp = (await sitePlayers()).find(x => x.id === p.id); return sp && sp.photo ? loadImg(sp.photo) : null; }
    async function draw() {
      if (busy) { again = true; return; } busy = true; q('#sp-dl').disabled = true;
      try {
        const [W, H] = F[st.fmt], p = cur(), lang = st.lang, ctx = cv.getContext('2d'); cv.width = W; cv.height = H;
        ctx.fillStyle = '#0b1020'; ctx.fillRect(0, 0, W, H);
        const img = st.img || await siteImage();
        if (img) {
          const base = Math.max(W / img.width, H / img.height) * st.zoom / 100, dw = img.width * base, dh = img.height * base; lay = { rx: Math.max(0, (dw - W) / 2), ry: Math.max(0, (dh - H) / 2) };
          ctx.drawImage(img, (W - dw) / 2 + st.ox / 100 * lay.rx, (H - dh) / 2 + st.oy / 100 * lay.ry, dw, dh);
        } else { const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, C.bg2); g.addColorStop(1, '#070b16'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); await K.logo(ctx, p.team, W / 2 - 200, H * 0.2, 400); }
        const a = st.dark / 100;                                           // dark gradients so the text stays readable on any photo
        ctx.fillStyle = `rgba(7,11,22,${0.05 + a * 0.2})`; ctx.fillRect(0, 0, W, H);
        let g = ctx.createLinearGradient(0, 0, 0, H * 0.24); g.addColorStop(0, `rgba(7,11,22,${0.55 + a * 0.35})`); g.addColorStop(1, 'rgba(7,11,22,0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H * 0.24);
        g = ctx.createLinearGradient(0, H * 0.34, 0, H); g.addColorStop(0, 'rgba(7,11,22,0)'); g.addColorStop(0.55, `rgba(7,11,22,${0.5 + a * 0.35})`); g.addColorStop(1, `rgba(7,11,22,${0.78 + a * 0.2})`); ctx.fillStyle = g; ctx.fillRect(0, H * 0.34, W, H * 0.66);
        ctx.fillStyle = C.acc; ctx.fillRect(0, 0, W, 8);
        // header: the brand on the left, the score of the game on the right
        const lg = await loadImg('/img/logo-96.png'); if (lg) ctx.drawImage(lg, 48, 34, 52, 64);
        txt(ctx, 'TUNISIA', 118, 78, { size: 34, weight: 900, color: C.acc, space: '2px' }); ctx.font = `900 34px ${FONT}`; ctx.letterSpacing = '2px'; const w1 = ctx.measureText('TUNISIA ').width; ctx.letterSpacing = '0px';
        txt(ctx, 'BASKET', 118 + w1, 78, { size: 34, weight: 900, space: '2px' });
        const sc = `${game.home} ${game.home_score} – ${game.away_score} ${game.away}`; ctx.font = `800 30px ${FONT}`; const cw = ctx.measureText(sc).width + 150;
        ctx.fillStyle = 'rgba(11,16,32,.72)'; rr(ctx, W - 48 - cw, 30, cw, 70, 35); ctx.fill();
        await K.logo(ctx, game.home, W - 48 - cw + 12, 40, 50); await K.logo(ctx, game.away, W - 48 - 62, 40, 50);
        txt(ctx, sc, W - 48 - cw / 2, 77, { size: 30, weight: 800, align: 'center' });
        // footer
        ctx.fillStyle = 'rgba(255,255,255,.25)'; ctx.fillRect(48, H - 78, W - 96, 2); txt(ctx, 'tunisiabasket.com', 48, H - 36, { size: 26, weight: 800, color: C.acc }); txt(ctx, `PRO A · ${lang === 'fr' ? 'JOURNÉE' : 'MATCHDAY'} ${md}`, W - 48, H - 36, { size: 22, weight: 700, color: '#cfd6ea', align: 'right', space: '2px' });
        // stat tiles
        const sel = Object.keys(STATS).filter(k => st.stats.includes(k)).slice(0, 6), TH = 150, ty = H - 78 - 30 - TH, gap = 14, tw = (W - 96 - gap * (sel.length - 1)) / (sel.length || 1);
        sel.forEach((k, i) => {
          const x = 48 + i * (tw + gap); ctx.fillStyle = 'rgba(11,16,32,.78)'; rr(ctx, x, ty, tw, TH, 20); ctx.fill(); ctx.strokeStyle = i === 0 ? C.acc : 'rgba(255,255,255,.18)'; ctx.lineWidth = 2; ctx.stroke();
          txt(ctx, k === 'pm' ? signed(p[k]) : String(p[k]), x + tw / 2, ty + 90, { size: 70, weight: 900, color: i === 0 ? C.acc : C.txt, align: 'center', maxW: tw - 20 });
          txt(ctx, STATS[k][lang === 'fr' ? 0 : 1], x + tw / 2, ty + 130, { size: 24, weight: 800, color: '#b8c2de', align: 'center', space: '2px' });
        });
        // team line, name, headline (stacked upwards from the tiles)
        let y = ty - 30; const opp = p.opp, team = `${p.team} · #${p.number} · ${lang === 'fr' ? 'contre' : 'vs'} ${opp}`;
        await K.logo(ctx, p.team, 48, y - 36, 44); txt(ctx, team, 106, y, { size: 30, weight: 700, color: '#dfe5f5' });
        const nameF = fit(ctx, nm(p.name).toUpperCase(), W - 96, 2, 110, 56, 900);
        y -= 56 + (nameF.lines.length - 1) * nameF.size * 1.02; nameF.lines.forEach((l, i) => txt(ctx, l, 48, y + i * nameF.size * 1.02, { size: nameF.size, weight: 900 }));
        const head = (st.head || defHead()).trim();
        if (head) { const hf = fit(ctx, head.toUpperCase(), W - 96, 2, 46, 28, 900); y -= nameF.size * 0.85 + 22 + (hf.lines.length - 1) * hf.size * 1.15; hf.lines.forEach((l, i) => txt(ctx, l, 48, y + i * hf.size * 1.15, { size: hf.size, weight: 900, color: C.acc, space: '3px' })); }
        q('#sp-err').textContent = ''; q('#sp-dl').disabled = false;
      } catch (e) { q('#sp-err').textContent = 'Could not draw the image: ' + e.message; }
      busy = false; if (again) { again = false; draw(); }
    }
    const caption = () => {
      const p = cur(), lang = st.lang, head = (st.head || defHead()).trim(), who = nm(p.name), md_ = game.mvp && game.mvp.name === p.name;
      const url = game.game_id ? (lang === 'fr' ? 'https://tunisiabasket.com/match/' : 'https://tunisiabasket.com/en/game/') + game.game_id : 'https://tunisiabasket.com';
      const line = lang === 'fr' ? `${p.pts} pts, ${p.reb} reb, ${p.ast} pd` : `${p.pts} pts, ${p.reb} reb, ${p.ast} ast`;
      return `${md_ ? '⭐' : '🔥'} ${head} : ${who} (${p.team}) !\n${line} — ${game.home_name} ${game.home_score}–${game.away_score} ${game.away_name} (${lang === 'fr' ? 'J' : 'MD'}${md})\n${lang === 'fr' ? '📋 La feuille de match complète' : '📋 The full box score'} : ${url}\n${TAGS}`;
    };
    const setHead = () => { q('#sp-head').value = st.touched ? st.head : ''; q('#sp-head').placeholder = defHead(); q('#sp-heads').innerHTML = HEADS[st.lang].map(h => `<option value="${esc(h)}">`).join(''); q('#sp-cap').value = caption(); };
    const upd = () => { q('#sp-cap').value = caption(); draw(); };
    q('#sp-player').onchange = e => { st.pid = e.target.value; st.img = st.own ? st.img : null; setHead(); draw(); };
    q('#sp-fmt').onchange = e => { st.fmt = e.target.value; draw(); };
    q('#sp-lang').onchange = e => { st.lang = e.target.value; setHead(); draw(); };
    q('#sp-head').oninput = e => { st.touched = true; st.head = e.target.value; upd(); };
    el.querySelectorAll('[data-stat]').forEach(b => b.onchange = () => { st.stats = [...el.querySelectorAll('[data-stat]:checked')].map(x => x.dataset.stat); draw(); });
    [['zoom', 'zoom'], ['ox', 'ox'], ['oy', 'oy'], ['dark', 'dark']].forEach(([id, k]) => q('#sp-' + id).oninput = e => { st[k] = +e.target.value; draw(); });
    q('#sp-file').onchange = e => {
      const f = e.target.files[0]; if (!f) return; const i = new Image(), u = URL.createObjectURL(f);
      i.onload = () => { st.img = i; st.own = true; st.zoom = 100; st.ox = 0; st.oy = 60; q('#sp-zoom').value = 100; q('#sp-ox').value = 0; q('#sp-oy').value = 60; q('#sp-fnote').textContent = f.name; draw(); };
      i.onerror = () => { q('#sp-err').textContent = 'This file is not an image the browser can read.'; URL.revokeObjectURL(u); }; i.src = u;
    };
    let drag = null;                                                     // drag the picture to place it
    cv.onpointerdown = e => { drag = { x: e.clientX, y: e.clientY }; cv.setPointerCapture(e.pointerId); cv.style.cursor = 'grabbing'; };
    cv.onpointerup = () => { drag = null; cv.style.cursor = 'grab'; };
    cv.onpointermove = e => {
      if (!drag) return; const k = cv.width / cv.clientWidth, dx = (e.clientX - drag.x) * k, dy = (e.clientY - drag.y) * k; drag = { x: e.clientX, y: e.clientY };
      if (lay.rx) st.ox = Math.max(-100, Math.min(100, st.ox + dx / lay.rx * 100)); if (lay.ry) st.oy = Math.max(-100, Math.min(100, st.oy + dy / lay.ry * 100));
      q('#sp-ox').value = st.ox; q('#sp-oy').value = st.oy; draw();
    };
    q('#sp-close').onclick = () => { el.innerHTML = ''; };
    q('#sp-dl').onclick = () => cv.toBlob(b => { const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `tunisia-basket-${st.pid}-${st.fmt}.png`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); }, 'image/png');
    q('#sp-copy').onclick = async () => { const c = q('#sp-cap'), b = q('#sp-copy'); try { await navigator.clipboard.writeText(c.value); b.textContent = '✅ Copied'; } catch (x) { c.select(); } setTimeout(() => { b.textContent = '📋 Copy the post text'; }, 1800); };
    setHead(); draw();
  }
  window.Spotlight = { mount };
})();
