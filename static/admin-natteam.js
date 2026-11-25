// Admin: the Tunisian national team (natteam.py, data/national_team.json). Four cards: the called-up players ("convoqués": the list changes for every window), the players who do not play in
// the Tunisian league (they get a small page of their own), the games (the results and the next game of the national team page) and the competitions.
// What is saved wins over the list that ships with the code (assets/national_team.json). Uses the helpers of admin.html ($, esc, api).
(function () {
  let S = null, msg = null, list = null, matches = null, editExt = null, editGame = null, boxFor = null, boxText = '', boxLines = null, statComp = null, statText = '', statLines = null;
  const J = { 'Content-Type': 'application/json' };
  const say = (t, ok = true) => { msg = t ? { t, ok } : null; };
  const today = () => new Date(Date.now() + 3600e3).toISOString().slice(0, 10);

  async function send(body) {
    try {
      const { ok, body: r } = await api('national-team', { method: 'POST', headers: J, body: JSON.stringify(body) });
      say(ok ? r.message : (r.error || 'Could not save.'), ok);
      if (ok) { S = r; document.dispatchEvent(new Event('natteam:changed')); }
      return ok ? r : null;
    } catch (e) { say(e.message, false); return null; }
  }
  async function load() {
    const { ok, body } = await api('national-team');
    if (!ok) { $('#ntbox').innerHTML = '<div class="problems">Could not load the national team.</div>'; return; }
    S = body; if (!list) list = S.view.callup.players.map(p => p.pid);
    render();
  }
  const pname = id => { const p = S.players.find(x => x.id === id), e = S.externals[id]; return p ? `${p.name} (${p.team} #${p.number})` : e ? `${e.name} (outside the league)` : id; };
  const compName = id => { const c = S.competitions.find(x => x.id === id); return c ? c.en : id; };
  const dirty = () => JSON.stringify(list) !== JSON.stringify(S.view.callup.players.map(p => p.pid));

  function callupCard() {
    const c = S.view.callup, inList = new Set(list);
    return `<div class="card"><h3 style="margin-top:0">Called-up players <span class="mut small">${S.admin.callup ? 'your list is shown on the site' : 'the list that ships with the code is shown'}</span></h3>
      <div class="row"><label class="small mut">Label (English)</label><input id="nt-label" value="${esc(c.label)}" style="min-width:230px" placeholder="e.g. AfroBasket 2027 qualifiers · February window">
        <label class="small mut">French</label><input id="nt-labelfr" value="${esc(c.label_fr)}" style="min-width:230px"><label class="small mut">Announced</label><input id="nt-date" type="date" value="${esc(c.date || '')}"></div>
      <table style="margin-top:8px"><tbody>${list.map((id, i) => `<tr><td class="mut">${i + 1}</td><td class="l"><b>${esc(pname(id))}</b></td>
        <td style="white-space:nowrap"><button data-up="${i}" ${i ? '' : 'disabled'}>↑</button> <button data-down="${i}" ${i < list.length - 1 ? '' : 'disabled'}>↓</button> <button data-rm="${i}" class="danger">Remove</button></td></tr>`).join('') || '<tr><td class="mut">Nobody yet.</td></tr>'}</tbody></table>
      <div class="row" style="margin-top:10px"><select id="nt-add"><option value="">Add a player of the league…</option>${S.players.filter(p => !inList.has(p.id)).map(p => `<option value="${esc(p.id)}">${esc(p.team)} #${p.number} · ${esc(p.name)}</option>`).join('')}</select>
        <select id="nt-addext"><option value="">…or a player outside the league</option>${Object.entries(S.externals).filter(([k]) => !inList.has(k)).map(([k, e]) => `<option value="${esc(k)}">${esc(e.name)}</option>`).join('')}</select></div>
      <details style="margin-top:10px" ${matches ? 'open' : ''}><summary class="small mut">Paste the names of the squad (one per line): the site finds the players</summary>
        <textarea id="nt-names" rows="6" style="width:100%;margin-top:6px" placeholder="Omar Abada&#10;Firas Lahiani&#10;Yacine Toumi">${matches ? esc(matches.text) : ''}</textarea>
        <div class="row" style="margin-top:6px"><button id="nt-match">Find the players</button><span class="mut small">Spelling may differ (Lahiani / Lahyani): the uncertain matches are marked, check them.</span></div>
        ${matches ? `<table style="margin-top:8px"><tbody>${matches.rows.map((r, i) => `<tr class="${r.uncertain ? 'saved' : ''}"><td class="l">${esc(r.input)}</td><td class="l">${r.pid ? `<select data-mrow="${i}"><option value="${esc(r.pid)}">${esc(r.name)} ${r.team ? '(' + esc(r.team) + ')' : '(outside the league)'}</option>${r.others.map(o => `<option value="${esc(o.pid)}">${esc(o.name)}</option>`).join('')}<option value="">— none, skip —</option></select>` : '<span class="mut">no player found: add him below (outside the league) then match again</span>'}</td>
          <td>${r.uncertain ? '<span class="pill warn">check</span>' : '<span class="pill ok">sure</span>'}</td></tr>`).join('')}</tbody></table>
          <div class="row" style="margin-top:6px"><button id="nt-useall" class="primary">Use these players as the list</button></div>` : ''}</details>
      <div class="row" style="margin-top:12px"><button class="primary" id="nt-save">Save the list</button>${S.admin.callup ? '<button id="nt-reset">Back to the shipped list</button>' : ''}<span class="mut small">${dirty() ? 'Not saved yet.' : ''}</span></div>
      <p class="mut small" style="margin-bottom:0">Every player of the list gets a small flag label on the site (profile, tables, box scores), and the list is on the national team page and in the Images tab (convocation picture).</p></div>`;
  }

  function extCard() {
    const e = editExt, cur = e && e.key ? S.externals[e.key] : null;
    return `<div class="card"><h3 style="margin-top:0">Players outside the Tunisian league</h3>
      ${Object.entries(S.externals).map(([k, x]) => `<div class="row" style="margin-top:4px"><b>${esc(x.name)}</b><span class="mut small">${esc([x.club, x.birth, x.height && x.height + ' cm', (x.nationality || []).join('/')].filter(Boolean).join(' · '))}</span><span class="sp"></span><a href="/en/national-team/${esc(k)}" target="_blank" class="small">page</a><button data-extedit="${esc(k)}">Edit</button><button data-extdel="${esc(k)}" class="danger">Delete</button></div>`).join('') || '<div class="mut small">None.</div>'}
      ${e ? `<div class="card" style="border-color:var(--acc);margin-top:10px"><b>${cur ? 'Edit ' + esc(cur.name) : 'New player'}</b>
        <div class="row" style="margin-top:6px"><input id="x-name" placeholder="Full name" value="${esc(cur ? cur.name : '')}" style="min-width:220px"><input id="x-birth" type="date" title="Birth date" value="${esc(cur ? cur.birth || '' : '')}"><input id="x-height" class="num" placeholder="cm" value="${esc(cur ? cur.height || '' : '')}">
          <input id="x-pos" placeholder="Position (PG, SF…)" style="width:130px" value="${esc(cur ? cur.position || '' : '')}"><input id="x-club" placeholder="Club" value="${esc(cur ? cur.club || '' : '')}"><input id="x-nat" placeholder="Nationality codes: TN, FR" style="width:150px" value="${esc(cur ? (cur.nationality || []).join(', ') : '')}"></div>
        <div class="row" style="margin-top:6px"><textarea id="x-noteen" rows="2" placeholder="What is known about him (English)" style="flex:1;min-width:240px">${esc(cur ? cur.note_en || '' : '')}</textarea><textarea id="x-notefr" rows="2" placeholder="Français" style="flex:1;min-width:240px">${esc(cur ? cur.note_fr || '' : '')}</textarea></div>
        <div class="row" style="margin-top:6px"><input id="x-src" placeholder="Source (a link, e.g. his FIBA profile)" style="flex:1;min-width:240px" value="${esc(cur ? cur.src || '' : '')}"></div>
        <div class="row" style="margin-top:8px"><button class="primary" id="x-save">Save</button><button id="x-no">Cancel</button></div></div>`
      : '<div class="row" style="margin-top:10px"><button id="x-new">➕ Add a player outside the league</button></div>'}</div>`;
  }

  const dflt = () => ({ competition: S.competitions[0].id, date: today(), time: '', opp_name: '', site: 'home', venue: 'Radès', round: '', tun: '', opp_score: '', ot: 0 });
  function gameCard() {
    const g = editGame, games = [...S.games].sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    return `<div class="card"><h3 style="margin-top:0">Games</h3>
      ${g ? `<div class="card" style="border-color:var(--acc);margin-bottom:10px"><b>${g.id ? 'Edit the game' : 'New game'}</b>
        <div class="row" style="margin-top:6px"><select id="g-comp">${S.competitions.map(c => `<option value="${esc(c.id)}" ${c.id === g.competition ? 'selected' : ''}>${esc(c.en)}</option>`).join('')}</select>
          <input id="g-round" placeholder="Round / group (optional)" value="${esc(g.round || '')}" style="min-width:180px"></div>
        <div class="row" style="margin-top:6px"><label class="small mut">Date</label><input id="g-date" type="date" value="${esc(g.date)}"><label class="small mut">Time</label><input id="g-time" placeholder="18:30" style="width:70px" value="${esc(g.time || '')}">
          <label class="small mut">Opponent</label><input id="g-opp" list="g-opps" placeholder="Nigeria" value="${esc(g.opp_name || '')}"><datalist id="g-opps">${S.countries.map(c => `<option value="${esc(c.name)}">`).join('')}</datalist>
          <select id="g-site"><option value="home" ${g.site === 'home' ? 'selected' : ''}>Home</option><option value="away" ${g.site === 'away' ? 'selected' : ''}>Away</option><option value="neutral" ${g.site === 'neutral' ? 'selected' : ''}>Neutral ground</option></select>
          <input id="g-venue" placeholder="Venue / city" value="${esc(g.venue || '')}"></div>
        <div class="row" style="margin-top:6px"><label class="small mut">Tunisia</label><input id="g-tun" class="num" type="number" min="0" value="${g.tun ?? ''}"><label class="small mut">Opponent</label><input id="g-os" class="num" type="number" min="0" value="${g.opp_score ?? ''}">
          <label class="small mut">Overtimes</label><input id="g-ot" class="num" type="number" min="0" max="6" value="${g.ot || 0}" style="width:60px"><span class="mut small">leave the scores empty while the game is to come: it is shown as the next game</span></div>
        ${g.check ? '<label class="small mut row" style="margin-top:6px"><input type="checkbox" id="g-conf"> I checked this game: remove the “?” mark</label>' : ''}
        <div class="row" style="margin-top:8px"><button class="primary" id="g-save">Save the game</button><button id="g-no">Cancel</button><span class="small" id="g-err" style="color:var(--bad)"></span></div></div>` : '<div class="row"><button class="primary" id="g-new">➕ Add a game</button></div>'}
      <table style="margin-top:8px"><thead><tr><th class="l">Date</th><th class="l">Game</th><th>Score</th><th class="l">Competition</th><th></th></tr></thead><tbody>
      ${games.map(x => `<tr><td class="l">${esc(x.date)}${x.time ? ' ' + esc(x.time) : ''}</td><td class="l">${x.site === 'away' ? esc(x.opp_name) + ' – Tunisia' : 'Tunisia – ' + esc(x.opp_name)} <span class="mut small">${esc(x.site)}</span>${x.check ? ' <span class="pill warn" title="Not confirmed by a second source">?</span>' : ''}</td>
        <td>${x.tun != null ? `<b>${x.tun}–${x.opp_score}</b>${x.ot ? ' OT' : ''}` : '<span class="mut">to come</span>'}</td><td class="l mut small">${esc(compName(x.competition))}${x.round ? ' · ' + esc(x.round) : ''}</td>
        <td style="white-space:nowrap">${x.tun != null ? `<button data-gbox="${esc(x.id)}" title="Paste the box score">${(x.box || []).length ? '📊 ' + x.box.length : '📊'}</button> ` : ''}<button data-gedit="${esc(x.id)}">Edit</button> <button data-gdel="${esc(x.id)}" class="danger">Delete</button></td></tr>`).join('') || '<tr><td colspan="5" class="mut">No game yet.</td></tr>'}</tbody></table></div>`;
  }


  // A pasted table (box score or per-game statistics) after the server matched the names: one row per line, a player to choose, the numbers editable.
  const FIELDS = { box: ['min', 'pts', 'reb', 'ast', 'stl', 'blk', 'tov', 'pf'], stats: ['g', 'min', 'pts', 'reb', 'ast', 'eff'] };
  function previewTable(lines, kind) {
    return `<table style="margin-top:8px"><thead><tr><th class="l">Pasted</th><th class="l">Player</th>${FIELDS[kind].map(f => `<th>${f.toUpperCase()}</th>`).join('')}<th></th></tr></thead><tbody>
      ${lines.map((r, i) => `<tr data-pv="${i}" class="${r.uncertain ? 'saved' : ''}"><td class="l">${esc(r.input)}</td><td class="l"><select data-f="pid"><option value="${esc(r.pid || '')}">${r.pid ? esc(r.name) + (r.team ? ' (' + esc(r.team) + ')' : ' (outside the league)') : '— nobody (' + (kind === 'box' ? 'kept by name' : 'skipped') + ') —'}</option>
        ${(r.others || []).map(o => `<option value="${esc(o.pid)}">${esc(o.name)}</option>`).join('')}${r.pid ? `<option value="">— nobody —</option>` : ''}</select></td>
        ${FIELDS[kind].map(f => `<td><input data-f="${f}" class="num" style="width:56px" value="${r.values[f] ?? ''}"></td>`).join('')}<td>${r.uncertain ? '<span class="pill warn">check</span>' : '<span class="pill ok">sure</span>'}</td></tr>`).join('')}</tbody></table>`;
  }
  const readPreview = (kind, lines) => [...document.querySelectorAll(`#${kind}-pv tr[data-pv]`)].map(tr => {
    const o = { pid: tr.querySelector('[data-f=pid]').value || null, name: lines[+tr.dataset.pv].input };
    FIELDS[kind].forEach(f => { const v = tr.querySelector(`[data-f=${f}]`).value.trim(); if (v !== '') o[f] = v.replace(',', '.'); });
    return o;
  });

  function boxCard() {
    const g = S.games.find(x => x.id === boxFor); if (!g) return '';
    return `<div class="card" style="border-color:var(--acc)"><h3 style="margin-top:0">Box score · ${g.site === 'away' ? esc(g.opp_name) + ' – Tunisia' : 'Tunisia – ' + esc(g.opp_name)} ${g.tun}–${g.opp_score} <span class="mut small">${esc(g.date)}</span></h3>
      ${(g.box || []).length ? `<table><thead><tr><th class="l">Player</th>${FIELDS.box.map(f => `<th>${f.toUpperCase()}</th>`).join('')}</tr></thead><tbody>${g.box.map(l => `<tr><td class="l">${esc(l.pid ? pname(l.pid) : l.name + ' (not matched)')}</td>${FIELDS.box.map(f => `<td>${l[f] ?? ''}</td>`).join('')}</tr>`).join('')}</tbody></table>
        <div class="row" style="margin-top:6px"><button data-boxclear class="danger">Remove this box score</button></div>` : '<div class="mut small">No box score yet.</div>'}
      <p class="small mut" style="margin-bottom:4px">Paste the lines of Tunisia's players, from a spreadsheet, a CSV or typed: <b>name, MIN, PTS, REB, AST, STL, BLK, TO, PF</b> (a first line with the column names works too, in any order; minutes like 24:30 are fine).</p>
      <textarea id="box-text" rows="7" style="width:100%" placeholder="Player;MIN;PTS;REB;AST&#10;Omar Abada;33:20;26;4;6">${esc(boxText)}</textarea>
      <div class="row" style="margin-top:6px"><button id="box-read">Read the lines</button><button id="box-close">Close</button></div>
      ${boxLines ? `<div id="box-pv">${previewTable(boxLines, 'box')}</div><div class="row" style="margin-top:8px"><button class="primary" id="box-save">Save this box score</button><span class="mut small">It replaces the one above. The statistics of the players are computed from the box scores of a competition as soon as they cover his games.</span></div>` : ''}</div>`;
  }

  function statsCard() {
    const comp = statComp || S.competitions[0].id, has = S.admin.stats.includes(comp);
    return `<div class="card"><h3 style="margin-top:0">Per-game statistics without box scores</h3>
      <p class="small mut" style="margin-top:0">For a competition whose box scores you do not have: paste a table <b>name, G, MIN, PTS, REB, AST, EFF</b> (per game; MIN and EFF are optional). It replaces the numbers that ship with the code for that competition. Box scores take over player by player once they cover as many games.</p>
      <div class="row"><select id="st-comp">${S.competitions.map(c => `<option value="${esc(c.id)}" ${c.id === comp ? 'selected' : ''}>${esc(c.en)}</option>`).join('')}</select>${has ? '<span class="pill ok">your table is shown</span><button id="st-clear">Back to the shipped numbers</button>' : '<span class="mut small">the numbers that ship with the code are shown (if any)</span>'}</div>
      <textarea id="st-text" rows="6" style="width:100%;margin-top:6px" placeholder="Omar Abada 7 33 18.1 4.3 5.7">${esc(statText)}</textarea>
      <div class="row" style="margin-top:6px"><button id="st-read">Read the lines</button></div>
      ${statLines ? `<div id="stats-pv">${previewTable(statLines, 'stats')}</div><div class="row" style="margin-top:8px"><button class="primary" id="st-save">Save these statistics</button></div>` : ''}</div>`;
  }

  function compCard() {
    return `<div class="card"><h3 style="margin-top:0">Competitions</h3>
      <div class="mut small">${S.competitions.map(c => `<span class="pill">${esc(c.en)}${c.admin ? ` <a href="#" data-cdel="${esc(c.id)}" title="Remove (only when no game uses it)">✕</a>` : ''}</span>`).join(' ')}</div>
      <div class="row" style="margin-top:8px"><input id="c-en" placeholder="New competition (English), e.g. AfroBasket 2029 qualifiers" style="min-width:300px"><input id="c-fr" placeholder="Français (optional)" style="min-width:240px"><button id="c-add">Add</button></div></div>`;
  }

  function render() {
    if (!S) return load();
    $('#ntbox').innerHTML = `${msg ? `<div class="${msg.ok ? 'okbox' : 'problems'}">${esc(msg.t)}</div>` : ''}<div style="display:grid;gap:12px">${callupCard()}${gameCard()}${boxFor ? boxCard() : ''}${statsCard()}${extCard()}${compCard()}</div>`;
    wire();
  }

  function wire() {
    const rerender = () => { list = list || []; render(); };
    document.querySelectorAll('[data-up]').forEach(b => b.onclick = () => { const i = +b.dataset.up; [list[i - 1], list[i]] = [list[i], list[i - 1]]; rerender(); });
    document.querySelectorAll('[data-down]').forEach(b => b.onclick = () => { const i = +b.dataset.down; [list[i + 1], list[i]] = [list[i], list[i + 1]]; rerender(); });
    document.querySelectorAll('[data-rm]').forEach(b => b.onclick = () => { list.splice(+b.dataset.rm, 1); rerender(); });
    for (const id of ['nt-add', 'nt-addext']) $('#' + id).onchange = e => { if (e.target.value) list.push(e.target.value); rerender(); };
    $('#nt-match').onclick = async () => {
      const text = $('#nt-names').value, r = await send({ op: 'callup_names', text });
      if (r) matches = { text, rows: r.matches };
      render();
    };
    if ($('#nt-useall')) $('#nt-useall').onclick = () => {
      const ids = [...document.querySelectorAll('[data-mrow]')].map(s => s.value).filter(Boolean);
      list = [...new Set(ids)]; matches = null; say('The list below holds these players: check it, then save.', true); render();
    };
    $('#nt-save').onclick = async () => {
      const r = await send({ op: 'callup', ids: list, label: $('#nt-label').value, label_fr: $('#nt-labelfr').value, date: $('#nt-date').value });
      if (r) list = S.view.callup.players.map(p => p.pid);
      render();
    };
    if ($('#nt-reset')) $('#nt-reset').onclick = async () => { if (confirm('Go back to the list that ships with the code?') && await send({ op: 'callup_reset' })) list = S.view.callup.players.map(p => p.pid); render(); };
    // players outside the league
    if ($('#x-new')) $('#x-new').onclick = () => { editExt = {}; render(); };
    document.querySelectorAll('[data-extedit]').forEach(b => b.onclick = () => { editExt = { key: b.dataset.extedit }; render(); });
    document.querySelectorAll('[data-extdel]').forEach(b => b.onclick = async () => {
      if (confirm('Delete this player? He is taken out of the list of called-up players too.') && await send({ op: 'external_delete', key: b.dataset.extdel })) list = S.view.callup.players.map(p => p.pid);
      render();
    });
    if ($('#x-no')) $('#x-no').onclick = () => { editExt = null; render(); };
    if ($('#x-save')) $('#x-save').onclick = async () => {
      const r = await send({ op: 'external', key: editExt.key, name: $('#x-name').value, birth: $('#x-birth').value, height: $('#x-height').value, position: $('#x-pos').value, club: $('#x-club').value,
        nationality: $('#x-nat').value, note_en: $('#x-noteen').value, note_fr: $('#x-notefr').value, src: $('#x-src').value });
      if (r) editExt = null; render();
    };
    // games
    if ($('#g-new')) $('#g-new').onclick = () => { editGame = dflt(); render(); };
    document.querySelectorAll('[data-gedit]').forEach(b => b.onclick = () => { const g = S.games.find(x => x.id === b.dataset.gedit); editGame = { ...g, opp_name: g.opp_name }; render(); $('#g-comp').scrollIntoView({ block: 'center' }); });
    document.querySelectorAll('[data-gdel]').forEach(b => b.onclick = async () => { if (confirm('Delete this game?')) await send({ op: 'game_delete', id: b.dataset.gdel }); render(); });
    if ($('#g-no')) $('#g-no').onclick = () => { editGame = null; render(); };
    if ($('#g-save')) $('#g-save').onclick = async () => {
      const body = { op: 'game', id: editGame.id || '', competition: $('#g-comp').value, round: $('#g-round').value, date: $('#g-date').value, time: $('#g-time').value, opp_name: $('#g-opp').value, site: $('#g-site').value, venue: $('#g-venue').value,
        tun: $('#g-tun').value, opp_score: $('#g-os').value, ot: $('#g-ot').value, confirmed: !!($('#g-conf') && $('#g-conf').checked) };
      const r = await send(body);
      if (r) editGame = null; render();
    };
    // box scores and statistics
    document.querySelectorAll('[data-gbox]').forEach(b => b.onclick = () => { boxFor = b.dataset.gbox; boxText = ''; boxLines = null; render(); $('#box-text').scrollIntoView({ block: 'center' }); });
    if ($('#box-close')) $('#box-close').onclick = () => { boxFor = null; boxLines = null; render(); };
    if ($('#box-read')) $('#box-read').onclick = async () => { boxText = $('#box-text').value; const r = await send({ op: 'box_preview', text: boxText }); boxLines = r ? r.lines : null; render(); };
    if ($('#box-save')) $('#box-save').onclick = async () => { const r = await send({ op: 'box_save', id: boxFor, lines: readPreview('box', boxLines) }); if (r) { boxLines = null; boxText = ''; } render(); };
    if ($('[data-boxclear]')) $('[data-boxclear]').onclick = async () => { if (confirm('Remove this box score?')) await send({ op: 'box_clear', id: boxFor }); render(); };
    $('#st-comp').onchange = e => { statComp = e.target.value; statLines = null; render(); };
    $('#st-read').onclick = async () => { statText = $('#st-text').value; const r = await send({ op: 'stats_preview', text: statText }); statLines = r ? r.lines : null; render(); };
    if ($('#st-save')) $('#st-save').onclick = async () => { const r = await send({ op: 'stats_save', competition: $('#st-comp').value, rows: readPreview('stats', statLines).filter(x => x.pid) }); if (r) { statLines = null; statText = ''; } render(); };
    if ($('#st-clear')) $('#st-clear').onclick = async () => { if (confirm('Go back to the statistics that ship with the code?')) await send({ op: 'stats_clear', competition: $('#st-comp').value }); render(); };
    // competitions
    $('#c-add').onclick = async () => { await send({ op: 'competition', en: $('#c-en').value, fr: $('#c-fr').value }); render(); };
    document.querySelectorAll('[data-cdel]').forEach(a => a.onclick = async e => { e.preventDefault(); if (confirm('Remove this competition?')) await send({ op: 'competition_delete', id: a.dataset.cdel }); render(); });
  }

  window.loadNatTeam = () => { S = null; list = null; load(); };
})();
