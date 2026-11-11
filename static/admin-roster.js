// Admin: players and rosters. Edit height / weight / birth date, rename, add a player, delete (hide) a player, mark a transfer.
// Uses the helpers of admin.html ($, esc, api). Everything is saved on the server (data/roster.json, data/players_info.json).
(function () {
  let R = null, A = {}, team = '', query = '', showHidden = false, msg = null;      // A: players marked as not playing {id: {note, since}}
  const today = () => new Date().toISOString().slice(0, 10);
  const age = b => b ? Math.floor((Date.now() - new Date(b + 'T12:00')) / 31557600000) : '';
  const hv = b => !b || !b.height ? '' : Array.isArray(b.height) ? b.height.join('-') : String(b.height);
  const approx = (b, k) => b && (b.approx || []).includes(k) ? ' title="Estimated value: typing a new one makes it official"' : '';
  const say = (t, ok = true) => { msg = t ? { t, ok } : null; };

  async function post(body) {
    try {
      const { ok, body: r } = await api('roster', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      say(ok ? 'Saved.' : (r.error || 'Could not save.'), ok);
      if (ok) R = null;
      return ok;
    } catch (e) { say(e.message, false); return false; }
  }

  async function absent(id, on, note) {
    try {
      const { ok, body: r } = await api('absences', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, absent: on, note }) });
      say(ok ? (on ? 'Marked as not playing: left out of the expected starting five.' : 'Back in the squad.') : (r.error || 'Could not save.'), ok);
      return ok;
    } catch (e) { say(e.message, false); return false; }
  }

  async function load() {
    const { ok, body } = await api('roster');
    if (!ok) { $('#rosterbox').innerHTML = '<div class="problems">Could not load the roster.</div>'; return; }
    R = body;
    try { A = (await api('absences')).body.absences || {}; } catch (e) { A = {}; }
    if (!team) team = Object.keys(R.teams).sort()[0];
    render();
  }

  // Photo: pick a file, crop a square (centred, a little above the middle to keep the face), 320 px JPEG, upload.
  function pickPhoto(id) {
    const inp = document.createElement('input');
    inp.type = 'file'; inp.accept = 'image/*';
    inp.onchange = async () => {
      const file = inp.files[0]; if (!file) return;
      try {
        const bmp = await createImageBitmap(file), side = Math.min(bmp.width, bmp.height), N = 320;
        const sx = (bmp.width - side) / 2, sy = (bmp.height - side) * 0.2;
        const c = document.createElement('canvas'); c.width = c.height = N;
        c.getContext('2d').drawImage(bmp, sx, sy, side, side, 0, 0, N, N);
        const blob = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.86));
        const fd = new FormData(); fd.append('id', id); fd.append('image', blob, id + '.jpg');
        const { ok, body } = await api('photo', { method: 'POST', body: fd });
        say(ok ? 'Photo saved.' : (body.error || 'Could not save the photo.'), ok);
      } catch (e) { say(e.message || 'That file is not a readable image.', false); }
      load();
    };
    inp.click();
  }

  function parseHeight(v) {
    v = String(v || '').trim();
    if (!v) return null;
    const p = v.split(/[-–]/).map(x => parseInt(x, 10)).filter(x => !isNaN(x));
    return p.length === 1 ? p[0] : p.length === 2 ? p : null;
  }

  function render() {
    if (!R) return load();
    const teams = R.teams, codes = Object.keys(teams).sort((a, b) => teams[a].localeCompare(teams[b]));
    const q = query.trim().toLowerCase();
    const rows = R.players.filter(p => (q ? p.name.toLowerCase().includes(q) : p.team === team) && (showHidden || !p.hidden));
    const opts = (sel, skip) => codes.filter(c => c !== skip).map(c => `<option value="${c}" ${c === sel ? 'selected' : ''}>${esc(teams[c])} (${c})</option>`).join('');
    $('#rosterbox').innerHTML = `
      ${msg ? `<div class="${msg.ok ? 'okbox' : 'problems'}">${esc(msg.t)}</div>` : ''}
      <div class="card" style="margin:12px 0"><b>🤕 Not playing</b> <span class="mut small">(injured, suspended…): left out of the <b>expected starting five</b> shown on the home page. Use the 🤕 button of a player below.</span>
        ${Object.keys(A).length ? Object.entries(A).map(([id, a]) => { const p = R.players.find(x => x.id === id); return `<div class="row" style="margin-top:6px"><b>${esc(p ? p.name : id)}</b> <span class="mut small">${esc(p ? p.team : '')}${a.note ? ' · ' + esc(a.note) : ''}${a.since ? ' · since ' + esc(a.since) : ''}</span><span class="sp"></span><button data-back="${esc(id)}">Back in the squad</button></div>`; }).join('') : '<div class="mut small" style="margin-top:6px">Nobody is marked as out.</div>'}</div>
      <div class="row" style="margin:12px 0">
        <select id="r-team" ${q ? 'disabled' : ''}>${opts(team)}</select>
        <input id="r-q" placeholder="Search any player…" value="${esc(query)}" style="min-width:200px">
        <label class="small mut"><input type="checkbox" id="r-hidden" ${showHidden ? 'checked' : ''}> show deleted</label>
        <span class="sp"></span><button class="primary" id="r-addbtn">➕ Add a player</button></div>
      <div class="card" style="padding:0;overflow-x:auto"><table id="r-table"><thead><tr><th>#</th><th>Photo</th><th class="l">Player</th><th>Position</th><th>GP</th><th>Height cm</th><th>Weight kg</th><th>Born</th><th>Age</th><th></th></tr></thead><tbody>
      ${rows.map(p => `<tr data-id="${esc(p.id)}" class="${p.hidden ? 'saved' : ''}"><td>${p.number}</td>
        <td style="white-space:nowrap"><img src="${esc(p.photo || '/img/players/generic.svg')}" alt="" width="34" height="34" style="border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:4px"><button data-act="photo" title="Upload a photo (square crop, JPEG)">📷</button>${p.photo && p.photo.startsWith('/photo/') ? ' <button data-act="nophoto" class="danger" title="Remove the uploaded photo">✕</button>' : ''}</td>
        <td class="l"><b>${esc(p.name)}</b> <span class="mut small">${p.team}</span>${p.added && !p.gp ? ' <span class="pill acc">new</span>' : ''}${p.hidden ? ' <span class="pill bad">deleted</span>' : ''}${A[p.id] ? ` <span class="pill bad" title="${esc(A[p.id].note || 'Not playing')}">🤕 out</span>` : ''}
          ${p.transfers.map(t => `<span class="pill warn" title="${esc(t.date || '')}">⇄ ${esc(t.from)}→${esc(t.to)}</span>`).join(' ')}</td>
        <td>${p.hidden ? esc(p.pos) : `<select data-f="pos" data-was="${esc(p.manual_pos || '')}" title="Guessed from the player’s stats. Pick another to correct it; pick the guessed one to go back."${p.manual_pos ? ' style="border-color:var(--acc)"' : ''}><option value="">${esc(p.auto_pos)} · guessed</option>${R.positions.map(x => `<option ${x === p.manual_pos ? 'selected' : ''}>${x}</option>`).join('')}</select>`}</td><td>${p.gp}</td>
        <td><input class="num" style="width:88px" data-f="height" value="${esc(hv(p.bio))}" placeholder="–"${approx(p.bio, 'height')}></td>
        <td><input class="num" style="width:72px" data-f="weight" value="${esc((p.bio && p.bio.weight) || '')}" placeholder="–"${approx(p.bio, 'weight')}></td>
        <td><input data-f="birth" type="date" value="${esc((p.bio && p.bio.birth) || '')}" style="width:140px"></td>
        <td class="mut">${age(p.bio && p.bio.birth)}</td>
        <td style="white-space:nowrap">${p.hidden ? `<button data-act="restore">↺ Restore</button>` :
          `<button data-act="save" hidden class="primary">Save</button> <button data-act="rename" title="Rename">✎</button> <button data-act="transfer" title="Mark a transfer">⇄</button> <button data-act="out" title="${A[p.id] ? 'Back in the squad' : 'Not playing (injured, suspended…): leave him out of the expected starting five'}"${A[p.id] ? ' class="primary"' : ''}>🤕</button> <button data-act="hide" class="danger" title="Delete from the site">🗑</button>`}</td></tr>`).join('')
        || '<tr><td colspan="10" class="mut" style="padding:14px">No players.</td></tr>'}
      </tbody></table></div>
      <p class="mut small">Photos: 📷 crops a centred square from the image you pick (crop it beforehand for exact framing) and shows it on the player page, the players list and the MVP race. Players without a photo show a silhouette. Only upload photos you have the right to publish.</p>
      <p class="mut small">Height accepts <b>190</b> or a range <b>189-192</b>. Values you type are official; empty fields clear the value. “Delete” hides a player from the site (rankings, leaders, MVP race, pages) but keeps the box scores, and can be undone with Restore.</p>
      <div id="r-forms"></div>
      <h3 class="sub">Transfers marked</h3>
      ${R.changes.transfers.length ? `<div class="card"><table><tbody>${R.changes.transfers.map((t, i) => { const p = R.players.find(x => x.id === t.id); return `<tr><td class="l"><b>${esc(p ? p.name : t.id)}</b></td><td>${esc(t.from)} → ${esc(t.to)} #${t.number}</td><td class="mut">${esc(t.date || '')}</td><td class="mut l">${esc(t.note || '')}</td><td><button data-undo="${i}" class="danger">Undo</button></td></tr>`; }).join('')}</tbody></table></div>` : '<div class="mut small">None yet.</div>'}`;
    wire();
  }

  function form(html) { $('#r-forms').innerHTML = `<div class="card" style="border-color:var(--acc)">${html}</div>`; $('#r-forms').scrollIntoView({ behavior: 'smooth', block: 'center' }); }

  function wire() {
    const teams = R.teams, codes = Object.keys(teams).sort((a, b) => teams[a].localeCompare(teams[b]));
    $('#r-team').onchange = e => { team = e.target.value; render(); };
    $('#r-q').oninput = e => { query = e.target.value; const pos = e.target.selectionStart; render(); const n = $('#r-q'); n.focus(); n.setSelectionRange(pos, pos); };
    $('#r-hidden').onchange = e => { showHidden = e.target.checked; render(); };
    document.querySelectorAll('#r-table tbody tr').forEach(tr => {
      const id = tr.dataset.id, p = R.players.find(x => x.id === id), btn = f => tr.querySelector(`[data-act=${f}]`);
      tr.querySelectorAll('input, select').forEach(i => i[i.tagName === 'SELECT' ? 'onchange' : 'oninput'] = () => { if (btn('save')) btn('save').hidden = false; });
      if (btn('save')) btn('save').onclick = async () => {
        const sel = tr.querySelector('[data-f=pos]'), posChanged = sel && sel.value !== sel.dataset.was;
        const bioInputs = ['height', 'weight', 'birth'].map(f => tr.querySelector(`[data-f=${f}]`)), bioChanged = bioInputs.some(i => i.value !== i.defaultValue);
        const h = parseHeight(tr.querySelector('[data-f=height]').value), w = tr.querySelector('[data-f=weight]').value.trim(), b = tr.querySelector('[data-f=birth]').value;
        if (bioChanged && tr.querySelector('[data-f=height]').value.trim() && h === null) { say('Height: type 190 or a range like 189-192.', false); return render(); }
        let ok = true;
        if (posChanged) {       // a correction of the guessed position (kept in data/positions.json; going back to the guessed one removes it)
          try { const r = await api('positions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ changes: { [id]: sel.value || null } }) }); ok = r.ok; say(ok ? 'Saved.' : (r.body.error || 'Could not save the position.'), ok); } catch (e) { ok = false; say(e.message, false); }
        }
        // the bio is only sent when one of its fields changed (sending it again would turn an estimated value into an official one)
        if (ok && bioChanged) ok = await post({ op: 'bio', id, height: h, weight: w ? parseInt(w, 10) : null, birth: b || null });
        R = null; if (ok) load(); else render();
      };
      if (btn('photo')) btn('photo').onclick = () => pickPhoto(id);
      if (btn('nophoto')) btn('nophoto').onclick = async () => {
        if (!confirm('Remove the uploaded photo of ' + p.name + '?')) return;
        try { const { ok } = await api('photo/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) }); say(ok ? 'Photo removed.' : 'Could not remove it.', ok); } catch (e) { say(e.message, false); }
        load();
      };
      if (btn('rename')) btn('rename').onclick = () => {
        form(`<b>Rename ${esc(p.name)}</b> <span class="mut small">(how the name is shown on the site)</span>
          <div class="row" style="margin-top:8px"><input id="f-name" value="${esc(p.name)}" style="min-width:260px"><button class="primary" id="f-go">Save name</button><button id="f-no">Cancel</button></div>`);
        $('#f-no').onclick = () => { $('#r-forms').innerHTML = ''; };
        $('#f-go').onclick = async () => { if (await post({ op: 'rename', id, name: $('#f-name').value })) load(); else render(); };
      };
      if (btn('hide')) btn('hide').onclick = async () => { if (confirm(`Delete ${p.name} (${p.team} #${p.number}) from the site?\n\nHe disappears from players, rankings and the MVP race. Box scores are kept and you can restore him later.`) && await post({ op: 'hide', id })) load(); };
      if (btn('out')) btn('out').onclick = async () => {
        if (A[id]) { if (await absent(id, false)) load(); return; }
        const note = prompt(`${p.name} (${p.team} #${p.number}) is not playing.\n\nOptional note (only you see it), e.g. knee injury:`, '');
        if (note !== null && await absent(id, true, note)) load();
      };
      if (btn('restore')) btn('restore').onclick = async () => { if (await post({ op: 'restore', id })) load(); };
      if (btn('transfer')) btn('transfer').onclick = () => {
        form(`<b>Transfer: ${esc(p.name)}</b> <span class="mut small">currently ${esc(p.team)} #${p.number}</span>
          <div class="row" style="margin-top:8px"><label class="small mut">To</label><select id="f-to">${codes.filter(c => c !== p.team).map(c => `<option value="${c}">${esc(teams[c])} (${c})</option>`).join('')}</select>
            <label class="small mut">New jersey #</label><input id="f-num" class="num" type="number" min="0" max="99" value="${p.number}">
            <label class="small mut">Date</label><input id="f-date" type="date" value="${today()}"></div>
          <div class="row" style="margin-top:8px"><input id="f-note" placeholder="Note (optional), e.g. loan, buy-out" style="flex:1;min-width:240px"></div>
          <label class="small mut row" style="margin-top:8px"><input type="checkbox" id="f-same"> He already has games under the new team’s number: merge them into this profile (same person)</label>
          <div class="row" style="margin-top:10px"><button class="primary" id="f-go">Mark the transfer</button><button id="f-no">Cancel</button></div>
          <p class="mut small" style="margin-bottom:0">The player keeps his history and profile; the site shows him in the new team. Box scores with the new team and number are linked to him automatically.</p>`);
        $('#f-no').onclick = () => $('#r-forms').innerHTML = '';
        $('#f-go').onclick = async () => { if (await post({ op: 'transfer', id, to: $('#f-to').value, number: +$('#f-num').value, date: $('#f-date').value, note: $('#f-note').value, same_person: $('#f-same').checked })) load(); else render(); };
      };
    });
    document.querySelectorAll('[data-back]').forEach(b => b.onclick = async () => { if (await absent(b.dataset.back, false)) load(); });
    document.querySelectorAll('[data-undo]').forEach(b => b.onclick = async () => { if (confirm('Undo this transfer?') && await post({ op: 'undo_transfer', index: +b.dataset.undo })) load(); });
    $('#r-addbtn').onclick = () => {
      form(`<b>Add a player</b> <span class="mut small">for a new signing who has no box score yet. Once a box score exists with the same team and number, the real statistics take over.</span>
        <div class="row" style="margin-top:8px"><select id="f-team">${codes.map(c => `<option value="${c}" ${c === team ? 'selected' : ''}>${esc(teams[c])} (${c})</option>`).join('')}</select>
          <input id="f-name" placeholder="Full name" style="min-width:220px"><input id="f-num" class="num" type="number" min="0" max="99" placeholder="#">
          <select id="f-pos"><option value="">Position (auto)</option>${R.positions.map(x => `<option>${x}</option>`).join('')}</select></div>
        <div class="row" style="margin-top:8px"><input id="f-h" class="num" placeholder="cm"><input id="f-w" class="num" placeholder="kg"><input id="f-b" type="date" title="Birth date"></div>
        <div class="row" style="margin-top:10px"><button class="primary" id="f-go">Add the player</button><button id="f-no">Cancel</button></div>`);
      $('#f-no').onclick = () => $('#r-forms').innerHTML = '';
      $('#f-go').onclick = async () => {
        const h = parseHeight($('#f-h').value), w = $('#f-w').value.trim();
        const body = { op: 'add', team: $('#f-team').value, name: $('#f-name').value, number: $('#f-num').value, pos: $('#f-pos').value };
        if (h) body.height = h; if (w) body.weight = parseInt(w, 10); if ($('#f-b').value) body.birth = $('#f-b').value;
        if (await post(body)) { team = body.team; load(); } else render();
      };
    };
  }

  window.loadRoster = () => { R = null; load(); };
})();
