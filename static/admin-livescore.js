// Admin: who scored, in the games read live from the broadcast. The Live reader (--scorers) names each scorer from the commentator's words; the site
// shows them at once. Here every basket of the last days' games, the doubtful ones first, with a menu to fix one (your choice is never overwritten).
// Uses the helpers of admin.html ($, esc, api).
(function () {
  let msg = null, only = true;
  const clock = t => t === null || t === undefined ? '' : `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
  const per = q => q <= 4 ? 'Q' + q : 'OT' + (q - 4);

  function row(g, b, roster) {
    const by = b.by || {};
    const state = by.admin ? '<span class="pill acc">fixed</span>' : !b.by ? '<span class="pill warn">not yet</span>'
      : !by.name ? '<span class="pill warn">nobody named</span>' : by.sure ? `<span class="pill">sure ${Math.round((by.conf || 0) * 100)}%</span>` : `<span class="pill warn">to check ${Math.round((by.conf || 0) * 100)}%</span>`;
    const opts = ['<option value="">— nobody / unknown —</option>'].concat((roster || []).map(p =>
      `<option value="${esc(p.id)}" ${by.id === p.id ? 'selected' : ''}>#${p.number ?? '?'} ${esc(p.name)}</option>`)).join('');
    return `<tr><td>${per(b.q)} ${clock(b.t)}</td><td><b>${esc(b.team)}</b> +${b.pts}</td><td class="mut">${esc(b.score)}</td>
      <td class="l">${by.name ? `#${by.number ?? '?'} ${esc(by.name)}` : '<span class="mut">–</span>'} ${state}</td>
      <td><select data-game="${esc(g.id)}" data-index="${b.index}" data-team="${esc(b.team)}">${opts}</select></td></tr>`;
  }

  async function load() {
    const box = $('#livescorebox'); if (!box) return;
    let d;
    try { d = (await api('livescore/scorers')).body; } catch (e) { box.innerHTML = `<div class="problems">${esc(e.message)}${/\b404\b/.test(e.message) ? ' (restart the server: it does not know this feature yet)' : ''}</div>`; return; }
    const games = d.games.map(g => {
      const list = only ? g.baskets.filter(b => !(b.by || {}).sure) : g.baskets;
      return `<div class="card" style="margin-top:8px"><div class="row"><b>${esc(g.home)} ${g.score[g.home]} – ${g.score[g.away]} ${esc(g.away)}</b>
          <span class="mut small">${g.matchday ? 'J' + g.matchday + ' · ' : ''}${g.final ? 'final' : 'live'} · ${g.baskets.length} baskets · ${g.to_check} to check</span></div>
        ${list.length ? `<table style="margin-top:8px"><thead><tr><th>When</th><th>Basket</th><th>Score</th><th class="l">Scorer (from the commentator)</th><th>Fix</th></tr></thead>
          <tbody>${list.map(b => row(g, b, d.rosters[b.team])).join('')}</tbody></table>` : '<div class="mut small" style="margin-top:6px">Nothing to check.</div>'}</div>`;
    }).join('');
    box.innerHTML = `<h3 style="margin-top:12px">🔴 Live scorers</h3>
      <p class="mut small" style="margin:4px 0">When the Live reader runs with <b>--scorers</b>, it names who scored each basket from the commentator's words (about 8 out of 10 right), a few seconds after the score changes. The site shows them at once. Fix a wrong one here: your choice stays, and the official box score replaces all of this after the game.</p>
      ${msg ? `<div class="${msg.ok ? 'okbox' : 'problems'}">${esc(msg.t)}</div>` : ''}
      <label class="small"><input type="checkbox" id="ls-only" ${only ? 'checked' : ''}> only the baskets to check (not sure, nobody named)</label>
      ${games || '<div class="mut" style="margin-top:8px">No game read from the broadcast in the last 3 days.</div>'}`;
    $('#ls-only').onchange = e => { only = e.target.checked; load(); };
    box.querySelectorAll('select[data-game]').forEach(s => s.onchange = async () => {
      try {
        const { ok, body } = await api('livescore/scorer', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: s.dataset.game, index: Number(s.dataset.index), team: s.dataset.team, player: s.value }) });
        msg = ok ? { t: 'Saved: ' + (body.basket.name || 'nobody'), ok: true } : { t: body.error || 'Could not save.', ok: false };
      } catch (e) { msg = { t: e.message, ok: false }; }
      load();
    });
  }

  window.loadLiveScorers = load;
})();
