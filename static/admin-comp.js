// Admin: the Cup (cup.py) and the play-off / play-out (finals.py). Uses the helpers of admin.html ($, esc, api).
(function () {
  const J = { 'Content-Type': 'application/json' };
  let msg = null;
  const say = (t, ok = true) => { msg = t ? { t, ok } : null; };
  const note = () => msg ? `<div class="${msg.ok ? 'okbox' : 'problems'}">${esc(msg.t)}</div>` : '';
  async function post(path, body) {
    const { ok, body: r } = await api(path, { method: 'POST', headers: J, body: JSON.stringify(body) });
    say(ok ? r.message : (r.error || 'Could not save.'), ok);
    return ok ? r : null;
  }

  // ------------------------------------------------------------------ the Cup
  let cupData = null;
  function paintCup() {
    const box = $('#cupbox'); if (!box) return;
    const d = cupData, ties = d.rounds.flatMap(r => r.ties.map(t => ({ ...t, round: r.name })));
    const label = x => x.code ? `${esc(x.name)} <span class="mut small">${esc(x.code)}</span>` : x.bye ? '<span class="mut">bye</span>' : `<span class="mut">winner of ${esc(x.label || '…')}</span>`;
    box.innerHTML = `
      <p class="mut small" style="margin:6px 0 10px">The Cup: clubs of the Pro A and of the National One (and any club you add here) meet in single games; the winner goes through. Draw the first round once (the whole bracket up to the final is built from it), then type the results: each round fills itself. Page “Coupe” of the Standings menu.</p>
      ${note()}${d.demo ? '<div class="warns">The bracket below is DEMONSTRATION data (tools/demo_cup_finals.py): reset it before the real draw.</div>' : ''}
      <div class="card"><h3 style="margin-top:0">Name and season</h3><div class="row"><input id="cname" value="${esc(d.name)}" style="flex:1;min-width:200px"><input id="cseason" value="${esc(d.season)}" size="10" placeholder="2026-2027"><button id="csavetitle">Save</button></div></div>
      <div class="card" style="margin-top:12px"><h3 style="margin-top:0">The draw (first round)</h3>
        <div class="mut small" style="margin-bottom:6px">Clubs known: ${Object.entries(d.known).map(([c, t]) => `<b>${esc(c)}</b>`).join(' ')}. Another club (lower division...): add it below, then draw it.</div>
        <div class="row" style="margin-bottom:6px"><input id="cxcode" placeholder="Code" size="8" maxlength="8" style="text-transform:uppercase"><input id="cxname" placeholder="Name of a club of neither league" style="flex:1;min-width:200px"><button id="cxadd">Add this club</button></div>
        <textarea id="cdraw" rows="8" style="width:100%" placeholder="CA, CAK, 2026-12-19&#10;EZS, CSS&#10;USM, BYE"></textarea>
        <div class="mut small" style="margin:4px 0 6px">One tie per line: <code>HOME, AWAY[, date]</code>. A club with <code>BYE</code> goes through without playing. The number of ties must be 1, 2, 4, 8, 16 or 32; later rounds are built automatically.</div>
        <div class="row"><input id="cround" placeholder="Round name (optional)" size="22"><button class="primary" id="cdrawgo">Save the draw (replaces the bracket)</button><button id="creset" class="danger">Empty the bracket</button></div></div>
      <div class="card" style="margin-top:12px"><h3 style="margin-top:0">Dates of the rounds</h3>${d.rounds.map(r => `<div class="row" style="margin:4px 0"><b style="min-width:150px">${esc(r.name)}</b><input type="date" data-rdate="${esc(r.key)}" value="${esc(r.date || '')}"><button data-rsave="${esc(r.key)}">Save</button></div>`).join('') || '<span class="mut small">No round yet.</span>'}</div>
      <div class="card" style="margin-top:12px"><h3 style="margin-top:0">Results</h3>${ties.map(t => { const ok = t.home.code && t.away.code; return `<div class="row" style="margin:5px 0;padding:4px 0;border-top:1px solid var(--line)"><span class="mut small" style="min-width:140px">${esc(t.round)} #${t.n}</span><span style="min-width:190px">${label(t.home)}</span>
        ${ok ? `<input type="number" min="0" max="250" data-hs="${esc(t.id)}" value="${t.home_score ?? ''}" style="width:70px"><b>–</b><input type="number" min="0" max="250" data-as="${esc(t.id)}" value="${t.away_score ?? ''}" style="width:70px">` : '<span class="mut small" style="width:170px">waiting for the previous round</span>'}
        <span style="min-width:190px">${label(t.away)}</span>${ok ? `<input type="date" data-td="${esc(t.id)}" value="${esc(t.date || '')}"><button data-ts="${esc(t.id)}">Save</button>` : ''}${t.winner ? `<span class="pill w">→ ${esc(t.winner)}</span>` : ''}</div>`; }).join('') || '<span class="mut small">Draw the first round first.</span>'}</div>`;
    const run = async fn => { const r = await fn(); if (r) cupData = r; paintCup(); };
    $('#csavetitle').onclick = () => run(() => post('cup', { op: 'title', name: $('#cname').value, season: $('#cseason').value }));
    $('#cxadd').onclick = () => run(async () => { const r = await post('cup', { op: 'team', code: $('#cxcode').value, name: $('#cxname').value, league: 'other' }); return r; });
    $('#cdrawgo').onclick = () => run(() => post('cup', { op: 'draw', text: $('#cdraw').value, round_name: $('#cround').value }));
    $('#creset').onclick = () => { if (confirm('Empty the whole bracket (draw and results)?')) run(() => post('cup', { op: 'reset' })); };
    box.querySelectorAll('[data-rsave]').forEach(b => b.onclick = () => run(() => post('cup', { op: 'round', key: b.dataset.rsave, date: box.querySelector(`[data-rdate="${b.dataset.rsave}"]`).value })));
    box.querySelectorAll('[data-ts]').forEach(b => b.onclick = () => { const id = b.dataset.ts; run(() => post('cup', { op: 'result', tie: id, home_score: box.querySelector(`[data-hs="${id}"]`).value, away_score: box.querySelector(`[data-as="${id}"]`).value, date: box.querySelector(`[data-td="${id}"]`).value })); });
  }
  window.loadCup = async function () { const box = $('#cupbox'); if (!box) return; try { cupData = (await api('cup')).body; paintCup(); } catch (e) { box.innerHTML = `<div class="problems">${esc(e.message)}</div>`; } };

  // ------------------------------------------------------------------ play-off / play-out
  let finData = null;
  function paintFinals() {
    const box = $('#finbox'); if (!box) return;
    const d = finData, G = { playoff: '🔥 Play-off', super: '⚡ Super play-off', playout: '🛟 Play-out' }, GS = ['playoff', 'super', 'playout'];
    box.innerHTML = `
      <p class="mut small" style="margin:6px 0 10px">After the regular season the six best clubs play the play-off (a mini-league), the first four of it go to the <b>super play-off</b> (1 v 4, 2 v 3, then the final, each a best of five), the six others play the play-out (a mini-league, the last two go down). This is the announced format, not yet confirmed for 2026-27: each group can be changed, it is either a <b>league</b> (a table, the six clubs play each other; the regular-season points can be carried over) or a <b>series</b> bracket (best-of-3/5/7). Type the games as lines; the site draws the rest. Page “Play-off · Play-out” of the Standings menu.</p>
      ${note()}${d.demo ? '<div class="warns">The content below is DEMONSTRATION data: empty both groups before the real thing.</div>' : ''}
      <div class="card" style="border-color:${d.announced ? 'var(--good)' : 'var(--acc)'}"><h3 style="margin-top:0">📣 Announcement</h3>
        <p class="mut small" style="margin:6px 0">${d.announced ? '<b>Announced.</b> The public site shows the Play-off · Play-out page INSTEAD of the championship standings (the regular season stays under its “Regular season” tab).' : '<b>Not announced.</b> Nothing changes on the public site (the championship standings stay, no Play-off tab) however much you type here. Prepare everything, then announce when the first game of the play-off or the play-out is announced.'}</p>
        <div class="row"><button id="fann" class="${d.announced ? 'danger' : 'primary'}">${d.announced ? 'Withdraw the announcement' : 'Announce: the play-off and the play-out start'}</button><a href="/playoff-playout?preview=1" target="_blank" rel="noopener">Preview the page (only you see it)</a></div></div>
      <div class="card" style="margin-top:12px"><h3 style="margin-top:0">Settings</h3><div class="row"><label class="small mut">Season</label><input id="fseason" value="${esc(d.season)}" size="10" placeholder="2026-2027">
        <label class="small mut">Regular-season points carried over</label><select id="fcarry">${['none', 'half', 'full'].map(c => `<option value="${c}" ${d.carry === c ? 'selected' : ''}>${c}</option>`).join('')}</select>
        <label class="small mut">Go to the super play-off</label><input id="fqual" type="number" min="1" max="6" value="${d.qualify}" style="width:52px"><label class="small mut">Relegated</label><input id="frel" type="number" min="0" max="6" value="${d.relegation}" style="width:52px">
        <label class="small"><input type="checkbox" id="fprev" ${d.preview ? 'checked' : ''}> preview: until the teams are typed, the groups are the table as it stands</label></div>
        <div class="row" style="margin-top:8px">${GS.map(g => `<label class="small mut">${G[g]}</label><select data-fmt="${g}">${['league', 'series'].map(f => `<option value="${f}" ${d.groups[g].format === f ? 'selected' : ''}>${f}</option>`).join('')}</select><input data-stake="${g}" value="${esc(d.groups[g].stakes)}" placeholder="what is at stake (shown under the title)" style="flex:1;min-width:180px">`).join('')}</div>
        <div class="row" style="margin-top:8px"><button class="primary" id="fsave">Save the settings</button><button id="fauto">Groups = the table as it stands (6 + 6)</button><button id="fscaf">Set up the super play-off (1 v 4, 2 v 3, final)</button></div></div>
      ${GS.map(g => { const x = d.groups[g]; return `<div class="card" style="margin-top:12px"><h3 style="margin-top:0">${G[g]} <span class="mut small">· ${x.format} · ${x.teams.length} clubs: ${x.teams.map(t => esc(t.code)).join(' ')}</span></h3>
        ${g === 'super' ? '<div class="mut small">The clubs are the first of the play-off: write sides as <code>S:playoff:1</code> (1st of the play-off) or <code>W:id</code>.</div>' : `<div class="row"><input data-teams="${g}" placeholder="Clubs (codes), e.g. CA USM JSK ESS DSG CSS" style="flex:1;min-width:240px"><button data-teamsgo="${g}">Set the clubs</button></div>`}
        <textarea data-text="${g}" rows="6" style="width:100%;margin-top:8px" placeholder="${x.format === 'league' ? 'round, HOME, AWAY, home score, away score, date&#10;3, CA, USM' : 'SERIES, qf1, Quarter-finals, JSK, CSS, 3&#10;SERIES, sf1, Semi-finals, CA, W:qf1, 5&#10;GAME, qf1, JSK, 81, 74, 2027-04-24'}"></textarea>
        <div class="mut small" style="margin:4px 0">${x.format === 'league' ? 'League games, one per line: <code>round, HOME, AWAY[, home score, away score[, date]]</code> (no score = still to play).' : 'Series: <code>SERIES, id, round name, A, B, best of</code> (A, B: a club code or <code>W:id</code>, the winner of another series), then games: <code>GAME, id, HOME, home score, away score[, date]</code>. The games of a series written again replace its games.'}</div>
        <div class="row"><button class="primary" data-textgo="${g}">Save these lines</button><button class="danger" data-clear="${g}">Empty this group</button></div></div>`; }).join('')}`;
    const run = async (p) => { const r = await p; if (r) finData = r; paintFinals(); };
    $('#fsave').onclick = () => { const stakes = {}, formats = {}; box.querySelectorAll('[data-stake]').forEach(i => { stakes[i.dataset.stake] = i.value; }); box.querySelectorAll('[data-fmt]').forEach(i => { formats[i.dataset.fmt] = i.value; });
      run(post('finals', { op: 'config', season: $('#fseason').value, carry: $('#fcarry').value, preview: $('#fprev').checked, qualify: +$('#fqual').value, relegation: +$('#frel').value, stakes, formats })); };
    $('#fscaf').onclick = () => run(post('finals', { op: 'super_scaffold' }));
    $('#fann').onclick = () => { if (confirm(d.announced ? 'Withdraw the announcement? The championship standings come back.' : 'Announce the play-off and the play-out? The site will show them instead of the championship standings.')) run(post('finals', { op: 'announce', on: !d.announced })); };
    $('#fauto').onclick = () => run(post('finals', { op: 'auto_teams' }));
    box.querySelectorAll('[data-teamsgo]').forEach(b => b.onclick = () => run(post('finals', { op: 'teams', group: b.dataset.teamsgo, text: box.querySelector(`[data-teams="${b.dataset.teamsgo}"]`).value })));
    box.querySelectorAll('[data-textgo]').forEach(b => b.onclick = () => { const g = b.dataset.textgo; run(post('finals', { op: d.groups[g].format === 'league' ? 'league_games' : 'series', group: g, text: box.querySelector(`[data-text="${g}"]`).value })); });
    box.querySelectorAll('[data-clear]').forEach(b => b.onclick = () => { if (confirm('Empty this group (clubs, games, series)?')) run(post('finals', { op: 'clear', group: b.dataset.clear })); });
  }
  window.loadFinals = async function () { const box = $('#finbox'); if (!box) return; try { finData = (await api('finals')).body; paintFinals(); } catch (e) { box.innerHTML = `<div class="problems">${esc(e.message)}</div>`; } };
})();
