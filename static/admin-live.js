// Admin: live scoring board. Create a match, tap +1/+2/+3 as points are scored, set the quarter and clock, post a note, finish.
// Visitors see it on the home page within 15 seconds. Uses the helpers of admin.html ($, esc, api).
(function () {
  let S = null, err = null, timer = null;
  const post = async body => {
    try {
      const { ok, body: r } = await api('live', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      err = ok ? null : (r.error || 'Could not save.');
      return ok;
    } catch (e) { err = e.message; return false; }
  };
  async function load() {
    const { ok, body } = await api('live');
    if (!ok) { $('#livebox2').innerHTML = '<div class="problems">Could not load the live board.</div>'; return; }
    S = body; render();
  }
  const row = (m, side) => {
    const k = side + '_score', name = side === 'home' ? m.home_name : m.away_name;
    return `<div style="text-align:center"><div><b>${esc(name)}</b></div><div style="font-size:54px;font-weight:900;line-height:1.1;font-variant-numeric:tabular-nums">${m[k]}</div>
      <div class="row" style="justify-content:center;gap:6px">${[1, 2, 3].map(n => `<button class="primary" data-id="${m.id}" data-k="${k}" data-d="${n}" style="min-width:48px;padding:10px 12px;font-size:16px">+${n}</button>`).join('')}<button data-id="${m.id}" data-k="${k}" data-d="-1" style="padding:10px 12px">−1</button></div></div>`;
  };
  function card(m) {
    const live = m.status === 'live', fin = m.status === 'final';
    return `<div class="card" ${live ? 'style="border-color:var(--bad)"' : ''}>
      <div class="row"><span class="pill ${live ? 'bad' : fin ? '' : 'warn'}">${fin ? 'FINAL' : live ? '● LIVE' : 'NOT STARTED'}</span><b>${esc(m.home_name)} – ${esc(m.away_name)}</b><span class="mut small">${esc(m.matchday || '')}</span><span class="sp"></span>
        <button class="danger" data-del="${m.id}">Delete</button></div>
      ${fin ? `<div style="font-size:34px;font-weight:900;margin:10px 0">${m.home_score} – ${m.away_score}</div><button data-reopen="${m.id}">Reopen</button>` : `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0">${row(m, 'home')}${row(m, 'away')}</div>
      <div class="row" style="justify-content:center">${['1', '2', '3', '4', 'OT'].map(p => `<button data-per="${p}" data-id="${m.id}" class="${m.period === p ? 'primary' : ''}">${p === 'OT' ? 'OT' : 'Q' + p}</button>`).join('')}
        <input data-clock="${m.id}" value="${esc(m.clock || '')}" style="width:80px;text-align:center" placeholder="07:32" aria-label="Clock"><button data-setclock="${m.id}">Set clock</button></div>
      <div class="row" style="margin-top:10px"><input data-note="${m.id}" placeholder="Update for the fans, e.g. 10-0 run for CA" style="flex:1;min-width:220px"><button data-post="${m.id}">Post</button>
        ${m.status === 'scheduled' ? `<button class="primary" data-start="${m.id}">▶ Start</button>` : ''}<button class="primary" data-fin="${m.id}">🏁 Finish match</button></div>`}
      ${m.updates && m.updates.length ? `<div class="small mut" style="margin-top:8px">${m.updates.slice(0, 4).map(u => `${new Date(u.ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · ${esc(u.text)}`).join('<br>')}</div>` : ''}</div>`;
  }
  function render() {
    const teams = S.teams, codes = Object.keys(teams).sort((a, b) => teams[a].localeCompare(teams[b])), opt = c => `<option value="${c}">${esc(teams[c])} (${c})</option>`;
    const active = S.matches.filter(m => m.status !== 'final'), done = S.matches.filter(m => m.status === 'final').slice(0, 8);
    $('#livebox2').innerHTML = `${err ? `<div class="problems">${esc(err)}</div>` : ''}
      <p class="mut small" style="margin:10px 0">Tap the points as they happen: fans see the score on the home page within 15 seconds, and a finished match becomes a news item. This board is your own live feed; no outside service is used.</p>
      <div class="card"><div class="row"><b>New match</b><select id="lv-h">${codes.map(opt).join('')}</select><span class="mut">vs</span><select id="lv-a">${codes.map(c => opt(c)).join('')}</select>
        <input id="lv-md" placeholder="J12" style="width:70px"><label class="small mut"><input type="checkbox" id="lv-go" checked> start now</label><button class="primary" id="lv-create">Create</button></div></div>
      ${active.map(card).join('') || '<div class="mut" style="margin:12px 0">No match in play.</div>'}
      ${done.length ? `<h3 class="sub">Finished (visible to fans for 36 hours)</h3>${done.map(card).join('')}` : ''}`;
    const a = $('#lv-a'); if (a && a.options.length > 1) a.selectedIndex = 1;
    const go = async (body) => { if (await post(body)) { await load(); } else render(); };
    $('#lv-create').onclick = () => go({ op: 'create', home: $('#lv-h').value, away: $('#lv-a').value, matchday: $('#lv-md').value, start: $('#lv-go').checked });
    const find = id => S.matches.find(m => m.id === id);
    document.querySelectorAll('[data-d]').forEach(b => b.onclick = () => { const m = find(b.dataset.id); go({ op: 'update', id: m.id, [b.dataset.k]: Math.max(0, m[b.dataset.k] + +b.dataset.d) }); });
    document.querySelectorAll('[data-per]').forEach(b => b.onclick = () => go({ op: 'update', id: b.dataset.id, period: b.dataset.per }));
    document.querySelectorAll('[data-setclock]').forEach(b => b.onclick = () => go({ op: 'update', id: b.dataset.setclock, clock: document.querySelector(`[data-clock="${b.dataset.setclock}"]`).value }));
    document.querySelectorAll('[data-post]').forEach(b => b.onclick = () => { const i = document.querySelector(`[data-note="${b.dataset.post}"]`); if (i.value.trim()) go({ op: 'update', id: b.dataset.post, note: i.value }); });
    document.querySelectorAll('[data-start]').forEach(b => b.onclick = () => go({ op: 'start', id: b.dataset.start }));
    document.querySelectorAll('[data-fin]').forEach(b => b.onclick = () => { const m = find(b.dataset.fin); if (confirm(`Finish ${m.home} ${m.home_score} – ${m.away_score} ${m.away}? It becomes a news item.`)) go({ op: 'finish', id: m.id }); });
    document.querySelectorAll('[data-reopen]').forEach(b => b.onclick = () => go({ op: 'reopen', id: b.dataset.reopen }));
    document.querySelectorAll('[data-del]').forEach(b => b.onclick = () => { if (confirm('Delete this match from the board?')) go({ op: 'delete', id: b.dataset.del }); });
  }
  window.loadLive = () => { err = null; load(); };
})();
