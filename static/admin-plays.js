// Admin: play of the week. Create a week, paste its clips (YouTube / Facebook links or a direct .mp4 address), open the fans' vote, close it, crown a clip.
// Uses the helpers of admin.html ($, esc, api). Saved on the server (data/plays.json); votes are final (data/votes.db). The app shows the latest opened week.
(function () {
  let msg = null;
  const say = (t, ok = true) => { msg = t ? { t, ok } : null; };

  async function post(body) {
    try {
      const { ok, body: r } = await api('plays', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      say(ok ? r.message : (r.error || 'Could not save.'), ok);
      return ok;
    } catch (e) { say(e.message + (/\b404\b/.test(e.message) ? ' (restart the server: it does not know this feature yet)' : ''), false); return false; }
  }

  const pill = s => ({ open: '<span class="pill acc">voting open</span>', closed: '<span class="pill">closed</span>', draft: '<span class="pill warn">draft</span>' }[s] || '');
  const kind = k => ({ youtube: '▶️ YouTube', facebook: '📘 Facebook', file: '🎞️ video file' }[k] || k);

  function block(w, max) {
    const clips = w.clips.map(c => `<tr><td class="l">${c.thumb ? `<img src="${esc(c.thumb)}" style="width:72px;height:40px;object-fit:cover;border-radius:6px;vertical-align:middle;margin-right:8px">` : ''}<b>${esc(c.title)}</b>
        <span class="mut small">${esc([c.player, c.team].filter(Boolean).join(' · '))} · <a href="${esc(c.url)}" target="_blank" rel="noopener">${kind(c.kind)}</a></span>
        ${w.winner === c.id ? ' <span class="pill acc">👑 crowned</span>' : !w.winner && w.leader === c.id ? ' <span class="pill">leads</span>' : ''}</td>
      <td>${c.votes} vote${c.votes === 1 ? '' : 's'} · ${c.vote_share}%</td>
      <td>${w.state !== 'draft' ? (w.winner === c.id ? `<button data-act="crown" data-week="${w.id}" data-winner="">Remove the crown</button>` : `<button data-act="crown" data-week="${w.id}" data-winner="${esc(c.id)}">👑 Crown</button>`) : ''}
          ${w.votes ? '' : `<button data-act="remove" data-week="${w.id}" data-clip="${esc(c.id)}" class="danger">Remove</button>`}</td></tr>`).join('');
    const bad = w.unplayable.length ? `<div class="problems small">Not playable (check the link): ${w.unplayable.map(c => esc(c.title)).join(', ')}</div>` : '';
    const add = w.clips.length < max && w.state !== 'closed' ? `<div class="row" style="margin-top:8px;flex-wrap:wrap;gap:6px">
        <input data-f="url" placeholder="https://www.youtube.com/watch?v=… or Facebook video link or .mp4" style="flex:2;min-width:240px">
        <input data-f="title" placeholder="Title (e.g. Dunk over two defenders)" style="flex:2;min-width:180px">
        <input data-f="player" placeholder="Player (optional)" style="flex:1;min-width:120px">
        <input data-f="team" placeholder="Club code (optional, e.g. ESR)" style="width:150px">
        <button data-act="add" data-week="${w.id}" class="primary">➕ Add the clip</button></div>` : '';
    const controls = w.state === 'open'
      ? `<button data-act="close" data-week="${w.id}" class="danger">Close the voting</button>`
      : `<label class="small mut">Deadline (optional, Tunisian time)</label><input type="datetime-local" data-dl="${w.id}"><button data-act="open" data-week="${w.id}" class="primary">${w.state === 'closed' ? '↺ Re-open the voting' : '🗳️ Open the voting'}</button>`;
    return `<div class="card" style="margin-top:8px${w.state === 'open' ? ';border-color:var(--acc)' : ''}">
      <div class="row"><b style="font-size:16px">${esc(w.title)}</b>${pill(w.state)}<span class="mut small">${w.clips.length} clip${w.clips.length === 1 ? '' : 's'} · ${w.votes} vote${w.votes === 1 ? '' : 's'}${w.deadline ? ' · deadline ' + esc(w.deadline.replace('T', ' ')) : ''}</span>
        ${w.votes ? '' : `<button data-act="delete" data-week="${w.id}" class="danger" style="margin-left:auto">Delete the week</button>`}</div>
      ${clips ? `<table style="margin-top:8px"><tbody>${clips}</tbody></table>` : '<div class="mut small" style="margin-top:6px">No clip yet.</div>'}${bad}${add}
      <div class="row" style="margin-top:8px">${controls}</div></div>`;
  }

  async function load() {
    const box = $('#playsbox'); if (!box) return;
    let d;
    try { d = (await api('plays')).body; } catch (e) { box.innerHTML = `<div class="problems">${esc(e.message)}${/\b404\b/.test(e.message) ? ' (restart the server: it does not know this feature yet)' : ''}</div>`; return; }
    box.innerHTML = `<h3 style="margin-top:12px">🎬 Play of the week</h3>
      <p class="mut small" style="margin:4px 0">Create a week, add 2 to ${d.max_clips} clips (YouTube or Facebook video links, or a direct https address of an .mp4 file), then open the vote. The app shows the latest opened week; its winner (most votes once closed, or your crown) stays on show until you open the next week, then joins the archive. Votes are final: once fans voted, clips can't be removed. Phones that turned on vote notifications are told when a vote opens.</p>
      ${msg ? `<div class="${msg.ok ? 'okbox' : 'problems'}">${esc(msg.t)}</div>` : ''}
      <div class="row" style="margin:8px 0"><input id="plays-title" placeholder="New week title (e.g. J12 or Week 12)"><button id="plays-create" class="primary">➕ Create a week</button></div>
      ${d.weeks.map(w => block(w, d.max_clips)).join('') || '<div class="mut">No week yet.</div>'}`;
    $('#plays-create').onclick = async () => { await post({ op: 'create', title: $('#plays-title').value }); load(); };
    box.querySelectorAll('[data-act]').forEach(b => b.onclick = async () => {
      const act = b.dataset.act, week = b.dataset.week, body = { op: act, week };
      const card = b.closest('.card'), f = n => (card.querySelector(`[data-f=${n}]`) || {}).value || '';
      if (act === 'add') Object.assign(body, { url: f('url'), title: f('title'), player: f('player'), team: f('team') });
      if (act === 'remove') body.clip = b.dataset.clip;
      if (act === 'crown') body.winner = b.dataset.winner || null;
      if (act === 'open') { const dl = box.querySelector(`[data-dl="${week}"]`); if (dl && dl.value) body.deadline = dl.value; }
      if (act === 'close' && !confirm('Close this vote? Nobody can vote after that (you can re-open it).')) return;
      if (act === 'delete' && !confirm('Delete this week and its clips?')) return;
      await post(body); load();
    });
  }

  window.loadPlays = load;
})();
