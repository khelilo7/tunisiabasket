// Admin: Nationale 1 (the league below the Pro A), the "National One" subsection of the Games & scores tab. Results first (pick a game of the calendar, type the score, save; edit or remove it),
// then the set-up (season, teams, calendar, the federation's table, the play-off). Teams and results only (nat1.py, data/nat1.json): there are no box scores.
// A saved result updates the table, the National One pages and the API at once (the server answers with the new view, painted here). Uses the helpers of admin.html ($, esc, api).
(function () {
  let msg = null, data = null, md = null, open = null, last = null;
  const say = (t, ok = true) => { msg = t ? { t, ok } : null; };
  const J = { 'Content-Type': 'application/json' };
  const today = () => new Date(Date.now() + 3600e3).toISOString().slice(0, 10);          // Tunisia time (UTC+1)
  const fmt = iso => iso ? new Date(iso + 'T12:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }) : '';
  const gkey = (m, g) => `${m}|${g.home}|${g.away}`;
  const signed = v => (v > 0 ? '+' : '') + v;

  async function send(body) {
    const { ok, body: r } = await api('nat1', { method: 'POST', headers: J, body: JSON.stringify(body) });
    say(ok ? r.message : (r.error || 'Could not save.'), ok);
    if (ok) { data = r; document.dispatchEvent(new Event('nat1:changed')); }               // the National One images redraw from the new data
    return ok;
  }
  const opts = (sel) => Object.entries(data.teams).sort((a, b) => a[1].localeCompare(b[1])).map(([c, n]) => `<option value="${esc(c)}" ${c === sel ? 'selected' : ''}>${esc(n)} (${esc(c)})</option>`).join('');

  // the matchday shown first: the latest one whose day has come (where results are typed), else the first one
  function pickMd() {
    const ms = data.matchdays;
    if (!ms.length) return null;
    if (md != null && ms.some(m => m.matchday === md)) return md;
    const due = ms.filter(m => m.date && m.date <= today());
    return (due.length ? due[due.length - 1] : ms[0]).matchday;
  }

  function scoreForm(m, g) {
    return `<div class="card n1form" style="border-color:var(--acc);margin:6px 0 10px" data-form="${esc(gkey(m.matchday, g))}">
      <b>${g.home_score != null ? 'Edit the result' : 'Enter the result'} · J${m.matchday}</b>
      <div class="n1score-in">${[['hs', g.home_name, g.home_score], ['as', g.away_name, g.away_score]].map(([k, n, v]) => `<label><span>${esc(n)}</span><input data-f="${k}" class="num" type="number" inputmode="numeric" min="0" max="250" value="${v ?? ''}" aria-label="${esc(n)} score"></label>`).join('')}</div>
      <div class="row" style="margin-top:8px"><label class="small mut">Date</label><input data-f="date" type="date" value="${esc(g.date || m.date || '')}"><label class="small mut">Time</label><input data-f="time" type="time" value="${esc(g.time || '')}"><span class="mut small">the calendar's day and time unless the game moved</span></div>
      <div class="row" style="margin-top:10px"><button class="primary" data-act="save">Save the result</button><button data-act="cancel">Cancel</button><span class="small" data-f="err" style="color:var(--bad)"></span></div></div>`;
  }

  function resultsCard() {
    const ms = data.matchdays;
    if (!ms.length) return `<div class="card"><h3 style="margin-top:0">Results</h3><div class="mut small">No calendar yet: paste it in “Set-up” below (or type a game that is not in the calendar).</div></div>`;
    const m = ms.find(x => x.matchday === md) || ms[0], i = ms.indexOf(m);
    const label = x => `J${x.matchday}${x.date ? ' · ' + fmt(x.date) : ''}${x.games.every(g => g.home_score != null) ? ' ✓' : x.missing ? ` · ${x.missing} missing` : ''}`;
    return `<div class="card"><h3 style="margin-top:0">Results</h3>
      <div class="row"><button data-md="${i > 0 ? ms[i - 1].matchday : ''}" ${i > 0 ? '' : 'disabled'} title="Previous matchday">‹</button><select id="n1mdsel" style="flex:1;max-width:280px">${ms.map(x => `<option value="${x.matchday}" ${x === m ? 'selected' : ''}>${label(x)}</option>`).join('')}</select><button data-md="${i < ms.length - 1 ? ms[i + 1].matchday : ''}" ${i < ms.length - 1 ? '' : 'disabled'} title="Next matchday">›</button>
        <span class="mut small">${m.games.filter(g => g.home_score != null).length}/${m.games.length} scores</span></div>
      <div class="n1games" style="margin-top:8px">
      ${m.games.map(g => { const k = gkey(m.matchday, g), done = g.home_score != null, hw = done && g.home_score > g.away_score; return `<div class="n1row${last === k ? ' n1just' : ''}" data-g="${esc(k)}">
        <div class="n1teams"><span style="${hw ? 'font-weight:800' : ''}">${esc(g.home_name)}</span> <span class="mut">–</span> <span style="${done && !hw ? 'font-weight:800' : ''}">${esc(g.away_name)}</span>${g.projected ? ' <span class="pill" title="pairing assumed, not published">projected</span>' : ''}<div class="mut small">${esc(fmt(g.date))}${g.time ? ' · ' + esc(g.time) : ''}</div>
          <div class="small" style="margin-top:4px"><input type="date" data-f="kd" value="${esc(g.date || '')}" aria-label="Day of the game" title="Day of the game: change it when the game is moved" style="width:140px"> <input type="time" data-f="kt" value="${esc(g.time || '')}" aria-label="Kick-off time" title="Kick-off time (hh:mm); empty = no time" style="width:108px"> <button data-act="time" title="Save the day and the kick-off time of this game">🕐 Save day &amp; time</button></div></div>
        <div class="n1score">${done ? `<span class="pill ok">${g.home_score} – ${g.away_score}</span>` : `<span class="mut small">${g.date && g.date < today() ? 'score missing' : 'to come'}</span>`}</div>
        <div class="n1acts"><button data-act="open" class="${done ? '' : 'primary'}">${done ? '✎ Edit' : '🏁 Enter result'}</button>${done ? ` <button data-act="img" title="Make the final-score image of this game">🖼️</button> <button data-act="rm" title="Remove this result">🗑</button>` : ` <button data-act="rmfx" title="Remove this game from the calendar (a game typed by mistake)">🗑</button>`}</div></div>
        ${open === k ? scoreForm(m, g) : ''}`; }).join('')}</div>
      <p class="mut small" style="margin:8px 0 0">Saving a result updates the National One table, its results and calendar pages, the app and the images at once. Same checks as the Pro A: both teams of the calendar, scores 0–250, no tie, a team plays once per matchday. A game moved to another day: change its day in its row (🕐 Save day &amp; time), before or after the score.</p></div>`;
  }

  function tableCard() {
    const rows = data.standings, off = data.official;
    if (!rows.length) return '';
    const src = off ? `Base: the ${esc(off.source)} table of ${esc(off.published || '?')}${off.since ? ` + ${off.since} result(s) typed since` : ' (no result typed since)'}.` : 'Computed from the results.';
    return `<details class="card" style="margin-top:12px" ${last ? 'open' : ''}><summary style="cursor:pointer"><b>Standings now</b> <span class="mut small">${src}</span></summary>
      <div style="overflow-x:auto;margin-top:8px"><table style="max-width:560px"><thead><tr><th>#</th><th class="l">Team</th><th>J</th><th>W-L</th><th>Diff</th><th>Pts</th></tr></thead><tbody>
      ${rows.map(r => `<tr><td>${r.rank}</td><td class="l">${esc(r.name)} <span class="mut small">${esc(r.code)}</span></td><td>${r.j}</td><td>${r.w}-${r.l}</td><td>${signed(r.diff)}</td><td><b>${r.pts}</b></td></tr>`).join('')}</tbody></table></div>
      <div class="row" style="margin-top:6px"><a href="/nationale-1" target="_blank" rel="noopener">Open the public page ↗</a></div></details>`;
  }

  function paint() {
    const box = $('#nat1box'); if (!box) return;
    md = pickMd();
    const teams = Object.keys(data.teams);
    box.innerHTML = `
      <p class="mut small" style="margin:6px 0 10px">National One: pick a game of the calendar, type the score, save. The table (2 points a win, 1 a loss, the FTBB's tie-break law) and the public pages follow at once. There are no box scores for this league.</p>
      ${msg ? `<div class="${msg.ok ? 'okbox' : 'problems'}">${esc(msg.t)}</div>` : ''}
      ${resultsCard()}
      ${tableCard()}
      <div class="subtabs-h" style="margin-top:18px">Set-up</div>
      <details class="card"><summary style="cursor:pointer"><b>Season and teams</b> <span class="mut small">${esc(data.season)} · ${teams.length} team(s) · ${data.games} result(s)</span></summary>
        <div class="row" style="margin-top:8px"><input id="n1season" value="${esc(data.season)}" size="10"><button id="n1saveseason">Save the season</button></div>
        <div class="row" style="margin-top:8px"><input id="n1code" placeholder="Code (ESM)" size="9" maxlength="8" style="text-transform:uppercase"><input id="n1name" placeholder="Name (ES Marsa)" maxlength="40" style="flex:1;min-width:200px"><button class="primary" id="n1addteam">Add / rename</button></div>
        <div style="margin-top:8px">${teams.length ? Object.entries(data.teams).sort((a, b) => a[1].localeCompare(b[1])).map(([c, n]) => `<span class="pill" style="margin:2px 6px 2px 0;font-size:13px;padding:4px 10px">${esc(n)} <b>${esc(c)}</b> <a href="#" data-rt="${esc(c)}" title="Remove this team (only if it has no result)" style="margin-left:4px">×</a></span>`).join('') : '<span class="mut small">No team yet.</span>'}</div></details>
      <details class="card" style="margin-top:10px"><summary style="cursor:pointer"><b>Calendar</b> <span class="mut small">paste the games with their dates</span></summary>
        <p class="mut small" style="margin:6px 0">One game per line: <code>matchday, HOME, AWAY, date[, time][, projected]</code> (time like <code>18:30</code> or <code>18h30</code>; you can also set it later, game by game, in Results). Add <code>projected</code> when the pairing is assumed, not published. A game with no result yet shows as “to come”, then “score missing” once its day has passed.</p>
        <textarea id="n1fix" rows="5" style="width:100%" placeholder="5, BS, EZS, 2026-11-21, 18:30"></textarea><div class="row" style="margin-top:6px"><button id="n1fixgo">Save the calendar</button></div></details>
      <details class="card" style="margin-top:10px"><summary style="cursor:pointer"><b>Several results at once, or a game not in the calendar</b></summary>
        ${teams.length < 2 ? '<div class="mut small">Add at least two teams first.</div>' : `<div class="row" style="margin-top:8px"><label class="small mut">J</label><input id="n1md" type="number" min="1" max="60" value="${md || 1}" style="width:70px">
          <select id="n1home">${opts()}</select><input id="n1hs" type="number" min="0" max="250" placeholder="pts" style="width:76px"><b>–</b><input id="n1as" type="number" min="0" max="250" placeholder="pts" style="width:76px"><select id="n1away">${opts(teams[1])}</select>
          <input id="n1date" type="date" title="Date of the game (optional)"><button id="n1addres">Save this result</button></div>
          <p class="mut small" style="margin:6px 0">Only for a matchday that has no calendar: when it has one, the game must be one of it.</p>`}
        <p class="mut small" style="margin:10px 0 6px">A list, one per line: <code>matchday, HOME, AWAY, home score, away score[, date[, time]]</code> (the team codes). All or nothing: if a line is wrong nothing is saved and the line is named.</p>
        <textarea id="n1paste" rows="5" style="width:100%" placeholder="3, ESM, EOS, 78, 71, 2026-10-04"></textarea><div class="row" style="margin-top:6px"><button id="n1pastego">Save the list</button></div></details>
      <details class="card" style="margin-top:10px"><summary style="cursor:pointer"><b>The federation's table</b> <span class="mut small">${data.official ? `FTBB table of ${esc(data.official.published || '?')} is the base` : 'none: the table is computed'}</span></summary>
        <p class="mut small" style="margin:6px 0">Paste it when the FTBB publishes one: it becomes the base of the table (its numbers win over ours, we may miss a score), and every result typed after it moves the table on from it. First line <code>date: 2026-11-15</code>, then one team per line in table order: <code>CODE, played, won, lost, difference, points</code>. Points must be 2 per win + 1 per loss. Send an empty box to remove it (the table is then computed from the results only).</p>
        <textarea id="n1off" rows="8" style="width:100%" placeholder="date: 2026-11-15&#10;EZS, 4, 4, 0, 97, 8"></textarea><div class="row" style="margin-top:6px"><button id="n1offgo">Save the table</button></div></details>
      <details class="card" style="margin-top:10px"><summary style="cursor:pointer"><b>Play-off (promotion to the Pro A)</b> <span class="mut small">${data.playoff_on ? 'announced' : 'not announced'}</span></summary>
        <div class="row" style="margin:6px 0"><b>${data.playoff_on ? 'Announced: the Play-off tab is visible.' : 'Not announced: the public site has no Play-off tab.'}</b><button id="n1poann" class="${data.playoff_on ? 'danger' : 'primary'}">${data.playoff_on ? 'Hide it again' : 'Announce the play-off'}</button><a href="/nationale-1/playoff?preview=1" target="_blank" rel="noopener">Preview (only you see it)</a></div>
        <p class="mut small" style="margin:6px 0">The bracket draws itself from the table: the first eight, 1v8, 4v5, 2v7, 3v6 (quarter-finals <code>qf1</code> <code>qf2</code> <code>qf3</code> <code>qf4</code>, best of three), then <code>sf1</code> (winners of qf1, qf2) and <code>sf2</code> (qf3, qf4), then the <code>final</code> in one game on neutral ground. The seeds are provisional until the last game of the calendar is past. Type the games, one per line: <code>GAME, series, HOME, home score, away score[, date]</code>. The games written for a series replace its games; nothing is saved if a line is wrong.</p>
        <textarea id="n1po" rows="5" style="width:100%" placeholder="GAME, qf1, EZS, 81, 74, 2027-04-24&#10;GAME, qf1, BCM, 70, 77, 2027-04-27"></textarea>
        <div class="row" style="margin-top:6px"><button id="n1pogo">Save the play-off games</button><button class="danger" id="n1poclear">Remove all play-off games</button>${data.playoff ? `<span class="mut small">${data.playoff.promoted.length} club(s) promoted so far</span>` : '<span class="mut small">Needs eight clubs in the table.</span>'}</div></details>`;
    wire(box);
  }

  function wire(box) {
    const run = async fn => { await fn(); paint(); };
    const sel = $('#n1mdsel'); if (sel) sel.onchange = () => { md = +sel.value; open = null; paint(); };
    box.querySelectorAll('[data-md]').forEach(b => b.onclick = () => { if (b.dataset.md) { md = +b.dataset.md; open = null; paint(); } });
    box.querySelectorAll('.n1row[data-g]').forEach(tr => {
      const k = tr.dataset.g, [m, home, away] = k.split('|');
      tr.querySelector('[data-act=open]').onclick = () => { open = open === k ? null : k; paint(); const f = box.querySelector('[data-form] [data-f=hs]'); if (f) f.focus(); };
      const rm = tr.querySelector('[data-act=rm]'); if (rm) rm.onclick = () => { if (confirm(`Remove the result J${m} ${home} – ${away}? The table goes back to how it was without it.`)) run(async () => { if (await send({ op: 'remove_result', matchday: +m, home, away })) { open = null; last = null; } }); };
      tr.querySelector('[data-act=time]').onclick = () => run(() => send({ op: 'time', matchday: +m, home, away, date: tr.querySelector('[data-f=kd]').value, time: tr.querySelector('[data-f=kt]').value }));
      const rx = tr.querySelector('[data-act=rmfx]'); if (rx) rx.onclick = () => { if (confirm(`Remove ${home} – ${away} (J${m}) from the calendar? It has no result.`)) run(() => send({ op: 'remove_fixture', matchday: +m, home, away })); };
      const im = tr.querySelector('[data-act=img]'); if (im) im.onclick = () => { if (window.N1Img) window.N1Img.game(+m, home, away); };
    });
    const f = box.querySelector('[data-form]');
    if (f) {
      const [m, home, away] = f.dataset.form.split('|'), err = f.querySelector('[data-f=err]');
      f.querySelector('[data-act=cancel]').onclick = () => { open = null; paint(); };
      const save = () => {
        const hs = f.querySelector('[data-f=hs]').value.trim(), as = f.querySelector('[data-f=as]').value.trim(), date = f.querySelector('[data-f=date]').value, time = f.querySelector('[data-f=time]').value;
        const bad = hs === '' || as === '' ? 'Type both scores.' : !/^\d{1,3}$/.test(hs) || !/^\d{1,3}$/.test(as) || +hs > 250 || +as > 250 ? 'A score is a whole number from 0 to 250.' : +hs === +as ? 'A basketball game has a winner: the scores are equal.' : '';
        if (bad) { err.textContent = bad; return; }
        run(async () => { if (await send({ op: 'result', matchday: +m, home, away, home_score: +hs, away_score: +as, date, time })) { open = null; last = f.dataset.form; } });
      };
      f.querySelector('[data-act=save]').onclick = save;
      f.querySelectorAll('input').forEach(i => i.onkeydown = e => { if (e.key === 'Enter') save(); });
    }
    $('#n1saveseason').onclick = () => run(() => send({ op: 'season', season: $('#n1season').value.trim() }));
    $('#n1addteam').onclick = () => run(async () => { if (await send({ op: 'team', code: $('#n1code').value, name: $('#n1name').value })) { $('#n1code').value = ''; $('#n1name').value = ''; } });
    box.querySelectorAll('[data-rt]').forEach(a => a.onclick = e => { e.preventDefault(); if (confirm('Remove team ' + a.dataset.rt + '?')) run(() => send({ op: 'remove_team', code: a.dataset.rt })); });
    if ($('#n1addres')) $('#n1addres').onclick = () => run(() => send({ op: 'result', matchday: $('#n1md').value, home: $('#n1home').value, away: $('#n1away').value, home_score: $('#n1hs').value, away_score: $('#n1as').value, date: $('#n1date').value }));
    $('#n1pastego').onclick = () => run(async () => { if (await send({ op: 'paste', text: $('#n1paste').value })) $('#n1paste').value = ''; });
    $('#n1fixgo').onclick = () => run(async () => { if (await send({ op: 'fixtures', text: $('#n1fix').value })) $('#n1fix').value = ''; });
    $('#n1poann').onclick = () => run(() => send({ op: 'playoff_announce', on: !data.playoff_on }));
    $('#n1pogo').onclick = () => run(async () => { if (await send({ op: 'playoff_games', text: $('#n1po').value })) $('#n1po').value = ''; });
    $('#n1poclear').onclick = () => run(async () => { if (confirm('Remove all the play-off games?')) await send({ op: 'playoff_clear' }); });
    $('#n1offgo').onclick = () => run(async () => { if ($('#n1off').value.trim() || confirm('Remove the federation table?')) await send({ op: 'official', text: $('#n1off').value }); });
  }

  window.loadNat1 = async function () {
    const box = $('#nat1box'); if (!box) return;
    try { data = (await api('nat1')).body; paint(); } catch (e) { box.innerHTML = `<div class="problems">${esc(e.message)}</div>`; }
  };
})();
