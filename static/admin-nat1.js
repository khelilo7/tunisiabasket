// Admin: Nationale 1 (the league below the Pro A). Teams and results only (nat1.py, data/nat1.json): the site shows the table and the results, there are no box scores.
// Uses the helpers of admin.html ($, esc, api).
(function () {
  let msg = null, data = null;
  const say = (t, ok = true) => { msg = t ? { t, ok } : null; };
  const J = { 'Content-Type': 'application/json' };

  async function send(body) {
    const { ok, body: r } = await api('nat1', { method: 'POST', headers: J, body: JSON.stringify(body) });
    say(ok ? r.message : (r.error || 'Could not save.'), ok);
    if (ok) data = r;
    return ok;
  }
  const opts = (sel) => Object.entries(data.teams).sort((a, b) => a[1].localeCompare(b[1])).map(([c, n]) => `<option value="${esc(c)}" ${c === sel ? 'selected' : ''}>${esc(n)} (${esc(c)})</option>`).join('');

  function paint() {
    const box = $('#nat1box'); if (!box) return;
    const teams = Object.keys(data.teams), nextMd = Math.max(0, ...data.matchdays.filter(m => m.games.some(g => g.home_score != null)).map(m => m.matchday)) + 1;
    box.innerHTML = `
      <p class="mut small" style="margin:6px 0 10px">Nationale 1 is shown on the site as a table and a list of results (page “Nationale 1” of the Standings menu). We only have results, so there are no player or box-score statistics: type the <b>teams</b> first, then the <b>results</b>, one by one or pasted as a list. Two points for a win, one for a loss, like the Pro A. The table is computed from the results, unless you paste the federation's own table.</p>
      ${msg ? `<div class="${msg.ok ? 'okbox' : 'problems'}">${esc(msg.t)}</div>` : ''}
      <div class="card"><h3 style="margin-top:0">Season</h3><div class="row"><input id="n1season" value="${esc(data.season)}" size="10"><button id="n1saveseason">Save</button><span class="mut small">${data.games} result(s) · ${teams.length} team(s)</span></div></div>
      <div class="card" style="margin-top:12px"><h3 style="margin-top:0">Teams</h3>
        <div class="row"><input id="n1code" placeholder="Code (ESM)" size="9" maxlength="8" style="text-transform:uppercase"><input id="n1name" placeholder="Name (ES Marsa)" maxlength="40" style="flex:1;min-width:200px"><button class="primary" id="n1addteam">Add / rename</button></div>
        <div style="margin-top:8px">${teams.length ? Object.entries(data.teams).sort((a, b) => a[1].localeCompare(b[1])).map(([c, n]) => `<span class="pill" style="margin:2px 6px 2px 0;font-size:13px;padding:4px 10px">${esc(n)} <b>${esc(c)}</b> <a href="#" data-rt="${esc(c)}" title="Remove this team (only if it has no result)" style="margin-left:4px">×</a></span>`).join('') : '<span class="mut small">No team yet.</span>'}</div></div>
      <div class="card" style="margin-top:12px"><h3 style="margin-top:0">Add a result</h3>${teams.length < 2 ? '<div class="mut small">Add at least two teams first.</div>' : `
        <div class="row"><label class="small mut">J</label><input id="n1md" type="number" min="1" max="60" value="${nextMd - 1 || 1}" style="width:70px">
          <select id="n1home">${opts()}</select><input id="n1hs" type="number" min="0" max="250" placeholder="pts" style="width:76px"><b>–</b><input id="n1as" type="number" min="0" max="250" placeholder="pts" style="width:76px"><select id="n1away">${opts(teams[1])}</select>
          <input id="n1date" type="date" title="Date of the game (optional)"><button class="primary" id="n1addres">Save the result</button></div>`}
        <details style="margin-top:10px"><summary class="mut small" style="cursor:pointer">Paste a list of results</summary>
          <p class="mut small" style="margin:6px 0">One per line: <code>matchday, HOME, AWAY, home score, away score[, date]</code> (the team codes above). All or nothing: if a line is wrong nothing is saved and the line is named.</p>
          <textarea id="n1paste" rows="6" style="width:100%" placeholder="3, ESM, EOS, 78, 71, 2026-10-04"></textarea><div class="row" style="margin-top:6px"><button id="n1pastego">Save the list</button></div></details></div>
      <div class="card" style="margin-top:12px"><h3 style="margin-top:0">Calendar and federation table</h3>
        <details><summary class="mut small" style="cursor:pointer">Paste the calendar (games with their dates; a score is added later as a result)</summary>
          <p class="mut small" style="margin:6px 0">One game per line: <code>matchday, HOME, AWAY, date[, projected]</code>. Add <code>projected</code> when the pairing is assumed, not published. A game with no result yet shows as “to come”, then “score missing” once its day has passed.</p>
          <textarea id="n1fix" rows="5" style="width:100%" placeholder="5, BS, EZS, 2026-11-21"></textarea><div class="row" style="margin-top:6px"><button id="n1fixgo">Save the calendar</button></div></details>
        <details style="margin-top:8px"><summary class="mut small" style="cursor:pointer">Paste the federation's table${data.official ? ` (current: ${esc(data.official.published || '')})` : ''}</summary>
          <p class="mut small" style="margin:6px 0">When it is there, it <b>is</b> the table of the site (we may not have every score). First line <code>date: 2026-11-15</code>, then one team per line in table order: <code>CODE, played, won, lost, difference, points</code>. Points must be 2 per win + 1 per loss. Send an empty box to remove it (the table is then computed from the results).</p>
          <textarea id="n1off" rows="8" style="width:100%" placeholder="date: 2026-11-15&#10;EZS, 4, 4, 0, 97, 8"></textarea><div class="row" style="margin-top:6px"><button id="n1offgo">Save the table</button></div></details></div>
      <div class="card" style="margin-top:12px"><h3 style="margin-top:0">Results</h3>${data.matchdays.filter(m => m.games.some(g => g.home_score != null)).map(m => `<div style="margin-top:8px"><b>J${m.matchday}</b>${m.date ? ` <span class="mut small">${esc(m.date)}</span>` : ''}
        ${m.games.filter(g => g.home_score != null).map(g => `<div class="row" style="padding:3px 0"><span style="min-width:180px">${esc(g.home_name)}</span><b>${g.home_score} – ${g.away_score}</b><span style="flex:1">${esc(g.away_name)}</span><button data-rm="${m.matchday}|${esc(g.home)}|${esc(g.away)}" title="Remove this result">🗑</button></div>`).join('')}</div>`).join('') || '<div class="mut small">No result yet.</div>'}</div>`;
    const run = async fn => { await fn(); paint(); };
    $('#n1saveseason').onclick = () => run(() => send({ op: 'season', season: $('#n1season').value.trim() }));
    $('#n1addteam').onclick = () => run(async () => { if (await send({ op: 'team', code: $('#n1code').value, name: $('#n1name').value })) { $('#n1code').value = ''; $('#n1name').value = ''; } });
    box.querySelectorAll('[data-rt]').forEach(a => a.onclick = e => { e.preventDefault(); if (confirm('Remove team ' + a.dataset.rt + '?')) run(() => send({ op: 'remove_team', code: a.dataset.rt })); });
    if ($('#n1addres')) $('#n1addres').onclick = () => run(() => send({ op: 'result', matchday: $('#n1md').value, home: $('#n1home').value, away: $('#n1away').value, home_score: $('#n1hs').value, away_score: $('#n1as').value, date: $('#n1date').value }));
    $('#n1pastego').onclick = () => run(async () => { if (await send({ op: 'paste', text: $('#n1paste').value })) $('#n1paste').value = ''; });
    $('#n1fixgo').onclick = () => run(async () => { if (await send({ op: 'fixtures', text: $('#n1fix').value })) $('#n1fix').value = ''; });
    $('#n1offgo').onclick = () => run(async () => { if ($('#n1off').value.trim() || confirm('Remove the federation table?')) await send({ op: 'official', text: $('#n1off').value }); });
    box.querySelectorAll('[data-rm]').forEach(b => b.onclick = () => { const [md, h, a] = b.dataset.rm.split('|'); if (confirm(`Remove J${md} ${h} – ${a}?`)) run(() => send({ op: 'remove_result', matchday: +md, home: h, away: a })); });
  }

  window.loadNat1 = async function () {
    const box = $('#nat1box'); if (!box) return;
    try { data = (await api('nat1')).body; paint(); } catch (e) { box.innerHTML = `<div class="problems">${esc(e.message)}</div>`; }
  };
})();
