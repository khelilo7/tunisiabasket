// Admin: the sources of a game (game_sources.py). Every version of a box score that was sent is kept; here the admin compares them and chooses what is published:
// one source as it is, or a MIX (a base source + cell by cell picks). Uses the helpers of admin.html ($, esc, api).
(function () {
  let list = null, cmp = null, sel = null, base = null, picks = {}, msg = null, problems = [], lock = true;
  const J = { 'Content-Type': 'application/json' };
  const say = (t, ok = true) => { msg = t ? { t, ok } : null; };
  const STAT = { min: 'MIN', fgm: 'FGM', fga: 'FGA', p2m: '2PM', p2a: '2PA', p3m: '3PM', p3a: '3PA', ftm: 'FTM', fta: 'FTA', oreb: 'OR', dreb: 'DR', reb: 'REB', ast: 'AST', tov: 'TO', stl: 'STL', blk: 'BLK', pf: 'PF', fd: 'FD', pm: '+/-', pts: 'PTS' };
  const COLORS = ['#6aa9ff', '#ffb74d', '#3ecf8e', '#ff6b81', '#c792ea', '#4dd0e1'];
  const col = sid => COLORS[(parseInt(String(sid).replace(/\D/g, ''), 10) - 1) % COLORS.length];
  const fmtAt = at => at ? String(at).replace('T', ' ').replace('Z', ' UTC').slice(0, 19) : '';

  async function post(path, body) {
    const { ok, body: r } = await api(path, { method: 'POST', headers: J, body: JSON.stringify(body || {}) });
    return { ok, r };
  }
  async function loadList() { const { ok, body } = await api('game-sources'); list = ok ? body : { games: [], duplicates: [] }; }
  async function open(id) {
    const { ok, body } = await api('game-sources/' + encodeURIComponent(id));
    if (!ok) { say(body.error || 'Could not load this game.', false); return; }
    setCmp(body);
  }
  function setCmp(c) {
    cmp = c; sel = c.id; picks = { ...(c.picks || {}) }; problems = [];
    base = c.base && c.sids.includes(c.base) ? c.base : c.sids[c.sids.length - 1]; lock = true;
  }
  function cellBlock(cell, label, vals, fmt) {
    const cur = picks[cell] || base;
    return `<span class="srcell"><b class="small mut">${esc(label)}</b>${Object.entries(vals).map(([sid, v]) =>
      `<button class="srv${sid === cur ? ' on' : ''}" data-cell="${esc(cell)}" data-sid="${sid}" style="border-color:${col(sid)}" title="${esc(sid)}"><i style="background:${col(sid)}"></i>${esc(fmt(v))}</button>`).join('')}</span>`;
  }
  function paint() {
    const box = $('#srcbox'); if (!box) return;
    const dups = (list.duplicates || []).filter(d => d.ids.length > 1);
    box.innerHTML = `
      <p class="mut small" style="margin:6px 0 10px">Every box score sent for a game is kept as a <b>source</b>. When a game has several, compare them here and choose what the site publishes: one source as it is, or a <b>mix</b> (take a base source, then pick the number you trust cell by cell). A game you choose is <b>locked</b>: later pushes only add sources (flagged “new”) and the published version does not change until you unlock it.</p>
      ${msg ? `<div class="${msg.ok ? 'okbox' : 'problems'}">${esc(msg.t)}</div>` : ''}
      ${dups.length ? `<div class="card" style="margin-bottom:12px"><h3 style="margin-top:0">Look like the same game</h3>${dups.map(d => `<div class="row" style="padding:3px 0"><span>${esc(d.title)} · J${esc(d.matchday)} · ${d.ids.map(esc).join(' / ')}</span><button data-attach="${esc(d.ids[0])}|${esc(d.ids[1])}">Make ${esc(d.ids[1])} a source of ${esc(d.ids[0])}</button></div>`).join('')}</div>` : ''}
      <div class="card"><h3 style="margin-top:0">Games with several sources</h3>${list.games.length ? `<table class="srtable"><thead><tr><th>Game</th><th>J</th><th>Sources</th><th>Differences</th><th></th></tr></thead><tbody>${list.games.map(g => `<tr class="${g.id === sel ? 'on' : ''}"><td><b>${esc(g.title)}</b> <span class="mut small">${esc(g.id)}</span></td><td>${esc(g.matchday ?? '')}</td><td>${g.sources}</td><td>${g.diffs ? '<b>' + g.diffs + '</b>' : '<span class="mut">none</span>'}</td><td>${g.locked ? '🔒 ' : ''}${g.unreviewed ? `<span class="pill" style="background:var(--acc);color:#10131c">${g.unreviewed} new</span> ` : ''}<button data-open="${esc(g.id)}">Compare</button></td></tr>`).join('')}</tbody></table>` : '<div class="mut small">None yet: a game appears here the day a second version of it is sent.</div>'}</div>
      ${cmp ? panel() : ''}`;
    box.querySelectorAll('[data-open]').forEach(b => b.onclick = async () => { say(null); await open(b.dataset.open); paint(); });
    box.querySelectorAll('[data-attach]').forEach(b => b.onclick = async () => {
      const [a, o] = b.dataset.attach.split('|'); if (!confirm(`Make ${o} a source of ${a}? ${o} leaves the site (kept in games_replaced).`)) return;
      const { ok, r } = await post(`game-sources/${a}/attach`, { from: o }); say(ok ? r.message : r.error, ok); if (ok) setCmp(r); await loadList(); paint();
    });
    if (!cmp) return;
    box.querySelectorAll('[data-base]').forEach(b => b.onclick = () => { base = b.dataset.base; for (const k of Object.keys(picks)) if (picks[k] === base) delete picks[k]; paint(); });
    box.querySelectorAll('[data-cell]').forEach(b => b.onclick = () => { const k = b.dataset.cell, sid = b.dataset.sid; if (sid === base) delete picks[k]; else picks[k] = sid; paint(); });
    const lk = $('#srlock'); if (lk) lk.onchange = () => { lock = lk.checked; };
    $('#srpub').onclick = async () => {
      const { ok, r } = await post(`game-sources/${cmp.id}/publish`, { base, picks, lock });
      problems = r.problems || []; say(ok ? r.message : (r.error || 'Could not publish.'), ok && !problems.length);
      if (ok) { const keep = lock; setCmp(r); lock = keep; await loadList(); }
      paint();
    };
    const force = $('#srforce'); if (force) force.onclick = async () => {
      if (!confirm('Publish although the checks fail?')) return;
      const { ok, r } = await post(`game-sources/${cmp.id}/publish`, { base, picks, lock, force: true });
      problems = r.problems || []; say(ok ? 'Published with warnings.' : (r.error || 'Could not publish.'), ok); if (ok) { setCmp(r); await loadList(); } paint();
    };
    const un = $('#srunlock'); if (un) un.onclick = async () => { const { ok, r } = await post(`game-sources/${cmp.id}/unlock`); say(ok ? r.message : r.error, ok); if (ok) { setCmp(r); await loadList(); } paint(); };
  }
  function panel() {
    const c = cmp, n = Object.keys(picks).length, cells = [];
    for (const t of c.teams) {
      if (c.diffs.includes(`${t.code}||points`)) cells.push(`<div class="srrow"><b>${esc(t.code)} · team total</b>${cellBlock(`${t.code}||points`, 'points', t.points, v => v ?? '–')}</div>`);
      for (const p of t.players) {
        const k = `${t.code}|${p.number}`, bits = [];
        if (c.diffs.includes(`${k}|*`)) bits.push(cellBlock(`${k}|*`, 'on the sheet', p.present, v => v ? 'yes' : 'no'));
        for (const s of p.diff) bits.push(cellBlock(`${k}|${s}`, STAT[s] || s, p.stats[s], v => v ?? '–'));
        if (bits.length) cells.push(`<div class="srrow"><b>${esc(t.code)} #${esc(p.number)} ${esc(Object.values(p.names)[0] || '')}</b>${p.name_diff ? `<span class="mut small"> (named ${esc([...new Set(Object.values(p.names))].join(' / '))})</span>` : ''}<div class="srcells">${bits.join('')}</div></div>`);
      }
    }
    return `<div class="card" style="margin-top:12px"><h3 style="margin-top:0">${esc(c.sources[0].title)} <span class="mut small">${esc(c.id)}</span> ${c.locked ? '🔒 locked' : ''}</h3>
      <div class="srsources">${c.sources.map(s => `<label class="srsrc" style="border-color:${col(s.sid)}"><input type="radio" name="srbase" data-base="${s.sid}" ${s.sid === base ? 'checked' : ''}> <i style="background:${col(s.sid)}"></i><b>${esc(s.label || s.sid)}</b> <span class="mut small">${esc(s.sid)} · ${esc(s.score)} · ${esc(fmtAt(s.at))}${s.reviewed ? '' : ' · <b style="color:var(--acc)">new</b>'}${c.chosen === s.sid ? ' · <b>published</b>' : ''}</span>${s.problems.length ? `<div class="small" style="color:var(--bad)">⚠ ${esc(s.problems.join(' · '))}</div>` : ''}</label>`).join('')}</div>
      <div class="mut small" style="margin:8px 0">The <b>base</b> is the source taken as it is. Below, only the cells where the sources disagree: click the value to take instead. ${c.chosen === 'mixed' ? 'The published version is currently a <b>mix</b>.' : ''}</div>
      ${cells.length ? `<div class="srdiff">${cells.join('')}</div>` : '<div class="mut small">The sources agree on every number.</div>'}
      <div class="row" style="margin-top:12px"><button class="primary" id="srpub">${n ? `Publish the mix (base ${esc(base)} + ${n} pick${n > 1 ? 's' : ''})` : `Publish ${esc(base)} as it is`}</button>
        <label class="small"><input type="checkbox" id="srlock" ${lock ? 'checked' : ''}> lock (later pushes only add sources)</label>${c.locked ? '<button id="srunlock">Unlock</button>' : ''}</div>
      ${problems.length ? `<div class="problems" style="margin-top:8px"><b>The result fails the checks:</b><ul>${problems.map(p => `<li>${esc(p)}</li>`).join('')}</ul><button class="danger" id="srforce">Publish anyway</button></div>` : ''}</div>`;
  }
  window.loadSources = async function () {
    const box = $('#srcbox'); if (!box) return;
    try { await loadList(); paint(); } catch (e) { box.innerHTML = `<div class="problems">${esc(e.message)}</div>`; }
  };
})();
