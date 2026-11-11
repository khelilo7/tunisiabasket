// Admin: player of the round. For each recent matchday: can its fan vote be opened (every game has its result and at least one player of the game)? Open it, close it, add players
// whose stats arrived later, crown a winner. Uses the helpers of admin.html ($, esc, api). Everything is saved on the server (data/rounds.json); votes are final (data/votes.db).
(function () {
  let msg = null;
  const say = (t, ok = true) => { msg = t ? { t, ok } : null; };

  async function post(body) {
    try {
      const { ok, body: r } = await api('rounds', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      say(ok ? r.message : (r.error || 'Could not save.'), ok);
      return ok;
    } catch (e) { say(e.message + (/\b404\b/.test(e.message) ? ' (this server does not know the feature yet: restart it after updating the code)' : ''), false); return false; }
  }

  const pill = s => ({ open: '<span class="pill acc">voting open</span>', closed: '<span class="pill">closed</span>', ready: '<span class="pill warn">ready to open</span>', waiting: '<span class="pill bad">not ready</span>' }[s] || '');

  function block(r) {
    const dl = r.deadline ? ` · deadline ${esc(r.deadline.replace('T', ' '))} (Tunisia)` : '';
    const head = `<div class="row"><b style="font-size:16px">J${r.matchday}</b>${pill(r.state)}<span class="mut small">${r.results}/${r.expected} results · ${r.candidates} player${r.candidates === 1 ? '' : 's'} of the game${dl}</span></div>`;
    if (r.state === 'waiting') return `<div class="card" style="margin-top:8px">${head}<div class="mut small" style="margin-top:6px">${esc(r.reason)}</div></div>`;
    const ballot = r.ballot.length ? `<table style="margin-top:8px"><tbody>${r.ballot.map(b => `<tr><td class="l"><b>${esc(b.name)}</b> <span class="mut small">${esc(b.team)}</span>${r.winner === b.id ? ' <span class="pill acc">👑 crowned</span>' : !r.winner && r.leader === b.id && r.votes ? ' <span class="pill">leads</span>' : ''}</td>
      <td>${b.votes} vote${b.votes === 1 ? '' : 's'} · ${b.vote_share}%</td><td>${r.winner === b.id ? `<button data-act="crown" data-round="${r.matchday}" data-winner="">Remove the crown</button>` : `<button data-act="crown" data-round="${r.matchday}" data-winner="${esc(b.id)}" title="Make him the player of the round, whatever the votes say">👑 Crown</button>`}</td></tr>`).join('')}</tbody></table>
      <div class="mut small">${r.votes} vote${r.votes === 1 ? '' : 's'} in total. Without a crown, the player with most votes wins once the vote is closed.</div>` : '';
    const controls = r.state === 'open'
      ? `<div class="row" style="margin-top:8px"><button data-act="close" data-round="${r.matchday}" class="danger">Close the voting</button><button data-act="refresh" data-round="${r.matchday}" title="Add the players of games whose stats arrived after the vote was opened">➕ Add new players of the game</button></div>`
      : r.can_open
        ? `<div class="row" style="margin-top:8px"><label class="small mut">Deadline (optional, Tunisian time)</label><input type="datetime-local" data-dl="${r.matchday}"><button data-act="open" data-round="${r.matchday}" class="primary">${r.state === 'closed' ? '↺ Re-open the voting' : '🗳️ Open the voting'}</button></div>
          <div class="mut small" style="margin-top:4px">Candidates: ${r.possible.map(p => esc(p.name) + ' (' + esc(p.team) + ')').join(', ')}</div>`
        : `<div class="mut small" style="margin-top:8px">${esc(r.reason)}</div>`;
    return `<div class="card" style="margin-top:8px${r.state === 'open' ? ';border-color:var(--acc)' : ''}">${head}${ballot}${controls}</div>`;
  }

  async function load() {
    const box = $('#roundbox'); if (!box) return;
    let rounds;
    try { rounds = (await api('rounds')).body.rounds; } catch (e) { box.innerHTML = `<div class="problems">${esc(e.message)}${/\b404\b/.test(e.message) ? ' (restart the server: it does not know this feature yet)' : ''}</div>`; return; }
    box.innerHTML = `<h3 style="margin-top:16px">🗳️ Player of the round</h3>
      <p class="mut small" style="margin:4px 0">The fans vote for the best player of a matchday, among the players of the game of that matchday. It can only be opened once <b>every game of the matchday has its result</b> and at least one game has a player of the game (a box score, or a one-team sheet). One vote open at a time; votes are final. When it is open, the home page shows it instead of the phase MVP vote (once that one is over).</p>
      ${msg ? `<div class="${msg.ok ? 'okbox' : 'problems'}">${esc(msg.t)}</div>` : ''}
      ${rounds.map(block).join('') || '<div class="mut">No results yet.</div>'}`;
    box.querySelectorAll('[data-act]').forEach(b => b.onclick = async () => {
      const act = b.dataset.act, round = +b.dataset.round, body = { op: act, round };
      if (act === 'open') { const dl = box.querySelector(`[data-dl="${round}"]`); if (dl && dl.value) body.deadline = dl.value; }
      if (act === 'crown') body.winner = b.dataset.winner || null;
      if (act === 'close' && !confirm(`Close the vote of J${round}? Nobody can vote after that (you can re-open it).`)) return;
      await post(body); load();
    });
  }

  window.loadRounds = load;
})();
