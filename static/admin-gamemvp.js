// Admin, Images tab: the MVP of ONE game as a poster for Facebook. You pick the matchday, the game and the player (the game MVP is pre-selected), import a photo of him
// (it is only read by your browser to draw the picture: nothing is uploaded) and choose which of his numbers of THAT game to show. The Tunisia Basket logo sits big and
// transparent behind him. Plugs into admin-images.js (ImgKit); data from /admin/api/matchday (the box scores of the matchday).
(function () {
  const K = window.ImgKit; if (!K) return;
  const { C, txt, rr, loadImg, nm, download } = K;
  const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif';
  const W = 1080, H = 1350;
  const STATS = { pts: ['PTS', 'PTS'], reb: ['REB', 'REB'], ast: ['PD', 'AST'], stl: ['INT', 'STL'], blk: ['CTR', 'BLK'], p3m: ['3PT', '3PT'], tov: ['BP', 'TOV'], pm: ['+/-', '+/-'], pir: ['PIR', 'PIR'], min: ['MIN', 'MIN'] };
  const MAN = '__manual';
  const st = { md: null, game: 0, pid: null, man: { id: '', pts: 0, reb: 0, ast: 0, stl: 0, blk: 0, p3m: 0, tov: 0, pm: 0, pir: 0, min: 0 }, stats: ['pts', 'reb', 'ast', 'pir'], photo: null, photoName: '', badge: true, mark: true };
  let M = null;
  const lang = () => K.lang();
  const signed = v => v > 0 ? '+' + v : String(v);

  async function ensure(md) {
    const r = await api('matchday' + (md ? '?md=' + md : ''));
    if (!r.ok) throw new Error('matchday data');
    M = r.body; st.md = M.md; st.game = Math.min(st.game, Math.max(0, (M.results || []).length - 1));
    const first = (M.results || []).findIndex(x => x.players.length);
    if (first >= 0 && !(M.results[st.game] || { players: [] }).players.length) st.game = first;        // start on a game that has a box score
    pickMvp();
  }
  const game = () => (M && M.results || [])[st.game];
  function pickMvp() {
    const g = game(); if (!g || !g.players.length) { st.pid = MAN; return; }       // no box score for this game: the numbers are typed
    st.pid = (g.mvp && g.players.some(p => p.id === g.mvp.player_id) ? g.mvp.player_id : (g.players.slice().sort((a, b) => b.pir - a.pir)[0] || {}).id) || MAN;
  }
  const sitePlayers = () => ((K.data() || {}).players || []).slice().sort((a, b) => a.name.localeCompare(b.name));
  const player = () => {
    const g = game(); if (!g) return null;
    if (st.pid === MAN) { const sp = sitePlayers().find(x => x.id === st.man.id) || sitePlayers()[0]; return sp ? { ...st.man, id: sp.id, name: sp.name, team: sp.team, number: sp.number } : null; }
    return g.players.find(p => p.id === st.pid);
  };
  const teamName = (g, code) => code === g.home ? g.home_name : code === g.away ? g.away_name : (((K.data() || {}).teams || []).find(t => t.code === code) || {}).name || code;

  function controls() {
    const g = game();
    if (!M) ensure().then(() => { const c = $('#imgctl'); if (c && K.extra.gamemvp) { c.innerHTML = K.extra.gamemvp.controls(); K.extra.gamemvp.bind(K.redraw); K.redraw(); } }).catch(() => {});
    const games = M ? M.results : [];
    return `<label class="small mut">Matchday</label><select id="g-md">${(M ? M.matchdays : []).map(m => `<option value="${m.matchday}" ${M && m.matchday === M.md ? 'selected' : ''}>J${m.matchday}${m.date ? ' · ' + m.date : ''}</option>`).join('')}</select>
      <label class="small mut">Game</label><select id="g-game">${games.map((r, i) => `<option value="${i}" ${i === st.game ? 'selected' : ''}>${r.home} ${r.home_score}–${r.away_score} ${r.away}${r.players.length ? '' : ' · no box score'}</option>`).join('')}</select>
      <label class="small mut">Player</label><select id="g-pl">${(g ? g.players : []).slice().sort((a, b) => b.pir - a.pir).map(p => `<option value="${esc(p.id)}" ${p.id === st.pid ? 'selected' : ''}>${esc(nm(p.name))} · ${p.team} · ${p.pts} pts · PIR ${p.pir}${g.mvp && g.mvp.player_id === p.id ? ' ★ MVP' : ''}</option>`).join('')}<option value="${MAN}" ${st.pid === MAN ? 'selected' : ''}>✎ Another player: type the numbers…</option></select>
      <div class="row" id="g-man" style="flex-basis:100%;gap:8px;align-items:center" ${st.pid === MAN ? '' : 'hidden'}><span class="small mut">${g && g.players.length ? '' : 'This game has no box score on the site, so '}type his numbers:</span>
        <select id="g-mp">${sitePlayers().map(p => `<option value="${esc(p.id)}" ${p.id === (st.man.id || '') ? 'selected' : ''}>${esc(nm(p.name))} · ${p.team} · #${p.number}</option>`).join('')}</select>
        ${['pts', 'reb', 'ast', 'stl', 'blk', 'p3m', 'tov', 'pm', 'pir', 'min'].map(k => `<label class="small mut">${STATS[k][1]} <input type="number" data-mv="${k}" value="${st.man[k]}" style="width:62px"></label>`).join('')}</div>
      <div class="row" style="flex-basis:100%;gap:8px;align-items:center">
        <label class="small mut">Photo of the player</label><input type="file" id="g-file" accept="image/*"><button id="g-nophoto" ${st.photo ? '' : 'hidden'}>Remove photo</button><span class="mut small" id="g-fname">${esc(st.photoName)}</span></div>
      <div class="row" style="flex-basis:100%;gap:10px;align-items:center"><span class="small mut">Numbers shown</span>${Object.keys(STATS).map(k => `<label class="small"><input type="checkbox" data-gs="${k}" ${st.stats.includes(k) ? 'checked' : ''}> ${STATS[k][1]}</label>`).join('')}
        <label class="small"><input type="checkbox" id="g-badge" ${st.badge ? 'checked' : ''}> club badge</label><label class="small"><input type="checkbox" id="g-mark" ${st.mark ? 'checked' : ''}> transparent logo behind</label></div>
      <div class="row" style="flex-basis:100%;align-items:flex-start;gap:8px"><textarea id="g-cap" rows="3" style="flex:1;min-width:260px;height:84px;min-height:0;font:inherit;resize:vertical" placeholder="Post text for Facebook"></textarea><button id="g-copy">📋 Copy the text</button></div>`;
  }
  function bind(redraw) {
    const on = (id, fn) => { const e = $(id); if (e) e.onchange = fn; };
    on('#g-md', async e => { await ensure(+e.target.value); const f = M.results.findIndex(x => x.players.length); st.game = f >= 0 ? f : 0; pickMvp(); $('#imgctl').innerHTML = controls(); bind(redraw); redraw(); });
    on('#g-game', e => { st.game = +e.target.value; pickMvp(); $('#imgctl').innerHTML = controls(); bind(redraw); redraw(); });
    on('#g-pl', e => { st.pid = e.target.value; const m = $('#g-man'); if (m) m.hidden = st.pid !== MAN; redraw(); });
    on('#g-mp', e => { st.man.id = e.target.value; redraw(); });
    document.querySelectorAll('[data-mv]').forEach(i => i.oninput = () => { st.man[i.dataset.mv] = +i.value || 0; redraw(); });
    on('#g-badge', e => { st.badge = e.target.checked; redraw(); });
    on('#g-mark', e => { st.mark = e.target.checked; redraw(); });
    document.querySelectorAll('[data-gs]').forEach(c => c.onchange = () => { st.stats = [...document.querySelectorAll('[data-gs]')].filter(x => x.checked).map(x => x.dataset.gs).slice(0, 5); redraw(); });
    const file = $('#g-file');
    if (file) file.onchange = () => {
      const f = file.files[0]; if (!f) return;
      const url = URL.createObjectURL(f), img = new Image();
      img.onload = () => { st.photo = img; st.photoName = f.name; $('#g-nophoto').hidden = false; $('#g-fname').textContent = f.name; redraw(); };
      img.onerror = () => { $('#imgerr').textContent = 'That file is not a readable image.'; };
      img.src = url;
    };
    const np = $('#g-nophoto'); if (np) np.onclick = () => { st.photo = null; st.photoName = ''; np.hidden = true; $('#g-fname').textContent = ''; if (file) file.value = ''; redraw(); };
    const cp = $('#g-copy'); if (cp) cp.onclick = async () => { const e = $('#g-cap'); try { await navigator.clipboard.writeText(e.value); cp.textContent = '✅ Copied'; } catch (x) { e.select(); } setTimeout(() => { cp.textContent = '📋 Copy the text'; }, 1500); };
  }

  // the photo, drawn big with soft edges: a sharp copy in the middle, its edges and bottom fading into the background
  function feathered(img, pw, ph) {
    const cv = document.createElement('canvas'); cv.width = pw; cv.height = ph; const c = cv.getContext('2d');
    const sh = Math.min(img.height, img.width * ph / pw);                                  // top of the photo first: heads sit high
    c.drawImage(img, 0, 0, img.width, sh, 0, 0, pw, ph);
    c.globalCompositeOperation = 'destination-in';
    let g = c.createLinearGradient(0, 0, pw, 0); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.14, 'rgba(0,0,0,1)'); g.addColorStop(0.86, 'rgba(0,0,0,1)'); g.addColorStop(1, 'rgba(0,0,0,0)');
    c.fillStyle = g; c.fillRect(0, 0, pw, ph);
    g = c.createLinearGradient(0, 0, 0, ph); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.07, 'rgba(0,0,0,1)'); g.addColorStop(0.58, 'rgba(0,0,0,1)'); g.addColorStop(1, 'rgba(0,0,0,0)');
    c.fillStyle = g; c.fillRect(0, 0, pw, ph);
    return cv;
  }
  function caption(g, p, fr) {
    const inGame = p.team === g.home || p.team === g.away, opp = p.team === g.home ? g.away : g.home, ps = p.team === g.home ? g.home_score : g.away_score, os = p.team === g.home ? g.away_score : g.home_score, tag = '#ProA #BasketballTunisie #TunisiaBasket';
    const line = [`${p.pts} ${fr ? 'pts' : 'pts'}`, `${p.reb} ${fr ? 'reb' : 'reb'}`, `${p.ast} ${fr ? 'pd' : 'ast'}`, p.stl ? `${p.stl} ${fr ? 'int' : 'stl'}` : '', p.blk ? `${p.blk} ${fr ? 'ctr' : 'blk'}` : '', `PIR ${p.pir}`].filter(Boolean).join(' · ');
    return fr ? `🏆 MVP du match (J${M.md}) : ${nm(p.name)} (${p.team}) !\n${line}\n${inGame ? `${p.team} ${ps}–${os} ${opp}` : ''}${(p.pm != null && p.pm !== 0) ? ` · ${signed(p.pm)} sur le terrain` : ''}\nTous les chiffres sur tunisiabasket.com 👇\n${tag}`
      : `🏆 Game MVP (J${M.md}): ${nm(p.name)} (${p.team})!\n${line}\n${inGame ? `${p.team} ${ps}–${os} ${opp}` : ''}${(p.pm != null && p.pm !== 0) ? ` · ${signed(p.pm)} on the court` : ''}\nAll the numbers on tunisiabasket.com 👇\n${tag}`;
  }

  async function draw() {
    const g = game(), p = player(), fr = lang() === 'fr';
    const cv = $('#imgcanvas'); cv.width = W; cv.height = H; const ctx = cv.getContext('2d');
    if (!g || !p) { ctx.fillStyle = C.bg1; ctx.fillRect(0, 0, W, H); txt(ctx, 'No box score for this matchday.', W / 2, H / 2, { size: 34, color: C.mut, align: 'center' }); return; }
    // background
    const bg = ctx.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, '#1f2a4d'); bg.addColorStop(0.5, '#0d1328'); bg.addColorStop(1, '#070b16'); ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
    const glow = ctx.createRadialGradient(W / 2, 520, 40, W / 2, 520, 620); glow.addColorStop(0, 'rgba(255,138,31,.32)'); glow.addColorStop(1, 'rgba(255,138,31,0)'); ctx.fillStyle = glow; ctx.fillRect(0, 0, W, H);
    const lg = await loadImg('/img/logo.png');
    // the logo of the page, big and transparent, UNDER the player
    if (st.mark && lg) { const lw = 940, lh = lw * lg.height / lg.width; ctx.save(); ctx.globalAlpha = 0.13; ctx.drawImage(lg, (W - lw) / 2, 470 - lh / 2, lw, lh); ctx.restore(); }
    // the player: his photo, or the club badge when there is none
    if (st.photo) {
      ctx.save(); ctx.globalAlpha = 0.28; ctx.filter = 'blur(26px)'; const sh = Math.min(st.photo.height, st.photo.width * H / W); ctx.drawImage(st.photo, 0, 0, st.photo.width, sh, -40, -40, W + 80, H + 80); ctx.restore();
      ctx.fillStyle = 'rgba(8,12,26,.45)'; ctx.fillRect(0, 0, W, H);
      if (st.mark && lg) { const lw = 940, lh = lw * lg.height / lg.width; ctx.save(); ctx.globalAlpha = 0.10; ctx.drawImage(lg, (W - lw) / 2, 470 - lh / 2, lw, lh); ctx.restore(); }
      const pw = 780, ph = 940, f = feathered(st.photo, pw, ph); ctx.drawImage(f, (W - pw) / 2, 150, pw, ph);
    } else {
      const bd = await loadImg(`/img/teams/${p.team}.png`); if (bd) { ctx.save(); ctx.beginPath(); ctx.arc(W / 2, 560, 250, 0, 7); ctx.fillStyle = '#fff'; ctx.fill(); ctx.clip(); ctx.drawImage(bd, W / 2 - 215, 345, 430, 430); ctx.restore(); }
    }
    // darker band for the text
    const sd = ctx.createLinearGradient(0, 760, 0, H); sd.addColorStop(0, 'rgba(7,11,22,0)'); sd.addColorStop(0.35, 'rgba(7,11,22,.88)'); sd.addColorStop(1, 'rgba(7,11,22,.97)'); ctx.fillStyle = sd; ctx.fillRect(0, 760, W, H - 760);
    // top bar
    ctx.fillStyle = C.acc; ctx.fillRect(0, 0, W, 8);
    if (lg) ctx.drawImage(lg, 48, 30, 56, 70);
    txt(ctx, 'TUNISIA BASKET', 124, 66, { size: 30, weight: 900, color: C.acc, space: '2px' });
    txt(ctx, `PRO A · ${(window.ImgKit.data() || {}).season || ''}`, 124, 98, { size: 21, weight: 600, color: C.mut });
    txt(ctx, `J${M.md}`, W - 48, 66, { size: 34, weight: 900, align: 'right' });
    if (M.date) txt(ctx, new Date(M.date + 'T12:00').toLocaleDateString(fr ? 'fr-FR' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric' }).toUpperCase(), W - 48, 98, { size: 21, color: C.mut, align: 'right' });
    // ribbon
    const tag = fr ? 'MVP DU MATCH' : 'GAME MVP'; ctx.font = `900 28px ${FONT}`; ctx.letterSpacing = '3px'; const tw = ctx.measureText(tag).width; ctx.letterSpacing = '0px';
    ctx.fillStyle = C.acc; rr(ctx, W / 2 - tw / 2 - 34, 132, tw + 68, 54, 27); ctx.fill(); txt(ctx, tag, W / 2, 170, { size: 28, weight: 900, color: '#10131c', align: 'center', space: '3px' });
    // name, team, score
    txt(ctx, nm(p.name).toUpperCase(), W / 2, 1008, { size: 110, weight: 900, align: 'center', maxW: W - 90 });
    const inGame = p.team === g.home || p.team === g.away, opp = p.team === g.home ? g.away : g.home, ps = p.team === g.home ? g.home_score : g.away_score, os = p.team === g.home ? g.away_score : g.home_score;
    const line = inGame ? `${teamName(g, p.team).toUpperCase()}  ·  ${p.team} ${ps} – ${os} ${opp}` : teamName(g, p.team).toUpperCase();
    if (st.badge) { const bd = await loadImg(`/img/teams/${p.team}.png`); ctx.font = `700 26px ${FONT}`; const lw = Math.min(ctx.measureText(line).width, W - 220), x0 = (W - lw - 64) / 2;
      ctx.save(); ctx.beginPath(); ctx.arc(x0 + 26, 1050, 26, 0, 7); ctx.fillStyle = '#fff'; ctx.fill(); ctx.clip(); if (bd) ctx.drawImage(bd, x0 + 5, 1029, 42, 42); ctx.restore();
      txt(ctx, line, x0 + 64, 1060, { size: 26, weight: 700, color: C.mut, maxW: W - 220 }); }
    else txt(ctx, line, W / 2, 1060, { size: 26, weight: 700, color: C.mut, align: 'center', maxW: W - 120 });
    // tiles: his numbers of this game
    const keys = st.stats.length ? st.stats : ['pts'], n = keys.length, gap = 14, tw2 = Math.min(230, (W - 96 - gap * (n - 1)) / n), x0 = (W - (n * tw2 + (n - 1) * gap)) / 2;
    keys.forEach((k, i) => {
      const x = x0 + i * (tw2 + gap), y = 1100, v = k === 'pm' ? signed(p[k]) : (k === 'min' ? Math.round(p[k]) : p[k]);
      ctx.fillStyle = 'rgba(26,34,62,.92)'; rr(ctx, x, y, tw2, 104, 20); ctx.fill(); if (k === 'pir') { ctx.strokeStyle = C.acc; ctx.lineWidth = 3; ctx.stroke(); }
      txt(ctx, String(v), x + tw2 / 2, y + 62, { size: 50, weight: 900, align: 'center', color: k === 'pir' ? C.acc : C.txt });
      txt(ctx, STATS[k][fr ? 0 : 1], x + tw2 / 2, y + 92, { size: 20, weight: 700, color: C.mut, align: 'center', space: '1px' });
    });
    txt(ctx, 'tunisiabasket.com', W / 2, H - 36, { size: 28, weight: 900, color: C.acc, align: 'center' });
    const cap = $('#g-cap'); if (cap && !cap.dataset.touched) cap.value = caption(Object.assign({}, g, { home_name: g.home_name }), p, fr);
    download(`tunisia-basket-j${M.md}-mvp-${nm(p.name).toLowerCase().replace(/\s+/g, '-')}.png`);
  }

  K.extra.gamemvp = { label: '🏆 Game MVP (photo)', controls, bind, draw: async () => { if (!M) await ensure(); await draw(); const cap = $('#g-cap'); if (cap) cap.addEventListener('input', () => { cap.dataset.touched = '1'; }, { once: true }); } };
})();
