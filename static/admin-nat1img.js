// Admin: Facebook images for the National One (the final score of one game, the results of a matchday, the standings) and a ready-to-paste post text. Plugs into admin-images.js (ImgKit),
// in its "National One" group. The data is the public one (/api/nat1), fetched again after a result is saved in the admin (event nat1:changed) and when older than 30 s:
// the table follows the FTBB's law (ranking.py), the results are the ones typed in Games & scores > National One.
(function () {
  const K = window.ImgKit; if (!K) return;
  const { W, C, txt, rr, logo, frame, download } = K;
  const T = {
    fr: { league: 'NATIONALE 1', day: n => `JOURNÉE ${n}`, results: 'Les résultats', table: 'Le classement', after: n => `APRÈS LA JOURNÉE ${n}`, wl: 'V-D', diff: 'Diff', pts: 'Pts', none: 'Rien à afficher.', tbd: 'à jouer',
      playoff: 'Les huit premiers jouent le play-off · les deux vainqueurs des demi-finales montent en Pro A', gp: 'M',
      final: 'Score final', win: 'VICTOIRE', standing: 'AU CLASSEMENT', ord: n => n === 1 ? '1er' : `${n}e`, pts: 'pts', nogame: 'Aucun résultat saisi.' },
    en: { league: 'NATIONAL ONE', day: n => `MATCHDAY ${n}`, results: 'The results', table: 'The standings', after: n => `AFTER MATCHDAY ${n}`, wl: 'W-L', diff: 'Diff', pts: 'Pts', none: 'Nothing to show.', tbd: 'to play',
      playoff: 'The first eight play the play-off · the two semi-final winners go up to the Pro A', gp: 'G',
      final: 'Final score', win: 'WIN', standing: 'IN THE STANDINGS', ord: n => n + ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 100 > 10 && n % 100 < 14 ? 0 : n % 10] || 'th'), pts: 'pts', nogame: 'No result typed yet.' },
  };
  let D = null, md = null, at = 0, game = null;                // game: "matchday|HOME|AWAY" of the final-score image
  document.addEventListener('nat1:changed', () => { D = null; });
  const lang = () => K.lang(), t = () => T[lang()];
  const tags = '#Nationale1 #BasketballTunisie #TunisiaBasket';
  const signed = v => (v > 0 ? '+' : '') + v;
  const day = iso => iso ? new Date(iso + 'T12:00').toLocaleDateString(lang() === 'fr' ? 'fr-FR' : 'en-GB', { weekday: 'long', day: 'numeric', month: 'long' }) : '';
  let fresh = false;                                                                   // new data since the controls were drawn: their lists are rebuilt (sync)
  async function ensure() { if (!D || Date.now() - at > 30000) { D = await (await fetch('/api/nat1', { cache: 'no-store' })).json(); at = Date.now(); fresh = true; } return D; }
  function sync(key) { if (!fresh) return; fresh = false; const c = document.getElementById('imgctl'); const on = document.querySelector('#imgmodes button.on'); if (c && K.extra[key] && on && on.dataset.m === key) { c.innerHTML = K.extra[key].controls(); K.extra[key].bind(K.redraw); } }
  const scored = () => playedDays().slice().reverse().flatMap(m => m.games.filter(g => g.home_score != null).map(g => ({ ...g, md: m.matchday, mdate: m.date, key: `${m.matchday}|${g.home}|${g.away}` })));
  const playedDays = () => (D ? D.matchdays : []).filter(m => m.games.some(g => g.home_score != null));
  function caption(s) { const e = document.getElementById('n1-cap'); if (e) e.value = s; }
  async function empty(msg) { const ctx = await frame(700, t().league, msg, '', t().league); txt(ctx, msg, W / 2, 420, { size: 30, color: C.mut, align: 'center', maxW: W - 120 }); caption(''); download('tunisia-basket-nationale-1.png'); }

  async function drawResults() {
    await ensure(); const days = playedDays();
    if (!days.length) return empty(t().none);
    if (md == null || !days.some(m => m.matchday === md)) md = days[days.length - 1].matchday;
    sync('n1_results');
    const m = days.find(x => x.matchday === md), rs = m.games, RH = 130, top = 300, H = top + rs.length * RH + 150, T_ = t();
    const ctx = await frame(H, `${T_.league} · ${T_.day(m.matchday)}`, T_.results, day(m.date), T_.league);
    for (let i = 0; i < rs.length; i++) {
      const r = rs[i], y = top + i * RH, done = r.home_score != null, hw = done && r.home_score > r.away_score, aw = done && r.away_score > r.home_score;
      ctx.fillStyle = C.card; rr(ctx, 40, y, W - 80, RH - 14, 22); ctx.fill(); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
      await logo(ctx, r.home, 66, y + 14, 88); await logo(ctx, r.away, W - 66 - 88, y + 14, 88);
      txt(ctx, r.home_name, 170, y + 66, { size: 28, weight: hw ? 900 : 700, color: aw ? C.mut : C.txt, maxW: 250 });
      txt(ctx, r.away_name, W - 170, y + 66, { size: 28, weight: aw ? 900 : 700, color: hw ? C.mut : C.txt, maxW: 250, align: 'right' });
      if (done) {
        txt(ctx, String(r.home_score), W / 2 - 34, y + 78, { size: 60, weight: 900, color: hw ? C.acc : C.mut, align: 'right' });
        txt(ctx, '–', W / 2, y + 72, { size: 38, weight: 700, color: C.mut, align: 'center' });
        txt(ctx, String(r.away_score), W / 2 + 34, y + 78, { size: 60, weight: 900, color: aw ? C.acc : C.mut });
      } else txt(ctx, T_.tbd.toUpperCase(), W / 2, y + 72, { size: 26, weight: 800, color: C.mut, align: 'center', space: '2px' });
    }
    const top2 = rs.filter(r => r.home_score != null).sort((a, b) => Math.abs(b.home_score - b.away_score) - Math.abs(a.home_score - a.away_score))[0];
    const big = top2 ? (top2.home_score > top2.away_score ? top2.home_name : top2.away_name) : '';
    caption(lang() === 'fr' ? `🏀 Nationale 1 : les résultats de la journée ${m.matchday} !\n${big ? `💥 Plus large succès : ${big}.\n` : ''}Quel match vous a le plus surpris ? Dites-le en commentaire 👇\nTous les détails : tunisiabasket.com\n${tags}`
      : `🏀 National One: the results of matchday ${m.matchday}!\n${big ? `💥 Biggest win: ${big}.\n` : ''}Which game surprised you the most? Tell us below 👇\nAll the details: tunisiabasket.com\n${tags}`);
    download(`tunisia-basket-nationale-1-j${m.matchday}-resultats.png`);
  }

  // ---------------------------------------------------------------- one game: the final score
  async function drawGame() {
    await ensure(); const gs = scored(), T_ = t();
    if (!gs.length) return empty(T_.nogame);
    const g = gs.find(x => x.key === game) || gs[0]; game = g.key; sync('n1_game');
    const H = 1350, hw = g.home_score > g.away_score, CX = [W * 0.27, W * 0.73], st = Object.fromEntries((D.standings || []).map(r => [r.code, r]));
    const ctx = await frame(H, `${T_.league} · ${T_.day(g.md)}`, T_.final, day(g.date || g.mdate), T_.league);
    ctx.fillStyle = C.card; rr(ctx, 40, 320, W - 80, 660, 34); ctx.fill(); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
    const side = [{ code: g.home, name: g.home_name, s: g.home_score, won: hw }, { code: g.away, name: g.away_name, s: g.away_score, won: !hw }];
    for (let i = 0; i < 2; i++) {
      const x = side[i], cx = CX[i];
      if (x.won) { const gl = ctx.createRadialGradient(cx, 510, 20, cx, 510, 230); gl.addColorStop(0, 'rgba(255,138,31,.30)'); gl.addColorStop(1, 'rgba(255,138,31,0)'); ctx.fillStyle = gl; ctx.fillRect(cx - 240, 280, 480, 460); }
      await logo(ctx, x.code, cx - 125, 385, 250);
      txt(ctx, x.name, cx, 700, { size: 36, weight: x.won ? 900 : 700, color: x.won ? C.txt : C.mut, align: 'center', maxW: 420 });
      txt(ctx, String(x.s), cx, 860, { size: 156, weight: 900, color: x.won ? C.acc : C.mut, align: 'center' });
      if (x.won) { ctx.fillStyle = C.acc; rr(ctx, cx - 90, 892, 180, 46, 23); ctx.fill(); txt(ctx, T_.win, cx, 925, { size: 22, weight: 900, color: '#16130a', align: 'center', space: '3px' }); }
    }
    txt(ctx, '–', W / 2, 830, { size: 80, weight: 800, color: C.mut, align: 'center' });
    ctx.beginPath(); ctx.arc(W / 2, 510, 44, 0, 7); ctx.fillStyle = C.bg1; ctx.fill(); ctx.strokeStyle = C.line; ctx.stroke();
    txt(ctx, `J${g.md}`, W / 2, 522, { size: 30, weight: 900, color: C.txt, align: 'center' });
    if (st[g.home] && st[g.away]) {
      txt(ctx, T_.standing, W / 2, 1075, { size: 20, weight: 800, color: C.mut, align: 'center', space: '3px' });
      side.forEach((x, i) => { const r = st[x.code]; txt(ctx, `${T_.ord(r.rank)} · ${r.pts} ${T_.pts} · ${r.w}-${r.l}`, CX[i], 1145, { size: 38, weight: 800, color: C.txt, align: 'center', maxW: 440 }); });
      ctx.fillStyle = C.line; ctx.fillRect(W / 2 - 1, 1105, 2, 56);
    }
    const win = side.find(x => x.won), lose = side.find(x => !x.won), gap = win.s - lose.s, r = st[win.code];
    caption(lang() === 'fr' ? `🏁 Score final en Nationale 1 (J${g.md}) : ${g.home_name} ${g.home_score} – ${g.away_score} ${g.away_name}.\n${win.name} s’impose de ${gap} point${gap > 1 ? 's' : ''}${r ? ` et pointe à la ${r.rank === 1 ? '1re' : r.rank + 'e'} place` : ''}.\nVotre avis sur ce match ? 👇\nTous les résultats : tunisiabasket.com\n${tags}`
      : `🏁 National One final (matchday ${g.md}): ${g.home_name} ${g.home_score} – ${g.away_score} ${g.away_name}.\n${win.name} win by ${gap} point${gap > 1 ? 's' : ''}${r ? ` and sit ${T.en.ord(r.rank)}` : ''}.\nYour take on this game? 👇\nAll the results: tunisiabasket.com\n${tags}`);
    download(`tunisia-basket-nationale-1-j${g.md}-${g.home}-${g.away}.png`.toLowerCase());
  }

  async function drawTable() {
    await ensure(); sync('n1_table'); const rows = D.standings, T_ = t();
    if (!rows.length) return empty(T_.none);
    const RH = 74, top = 350, H = top + rows.length * RH + 210, n = Math.max(0, ...D.matchdays.filter(x => x.played).map(x => x.matchday)), cut = (D.format && D.format.playoff) || 8;
    const ctx = await frame(H, n ? `${T_.league} · ${T_.after(n)}` : T_.league, T_.table, D.official ? `FTBB · ${D.official.published || ''}` : '', T_.league);
    ['', '', '', T_.wl, T_.diff, T_.pts].forEach((h, i) => { if (h) txt(ctx, h.toUpperCase(), [0, 0, 0, 700, 830, W - 52][i], top - 14, { size: 18, weight: 800, color: C.mut, align: 'right', space: '2px' }); });
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i], y = top + i * RH;
      if (i % 2 === 0) { ctx.fillStyle = 'rgba(255,255,255,.035)'; ctx.fillRect(40, y, W - 80, RH); }
      ctx.fillStyle = i < cut ? C.good : 'rgba(255,255,255,.12)'; ctx.fillRect(40, y + 6, 6, RH - 12);          // the first eight play the play-off
      ctx.beginPath(); ctx.arc(94, y + RH / 2, 20, 0, 7); ctx.fillStyle = i === 0 ? C.gold : i < 3 ? '#c9d2e6' : C.line; ctx.fill();
      txt(ctx, String(r.rank), 94, y + RH / 2 + 8, { size: 22, weight: 900, color: i < 3 ? '#16130a' : C.txt, align: 'center' });
      await logo(ctx, r.code, 140, y + 11, 52);
      txt(ctx, r.name, 212, y + RH / 2 + 10, { size: 29, weight: i < 3 ? 900 : 700, maxW: 440 });
      txt(ctx, `${r.w}–${r.l}`, 700, y + RH / 2 + 10, { size: 28, weight: 700, align: 'right' });
      txt(ctx, signed(r.diff), 830, y + RH / 2 + 10, { size: 26, weight: 700, color: r.diff >= 0 ? C.good : '#ff5d6c', align: 'right' });
      txt(ctx, String(r.pts), W - 52, y + RH / 2 + 12, { size: 36, weight: 900, color: i === 0 ? C.acc : C.txt, align: 'right' });
    }
    ctx.fillStyle = C.good; ctx.fillRect(48, top + rows.length * RH + 30, 6, 28); txt(ctx, T_.playoff, 68, top + rows.length * RH + 53, { size: 21, weight: 600, color: C.mut, maxW: W - 130 });
    caption(lang() === 'fr' ? `📊 Le classement de la Nationale 1${n ? ` après la journée ${n}` : ''}\n${rows[0] ? `🥇 ${rows[0].name} en tête.\n` : ''}Qui montera en Pro A selon vous ? 👇\ntunisiabasket.com\n${tags}`
      : `📊 National One standings${n ? ` after matchday ${n}` : ''}\n${rows[0] ? `🥇 ${rows[0].name} lead.\n` : ''}Who goes up to the Pro A? 👇\ntunisiabasket.com\n${tags}`);
    download('tunisia-basket-nationale-1-classement.png');
  }

  const capBox = `<div class="row" style="flex-basis:100%;align-items:flex-start;gap:8px"><textarea id="n1-cap" rows="3" style="flex:1;min-width:260px;height:84px;min-height:0;font:inherit;resize:vertical" placeholder="Post text for Facebook"></textarea><button id="n1-copy">📋 Copy the post text</button></div>`;
  const bind = redraw => {
    const sel = document.getElementById('n1-md'); if (sel) sel.onchange = () => { md = +sel.value; redraw(); };
    const gs = document.getElementById('n1-game'); if (gs) gs.onchange = () => { game = gs.value; redraw(); };
    const cp = document.getElementById('n1-copy'); if (cp) cp.onclick = async () => { const e = document.getElementById('n1-cap'); try { await navigator.clipboard.writeText(e.value); cp.textContent = '✅ Copied'; } catch (x) { e.select(); } setTimeout(() => { cp.textContent = '📋 Copy the post text'; }, 1500); };
  };
  const mdSelect = () => `<label class="small mut">Matchday</label><select id="n1-md">${playedDays().map(m => `<option value="${m.matchday}" ${m.matchday === md ? 'selected' : ''}>J${m.matchday}${m.date ? ' · ' + m.date : ''}</option>`).join('')}</select>`;
  const lazy = (key, html) => () => { if (!D) ensure().then(() => { const c = document.getElementById('imgctl'); if (c && K.extra[key]) { if (md == null && playedDays().length) md = playedDays().slice(-1)[0].matchday; c.innerHTML = K.extra[key].controls(); K.extra[key].bind(K.redraw); } }).catch(() => {}); return html() + capBox; };
  const gameSelect = () => { const gs = scored(); return gs.length ? `<label class="small mut">Game</label><select id="n1-game">${playedDays().slice().reverse().map(m => `<optgroup label="J${m.matchday}${m.date ? ' · ' + m.date : ''}">${gs.filter(g => g.md === m.matchday).map(g => `<option value="${esc(g.key)}" ${g.key === game ? 'selected' : ''}>${esc(g.home_name)} ${g.home_score}–${g.away_score} ${esc(g.away_name)}</option>`).join('')}</optgroup>`).join('')}</select>` : ''; };
  K.extra.n1_game = { group: 'nat1', label: '🏁 Final score (one game)', controls: lazy('n1_game', gameSelect), bind, draw: drawGame };
  K.extra.n1_results = { group: 'nat1', label: '📋 Results of a matchday', controls: lazy('n1_results', mdSelect), bind, draw: drawResults };
  K.extra.n1_table = { group: 'nat1', label: '📊 Standings', controls: lazy('n1_table', () => ''), bind, draw: drawTable };
  // From Games & scores > National One: open the Images tab on the final score of that game, with the data just saved
  window.N1Img = { game: async (m, home, away) => { D = null; game = `${m}|${home}|${away}`; if (window.showTab) window.showTab('images'); await K.show('n1_game'); } };
})();
