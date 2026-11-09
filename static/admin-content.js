// Admin: the Games tab (kick-off time, own date and featured rank of each game; results typed by hand with optional stats) and the News tab.
// Uses the helpers of admin.html ($, esc, api). Everything is saved on the server (data/schedule.json, data/result_notes.json, data/news.json, data/official.json).
(function () {
  let S = null, md = null, showPast = false, openForm = null, gMsg = null, players = null;
  const LABELS = { official: 'Official', injury: 'Injury', transfer: 'Transfer', result: 'Result', info: 'Info', interview: 'Interview' };
  const today = () => new Date().toISOString().slice(0, 10);
  const post = (path, body) => api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const fmt = iso => iso ? new Date(iso + 'T12:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }) : '';

  // ---------------------------------------------------------------- Games
  async function loadGames() {
    const box = $('#gamesbox');
    const { ok, body } = await api('schedule');
    if (!ok) { box.innerHTML = '<div class="problems">Could not load the calendar.</div>'; return; }
    S = body;
    if (!players) players = await fetch('/api/players').then(r => r.json()).then(j => j.players).catch(() => []);
    if (md == null) { const nx = S.matchdays.find(m => m.games.some(g => !g.played)); md = nx ? nx.matchday : S.matchdays[0].matchday; }
    renderGames();
  }

  function featuredNow() {
    return S.matchdays.flatMap(m => m.games.filter(g => g.featured && !g.played).map(g => ({ ...g, md: m.matchday }))).sort((a, b) => a.featured - b.featured);
  }

  function statLine(i, g, p = {}) {
    const names = players.filter(x => x.teams.includes(g.home) || x.teams.includes(g.away));
    return `<div class="row" style="margin-top:6px;gap:6px" data-line="${i}">
      <input data-s="name" list="pl-${g.key.replace(/[^A-Z0-9]/gi, '')}" placeholder="Player (optional)" value="${esc(p.name || '')}" style="min-width:170px">
      <select data-s="team"><option value="${g.home}" ${p.team === g.home ? 'selected' : ''}>${g.home}</option><option value="${g.away}" ${p.team === g.away ? 'selected' : ''}>${g.away}</option></select>
      ${['pts', 'reb', 'ast', 'stl', 'blk'].map(k => `<input data-s="${k}" class="num" type="number" min="0" max="99" placeholder="${k.toUpperCase()}" value="${p[k] ?? ''}" style="width:62px">`).join('')}
      ${i === 0 ? `<datalist id="pl-${g.key.replace(/[^A-Z0-9]/gi, '')}">${names.map(x => `<option value="${esc(x.name)}">`).join('')}</datalist>` : ''}</div>`;
  }

  function resultForm(g, m) {
    const n = g.notes || {}, ps = (n.players && n.players.length ? n.players : [{}]).concat([{}, {}]).slice(0, 4);
    return `<div class="card" style="border-color:var(--acc);margin:8px 0" data-rform="${g.key}">
      <b>${g.played ? 'Edit the result' : 'Enter the result'}: ${esc(S.teams[g.home])} – ${esc(S.teams[g.away])}</b>
      <div class="row" style="margin-top:8px"><span>${g.home}</span><input data-r="hs" class="num" type="number" min="0" max="250" style="width:80px" value="${g.home_score ?? ''}"><span>–</span><input data-r="as" class="num" type="number" min="0" max="250" style="width:80px" value="${g.away_score ?? ''}"><span>${g.away}</span></div>
      <div class="small mut" style="margin-top:10px">Optional: a sentence and a few stat lines shown with the result on the home page (best players, any stat can stay empty).</div>
      <input data-r="note" maxlength="300" placeholder="Optional note, e.g. “Decisive 12–0 run in the 4th quarter”" style="width:100%;margin-top:6px" value="${esc(n.note || '')}">
      ${ps.map((p, i) => statLine(i, g, p)).join('')}
      <div class="row" style="margin-top:10px"><button class="primary" data-act="saveresult">Save the result</button><button data-act="cancelform">Cancel</button></div></div>`;
  }

  function renderGames() {
    const m = S.matchdays.find(x => x.matchday === md) || S.matchdays[0], list = featuredNow();
    const opts = S.matchdays.filter(x => showPast || x.games.some(g => !g.played) || x.matchday === md).map(x => `<option value="${x.matchday}" ${x.matchday === md ? 'selected' : ''}>J${x.matchday}${x.date ? ' · ' + fmt(x.date) : ''}${x.games.every(g => g.played) ? ' ✓' : ''}</option>`).join('');
    $('#gamesbox').innerHTML = `
      ${gMsg ? `<div class="${gMsg.ok ? 'okbox' : 'problems'}">${esc(gMsg.t)}</div>` : ''}
      <div class="card"><b>⭐ Featured now</b> <span class="mut small">(shown first on the home page banner, by rank; a game appears there as soon as its matchday is the next one)</span>
        ${list.length ? `<div style="margin-top:6px">${list.map(g => `<div>#${g.featured} · <b>${g.home} – ${g.away}</b> <span class="mut small">J${g.md}${g.time ? ' · ' + g.time : ''}</span></div>`).join('')}</div>` : '<div class="mut small" style="margin-top:6px">None yet: tick ⭐ on a game below.</div>'}</div>
      <div class="row" style="margin:12px 0"><label class="small mut">Matchday</label><select id="g-md">${opts}</select>
        <label class="small mut"><input type="checkbox" id="g-past" ${showPast ? 'checked' : ''}> show played matchdays</label></div>
      <div class="card" style="padding:0;overflow-x:auto"><table><thead><tr><th class="l">Game</th><th>Date</th><th>Time</th><th>⭐ Rank</th><th></th></tr></thead><tbody>
      ${m.games.map(g => `<tr data-key="${g.key}"><td class="l"><b>${g.home}</b> – <b>${g.away}</b> ${g.played ? `<span class="pill ok">${g.home_score}–${g.away_score}</span>` : ''}${g.notes ? ' <span class="mut small" title="has a note or stats">📝</span>' : ''}</td>
        <td><input data-f="date" type="date" value="${esc(g.game_date || '')}" placeholder="${esc(m.date || '')}" title="${m.date ? 'Matchday date: ' + m.date + '. Leave empty to use it.' : ''}" style="width:140px"></td>
        <td><input data-f="time" type="time" value="${esc(g.time || '')}" style="width:100px"></td>
        <td><input data-f="featured" class="num" type="number" min="1" max="99" value="${g.featured ?? ''}" placeholder="–" style="width:64px" title="1 = first. Empty = not featured"></td>
        <td style="white-space:nowrap"><button class="primary" data-act="save" hidden>Save</button> <button data-act="result">${g.played ? '✎ Result' : '🏁 Enter result'}</button></td></tr>
        ${openForm === g.key ? `<tr><td colspan="5">${resultForm(g, m)}</td></tr>` : ''}`).join('')}
      </tbody></table></div>
      <p class="mut small">Date: only if this game is not on the matchday’s date. Time: 24-hour, Tunisia time. Rank: 1 comes first; games without a rank follow by date and time. A result you enter updates the standings, the home page’s latest games and the calendar at once; you can add the full box score later (upload a sheet) and it takes over.</p>`;
    wireGames(m);
  }

  function wireGames(m) {
    $('#g-md').onchange = e => { md = +e.target.value; openForm = null; renderGames(); };
    $('#g-past').onchange = e => { showPast = e.target.checked; renderGames(); };
    document.querySelectorAll('#gamesbox tr[data-key]').forEach(tr => {
      const key = tr.dataset.key, g = m.games.find(x => x.key === key), sv = tr.querySelector('[data-act=save]');
      tr.querySelectorAll('input').forEach(i => i.oninput = () => { sv.hidden = false; });
      sv.onclick = async () => {
        const body = { key, date: tr.querySelector('[data-f=date]').value, time: tr.querySelector('[data-f=time]').value, featured: tr.querySelector('[data-f=featured]').value };
        try { const r = await post('schedule', body); gMsg = { t: r.ok ? 'Saved.' : (r.body.error || 'Could not save.'), ok: r.ok }; } catch (e) { gMsg = { t: e.message, ok: false }; }
        loadGames();
      };
      tr.querySelector('[data-act=result]').onclick = () => { openForm = openForm === key ? null : key; renderGames(); };
    });
    const f = document.querySelector('[data-rform]');
    if (f) {
      const g = m.games.find(x => x.key === f.dataset.rform);
      f.querySelector('[data-act=cancelform]').onclick = () => { openForm = null; renderGames(); };
      f.querySelector('[data-act=saveresult]').onclick = async () => {
        const lines = [...f.querySelectorAll('[data-line]')].map(l => Object.fromEntries([...l.querySelectorAll('[data-s]')].map(i => [i.dataset.s, i.value]))).filter(l => l.name.trim());
        const body = { matchday: m.matchday, home: g.home, away: g.away, home_score: f.querySelector('[data-r=hs]').value, away_score: f.querySelector('[data-r=as]').value, note: f.querySelector('[data-r=note]').value, players: lines };
        if (body.home_score === '' || body.away_score === '') { gMsg = { t: 'Enter both scores.', ok: false }; return renderGames(); }
        try { const r = await post('result', body); gMsg = { t: r.ok ? r.body.message : (r.body.error || 'Could not save the result.'), ok: r.ok }; if (r.ok) openForm = null; } catch (e) { gMsg = { t: e.message, ok: false }; }
        loadGames();
      };
    }
  }

  // ---------------------------------------------------------------- News
  let N = [], editing = null, nMsg = null, imgItem = null, draft = null, A = null, aGi = 0;
  async function loadNews() {
    const { ok, body } = await api('news');
    if (!ok) { $('#newsbox').innerHTML = '<div class="problems">Could not load the news.</div>'; return; }
    if (!players) players = await fetch('/api/players').then(r => r.json()).then(j => j.players).catch(() => []);
    N = body.items; renderNews();
  }
  const playerOpts = cur => { const by = {}; players.forEach(p => (by[p.team] = by[p.team] || []).push(p)); return Object.keys(by).sort().map(t => `<optgroup label="${esc(t)}">${by[t].sort((a, b) => a.name.localeCompare(b.name)).map(p => `<option value="${esc(p.id)}" data-name="${esc(p.name)}" ${p.id === cur ? 'selected' : ''}>${esc(p.name)} · #${p.number}</option>`).join('')}</optgroup>`).join(''); };
  const teamOpts = cur => [...new Set(players.map(p => p.team))].sort().map(t => `<option ${t === cur ? 'selected' : ''}>${esc(t)}</option>`).join('');
  const formItem = e => {   // what the form holds right now (for the image preview before publishing)
    const pl = $('#n-player'), o = pl.selectedOptions[0], pid = pl.value, pp = players.find(x => x.id === pid);
    return { label: $('#n-label').value, date: $('#n-date').value, title: $('#n-title').value, body: $('#n-body').value, title_en: $('#n-title-en').value, body_en: $('#n-body-en').value,
      team: pid ? pid.split('-')[0].toUpperCase() : $('#n-team').value, player: pid, player_name: pid ? o.dataset.name : '', photo: pp && pp.photo || null, game: e && e.game || '', match: e && e.match || null };
  };
  function renderNews() {
    const e = editing ? (editing === 'new' ? {} : N.find(n => n.id === editing) || null) : draft;
    $('#newsbox').innerHTML = `
      ${nMsg ? `<div class="${nMsg.ok ? 'okbox' : 'problems'}">${esc(nMsg.t)}</div>` : ''}
      <div id="annbox"></div>
      <div class="card" style="border-color:var(--acc)"><b>${e && e.id ? 'Edit the news' : 'Add news'}</b> <span class="mut small">for example “Player X is out for 6 weeks”</span>
        <div class="row" style="margin-top:8px"><select id="n-label">${Object.entries(LABELS).map(([k, v]) => `<option value="${k}" ${(e && e.label || 'info') === k ? 'selected' : ''}>${v}</option>`).join('')}</select>
          <input id="n-date" type="date" value="${esc((e && e.date) || today())}"><label class="small mut"><input type="checkbox" id="n-pin" ${e && e.pinned ? 'checked' : ''}> 📌 pin on top</label></div>
        <div class="row" style="margin-top:8px"><label class="small mut">Picture: a player</label><select id="n-player"><option value="">—</option>${playerOpts(e && e.player)}</select>
          <label class="small mut">or a club</label><select id="n-team"><option value="">—</option>${teamOpts(e && !e.player && e.team)}</select></div>
        <input id="n-title" maxlength="140" placeholder="Title (French or the main language)" style="width:100%;margin-top:8px" value="${esc((e && e.title) || '')}">
        <textarea id="n-body" maxlength="2000" rows="3" placeholder="Text (optional)" style="width:100%;margin-top:6px;font:inherit">${esc((e && e.body) || '')}</textarea>
        <details style="margin-top:6px" ${e && (e.title_en || e.body_en) ? 'open' : ''}><summary class="small mut">English version (optional: shown to English visitors)</summary>
          <input id="n-title-en" maxlength="140" placeholder="English title" style="width:100%;margin-top:6px" value="${esc((e && e.title_en) || '')}">
          <textarea id="n-body-en" maxlength="2000" rows="2" placeholder="English text" style="width:100%;margin-top:6px;font:inherit">${esc((e && e.body_en) || '')}</textarea></details>
        <div class="row" style="margin-top:10px"><button class="primary" id="n-save">${e && e.id ? 'Save changes' : 'Publish'}</button>${e ? '<button id="n-cancel">Cancel</button>' : ''}<button id="n-img">🖼 Facebook image from this form</button></div></div>
      <div id="nimgbox"></div>
      <h3 class="sub" style="margin-top:18px">Published (${N.length})</h3>
      ${N.length ? N.map(n => `<div class="card" data-nid="${n.id}"><div class="row"><span class="pill">${LABELS[n.label] || n.label}</span><span class="mut small">${esc(n.date)}</span>${n.pinned ? '<span class="pill acc">📌</span>' : ''}<span class="sp"></span><button data-act="img">🖼 Facebook image</button><button data-act="edit">✎ Edit</button><button class="danger" data-act="del">🗑 Delete</button></div>
        <b>${esc(n.title)}</b>${n.body ? `<div class="mut small" style="white-space:pre-line">${esc(n.body)}</div>` : ''}</div>`).join('') : '<div class="mut small">Nothing yet.</div>'}
      <p class="mut small">News shows on the home page (the latest four) and on the News page, with its label. A deleted news item cannot be brought back.</p>`;
    $('#n-save').onclick = async () => {
      const body = { id: e && e.id, label: $('#n-label').value, date: $('#n-date').value, pinned: $('#n-pin').checked, title: $('#n-title').value, body: $('#n-body').value, title_en: $('#n-title-en').value, body_en: $('#n-body-en').value, game: e && e.game || '', match: e && e.match || null,
        player: $('#n-player').value, player_name: $('#n-player').selectedOptions[0].dataset.name || '', team: $('#n-team').value };
      try { const r = await post('news', body); nMsg = { t: r.ok ? 'Published.' : (r.body.error || 'Could not save.'), ok: r.ok }; if (r.ok) { editing = null; draft = null; } } catch (x) { nMsg = { t: x.message, ok: false }; }
      loadNews();
    };
    const showImg = item => { imgItem = item; const b = $('#nimgbox'); window.NewsImg.mount(b, item, () => { imgItem = null; }); b.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); };
    $('#n-img').onclick = () => { if (!$('#n-title').value.trim()) { nMsg = null; $('#n-title').focus(); return; } showImg(formItem(e)); };
    if (imgItem) window.NewsImg.mount($('#nimgbox'), imgItem, () => { imgItem = null; });
    const c = $('#n-cancel'); if (c) c.onclick = () => { editing = null; draft = null; renderNews(); };
    renderAnn();
    document.querySelectorAll('[data-nid]').forEach(card => {
      const id = card.dataset.nid;
      card.querySelector('[data-act=img]').onclick = () => showImg(N.find(n => n.id === id));
      card.querySelector('[data-act=edit]').onclick = () => { editing = id; nMsg = null; renderNews(); window.scrollTo({ top: 0, behavior: 'smooth' }); };
      card.querySelector('[data-act=del]').onclick = async () => { if (!confirm('Delete this news item? This cannot be undone.')) return; const r = await post('news/delete', { id }); nMsg = { t: r.ok ? 'Deleted.' : 'Could not delete.', ok: r.ok }; loadNews(); };
    });
  }


  // ---------------------------------------------------------------- announce a game: pick a played game, then write the news, or make its score image or a photo of one player
  async function loadAnn(md) {
    const { ok, body } = await api('matchday' + (md ? '?md=' + md : ''));
    if (ok) { A = body; aGi = 0; } else A = { results: [], matchdays: [] };
    renderAnn();
  }
  const winner = r => r.home_score > r.away_score ? { w: r.home, wn: r.home_name, l: r.away, ln: r.away_name, ws: r.home_score, ls: r.away_score, away: false } : { w: r.away, wn: r.away_name, l: r.home, ln: r.home_name, ws: r.away_score, ls: r.home_score, away: true };
  function gameDraft(r) {
    const x = winner(r), m = r.mvp, line = m ? `${m.pts} pts, ${m.reb} reb, ${m.ast} pd` : '', lineEn = m ? `${m.pts} pts, ${m.reb} reb, ${m.ast} ast` : '';
    const nm = n => String(n || '').toLowerCase().replace(/(^|[\s'-])\w/g, c => c.toUpperCase());
    return { label: 'result', date: A.date || today(), team: x.w, game: r.game_id || '',
      match: { home: r.home, away: r.away, home_name: r.home_name, away_name: r.away_name, home_score: r.home_score, away_score: r.away_score, md: A.md },
      title: `${x.wn} ${x.away ? 's’impose chez' : 's’impose face à'} ${x.ln} (${x.ws}–${x.ls})`, title_en: `${x.wn} ${x.away ? 'win at' : 'beat'} ${x.ln} ${x.ws}–${x.ls}`,
      body: `Journée ${A.md}.${m ? ` ${nm(m.name)} élu homme du match : ${line}.` : ''}`, body_en: `Matchday ${A.md}.${m ? ` ${nm(m.name)} is the game’s MVP: ${lineEn}.` : ''}` };
  }
  function renderAnn() {
    const box = $('#annbox'); if (!box) return;
    if (!A) { box.innerHTML = '<div class="mut small" style="margin-bottom:10px">Loading the games…</div>'; loadAnn(); return; }
    const rs = A.results || [];
    box.innerHTML = `<div class="card" style="margin-bottom:12px"><b>📣 Announce a game</b> <span class="mut small">a result for the news (“JSK beat USM”), a score image, or a photo of a player with his stats</span>
      ${rs.length ? `<div class="row" style="margin-top:8px"><select id="a-md">${A.matchdays.map(m => `<option value="${m.matchday}" ${m.matchday === A.md ? 'selected' : ''}>J${m.matchday}${m.date ? ' · ' + m.date : ''}</option>`).join('')}</select>
        <select id="a-g">${rs.map((r, i) => `<option value="${i}" ${i === aGi ? 'selected' : ''}>${esc(r.home)} ${r.home_score}–${r.away_score} ${esc(r.away)}</option>`).join('')}</select></div>
        <div class="row" style="margin-top:8px"><button id="a-news">✍ Write the news</button><button id="a-score">🖼 Score image</button><button id="a-photo">📸 Player photo image</button></div>
        <div id="spotbox"></div>` : '<div class="mut small" style="margin-top:6px">No played games yet.</div>'}</div>`;
    if (!rs.length) return;
    $('#a-md').onchange = e => loadAnn(+e.target.value);
    $('#a-g').onchange = e => { aGi = +e.target.value; };
    $('#a-news').onclick = () => { draft = gameDraft(rs[aGi]); editing = null; imgItem = null; nMsg = { t: 'Filled in from the game: check the text, then publish.', ok: true }; renderNews(); window.scrollTo({ top: 0, behavior: 'smooth' }); };
    $('#a-score').onclick = () => { imgItem = { ...gameDraft(rs[aGi]), id: 'game' }; window.NewsImg.mount($('#nimgbox'), imgItem, () => { imgItem = null; }); $('#nimgbox').scrollIntoView({ behavior: 'smooth', block: 'nearest' }); };
    $('#a-photo').onclick = () => { window.Spotlight.mount($('#spotbox'), rs[aGi], A.md); $('#spotbox').scrollIntoView({ behavior: 'smooth', block: 'nearest' }); };
  }

  window.loadGames = loadGames; window.loadNews = loadNews;
})();
