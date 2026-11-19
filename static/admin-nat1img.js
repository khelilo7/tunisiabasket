// Admin: Facebook images for the National One (results of a matchday, the standings) and a ready-to-paste post text. Plugs into admin-images.js (ImgKit).
// The data is the public one (/api/nat1): the table follows the FTBB's law (ranking.py), the results are the ones typed in the Nationale 1 tab.
(function () {
  const K = window.ImgKit; if (!K) return;
  const { W, C, txt, rr, logo, frame, download } = K;
  const T = {
    fr: { league: 'NATIONALE 1', day: n => `JOURNÉE ${n}`, results: 'Les résultats', table: 'Le classement', after: n => `APRÈS LA JOURNÉE ${n}`, wl: 'V-D', diff: 'Diff', pts: 'Pts', none: 'Rien à afficher.', tbd: 'à jouer',
      playoff: 'Les huit premiers jouent le play-off · les deux vainqueurs des demi-finales montent en Pro A', gp: 'M' },
    en: { league: 'NATIONAL ONE', day: n => `MATCHDAY ${n}`, results: 'The results', table: 'The standings', after: n => `AFTER MATCHDAY ${n}`, wl: 'W-L', diff: 'Diff', pts: 'Pts', none: 'Nothing to show.', tbd: 'to play',
      playoff: 'The first eight play the play-off · the two semi-final winners go up to the Pro A', gp: 'G' },
  };
  let D = null, md = null;
  const lang = () => K.lang(), t = () => T[lang()];
  const tags = '#Nationale1 #BasketballTunisie #TunisiaBasket';
  const signed = v => (v > 0 ? '+' : '') + v;
  const day = iso => iso ? new Date(iso + 'T12:00').toLocaleDateString(lang() === 'fr' ? 'fr-FR' : 'en-GB', { weekday: 'long', day: 'numeric', month: 'long' }) : '';
  async function ensure() { if (!D) D = await (await fetch('/api/nat1', { cache: 'no-store' })).json(); return D; }
  const playedDays = () => (D ? D.matchdays : []).filter(m => m.games.some(g => g.home_score != null));
  function caption(s) { const e = document.getElementById('n1-cap'); if (e) e.value = s; }
  async function empty(msg) { const ctx = await frame(700, t().league, msg, '', t().league); txt(ctx, msg, W / 2, 420, { size: 30, color: C.mut, align: 'center', maxW: W - 120 }); caption(''); download('tunisia-basket-nationale-1.png'); }

  async function drawResults() {
    await ensure(); const days = playedDays();
    if (!days.length) return empty(t().none);
    if (md == null || !days.some(m => m.matchday === md)) md = days[days.length - 1].matchday;
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

  async function drawTable() {
    await ensure(); const rows = D.standings, T_ = t();
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
    const cp = document.getElementById('n1-copy'); if (cp) cp.onclick = async () => { const e = document.getElementById('n1-cap'); try { await navigator.clipboard.writeText(e.value); cp.textContent = '✅ Copied'; } catch (x) { e.select(); } setTimeout(() => { cp.textContent = '📋 Copy the post text'; }, 1500); };
  };
  const mdSelect = () => `<label class="small mut">Matchday</label><select id="n1-md">${playedDays().map(m => `<option value="${m.matchday}" ${m.matchday === md ? 'selected' : ''}>J${m.matchday}${m.date ? ' · ' + m.date : ''}</option>`).join('')}</select>`;
  const lazy = (key, html) => () => { if (!D) ensure().then(() => { const c = document.getElementById('imgctl'); if (c && K.extra[key]) { if (md == null && playedDays().length) md = playedDays().slice(-1)[0].matchday; c.innerHTML = K.extra[key].controls(); K.extra[key].bind(K.redraw); } }).catch(() => {}); return html() + capBox; };
  K.extra.n1_results = { label: '🏀 National One: results', controls: lazy('n1_results', mdSelect), bind, draw: drawResults };
  K.extra.n1_table = { label: '🏀 National One: standings', controls: lazy('n1_table', () => ''), bind, draw: drawTable };
})();
