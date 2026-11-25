// Admin: Facebook images for the Tunisian national team: the called-up players ("convocation") and the results of one competition, with a ready-to-paste post text. Plugs into
// admin-images.js (ImgKit), in its "National team" group. The data is the public one (/api/national-team), fetched again after the admin saves something in the National team tab
// (event natteam:changed) and when older than 30 s. The flag is /img/tunisia-flag.svg; the opponents are drawn as a round badge with their country code.
(function () {
  const K = window.ImgKit; if (!K) return;
  const { W, C, txt, rr, frame, download, loadImg } = K;
  const T = {
    fr: { league: 'ÉQUIPE NATIONALE', tun: 'TUNISIE', squad: 'Les convoqués', results: 'Les résultats', outside: 'Hors championnat tunisien', none: 'Rien à afficher.', last: n => `Les ${n} derniers matchs`, w: 'V', l: 'D', ot: 'prol.', nores: 'Aucun résultat dans cette compétition.', empty: 'La liste n’est pas encore annoncée.' },
    en: { league: 'NATIONAL TEAM', tun: 'TUNISIA', squad: 'The squad', results: 'The results', outside: 'Outside the Tunisian league', none: 'Nothing to show.', last: n => `The last ${n} games`, w: 'W', l: 'L', ot: 'OT', nores: 'No result in this competition.', empty: 'The list has not been announced yet.' },
  };
  let D = null, at = 0, comp = null, fresh = false;
  document.addEventListener('natteam:changed', () => { D = null; });
  const lang = () => K.lang(), t = () => T[lang()];
  const tags = '#Tunisie #EquipeNationale #BasketballTunisie #TunisiaBasket';
  const fmt = iso => new Date(iso + 'T12:00').toLocaleDateString(lang() === 'fr' ? 'fr-FR' : 'en-GB', { day: 'numeric', month: 'short' });
  const long = iso => new Date(iso + 'T12:00').toLocaleDateString(lang() === 'fr' ? 'fr-FR' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
  const cname = id => { const c = D.competitions.find(x => x.id === id); return c ? (lang() === 'fr' ? c.fr : c.en) : id; };
  const oname = g => lang() === 'fr' ? g.opp_name_fr : g.opp_name_en;
  const rnd = r => lang() === 'fr' ? String(r || '').replace('First round', 'Premier tour').replace('Second round', 'Deuxième tour').replace('Group', 'Groupe') : r;
  async function ensure() { if (!D || Date.now() - at > 30000) { D = await (await fetch('/api/national-team', { cache: 'no-store' })).json(); at = Date.now(); fresh = true; } return D; }
  function sync(key) { if (!fresh) return; fresh = false; const c = document.getElementById('imgctl'); const on = document.querySelector('#imgmodes button.on'); if (c && K.extra[key] && on && on.dataset.m === key) { c.innerHTML = K.extra[key].controls(); K.extra[key].bind(K.redraw); } }
  function caption(s) { const e = document.getElementById('nt-cap'); if (e) e.value = s; }
  const played = () => D.games.filter(g => g.played);
  const withGames = () => D.competitions.filter(c => played().some(g => g.competition === c.id));
  async function empty(msg, name) { const ctx = await frame(700, t().league, msg, '', t().league, { noSeason: true }); txt(ctx, msg, W / 2, 420, { size: 30, color: C.mut, align: 'center', maxW: W - 120 }); caption(''); download(name); }

  async function badge(ctx, cx, cy, r, g) {            // Tunisia: the flag in a circle; an opponent: its country code in a circle
    ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.clip();
    if (!g) { const f = await loadImg('/img/tunisia-flag.svg'); if (f) ctx.drawImage(f, cx - r * 1.5, cy - r, r * 3, r * 2); else { ctx.fillStyle = '#e70013'; ctx.fill(); } }
    else { ctx.fillStyle = '#22304f'; ctx.fillRect(cx - r, cy - r, 2 * r, 2 * r); }
    ctx.restore();
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.strokeStyle = C.line; ctx.lineWidth = 3; ctx.stroke();
    if (g) txt(ctx, g.opp || (g.opp_name || '?').slice(0, 3).toUpperCase(), cx, cy + r * 0.26, { size: r * 0.78, weight: 900, color: C.txt, align: 'center' });
  }
  async function photo(ctx, p, x, y, size) {
    const img = await loadImg(p.photo || '/img/players/generic.svg');
    ctx.save(); ctx.beginPath(); ctx.arc(x + size / 2, y + size / 2, size / 2, 0, 7); ctx.fillStyle = '#26324f'; ctx.fill(); ctx.clip();
    if (img) { const w = img.width || size, h = img.height || size, s = Math.max(size / w, size / h); ctx.drawImage(img, x + (size - w * s) / 2, y + (p.photo ? 0 : (size - h * s) / 2), w * s, h * s); }
    ctx.restore(); ctx.beginPath(); ctx.arc(x + size / 2, y + size / 2, size / 2, 0, 7); ctx.strokeStyle = C.line; ctx.lineWidth = 3; ctx.stroke();
  }

  // ---------------------------------------------------------------- the called-up players
  async function drawCallup() {
    await ensure(); sync('nt_callup');
    const T_ = t(), pl = D.callup.players, label = lang() === 'fr' ? D.callup.label_fr || D.callup.label : D.callup.label;
    if (!pl.length) return empty(T_.empty, 'tunisia-basket-equipe-nationale-convoques.png');
    const rows = Math.ceil(pl.length / 2), CH = 96, top = 330, H = top + rows * (CH + 12) + 150;
    const ctx = await frame(H, T_.league, T_.squad, [label, D.callup.date ? long(D.callup.date) : ''].filter(Boolean).join(' · '), T_.league, { noSeason: true });
    const fl = await loadImg('/img/tunisia-flag.svg'); if (fl) { ctx.drawImage(fl, W - 48 - 120, 184, 120, 80); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.strokeRect(W - 48 - 120, 184, 120, 80); }
    for (let i = 0; i < pl.length; i++) {
      const p = pl[i], col = i % 2, x = 40 + col * 510, y = top + Math.floor(i / 2) * (CH + 12);
      ctx.fillStyle = C.card; rr(ctx, x, y, 490, CH, 22); ctx.fill(); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
      await photo(ctx, p, x + 14, y + 14, 68);
      txt(ctx, K.nm(p.name), x + 98, y + 42, { size: 29, weight: 800, maxW: 380 });
      if (p.team) { await K.logo(ctx, p.team, x + 98, y + 54, 30); txt(ctx, `${p.team}${p.number != null ? ' · #' + p.number : ''}${p.pos ? ' · ' + p.pos : ''}`, x + 138, y + 76, { size: 21, weight: 700, color: C.mut, maxW: 330 }); }
      else txt(ctx, p.club || T_.outside, x + 98, y + 76, { size: 21, weight: 700, color: C.acc, maxW: 380 });
    }
    const names = pl.map(p => K.nm(p.name));
    caption(lang() === 'fr' ? `🇹🇳 Équipe nationale : les convoqués${label ? ` (${label})` : ''} !\n${names.map(n => '• ' + n).join('\n')}\n\nUn mot pour nos Aigles de Carthage ? 👇\nTous les détails : tunisiabasket.com\n${tags}`
      : `🇹🇳 National team: the called-up players${label ? ` (${label})` : ''}!\n${names.map(n => '• ' + n).join('\n')}\n\nA word for our Eagles of Carthage? 👇\nAll the details: tunisiabasket.com\n${tags}`);
    download('tunisia-basket-equipe-nationale-convoques.png');
  }

  // ---------------------------------------------------------------- the results of one competition
  async function drawResults() {
    await ensure(); const cs = withGames(), T_ = t();
    if (!cs.length) return empty(T_.nores, 'tunisia-basket-equipe-nationale-resultats.png');
    if (!cs.some(c => c.id === comp)) comp = played()[0].competition;          // the competition of the latest game
    sync('nt_results');
    const all = played().filter(g => g.competition === comp), gs = all.slice(0, 10), top = 330, RH = 124, H = top + gs.length * RH + 150;
    const w = all.filter(g => g.won).length, l = all.length - w, pf = all.reduce((s, g) => s + g.tun, 0), pa = all.reduce((s, g) => s + g.opp_score, 0);
    const ctx = await frame(H, T_.league, T_.results, `${cname(comp)} · ${w}${T_.w} – ${l}${T_.l} · ${pf}–${pa}${all.length > gs.length ? ' · ' + T_.last(gs.length) : ''}`, T_.league, { noSeason: true });
    for (let i = 0; i < gs.length; i++) {
      const g = gs[i], y = top + i * RH, away = g.site === 'away', L = away ? { opp: g } : { tun: true }, R = away ? { tun: true } : { opp: g };
      ctx.fillStyle = C.card; rr(ctx, 40, y, W - 80, RH - 14, 22); ctx.fill(); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
      ctx.fillStyle = g.won ? C.good : '#ff5d6c'; rr(ctx, 40, y, 10, RH - 14, 5); ctx.fill();
      txt(ctx, fmt(g.date), 74, y + 46, { size: 27, weight: 800 });
      txt(ctx, rnd(g.round), 74, y + 78, { size: 18, color: C.mut, maxW: 205 });
      const side = async (S, cx, nameX, align) => { await badge(ctx, cx, y + (RH - 14) / 2, 34, S.tun ? null : S.opp); txt(ctx, S.tun ? T_.tun : oname(S.opp), nameX, y + (RH - 14) / 2 + 9, { size: 25, weight: 800, align, maxW: 170 }); };
      await side(L, 330, 376, 'left'); await side(R, 1000 - 24, 1000 - 24 - 48, 'right');
      const ls = L.tun ? g.tun : g.opp_score, rs = R.tun ? g.tun : g.opp_score, lw = ls > rs;
      txt(ctx, String(ls), W / 2 + 110 - 34, y + 70, { size: 54, weight: 900, color: lw ? C.acc : C.mut, align: 'right' });
      txt(ctx, '–', W / 2 + 110, y + 64, { size: 34, weight: 700, color: C.mut, align: 'center' });
      txt(ctx, String(rs), W / 2 + 110 + 34, y + 70, { size: 54, weight: 900, color: lw ? C.mut : C.acc });
      if (g.ot) txt(ctx, T_.ot.toUpperCase(), W / 2 + 110, y + 96, { size: 16, weight: 800, color: C.mut, align: 'center', space: '2px' });
    }
    const last = gs[0], won = last.won;
    caption(lang() === 'fr' ? `🇹🇳 ${cname(comp)} : les résultats de la Tunisie\n${last.site === 'away' ? oname(last) + ' ' + last.opp_score + ' – ' + last.tun + ' Tunisie' : 'Tunisie ' + last.tun + ' – ' + last.opp_score + ' ' + oname(last)} ${won ? '✅' : '❌'}\nBilan : ${w} victoire${w > 1 ? 's' : ''}, ${l} défaite${l > 1 ? 's' : ''}.\nVotre avis sur le parcours de nos Aigles de Carthage ? 👇\nTous les détails : tunisiabasket.com\n${tags}`
      : `🇹🇳 ${cname(comp)}: Tunisia's results\n${last.site === 'away' ? oname(last) + ' ' + last.opp_score + ' – ' + last.tun + ' Tunisia' : 'Tunisia ' + last.tun + ' – ' + last.opp_score + ' ' + oname(last)} ${won ? '✅' : '❌'}\nRecord: ${w}-${l}.\nWhat do you make of our Eagles of Carthage? 👇\nAll the details: tunisiabasket.com\n${tags}`);
    download(`tunisia-basket-equipe-nationale-${comp}-resultats.png`);
  }

  const capBox = `<div class="row" style="flex-basis:100%;align-items:flex-start;gap:8px"><textarea id="nt-cap" rows="3" style="flex:1;min-width:260px;height:84px;min-height:0;font:inherit;resize:vertical" placeholder="Post text for Facebook"></textarea><button id="nt-copy">📋 Copy the post text</button></div>`;
  const bind = redraw => {
    const sel = document.getElementById('nt-comp'); if (sel) sel.onchange = () => { comp = sel.value; redraw(); };
    const cp = document.getElementById('nt-copy'); if (cp) cp.onclick = async () => { const e = document.getElementById('nt-cap'); try { await navigator.clipboard.writeText(e.value); cp.textContent = '✅ Copied'; } catch (x) { e.select(); } setTimeout(() => { cp.textContent = '📋 Copy the post text'; }, 1500); };
  };
  const compSelect = () => `<label class="small mut">Competition</label><select id="nt-comp">${D ? withGames().map(c => `<option value="${esc(c.id)}" ${c.id === comp ? 'selected' : ''}>${esc(c.en)}</option>`).join('') : ''}</select>`;
  const lazy = (key, html) => () => { if (!D) ensure().then(() => { const c = document.getElementById('imgctl'); if (c && K.extra[key]) { c.innerHTML = K.extra[key].controls(); K.extra[key].bind(K.redraw); } }).catch(() => {}); return html() + capBox; };
  K.extra.nt_callup = { group: 'natteam', label: '📋 The called-up players', controls: lazy('nt_callup', () => ''), bind, draw: drawCallup };
  K.extra.nt_results = { group: 'natteam', label: '🏁 Results of a competition', controls: lazy('nt_results', compSelect), bind, draw: drawResults };
})();
