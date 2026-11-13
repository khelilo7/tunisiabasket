// Admin: games counted by hand by the analysts (/analytics). Nothing they enter is public until it is approved here; approving publishes it as one-team sheets
// (data/partial_games.json: minutes, +/- and fouls drawn stay unknown, no standings, no MVP race). Uses the helpers of admin.html ($, esc, api).
(function () {
  let msg = null;
  const opened = new Set();                       // the games the admin has opened: they stay open when the list is redrawn
  const say = (t, ok = true) => { msg = t ? { t, ok } : null; };

  async function post(path, body) {
    try {
      const { ok, body: r } = await api('analytics/' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
      say(ok ? r.message : (r.error || 'Could not save.'), ok);
      return ok;
    } catch (e) { say(e.message, false); return false; }
  }

  const state = { submitted: '<span class="pill warn">waiting for approval</span>', published: '<span class="pill ok">published</span>', rejected: '<span class="pill bad">sent back</span>' };
  const cols = ['pts', 'fgm', 'fga', 'p3m', 'p3a', 'ftm', 'fta', 'oreb', 'dreb', 'ast', 'stl', 'blk', 'tov', 'pf'];

  function block(g) {
    const sc = `${g.home} ${g.home_score} – ${g.away_score} ${g.away}`;
    const off = g.official
      ? (g.same_score ? `<span class="pill ok">same score as the official result</span>` : `<span class="pill bad">official result: ${esc(g.official.home)} ${g.official.home_score} – ${g.official.away_score} ${esc(g.official.away)}</span>`)
      : `<span class="pill warn">no official result yet for J${g.matchday}: it will show once you enter it</span>`;
    const table = c => `<div class="small mut" style="margin-top:6px">${esc(c)}</div><div style="overflow-x:auto"><table><thead><tr><th>#</th><th class="l">Player</th>${cols.map(k => `<th>${k.toUpperCase()}</th>`).join('')}</tr></thead>
      <tbody>${g.box[c].map(p => `<tr><td>${p.number}</td><td class="l">${esc(p.name)}</td>${cols.map(k => `<td>${p[k]}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    const buttons = g.status === 'submitted'
      ? `<div class="row" style="margin-top:8px"><label class="small mut">Matchday</label><input class="num" type="number" data-md value="${g.matchday ?? ''}"><label class="small mut">Date</label><input type="date" data-date value="${esc(g.date || '')}">
          <button class="primary" data-act="approve" data-id="${g.id}">✔ Approve and publish</button><input data-note placeholder="Reason (shown to the analyst)" style="min-width:200px"><button class="danger" data-act="reject" data-id="${g.id}">Send back</button></div>`
      : g.status === 'published' ? `<div class="row" style="margin-top:8px"><button class="danger" data-act="unpublish" data-id="${g.id}">Remove from the site</button></div>` : (g.note ? `<div class="mut small" style="margin-top:6px">Reason sent: ${esc(g.note)}</div>` : '');
    const who = (g.analyst ? `<span class="pill" title="the analyst who counted this version">✎ ${esc(g.analyst)}</span>` : '<span class="pill">no name (older game)</span>') + (g.kind === 'video' ? '<span class="pill" title="counted from the video of the game">🎥 video</span>' : '');
    const log = `<details style="margin-top:8px"><summary class="small mut" style="cursor:pointer">Change log (${(g.log || []).length}): who did what</summary><div class="small" style="max-height:260px;overflow:auto;margin-top:6px">${(g.log || []).slice().reverse().map(l => `<div style="display:grid;grid-template-columns:140px 90px 1fr;gap:8px;padding:2px 0;border-bottom:1px solid var(--line)"><span class="mut">${esc(l.at)}</span><b>${esc(l.by)}</b><span>${esc(l.detail)}</span></div>`).join('') || '<span class="mut">Nothing logged.</span>'}</div></details>`;
    const open = g.status === 'published' ? '' : `<a href="/analytics#game=${g.id}" target="_blank" rel="noopener"><button title="Opens this version in the counting page: you can add, change or remove any action (logged as Admin)">✎ Open and edit this version</button></a>`;
    return `<details class="card" style="margin-top:8px" data-g="${g.id}" ${opened.has(g.id) ? 'open' : ''}><summary style="cursor:pointer;list-style:none"><div class="row"><span class="mut">▸</span><b style="font-size:16px">${esc(sc)}</b>${who}${state[g.status] || ''}<span class="mut small">J${g.matchday ?? '?'} · ${esc(g.date || '')} · ${g.events} actions</span><span class="sp"></span>${g.official ? (g.same_score ? '<span class="pill ok">✓ score = official</span>' : '<span class="pill bad">score ≠ official</span>') : '<span class="pill warn">no official result yet</span>'}</div></summary>
      <div class="row" style="margin-top:8px">${off}<span class="sp"></span>${open}</div>
      ${Object.keys(g.box).map(table).join('')}${buttons}${log}</details>`;
  }

  async function load() {
    const box = $('#analyticsbox'); if (!box) return;
    let games, counting = [];
    try { const r = (await api('analytics')).body; games = r.games; counting = r.counting || []; } catch (e) { box.innerHTML = `<div class="problems">${esc(e.message)}</div>`; return; }
    box.innerHTML = `<h3 style="margin-top:16px">📋 Games counted by analysts</h3>
      <p class="mut small" style="margin:4px 0">Analysts sign in at <b>/analytics</b> with their own token (it never opens this panel) <b>and a name</b>: every action carries it, and two analysts with two names each get their own version of a game. Open any version to change anything (logged as Admin), approve <b>one</b> (approving another version of the same game replaces it on the site). <b>Nothing is public until you approve it.</b> An approved game appears as a one-team sheet on each player's page, like the hand-kept sheets: minutes, +/- and fouls drawn stay unknown, it never changes standings or the MVP race, and a real box score of the same game replaces it. Check the score against the official result first.</p>
      ${msg ? `<div class="${msg.ok ? 'okbox' : 'problems'}">${esc(msg.t)}</div>` : ''}
      <div class="card" style="margin-top:8px"><b>🔴 Being counted now</b> <span class="mut small">Switch a game to <b>Live</b> and the public can follow it on the site's Live page (score, clock, box score, last plays), updating every few seconds. It stops being live when the analyst sends it for approval.</span>
        ${counting.length ? counting.map(g => `<div class="row" style="margin-top:8px"><b>${esc(g.score)}</b><span class="pill">✎ ${esc(g.analyst || 'no name')}</span>${g.kind === 'video' ? '<span class="pill">🎥 video</span>' : ''}<span class="mut small">${g.matchday ? 'J' + g.matchday + ' · ' : ''}${g.events} actions</span>${g.live ? '<span class="pill bad">● LIVE</span>' : ''}<span class="sp"></span><a href="/analytics#game=${g.id}" target="_blank" rel="noopener"><button title="Open this version in the counting page and change anything">✎ Open and edit</button></a>
          ${g.kind === 'video' ? '' : `<button class="${g.live ? 'danger' : 'primary'}" data-live="${g.id}" data-on="${g.live ? 0 : 1}">${g.live ? 'Stop live' : '● Go live'}</button>`}</div>`).join('') : '<div class="mut small" style="margin-top:6px">No game is being counted at the moment.</div>'}</div>
      ${games.map(block).join('') || '<div class="mut">No game sent yet.</div>'}`;
    box.querySelectorAll('details[data-g]').forEach(d => { d.ontoggle = () => { d.open ? opened.add(d.dataset.g) : opened.delete(d.dataset.g); }; });
    box.querySelectorAll('[data-live]').forEach(b => b.onclick = async () => { await post(`${b.dataset.live}/live`, { on: b.dataset.on === '1' }); load(); });
    box.querySelectorAll('[data-act]').forEach(b => b.onclick = async () => {
      const card = b.closest('.card'), act = b.dataset.act, body = {};
      if (act === 'approve') { body.matchday = +card.querySelector('[data-md]').value; body.date = card.querySelector('[data-date]').value; }
      if (act === 'reject') body.note = card.querySelector('[data-note]').value;
      if (act === 'unpublish' && !confirm('Remove these stats from the site?')) return;
      await post(`${b.dataset.id}/${act}`, body); load();
    });
  }
  window.loadAnalytics = load;
})();
