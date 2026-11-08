// Admin: Facebook images for a matchday (results, table with moves, best players, MVPs, a game sheet with its players, next matchday,
// the fans' predictions) plus a ready-to-paste post text that asks a question, to get people talking. Plugs into admin-images.js (ImgKit).
(function () {
  const K = window.ImgKit; if (!K) return;
  const { W, C, txt, rr, logo, frame, f1, nm, download } = K;
  const T = {
    fr: { day: 'Journée', results: 'Les résultats', table: 'Le classement', top: 'Les meilleurs de la journée', mvps: 'Les MVP de la journée', sheet: 'Feuille de match', next: 'La prochaine journée', fans: 'Le pronostic des fans',
      afterMd: n => `APRÈS LA JOURNÉE ${n}`, vsPrev: 'Évolution par rapport à la journée précédente', wl: 'V-D', diff: 'Diff', pts: 'Pts', gp: 'Matchs', PD: 'PD', INT: 'INT', CTR: 'CTR',
      metric: { pir: 'Évaluation (PIR)', pts: 'Points', reb: 'Rebonds', ast: 'Passes décisives', stl: 'Interceptions', blk: 'Contres', p3m: '3 points réussis', pm: '+/-' },
      unit: { pir: 'PIR', pts: 'PTS', reb: 'REB', ast: 'PD', stl: 'INT', blk: 'CTR', p3m: '3PT', pm: '+/-' }, none: 'Rien à afficher pour cette journée.', nobox: 'Pas de feuille de match pour cette rencontre.',
      predict: 'Qui va gagner ? Pronostiquez sur tunisiabasket.com', vote: 'Votez avant le début de la journée sur tunisiabasket.com', nopicks: 'Pas encore de pronostics pour la prochaine journée.', voted: 'des fans', sheetFor: 'Les joueurs', best: 'Meilleur' },
    en: { day: 'Matchday', results: 'The results', table: 'The standings', top: 'Best players of the matchday', mvps: 'MVPs of the matchday', sheet: 'Game sheet', next: 'The next matchday', fans: 'What the fans predict',
      afterMd: n => `AFTER MATCHDAY ${n}`, vsPrev: 'Change since the previous matchday', wl: 'W-L', diff: 'Diff', pts: 'Pts', gp: 'Games', PD: 'AST', INT: 'STL', CTR: 'BLK',
      metric: { pir: 'Rating (PIR)', pts: 'Points', reb: 'Rebounds', ast: 'Assists', stl: 'Steals', blk: 'Blocks', p3m: 'Three-pointers made', pm: '+/-' },
      unit: { pir: 'PIR', pts: 'PTS', reb: 'REB', ast: 'AST', stl: 'STL', blk: 'BLK', p3m: '3P', pm: '+/-' }, none: 'Nothing to show for this matchday.', nobox: 'No box score for this game.',
      predict: 'Who wins? Predict on tunisiabasket.com', vote: 'Pick before the matchday starts on tunisiabasket.com', nopicks: 'No predictions yet for the next matchday.', voted: 'of fans', sheetFor: 'Players', best: 'Best' }
  };
  let M = null; const st = { metric: 'pir', n: 8, game: 0, sn: 6 };
  const lang = () => K.lang(), t = () => T[lang()];
  const day = iso => iso ? new Date(iso + 'T12:00').toLocaleDateString(lang() === 'fr' ? 'fr-FR' : 'en-GB', { weekday: 'long', day: 'numeric', month: 'long' }) : '';
  const signed = v => (v > 0 ? '+' : '') + v;
  const mv = (p, k) => k === 'pm' ? signed(p.pm) : String(p[k]);
  const line = p => `${p.pts} PTS · ${p.reb} REB · ${p.ast} ${t().PD}`;
  const medal = i => i === 0 ? C.gold : i === 1 ? '#c9d2e6' : i === 2 ? '#d99b62' : C.line;
  async function load(md) {
    const { ok, body } = await api('matchday' + (md ? '?md=' + md : ''));
    if (!ok) throw new Error('Could not load the matchday data.');
    M = body; if (st.game >= (M.results || []).length) st.game = 0;
  }
  let pending = null;
  const ensure = async () => { if (!M) { pending = pending || load().finally(() => { pending = null; }); await pending; } };
  async function empty(msg, file) {
    const ctx = await frame(700, `${t().day.toUpperCase()} ${M && M.md || ''}`, '—', ''); txt(ctx, msg, W / 2, 420, { size: 30, color: C.mut, align: 'center', maxW: W - 120 }); download('tunisia-basket-empty.png'); caption('');
  }
  function badge(ctx, x, y, i, label) {
    ctx.beginPath(); ctx.arc(x, y, 20, 0, 7); ctx.fillStyle = medal(i); ctx.fill();
    txt(ctx, String(label ?? i + 1), x, y + 8, { size: 22, weight: 900, color: i < 3 ? '#16130a' : C.txt, align: 'center' });
  }
  function caption(text) { const e = document.getElementById('m-cap'); if (e) e.value = text; }
  const tags = '#ProA #BasketballTunisie #TunisiaBasket';
  const pool = () => (M.results || []).flatMap(r => r.players);

  // ---------------------------------------------------------------- results
  async function drawResults() {
    await ensure(); const T_ = t(), rs = M.results; if (!rs.length) return empty(T_.none, 'x.png');
    const RH = 150, top = 300, H = top + rs.length * RH + 150;
    const ctx = await frame(H, `${T_.day.toUpperCase()} ${M.md}`, T_.results, day(M.date));
    for (let i = 0; i < rs.length; i++) {
      const r = rs[i], y = top + i * RH, hw = r.home_score > r.away_score;
      ctx.fillStyle = C.card; rr(ctx, 40, y, W - 80, RH - 14, 22); ctx.fill(); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
      await logo(ctx, r.home, 66, y + 18, 84); await logo(ctx, r.away, W - 66 - 84, y + 18, 84);
      txt(ctx, r.home_name, 168, y + 70, { size: 30, weight: hw ? 900 : 700, color: hw ? C.txt : C.mut, maxW: 212 });
      txt(ctx, r.away_name, W - 168, y + 70, { size: 30, weight: hw ? 700 : 900, color: hw ? C.mut : C.txt, maxW: 212, align: 'right' });
      txt(ctx, String(r.home_score), W / 2 - 38, y + 86, { size: 64, weight: 900, color: hw ? C.acc : C.mut, align: 'right' });
      txt(ctx, '–', W / 2, y + 80, { size: 40, weight: 700, color: C.mut, align: 'center' });
      txt(ctx, String(r.away_score), W / 2 + 38, y + 86, { size: 64, weight: 900, color: hw ? C.mut : C.acc });
      if (r.mvp) txt(ctx, `⭐ ${nm(r.mvp.name)} · ${r.mvp.pts} PTS · ${r.mvp.reb} REB · ${r.mvp.ast} ${T_.PD}`, W / 2, y + RH - 36, { size: 21, color: C.mut, align: 'center', maxW: W - 220 });
    }
    caption(lang() === 'fr' ? `🏀 Résultats de la journée ${M.md} de la Pro A !\nQuel match vous a le plus surpris ? Dites-le en commentaire 👇\nTous les détails : tunisiabasket.com\n${tags}`
      : `🏀 Pro A results, matchday ${M.md}!\nWhich game surprised you the most? Tell us below 👇\nAll the details: tunisiabasket.com\n${tags}`);
    download(`tunisia-basket-j${M.md}-resultats.png`);
  }

  // ---------------------------------------------------------------- the table with moves
  async function drawTable() {
    await ensure(); const T_ = t(), rows = M.standings; if (!rows.length) return empty(T_.none, 'x.png');
    const RH = 74, top = 350, H = top + rows.length * RH + 150;
    const ctx = await frame(H, T_.afterMd(M.md), T_.table, T_.vsPrev);
    ['', '', '', T_.wl, T_.diff, T_.pts].forEach((h, i) => { if (h) txt(ctx, h.toUpperCase(), [0, 0, 0, 700, 830, W - 52][i], top - 14, { size: 18, weight: 800, color: C.mut, align: 'right', space: '2px' }); });
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i], y = top + i * RH, mv_ = r.prev_rank ? r.prev_rank - r.rank : 0;
      if (i % 2 === 0) { ctx.fillStyle = 'rgba(255,255,255,.035)'; ctx.fillRect(40, y, W - 80, RH); }
      badge(ctx, 84, y + RH / 2, i, r.rank);
      txt(ctx, mv_ > 0 ? `▲ ${mv_}` : mv_ < 0 ? `▼ ${-mv_}` : '–', 150, y + RH / 2 + 8, { size: 22, weight: 900, color: mv_ > 0 ? C.good : mv_ < 0 ? '#ff5d6c' : C.mut, align: 'center' });
      await logo(ctx, r.code, 196, y + 11, 52);
      txt(ctx, r.name, 268, y + RH / 2 + 10, { size: 30, weight: i < 3 ? 900 : 700, maxW: 380 });
      txt(ctx, `${r.w}–${r.l}`, 700, y + RH / 2 + 10, { size: 28, weight: 700, color: C.txt, align: 'right' });
      txt(ctx, signed(r.diff), 830, y + RH / 2 + 10, { size: 26, weight: 700, color: r.diff >= 0 ? C.good : '#ff5d6c', align: 'right' });
      txt(ctx, String(r.pts), W - 52, y + RH / 2 + 12, { size: 36, weight: 900, color: i === 0 ? C.acc : C.txt, align: 'right' });
    }
    const up = rows.filter(r => r.prev_rank && r.prev_rank - r.rank > 0).sort((a, b) => (b.prev_rank - b.rank) - (a.prev_rank - a.rank))[0];
    caption(lang() === 'fr' ? `📊 Le classement de la Pro A après la journée ${M.md}\n${rows[0] ? `🥇 ${rows[0].name} en tête.` : ''}${up ? ` 📈 ${up.name} grimpe de ${up.prev_rank - up.rank} place${up.prev_rank - up.rank > 1 ? 's' : ''} !` : ''}\nQui sera champion selon vous ? 👇\ntunisiabasket.com\n${tags}`
      : `📊 Pro A standings after matchday ${M.md}\n${rows[0] ? `🥇 ${rows[0].name} lead.` : ''}${up ? ` 📈 ${up.name} climb ${up.prev_rank - up.rank} place${up.prev_rank - up.rank > 1 ? 's' : ''}!` : ''}\nWho wins the title? 👇\ntunisiabasket.com\n${tags}`);
    download(`tunisia-basket-j${M.md}-classement.png`);
  }

  // ---------------------------------------------------------------- best players of the matchday (any stat) and the game MVPs
  async function playerRows(ctx, top, list, key, RH) {
    const best = Math.max(1, ...list.map(p => Math.abs(p[key])));
    for (let i = 0; i < list.length; i++) {
      const p = list[i], y = top + i * RH;
      if (i % 2 === 0) { ctx.fillStyle = 'rgba(255,255,255,.035)'; ctx.fillRect(40, y, W - 80, RH); }
      badge(ctx, 82, y + RH / 2, i);
      await logo(ctx, p.team, 122, y + 12, RH - 24);
      txt(ctx, nm(p.name), 122 + RH - 10, y + 38, { size: i === 0 ? 32 : 28, weight: 800, maxW: 400 });
      txt(ctx, `${p.team} ${lang() === 'fr' ? 'vs' : 'vs'} ${p.opp} · ${p.won ? (lang() === 'fr' ? 'victoire' : 'win') : (lang() === 'fr' ? 'défaite' : 'loss')} · ${line(p)}`, 122 + RH - 10, y + 64, { size: 19, color: C.mut, maxW: 520 });
      const bx = 700, bw = 160; ctx.fillStyle = C.line; rr(ctx, bx, y + RH / 2 - 7, bw, 14, 7); ctx.fill(); ctx.fillStyle = i === 0 ? C.acc : '#c46a1a'; rr(ctx, bx, y + RH / 2 - 7, Math.max(8, bw * Math.max(0, p[key]) / best), 14, 7); ctx.fill();
      txt(ctx, mv(p, key), W - 52, y + RH / 2 + 14, { size: i === 0 ? 46 : 38, weight: 900, color: i === 0 ? C.acc : C.txt, align: 'right' });
    }
  }
  const ranked = (list, key) => list.slice().sort((a, b) => b[key] - a[key] || b.pir - a.pir);
  async function drawTop() {
    await ensure(); const T_ = t(), key = st.metric, list = ranked(pool(), key).slice(0, st.n); if (!list.length) return empty(T_.none, 'x.png');
    const RH = 84, top = 310, H = top + list.length * RH + 140;
    const ctx = await frame(H, `${T_.day.toUpperCase()} ${M.md} · ${T_.metric[key].toUpperCase()}`, T_.top, day(M.date));
    await playerRows(ctx, top, list, key, RH);
    const p = list[0];
    caption(lang() === 'fr' ? `⭐ Les meilleurs de la journée ${M.md} (${T_.unit[key]})\n🥇 ${nm(p.name)} (${p.team}) : ${mv(p, key)} ${T_.unit[key]}\nVotre joueur de la journée ? 👇\ntunisiabasket.com\n${tags}`
      : `⭐ Best players of matchday ${M.md} (${T_.unit[key]})\n🥇 ${nm(p.name)} (${p.team}): ${mv(p, key)} ${T_.unit[key]}\nYour player of the matchday? 👇\ntunisiabasket.com\n${tags}`);
    download(`tunisia-basket-j${M.md}-top-${key}.png`);
  }
  async function drawMvps() {
    await ensure(); const T_ = t();
    const list = M.results.filter(r => r.mvp).map(r => { const p = r.players.find(x => x.id === r.mvp.player_id) || { ...r.mvp, opp: r.mvp.team === r.home ? r.away : r.home, won: true, stl: 0, blk: 0 }; return { ...p, pir: r.mvp.pir }; }).sort((a, b) => b.pir - a.pir);
    if (!list.length) return empty(T_.none, 'x.png');
    const RH = 96, top = 310, H = top + list.length * RH + 140;
    const ctx = await frame(H, `${T_.day.toUpperCase()} ${M.md} · MVP`, T_.mvps, day(M.date));
    await playerRows(ctx, top, list, 'pir', RH);
    caption(lang() === 'fr' ? `🏆 Les MVP de la journée ${M.md} !\n👑 ${nm(list[0].name)} (${list[0].team}) en tête avec ${list[0].pir} PIR.\nEst-ce le bon choix ? 👇\ntunisiabasket.com\n${tags}`
      : `🏆 MVPs of matchday ${M.md}!\n👑 ${nm(list[0].name)} (${list[0].team}) on top with ${list[0].pir} PIR.\nRight choice? 👇\ntunisiabasket.com\n${tags}`);
    download(`tunisia-basket-j${M.md}-mvp.png`);
  }

  // ---------------------------------------------------------------- one game: the result, then its players ranked by the chosen stat
  async function drawSheet() {
    await ensure(); const T_ = t(), r = M.results[st.game]; if (!r) return empty(T_.none, 'x.png');
    const key = st.metric, n = st.sn, RH = 86, top = 330, bannerH = 190, listTop = top + bannerH + 70;
    const side = code => ranked(r.players.filter(p => p.team === code), key).slice(0, n);
    const A = side(r.home), B = side(r.away), rows = Math.max(A.length, B.length, 1), H = listTop + rows * RH + 150;
    const hw = r.home_score > r.away_score;
    const ctx = await frame(H, `${T_.day.toUpperCase()} ${M.md} · ${T_.metric[key].toUpperCase()}`, T_.sheet, day(M.date));
    ctx.fillStyle = C.card; rr(ctx, 40, top, W - 80, bannerH, 24); ctx.fill(); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
    await logo(ctx, r.home, 70, top + 36, 120); await logo(ctx, r.away, W - 70 - 120, top + 36, 120);
    txt(ctx, r.home_name, 210, top + 92, { size: 32, weight: hw ? 900 : 700, color: hw ? C.txt : C.mut, maxW: 180 });
    txt(ctx, r.away_name, W - 210, top + 92, { size: 32, weight: hw ? 700 : 900, color: hw ? C.mut : C.txt, maxW: 180, align: 'right' });
    txt(ctx, String(r.home_score), W / 2 - 34, top + 120, { size: 72, weight: 900, color: hw ? C.acc : C.mut, align: 'right' });
    txt(ctx, '–', W / 2, top + 110, { size: 44, weight: 700, color: C.mut, align: 'center' });
    txt(ctx, String(r.away_score), W / 2 + 34, top + 120, { size: 72, weight: 900, color: hw ? C.mut : C.acc });
    if (!r.players.length) { txt(ctx, T_.nobox, W / 2, listTop + 60, { size: 28, color: C.mut, align: 'center' }); }
    for (const [ci, list] of [[0, A], [1, B]]) {
      const x0 = 40 + ci * 520, col = ci ? C.blue : C.acc;
      txt(ctx, `${ci ? r.away : r.home} · ${T_.unit[key]}`, x0 + 8, listTop - 22, { size: 22, weight: 800, color: col, space: '2px' });
      for (let i = 0; i < list.length; i++) {
        const p = list[i], y = listTop + i * RH;
        ctx.fillStyle = C.card; rr(ctx, x0, y, 500, RH - 10, 16); ctx.fill();
        ctx.fillStyle = col; rr(ctx, x0, y, 8, RH - 10, 4); ctx.fill();
        txt(ctx, nm(p.name), x0 + 26, y + 36, { size: 25, weight: 800, maxW: 300 });
        txt(ctx, `#${p.number} · ${line(p)}`, x0 + 26, y + 62, { size: 17, color: C.mut, maxW: 330 });
        txt(ctx, mv(p, key), x0 + 482, y + 52, { size: 42, weight: 900, color: i === 0 ? col : C.txt, align: 'right' });
      }
    }
    const star = ranked(r.players, key)[0];
    caption(lang() === 'fr' ? `🏀 ${r.home_name} ${r.home_score}–${r.away_score} ${r.away_name} (J${M.md})\n${star ? `⭐ ${nm(star.name)} : ${mv(star, key)} ${T_.unit[key]}\n` : ''}Votre homme du match ? 👇\ntunisiabasket.com\n${tags}`
      : `🏀 ${r.home_name} ${r.home_score}–${r.away_score} ${r.away_name} (MD${M.md})\n${star ? `⭐ ${nm(star.name)}: ${mv(star, key)} ${T_.unit[key]}\n` : ''}Your man of the match? 👇\ntunisiabasket.com\n${tags}`);
    download(`tunisia-basket-j${M.md}-${r.home}-${r.away}.png`);
  }

  // ---------------------------------------------------------------- next matchday, and what the fans predict (percentages only)
  async function drawNext() {
    await ensure(); const T_ = t(), nx = M.next; if (!nx) return empty(T_.none, 'x.png');
    const RH = 120, top = 300, H = top + nx.games.length * RH + 150 + 110;
    const ctx = await frame(H, `${T_.day.toUpperCase()} ${nx.matchday}`, T_.next, day(nx.date));
    for (let i = 0; i < nx.games.length; i++) {
      const g = nx.games[i], y = top + i * RH;
      ctx.fillStyle = C.card; rr(ctx, 40, y, W - 80, RH - 14, 22); ctx.fill(); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
      await logo(ctx, g.home, 66, y + 14, 78); await logo(ctx, g.away, W - 66 - 78, y + 14, 78);
      txt(ctx, g.home_name, 162, y + 62, { size: 29, weight: 800, maxW: 290 });
      txt(ctx, g.away_name, W - 162, y + 62, { size: 29, weight: 800, maxW: 290, align: 'right' });
      txt(ctx, 'VS', W / 2, y + 66, { size: 34, weight: 900, color: C.acc, align: 'center' });
    }
    const by = top + nx.games.length * RH + 6;
    ctx.fillStyle = C.acc; rr(ctx, 40, by, W - 80, 86, 43); ctx.fill();
    txt(ctx, '🔮 ' + T_.predict, W / 2, by + 56, { size: 29, weight: 900, color: '#10131c', align: 'center', maxW: W - 140 });
    caption(lang() === 'fr' ? `📅 La journée ${nx.matchday} de la Pro A, ${day(nx.date)} !\n🔮 Qui va gagner ? Faites vos pronostics avant le début de la journée et découvrez l'avis des autres fans : tunisiabasket.com\nQuel match attendez-vous le plus ? 👇\n${tags}`
      : `📅 Pro A matchday ${nx.matchday}, ${day(nx.date)}!\n🔮 Who wins? Make your predictions before the matchday starts and see what other fans think: tunisiabasket.com\nWhich game are you waiting for? 👇\n${tags}`);
    download(`tunisia-basket-j${nx.matchday}-programme.png`);
  }
  async function drawFans() {
    await ensure(); const T_ = t(), nx = M.next;
    const gs = nx ? nx.games.filter(g => g.home_picks + g.away_picks > 0) : [];
    if (!gs.length) return empty(T_.nopicks, 'x.png');
    const RH = 130, top = 300, H = top + gs.length * RH + 150 + 40;
    const ctx = await frame(H, `${T_.day.toUpperCase()} ${nx.matchday}`, T_.fans, day(nx.date));
    for (let i = 0; i < gs.length; i++) {
      const g = gs[i], y = top + i * RH, tot = g.home_picks + g.away_picks, hp = Math.round(100 * g.home_picks / tot), ap = 100 - hp;
      ctx.fillStyle = C.card; rr(ctx, 40, y, W - 80, RH - 14, 22); ctx.fill(); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
      await logo(ctx, g.home, 62, y + 12, 52); await logo(ctx, g.away, W - 62 - 52, y + 12, 52);
      txt(ctx, g.home_name, 128, y + 48, { size: 25, weight: 800, maxW: 300 });
      txt(ctx, g.away_name, W - 128, y + 48, { size: 25, weight: 800, maxW: 300, align: 'right' });
      const bx = 62, bw = W - 124, by = y + 72, bh = 30, hwid = hp ? Math.max(24, bw * hp / 100) : 0;
      ctx.fillStyle = C.blue; rr(ctx, bx, by, bw, bh, 15); ctx.fill(); if (hwid) { ctx.fillStyle = C.acc; rr(ctx, bx, by, hwid, bh, 15); ctx.fill(); }
      txt(ctx, hp + '%', bx + 16, by + 23, { size: 22, weight: 900, color: '#10131c' }); txt(ctx, ap + '%', bx + bw - 16, by + 23, { size: 22, weight: 900, color: '#fff', align: 'right' });
    }
    txt(ctx, T_.vote, W / 2, top + gs.length * RH + 36, { size: 24, weight: 800, color: C.acc, align: 'center', maxW: W - 100 });
    const top1 = gs.slice().sort((a, b) => Math.abs(a.home_picks - a.away_picks) / (a.home_picks + a.away_picks) - Math.abs(b.home_picks - b.away_picks) / (b.home_picks + b.away_picks))[0];
    caption(lang() === 'fr' ? `🔮 Le pronostic des fans pour la journée ${nx.matchday} !\n${top1 ? `Match le plus serré : ${top1.home_name} – ${top1.away_name}. ` : ''}Et vous, qui gagne ? Votez avant le début de la journée : tunisiabasket.com 👇\n${tags}`
      : `🔮 What fans predict for matchday ${nx.matchday}!\n${top1 ? `Closest call: ${top1.home_name} – ${top1.away_name}. ` : ''}And you, who wins? Pick before the matchday starts: tunisiabasket.com 👇\n${tags}`);
    download(`tunisia-basket-j${nx.matchday}-pronostics-fans.png`);
  }

  // ---------------------------------------------------------------- controls
  const mdSelect = () => `<label class="small mut">Matchday</label><select id="m-md">${(M ? M.matchdays : []).map(m => `<option value="${m.matchday}" ${M && m.matchday === M.md ? 'selected' : ''}>J${m.matchday}${m.date ? ' · ' + m.date : ''}</option>`).join('')}</select>`;
  const metricSelect = () => `<label class="small mut">Stat</label><select id="m-metric">${Object.keys(T.en.metric).map(k => `<option value="${k}" ${k === st.metric ? 'selected' : ''}>${T.en.metric[k]}</option>`).join('')}</select>`;
  const capBox = `<div class="row" style="flex-basis:100%;align-items:flex-start;gap:8px"><textarea id="m-cap" rows="3" style="flex:1;min-width:260px;height:84px;min-height:0;font:inherit;resize:vertical" placeholder="Post text for Facebook"></textarea><button id="m-copy">📋 Copy the post text</button></div>`;
  function bindCommon(redraw) {
    const md = $('#m-md'); if (md) md.onchange = async () => { await load(+md.value); redraw(); };
    const me = $('#m-metric'); if (me) me.onchange = () => { st.metric = me.value; redraw(); };
    const n = $('#m-n'); if (n) n.onchange = () => { st.n = +n.value; redraw(); };
    const sn = $('#m-sn'); if (sn) sn.onchange = () => { st.sn = +sn.value; redraw(); };
    const g = $('#m-game'); if (g) g.onchange = () => { st.game = +g.value; redraw(); };
    const cp = $('#m-copy'); if (cp) cp.onclick = async () => { const e = $('#m-cap'); try { await navigator.clipboard.writeText(e.value); cp.textContent = '✅ Copied'; } catch (x) { e.select(); } setTimeout(() => { cp.textContent = '📋 Copy the post text'; }, 1800); };
  }
  const reg = (key, label, extraHtml, draw) => {
    K.extra[key] = { label, controls: () => {
      if (!M) ensure().then(() => { const c = $('#imgctl'); if (c && K.extra[key]) { c.innerHTML = K.extra[key].controls(); K.extra[key].bind(K.redraw); } }).catch(() => {});
      return mdSelect() + extraHtml() + capBox;
    }, bind: bindCommon, draw };
  };
  reg('md_results', '📋 Results', () => '', drawResults);
  reg('md_table', '📊 Standings', () => '', drawTable);
  reg('md_top', '⭐ Best players', () => `${metricSelect()}<label class="small mut">Rows</label><select id="m-n">${[5, 8, 10].map(n => `<option ${n === st.n ? 'selected' : ''}>${n}</option>`).join('')}</select>`, drawTop);
  reg('md_mvp', '🏆 Game MVPs', () => '', drawMvps);
  reg('md_sheet', '🧾 Game + players', () => `<select id="m-game">${(M ? M.results : []).map((r, i) => `<option value="${i}" ${i === st.game ? 'selected' : ''}>${r.home} ${r.home_score}–${r.away_score} ${r.away}</option>`).join('')}</select>${metricSelect()}
    <label class="small mut">Players per team</label><select id="m-sn">${[3, 5, 6, 8, 10].map(n => `<option ${n === st.sn ? 'selected' : ''}>${n}</option>`).join('')}</select>`, drawSheet);
  reg('md_next', '📅 Next matchday', () => '', drawNext);
  reg('md_fans', '🔮 Fans’ predictions', () => '', drawFans);
})();
