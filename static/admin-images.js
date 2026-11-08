// Admin: shareable images (PNG), drawn in the browser from the live data. Player vs player, team vs team, the MVP race, and the
// category leaders (points, rebounds, steals...). Uses the helpers of admin.html ($, esc, api). Nothing is uploaded anywhere.
(function () {
  const W = 1080, FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif';
  const C = { bg1: '#0b1020', bg2: '#1b2646', card: '#151f38', line: '#2b3759', txt: '#eef2fb', mut: '#93a0c0', acc: '#ff8a1f', blue: '#4f93ff', good: '#3ecf8e', gold: '#ffd75e', acc2: '#ffb15c' };
  const L = {
    fr: { player: 'Joueur', pcmp: 'COMPARAISON DES JOUEURS', tcmp: 'COMPARAISON DES ÉQUIPES', race: 'COURSE AU MVP · PHASE 1', per: 'Moyennes par match', yrs: 'ans',
      GP: 'Matchs', MIN: 'Minutes', PTS: 'Points', REB: 'Rebonds', AST: 'Passes décisives', STL: 'Interceptions', BLK: 'Contres', TOV: 'Balles perdues', FG: 'Tir %', P3: '3 points %', FT: 'Lancers francs %', PIR: 'PIR (évaluation)',
      REC: 'Bilan', RANK: 'Classement', PPG: 'Points marqués', OPP: 'Points encaissés', DIFF: 'Différence / match', edge: 'Avantage', cats: 'catégories',
      scorer: 'Meilleur marqueur', leader: 'MEILLEUR JOUEUR À CE JOUR', score: 'Score', votes: 'votes', weights: () => 'Classement aux statistiques · le MVP est choisi par les fans',
      closes: 'Fin du vote', closed: 'Vote clos', topn: n => `Top ${n}`, lead: 'Leaders de la ligue', qual: 'Joueurs ayant joué au moins 70 % des matchs de leur équipe', ranking: 'Classement',
      cat: { pts: 'Meilleurs marqueurs', reb: 'Meilleurs rebondeurs', ast: 'Meilleurs passeurs', stl: 'Meilleurs intercepteurs', blk: 'Meilleurs contreurs', p3m: 'Tirs à 3 points réussis', fg_pct: 'Meilleurs shooteurs (TIR %)', pir: 'Plus efficaces (PIR)' },
      unit: { pts: 'PTS', reb: 'REB', ast: 'PD', stl: 'INT', blk: 'CTR', p3m: '3PT', fg_pct: '%', pir: 'PIR' }, season: 'Saison', pos: { PG: 'MEN', SG: 'ARR', SF: 'AIL', PF: 'AF', C: 'PIV' }, w: 'V', l: 'D', allcats: 'Les 3 premiers de chaque catégorie' },
    en: { player: 'Player', pcmp: 'PLAYER COMPARISON', tcmp: 'TEAM COMPARISON', race: 'MVP RACE · PHASE 1', per: 'Per-game averages', yrs: 'yrs',
      GP: 'Games', MIN: 'Minutes', PTS: 'Points', REB: 'Rebounds', AST: 'Assists', STL: 'Steals', BLK: 'Blocks', TOV: 'Turnovers', FG: 'FG %', P3: '3-point %', FT: 'Free throw %', PIR: 'PIR (efficiency)',
      REC: 'Record', RANK: 'Standing', PPG: 'Points scored', OPP: 'Points allowed', DIFF: 'Margin / game', edge: 'Edge', cats: 'categories',
      scorer: 'Top scorer', leader: 'BEST PLAYER SO FAR', score: 'Score', votes: 'votes', weights: () => 'Stats ranking · the MVP is chosen by the fans',
      closes: 'Voting closes', closed: 'Voting closed', topn: n => `Top ${n}`, lead: 'League leaders', qual: 'Players with at least 70% of their team’s games', ranking: 'Ranking',
      cat: { pts: 'Top scorers', reb: 'Top rebounders', ast: 'Top passers', stl: 'Top ball stealers', blk: 'Top shot blockers', p3m: 'Three-pointers made', fg_pct: 'Best shooters (FG%)', pir: 'Most efficient (PIR)' },
      unit: { pts: 'PTS', reb: 'REB', ast: 'AST', stl: 'STL', blk: 'BLK', p3m: '3P', fg_pct: '%', pir: 'PIR' }, season: 'Season', pos: { PG: 'PG', SG: 'SG', SF: 'SF', PF: 'PF', C: 'C' }, w: 'W', l: 'L', allcats: 'Top 3 in every category' }
  };
  let D = null, mode = 'players', lang = 'fr', sel = {}, busy = false, again = false;
  const cache = {};
  const loadImg = src => cache[src] || (cache[src] = new Promise(res => { const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = src; }));
  const f1 = v => (Math.round(v * 10) / 10).toFixed(1), pct = v => f1(v) + '%';
  const nm = s => String(s || '').toLowerCase().replace(/(^|[\s'-])\w/g, c => c.toUpperCase());

  // ---------------------------------------------------------------- drawing helpers
  function rr(ctx, x, y, w, h, r) { ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(x, y, w, h, r); else ctx.rect(x, y, w, h); }
  function txt(ctx, s, x, y, o = {}) {
    let size = o.size || 28; const weight = o.weight || 600;
    ctx.font = `${weight} ${size}px ${FONT}`;
    if (o.maxW) while (ctx.measureText(s).width > o.maxW && size > 14) { size -= 1; ctx.font = `${weight} ${size}px ${FONT}`; }
    ctx.fillStyle = o.color || C.txt; ctx.textAlign = o.align || 'left'; ctx.textBaseline = o.base || 'alphabetic';
    if (o.space) ctx.letterSpacing = o.space; else ctx.letterSpacing = '0px';
    ctx.fillText(s, x, y); ctx.letterSpacing = '0px';
  }
  function lines(ctx, s, maxW, size, weight, max = 2) {
    ctx.font = `${weight} ${size}px ${FONT}`;
    const out = []; let cur = '';
    for (const w of String(s).split(' ')) { const t = cur ? cur + ' ' + w : w; if (ctx.measureText(t).width > maxW && cur) { out.push(cur); cur = w; } else cur = t; }
    if (cur) out.push(cur);
    return out.slice(0, max);
  }
  async function logo(ctx, code, x, y, size) {
    const img = await loadImg(`/img/teams/${code}.png`);
    ctx.save(); ctx.beginPath(); ctx.arc(x + size / 2, y + size / 2, size / 2, 0, 7); ctx.fillStyle = '#ffffff'; ctx.fill(); ctx.clip();
    if (img) { const p = size * 0.1; ctx.drawImage(img, x + p, y + p, size - 2 * p, size - 2 * p); }
    else { txt(ctx, code, x + size / 2, y + size / 2 + 8, { size: size * 0.3, weight: 800, color: '#222', align: 'center' }); }
    ctx.restore();
  }
  async function frame(H, kicker, title, sub) {
    const cv = $('#imgcanvas'); cv.width = W; cv.height = H; const ctx = cv.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, C.bg2); g.addColorStop(0.5, C.bg1); g.addColorStop(1, '#070b16');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    const glow = ctx.createRadialGradient(W - 60, 40, 10, W - 60, 40, 520); glow.addColorStop(0, 'rgba(255,138,31,.28)'); glow.addColorStop(1, 'rgba(255,138,31,0)');
    ctx.fillStyle = glow; ctx.fillRect(0, 0, W, 560);
    ctx.fillStyle = C.acc; ctx.fillRect(0, 0, W, 8);
    const lg = await loadImg('/img/logo-96.png'); if (lg) ctx.drawImage(lg, 48, 34, 52, 64);
    txt(ctx, 'TUNISIA', 118, 78, { size: 34, weight: 900, color: C.acc, space: '2px' }); ctx.font = `900 34px ${FONT}`; ctx.letterSpacing = '2px';
    const w1 = ctx.measureText('TUNISIA ').width; ctx.letterSpacing = '0px'; txt(ctx, 'BASKET', 118 + w1, 78, { size: 34, weight: 900, space: '2px' });
    txt(ctx, `PRO A · ${D.season || ''}`, W - 48, 76, { size: 22, weight: 700, color: C.mut, align: 'right', space: '2px' });
    txt(ctx, kicker, 48, 168, { size: 24, weight: 800, color: C.acc, space: '4px' });
    txt(ctx, title, 48, 230, { size: 56, weight: 900, maxW: W - 96 });
    if (sub) txt(ctx, sub, 48, 270, { size: 24, color: C.mut, maxW: W - 96 });
    ctx.fillStyle = C.line; ctx.fillRect(48, H - 78, W - 96, 2);
    txt(ctx, 'tunisiabasket.com', 48, H - 36, { size: 26, weight: 800, color: C.acc });
    txt(ctx, new Date().toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric' }), W - 48, H - 36, { size: 22, color: C.mut, align: 'right' });
    return ctx;
  }

  // Head-to-head rows. row = { label, a, b, fa, fb, low (lower is better), plain (not counted) }
  function compareRows(ctx, y0, rows, RH) {
    const cx = W / 2, BW = 270, GAP = 96;
    let sa = 0, sb = 0;
    rows.forEach((r, i) => {
      const y = y0 + i * RH, tie = r.a === r.b;
      const aw = !r.plain && !tie && (r.low ? r.a < r.b : r.a > r.b), bw = !r.plain && !tie && (r.low ? r.b < r.a : r.b > r.a);
      if (aw) sa++; if (bw) sb++;
      if (i % 2 === 0) { ctx.fillStyle = 'rgba(255,255,255,.035)'; ctx.fillRect(40, y, W - 80, RH); }
      txt(ctx, r.label, cx, y + 26, { size: 21, weight: 700, color: C.mut, align: 'center', maxW: 2 * GAP - 20 });
      const mx = Math.max(Math.abs(r.a), Math.abs(r.b), 0.0001);
      const bar = (side, v, win, col) => {
        const len = Math.max(6, BW * Math.abs(v) / mx), x = side < 0 ? cx - GAP - len : cx + GAP;
        ctx.globalAlpha = r.plain ? 0.45 : win || tie ? 1 : 0.4; ctx.fillStyle = col; rr(ctx, x, y + RH / 2 - 9, len, 18, 9); ctx.fill(); ctx.globalAlpha = 1;
      };
      bar(-1, r.a, aw, C.acc); bar(1, r.b, bw, C.blue);
      txt(ctx, r.fa, 52, y + RH / 2 + 12, { size: 34, weight: aw ? 900 : 700, color: aw ? C.txt : C.mut, maxW: 140 });
      txt(ctx, r.fb, W - 52, y + RH / 2 + 12, { size: 34, weight: bw ? 900 : 700, color: bw ? C.txt : C.mut, align: 'right', maxW: 140 });
    });
    return [sa, sb];
  }
  function edgeBox(ctx, y, na, nb, sa, sb, t) {
    ctx.fillStyle = C.card; rr(ctx, 48, y, W - 96, 92, 18); ctx.fill(); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
    txt(ctx, t.edge.toUpperCase(), W / 2, y + 30, { size: 18, weight: 800, color: C.mut, align: 'center', space: '3px' });
    txt(ctx, `${sa}`, W / 2 - 60, y + 74, { size: 46, weight: 900, color: sa >= sb ? C.acc : C.mut, align: 'right' });
    txt(ctx, '–', W / 2, y + 70, { size: 40, weight: 700, color: C.mut, align: 'center' });
    txt(ctx, `${sb}`, W / 2 + 60, y + 74, { size: 46, weight: 900, color: sb >= sa ? C.blue : C.mut });
    txt(ctx, na, 72, y + 62, { size: 26, weight: 800, color: C.acc, maxW: 300 });
    txt(ctx, nb, W - 72, y + 62, { size: 26, weight: 800, color: C.blue, align: 'right', maxW: 300 });
  }
  async function sideCard(ctx, x, y, w, h, col, code, name, l1, l2, l3) {
    ctx.fillStyle = C.card; rr(ctx, x, y, w, h, 22); ctx.fill(); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = col; rr(ctx, x, y, w, 10, 5); ctx.fill();
    await logo(ctx, code, x + 22, y + 34, 108);
    const tx = x + 148, tw = w - 148 - 18, ls = lines(ctx, name, tw, 34, 900, 2);
    ls.forEach((s, i) => txt(ctx, s, tx, y + 74 + i * 38, { size: 34, weight: 900, maxW: tw }));
    const yy = y + 74 + ls.length * 38 + 4;
    if (l1) txt(ctx, l1, tx, yy, { size: 22, weight: 700, color: col, maxW: tw });
    if (l2) txt(ctx, l2, x + 22, y + h - 56, { size: 22, color: C.mut, maxW: w - 44 });
    if (l3) txt(ctx, l3, x + 22, y + h - 22, { size: 22, weight: 700, color: C.txt, maxW: w - 44 });
  }
  const extra = {};    // image types added by other scripts (admin-matchday.js): { key: { label, controls() -> html, bind(redraw), draw() } }
  const download = name => { $('#imgdl').onclick = () => $('#imgcanvas').toBlob(b => { const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); }, 'image/png'); $('#imgdl').disabled = false; };

  // ---------------------------------------------------------------- the four images
  async function drawPlayers() {
    const t = L[lang], a = D.players.find(p => p.id === sel.pa), b = D.players.find(p => p.id === sel.pb);
    if (!a || !b) return;
    const bio = p => { const x = p.bio || {}, h = Array.isArray(x.height) ? x.height.join('–') : x.height, age = x.birth && Math.floor((Date.now() - new Date(x.birth + 'T12:00')) / 31557600000);
      return [h && `${h} cm`, x.weight && `${x.weight} kg`, age && `${age} ${t.yrs}`].filter(Boolean).join(' · '); };
    const rows = [
      { label: t.GP, a: a.gp, b: b.gp, fa: a.gp, fb: b.gp, plain: 1 }, { label: t.MIN, a: a.min, b: b.min, fa: f1(a.min), fb: f1(b.min), plain: 1 },
      { label: t.PTS, a: a.pts, b: b.pts, fa: f1(a.pts), fb: f1(b.pts) }, { label: t.REB, a: a.reb, b: b.reb, fa: f1(a.reb), fb: f1(b.reb) },
      { label: t.AST, a: a.ast, b: b.ast, fa: f1(a.ast), fb: f1(b.ast) }, { label: t.STL, a: a.stl, b: b.stl, fa: f1(a.stl), fb: f1(b.stl) },
      { label: t.BLK, a: a.blk, b: b.blk, fa: f1(a.blk), fb: f1(b.blk) }, { label: t.TOV, a: a.tov, b: b.tov, fa: f1(a.tov), fb: f1(b.tov), low: 1 },
      { label: t.FG, a: a.fg_pct, b: b.fg_pct, fa: pct(a.fg_pct), fb: pct(b.fg_pct) }, { label: t.P3, a: a.p3_pct, b: b.p3_pct, fa: pct(a.p3_pct), fb: pct(b.p3_pct) },
      { label: t.FT, a: a.ft_pct, b: b.ft_pct, fa: pct(a.ft_pct), fb: pct(b.ft_pct) }, { label: t.PIR, a: a.pir, b: b.pir, fa: f1(a.pir), fb: f1(b.pir) }];
    const RH = 62, top = 310, cardH = 250, H = top + cardH + 30 + rows.length * RH + 20 + 92 + 130;
    const ctx = await frame(H, t.pcmp, `${nm(a.name).split(' ').slice(-1)[0]}  vs  ${nm(b.name).split(' ').slice(-1)[0]}`, `${t.per} · ${D.season}`);
    await sideCard(ctx, 40, top, 480, cardH, C.acc, a.team, nm(a.name), `${a.team} · #${a.number} · ${t.pos[a.pos] || a.pos}`, bio(a), `PIR ${f1(a.pir)} · ${a.rating}/99`);
    await sideCard(ctx, 560, top, 480, cardH, C.blue, b.team, nm(b.name), `${b.team} · #${b.number} · ${t.pos[b.pos] || b.pos}`, bio(b), `PIR ${f1(b.pir)} · ${b.rating}/99`);
    txt(ctx, 'VS', W / 2, top + cardH / 2 + 14, { size: 36, weight: 900, color: C.acc, align: 'center' });
    const [sa, sb] = compareRows(ctx, top + cardH + 30, rows, RH);
    edgeBox(ctx, top + cardH + 30 + rows.length * RH + 20, nm(a.name).split(' ').slice(-1)[0], nm(b.name).split(' ').slice(-1)[0], sa, sb, t);
    download(`tunisia-basket-${a.id}-vs-${b.id}.png`);
  }

  async function drawTeams() {
    const t = L[lang], a = D.teams.find(x => x.code === sel.ta), b = D.teams.find(x => x.code === sel.tb);
    if (!a || !b) return;
    const rows = [
      { label: t.REC, a: a.w, b: b.w, fa: `${a.w}${t.w}–${a.l}${t.l}`, fb: `${b.w}${t.w}–${b.l}${t.l}` }, { label: t.RANK, a: a.rank, b: b.rank, fa: `#${a.rank}`, fb: `#${b.rank}`, low: 1 },
      { label: t.PPG, a: a.ppg, b: b.ppg, fa: f1(a.ppg), fb: f1(b.ppg) }, { label: t.OPP, a: a.opp_ppg, b: b.opp_ppg, fa: f1(a.opp_ppg), fb: f1(b.opp_ppg), low: 1 },
      { label: t.DIFF, a: a.diff_pg, b: b.diff_pg, fa: (a.diff_pg > 0 ? '+' : '') + f1(a.diff_pg), fb: (b.diff_pg > 0 ? '+' : '') + f1(b.diff_pg) },
      { label: t.FG, a: a.fg_pct, b: b.fg_pct, fa: pct(a.fg_pct), fb: pct(b.fg_pct) }, { label: t.P3, a: a.p3_pct, b: b.p3_pct, fa: pct(a.p3_pct), fb: pct(b.p3_pct) },
      { label: t.FT, a: a.ft_pct, b: b.ft_pct, fa: pct(a.ft_pct), fb: pct(b.ft_pct) }, { label: t.REB, a: a.reb, b: b.reb, fa: f1(a.reb), fb: f1(b.reb) },
      { label: t.AST, a: a.ast, b: b.ast, fa: f1(a.ast), fb: f1(b.ast) }, { label: t.STL, a: a.stl, b: b.stl, fa: f1(a.stl), fb: f1(b.stl) },
      { label: t.BLK, a: a.blk, b: b.blk, fa: f1(a.blk), fb: f1(b.blk) }, { label: t.TOV, a: a.tov, b: b.tov, fa: f1(a.tov), fb: f1(b.tov), low: 1 }];
    const RH = 60, top = 310, cardH = 250, H = top + cardH + 30 + rows.length * RH + 20 + 92 + 130;
    const ctx = await frame(H, t.tcmp, `${a.code}  vs  ${b.code}`, `${t.per} · ${D.season}`);
    const sc = x => x.top_scorer ? `${t.scorer}: ${nm(x.top_scorer.name)} · ${f1(x.top_scorer.pts)}` : '';
    await sideCard(ctx, 40, top, 480, cardH, C.acc, a.code, a.name, `${t.RANK} #${a.rank}`, sc(a), `${a.w}${t.w} – ${a.l}${t.l}`);
    await sideCard(ctx, 560, top, 480, cardH, C.blue, b.code, b.name, `${t.RANK} #${b.rank}`, sc(b), `${b.w}${t.w} – ${b.l}${t.l}`);
    txt(ctx, 'VS', W / 2, top + cardH / 2 + 14, { size: 36, weight: 900, color: C.acc, align: 'center' });
    const [sa, sb] = compareRows(ctx, top + cardH + 30, rows, RH);
    edgeBox(ctx, top + cardH + 30 + rows.length * RH + 20, a.code, b.code, sa, sb, t);
    download(`tunisia-basket-${a.code}-vs-${b.code}.png`);
  }

  async function drawRace() {
    const t = L[lang], r = D.mvp, n = Math.min(+sel.rn || 8, r.candidates.length), rows = r.candidates.slice(0, n), lead = r.winner || r.leader;
    if (!lead) return;
    const RH = 96, top = 300, banner = 200, H = top + banner + 28 + n * RH + 70 + 120;
    const ctx = await frame(H, t.race, t.leader.charAt(0) + t.leader.slice(1).toLowerCase() + ': ' + nm(lead.name), t.weights());
    // leader banner
    ctx.fillStyle = C.card; rr(ctx, 40, top, W - 80, banner, 24); ctx.fill(); ctx.strokeStyle = C.acc; ctx.lineWidth = 3; ctx.stroke();
    await logo(ctx, lead.team, 70, top + 36, 128);
    txt(ctx, '🏆 ' + (r.winner ? (lang === 'fr' ? 'MVP DE LA PHASE 1' : 'PHASE 1 MVP') : t.leader), 230, top + 52, { size: 22, weight: 800, color: C.acc, space: '3px' });
    txt(ctx, nm(lead.name), 230, top + 108, { size: 50, weight: 900, maxW: W - 310 });
    txt(ctx, `${lead.team} · #${lead.number} · ${lead.gp} ${t.GP.toLowerCase()}`, 230, top + 146, { size: 24, color: C.mut });
    txt(ctx, `${f1(lead.pts)} PTS   ${f1(lead.reb)} REB   ${f1(lead.ast)} ${lang === 'fr' ? 'PD' : 'AST'}   PIR ${f1(lead.pir)}`, 230, top + 184, { size: 28, weight: 800, color: C.acc2 || C.acc });
    // rows
    const best = Math.max(1, ...rows.map(x => x.stats_score));
    for (let i = 0; i < n; i++) {
      const x = rows[i], y = top + banner + 28 + i * RH;
      if (i % 2 === 0) { ctx.fillStyle = 'rgba(255,255,255,.035)'; ctx.fillRect(40, y, W - 80, RH); }
      ctx.beginPath(); ctx.arc(80, y + RH / 2, 20, 0, 7); ctx.fillStyle = i === 0 ? C.gold : i === 1 ? '#c9d2e6' : i === 2 ? '#d99b62' : C.line; ctx.fill();
      txt(ctx, String(x.rank), 80, y + RH / 2 + 8, { size: 22, weight: 900, color: i < 3 ? '#16130a' : C.txt, align: 'center' });
      await logo(ctx, x.team, 118, y + 18, 60);
      txt(ctx, nm(x.name), 196, y + 38, { size: 30, weight: 800, maxW: 400 });
      txt(ctx, `${x.team} · ${f1(x.pts)} PTS · ${f1(x.reb)} REB · ${f1(x.ast)} ${lang === 'fr' ? 'PD' : 'AST'} · PIR ${f1(x.pir)}`, 196, y + 64, { size: 20, color: C.mut, maxW: 520 });
      const bx = 716, bw = 190; ctx.fillStyle = C.line; rr(ctx, bx, y + 30, bw, 14, 7); ctx.fill(); ctx.fillStyle = C.acc; rr(ctx, bx, y + 30, Math.max(8, bw * x.stats_score / best), 14, 7); ctx.fill();
      txt(ctx, f1(x.stats_score), W - 52, y + 52, { size: 38, weight: 900, color: i === 0 ? C.acc : C.txt, align: 'right' });
      txt(ctx, `${x.votes} ${t.votes} · ${f1(x.vote_share)}%`, bx, y + 72, { size: 18, color: C.mut });
    }
    const foot = r.deadline_ts ? `${r.voting_open ? t.closes : t.closed}: ${new Date(r.deadline_ts * 1000).toLocaleString(lang === 'fr' ? 'fr-FR' : 'en-GB', { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Tunis' })}` : '';
    txt(ctx, `${r.total_votes} ${t.votes}${foot ? ' · ' + foot : ''}`, 48, H - 106, { size: 22, color: C.mut, maxW: W - 96 });
    download('tunisia-basket-mvp-race.png');
  }

  async function drawLeaders() {
    const t = L[lang], all = sel.lk === 'all';
    if (all) {
      const cats = D.leaders, CH = 300, top = 300, H = top + 4 * (CH + 18) + 30 + 100;
      const ctx = await frame(H, t.lead, t.allcats, `${t.per} · ${t.qual}`);
      for (let i = 0; i < cats.length; i++) {
        const c = cats[i], x = 40 + (i % 2) * 520, y = top + Math.floor(i / 2) * (CH + 18);
        ctx.fillStyle = C.card; rr(ctx, x, y, 500, CH, 20); ctx.fill(); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
        txt(ctx, t.cat[c.key].toUpperCase(), x + 22, y + 40, { size: 20, weight: 800, color: C.acc, space: '1.5px', maxW: 456 });
        for (let k = 0; k < 3 && c.top[k]; k++) {
          const p = c.top[k], yy = y + 64 + k * 74;
          await logo(ctx, p.team, x + 22, yy, k ? 48 : 56);
          txt(ctx, nm(p.name), x + (k ? 82 : 90), yy + 24, { size: k ? 24 : 28, weight: 800, maxW: 250 });
          txt(ctx, `${p.team} · #${p.number}`, x + (k ? 82 : 90), yy + 48, { size: 18, color: C.mut });
          txt(ctx, c.key === 'fg_pct' ? pct(p.value) : f1(p.value), x + 478, yy + 38, { size: k ? 34 : 42, weight: 900, color: k ? C.txt : C.acc, align: 'right' });
        }
      }
      download('tunisia-basket-leaders.png');
      return;
    }
    const c = D.leaders.find(x => x.key === sel.lk), n = +sel.ln || 10, rows = c.top.slice(0, n), RH = 80, top = 300, H = top + rows.length * RH + 30 + 110;
    const ctx = await frame(H, `${t.topn(rows.length)} · ${t.per}`, t.cat[c.key], t.qual);
    const best = Math.max(1, ...rows.map(x => x.value));
    for (let i = 0; i < rows.length; i++) {
      const p = rows[i], y = top + i * RH;
      if (i % 2 === 0) { ctx.fillStyle = 'rgba(255,255,255,.035)'; ctx.fillRect(40, y, W - 80, RH); }
      ctx.beginPath(); ctx.arc(82, y + RH / 2, 20, 0, 7); ctx.fillStyle = i === 0 ? C.gold : i === 1 ? '#c9d2e6' : i === 2 ? '#d99b62' : C.line; ctx.fill();
      txt(ctx, String(i + 1), 82, y + RH / 2 + 8, { size: 22, weight: 900, color: i < 3 ? '#16130a' : C.txt, align: 'center' });
      await logo(ctx, p.team, 122, y + 12, 56);
      txt(ctx, nm(p.name), 196, y + 38, { size: i === 0 ? 32 : 28, weight: 800, maxW: 420 });
      txt(ctx, `${p.team} · #${p.number} · ${p.gp} ${t.GP.toLowerCase()}`, 196, y + 64, { size: 20, color: C.mut });
      const bx = 640, bw = 250; ctx.fillStyle = C.line; rr(ctx, bx, y + 33, bw, 14, 7); ctx.fill(); ctx.fillStyle = i === 0 ? C.acc : '#c46a1a'; rr(ctx, bx, y + 33, Math.max(8, bw * p.value / best), 14, 7); ctx.fill();
      txt(ctx, c.key === 'fg_pct' ? pct(p.value) : f1(p.value), W - 52, y + 54, { size: i === 0 ? 44 : 36, weight: 900, color: i === 0 ? C.acc : C.txt, align: 'right' });
    }
    download(`tunisia-basket-leaders-${c.key}.png`);
  }

  // ---------------------------------------------------------------- controls
  const optsPlayers = (cur) => {
    const by = {};
    D.players.forEach(p => (by[p.team] = by[p.team] || []).push(p));
    return Object.keys(by).sort().map(tm => `<optgroup label="${esc(tm)}">${by[tm].sort((x, y) => x.name.localeCompare(y.name)).map(p => `<option value="${esc(p.id)}" ${p.id === cur ? 'selected' : ''}>${esc(nm(p.name))} · #${p.number}</option>`).join('')}</optgroup>`).join('');
  };
  const optsTeams = cur => D.teams.map(x => `<option value="${x.code}" ${x.code === cur ? 'selected' : ''}>${esc(x.name)} (${x.code})</option>`).join('');

  function controls() {
    const m = mode;
    if (extra[m]) { $('#imgctl').innerHTML = extra[m].controls(); extra[m].bind(draw); return; }
    $('#imgctl').innerHTML = m === 'players' ? `<select id="c-pa">${optsPlayers(sel.pa)}</select><span class="mut">vs</span><select id="c-pb">${optsPlayers(sel.pb)}</select>`
      : m === 'teams' ? `<select id="c-ta">${optsTeams(sel.ta)}</select><span class="mut">vs</span><select id="c-tb">${optsTeams(sel.tb)}</select>`
      : m === 'race' ? `<label class="small mut">Players shown</label><select id="c-rn">${[5, 8, 10].map(n => `<option ${n == sel.rn ? 'selected' : ''}>${n}</option>`).join('')}</select>`
      : `<select id="c-lk">${D.leaders.map(c => `<option value="${c.key}" ${c.key === sel.lk ? 'selected' : ''}>${esc(L.en.cat[c.key])}</option>`).join('')}<option value="all" ${sel.lk === 'all' ? 'selected' : ''}>Top 3 in every category (one image)</option></select>
         <label class="small mut">Rows</label><select id="c-ln">${[5, 10].map(n => `<option ${n == sel.ln ? 'selected' : ''}>${n}</option>`).join('')}</select>`;
    const bind = (id, key) => { const e = $(id); if (e) e.onchange = () => { sel[key] = e.value; draw(); }; };
    bind('#c-pa', 'pa'); bind('#c-pb', 'pb'); bind('#c-ta', 'ta'); bind('#c-tb', 'tb'); bind('#c-rn', 'rn'); bind('#c-lk', 'lk'); bind('#c-ln', 'ln');
  }
  async function draw() {
    if (busy) { again = true; return; } busy = true;
    $('#imgdl').disabled = true;
    try { await (extra[mode] ? extra[mode].draw() : ({ players: drawPlayers, teams: drawTeams, race: drawRace, leaders: drawLeaders })[mode]()); $('#imgerr').textContent = ''; }
    catch (e) { $('#imgerr').textContent = 'Could not draw the image: ' + e.message; }
    busy = false;
    if (again) { again = false; draw(); }
  }

  async function open() {
    const box = $('#imgbox');
    if (!D) {
      box.innerHTML = '<div class="mut">Loading…</div>';
      try {
        const [pl, ts, mv, ov] = await Promise.all([fetch('/api/players').then(r => r.json()), api('team-stats').then(r => r.body), fetch('/api/mvp?phase=1').then(r => r.json()), fetch('/api/overview').then(r => r.json())]);
        D = { season: pl.season, players: pl.players.filter(p => p.gp > 0), teams: ts.teams, mvp: mv, leaders: ov.leaders };
      } catch (e) { box.innerHTML = '<div class="problems">Could not load the data for the images.</div>'; return; }
      sel = { pa: D.players[0].id, pb: D.players[1].id, ta: D.teams[0].code, tb: D.teams[1].code, rn: 8, lk: 'pts', ln: 10 };
      box.innerHTML = `<div class="row" style="margin:12px 0"><div class="tabs" id="imgmodes" style="margin:0;flex-wrap:wrap"><button data-m="players" class="on">Player vs player</button><button data-m="teams">Team vs team</button><button data-m="race">MVP race</button><button data-m="leaders">Leaders</button>${Object.entries(extra).map(([k, x]) => `<button data-m="${k}">${x.label}</button>`).join('')}</div>
          <span class="sp"></span><label class="small mut">Image language</label><select id="imglang"><option value="fr">Français</option><option value="en">English</option></select></div>
        <div class="row" id="imgctl" style="margin-bottom:12px"></div>
        <div class="row" style="margin-bottom:10px"><button class="primary" id="imgdl" disabled>⬇ Download PNG</button><span class="mut small">1080 px wide, ready to post. Drawn from today’s data.</span><span id="imgerr" class="small" style="color:var(--bad)"></span></div>
        <canvas id="imgcanvas" width="1080" height="1350" style="width:100%;max-width:560px;height:auto;border-radius:14px;border:1px solid var(--line);display:block"></canvas>`;
      $('#imgmodes').querySelectorAll('button').forEach(b => b.onclick = () => { mode = b.dataset.m; $('#imgmodes').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); controls(); draw(); });
      $('#imglang').onchange = e => { lang = e.target.value; draw(); };
      controls();
    }
    draw();
  }
  window.loadImages = open;
  window.ImgKit = { W, C, txt, rr, lines, logo, frame, f1, pct, nm, download, extra, loadImg, lang: () => lang, data: () => D, redraw: draw };
})();
