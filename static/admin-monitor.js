// Admin: the Server tab. Health of the machine and of the app (one sample a minute, health.py), the website, the mobile app's users,
// push notification sign-ups and fan votes, from GET /admin/api/monitor (monitor.py). Refreshes every minute while the tab is open.
// Uses the helpers of admin.html ($, esc, api).
(function () {
  let range = '24h', timer = null;
  const GB = 1024 ** 3, MB = 1024 ** 2;
  const num = x => (x == null ? '–' : Number(x).toLocaleString('en'));
  const size = b => (b == null ? '–' : b >= GB ? (b / GB).toFixed(1) + ' GB' : Math.round(b / MB) + ' MB');
  const pct = (a, b) => (a == null || !b ? null : 100 * a / b);
  const pctTxt = p => (p == null ? '–' : Math.round(p) + '%');
  const dur = s => { if (s == null) return '–'; const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return d ? `${d} d ${h} h` : h ? `${h} h ${m} min` : `${m} min`; };
  const level = (p, warn, bad) => (p == null ? '' : p >= bad ? 'bad' : p >= warn ? 'warn' : 'ok');
  const kpi = (value, label, cls = '', sub = '') => `<div class="kpi ${cls}"><b>${value}</b><span>${label}</span>${sub ? `<small>${sub}</small>` : ''}</div>`;
  const RANGES = { '1h': 'Last hour', '24h': '24 hours', '7d': '7 days', '30d': '30 days', '1y': '1 year' };

  // a line chart; a gap in the samples (app down, restart) breaks the line instead of drawing across it
  function lines(points, step, series, { max, unit = '', title }) {
    const W = 700, H = 120, top = 8, bottom = 2;
    if (!points.length) return `<div class="card mon"><h3>${title}</h3><div class="mut small">No samples yet: the first one is stored a minute after the app starts.</div></div>`;
    const t0 = points[0].ts, t1 = Math.max(points[points.length - 1].ts, t0 + step);
    const vals = series.flatMap(s => points.map(s.get).filter(v => v != null));
    const top_ = max ?? Math.max(1, ...vals) * 1.15;
    const x = ts => (W * (ts - t0)) / (t1 - t0), y = v => top + (H - top - bottom) * (1 - Math.min(v, top_) / top_);
    const paths = series.map(s => {
      let d = '', prev = null;
      for (const p of points) {
        const v = s.get(p);
        if (v == null) { prev = null; continue; }
        d += `${prev == null || p.ts - prev > step * 1.5 ? 'M' : 'L'}${x(p.ts).toFixed(1)},${y(v).toFixed(1)}`;
        prev = p.ts;
      }
      return `<path d="${d}" style="stroke:${s.color}"/>`;
    }).join('');
    const last = series.map(s => { const p = [...points].reverse().find(q => s.get(q) != null); return p ? `<span style="color:${s.color}">■</span> ${s.name} <b>${s.fmt ? s.fmt(s.get(p)) : Math.round(s.get(p) * 10) / 10 + unit}</b>` : ''; }).join(' &nbsp; ');
    const fmtT = ts => { const d = new Date(ts * 1000); return step >= 86400 || range === '7d' || range === '30d' ? `${d.getDate()}/${d.getMonth() + 1}` : d.toTimeString().slice(0, 5); };
    const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => `<span>${fmtT(t0 + f * (t1 - t0))}</span>`).join('');
    return `<div class="card mon"><h3>${title} <span class="mut small" style="font-weight:400;text-transform:none;letter-spacing:0">· top of chart ${Math.round(top_ * 10) / 10}${unit}</span></h3>
      <svg class="line" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(title)}"><line x1="0" x2="${W}" y1="${H - bottom}" y2="${H - bottom}"/>${paths}</svg>
      <div class="ticks">${ticks}</div><div class="small mut">${last}</div></div>`;
  }

  // daily bars, two series side by side
  function days(series, a, b) {
    const W = 700, H = 130, max = Math.max(1, ...series.map(d => Math.max(d[a.key], d[b.key]))), bw = W / series.length, every = Math.ceil(series.length / 8);
    return `<svg class="bars" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(a.name)} and ${esc(b.name)} per day">
      ${series.map((d, i) => { const ha = (H - 22) * d[a.key] / max, hb = (H - 22) * d[b.key] / max, xx = i * bw;
        return `<g><title>${d.day}: ${d[a.key]} ${a.name}, ${d[b.key]} ${b.name}</title><rect class="v" x="${xx + 1}" y="${H - 16 - ha}" width="${Math.max(1, bw / 2 - 1)}" height="${ha}" rx="1"/><rect class="u" x="${xx + bw / 2}" y="${H - 16 - hb}" width="${Math.max(1, bw / 2 - 1)}" height="${hb}" rx="1"/></g>` +
          (i % every === 0 ? `<text x="${xx}" y="${H - 3}">${d.day.slice(5)}</text>` : ''); }).join('')}</svg>
      <div class="small mut"><span style="color:var(--acc)">■</span> ${a.name} &nbsp; <span style="color:var(--good)">■</span> ${b.name}</div>`;
  }

  const list = (rows, label) => (rows.length ? rows.map(r => `<div class="brow"><span class="n">${label(r)}</span><b>${num(r[1])}</b></div>`).join('') : '<div class="mut small">Nothing yet.</div>');

  async function load() {
    const box = $('#monitorbox'); if (!box) return;
    let m;
    try {
      const r = await api('monitor?range=' + range);
      if (!r.ok) throw new Error(r.body.error || 'Could not load.');
      m = r.body;
    } catch (e) { box.innerHTML = `<div class="problems">${esc(e.message)}</div>`; return; }
    const h = m.health, c = h.current, d = h.day, pts = m.chart.points, step = m.chart.step;
    const memP = pct(c.mem_used, c.mem_total), diskP = pct(c.disk_used, c.disk_total), swapP = pct(c.swap_used, c.swap_total);
    const loadP = c.load5 == null ? null : 100 * c.load5 / (h.cpus || 1);
    const app = m.app, web = m.web, push = m.push, v = m.votes.kinds;
    const warn = h.warnings.length
      ? h.warnings.map(w => `<div class="${w.level === 'bad' ? 'problems' : 'warns'}">${w.level === 'bad' ? '⛔' : '⚠️'} ${esc(w.text)}</div>`).join('')
      : '<div class="okbox">✔ All good: memory, disk, load and errors are normal.</div>';
    const linux = c.mem_total != null;
    box.innerHTML = `
      <div class="row" style="margin:12px 0"><b>Server</b><span class="mut small">${h.at ? 'last sample ' + new Date(h.at * 1000).toTimeString().slice(0, 5) : ''} · refreshes every minute</span><span class="sp"></span>
        ${Object.entries(RANGES).map(([k, t]) => `<button data-range="${k}" class="${k === range ? 'primary' : ''}">${t}</button>`).join('')}</div>
      ${warn}
      ${linux ? '' : '<div class="mut small">This machine has no /proc (a Mac?): CPU, memory and uptime appear on the Linux server only.</div>'}
      <div class="kpis">
        ${kpi(pctTxt(c.cpu), 'CPU (machine)', level(c.cpu, 80, 95), c.app_cpu != null ? `app ${c.app_cpu}% · ${h.cpus} CPUs` : `${h.cpus} CPUs`)}
        ${kpi(pctTxt(memP), 'memory used', level(memP, 85, 95), `${size(c.mem_used)} of ${size(c.mem_total)}${c.swap_total ? ' · swap ' + pctTxt(swapP) : ''}`)}
        ${kpi(pctTxt(diskP), 'disk used', level(diskP, 85, 95), `${size(c.disk_total == null ? null : c.disk_total - c.disk_used)} free of ${size(c.disk_total)}`)}
        ${kpi(c.load5 ?? '–', 'load (5 min)', level(loadP, 150, 300), `1 min ${c.load1 ?? '–'} · 15 min ${c.load15 ?? '–'}`)}
        ${kpi(dur(c.uptime), 'machine up for')}
        ${kpi(size(c.rss), 'app memory', '', `up ${dur(h.app_uptime)} · ${c.threads ?? '–'} threads${c.fds != null ? ' · ' + c.fds + ' files' : ''}`)}
        ${kpi(num(d.requests), 'requests · 24 h', '', `p95 worst minute ${d.p95_max == null ? '–' : Math.round(d.p95_max) + ' ms'}`)}
        ${kpi(num(d.errors_5xx), 'server errors · 24 h', d.errors_5xx ? 'bad' : 'ok', `${num(d.errors_4xx)} not found / refused (4xx)`)}
      </div>
      <div class="tgrid">
        ${lines(pts, step, [{ name: 'machine', color: 'var(--acc)', get: p => p.cpu }, { name: 'app', color: 'var(--good)', get: p => p.app_cpu }], { max: 100, unit: '%', title: 'CPU' })}
        ${lines(pts, step, [{ name: 'memory', color: 'var(--acc)', get: p => pct(p.mem_used, p.mem_total) }, { name: 'app', color: 'var(--good)', get: p => pct(p.rss, p.mem_total) }, { name: 'swap', color: 'var(--bad)', get: p => pct(p.swap_used, p.swap_total) }], { max: 100, unit: '%', title: 'Memory' })}
        ${lines(pts, step, [{ name: '5 min', color: 'var(--acc)', get: p => p.load5 }, { name: 'CPUs', color: 'var(--mut)', get: () => h.cpus }], { title: 'Load' })}
        ${lines(pts, step, [{ name: 'disk', color: 'var(--acc)', get: p => pct(p.disk_used, p.disk_total) }], { max: 100, unit: '%', title: 'Disk' })}
        ${lines(pts, step, [{ name: 'requests', color: 'var(--acc)', get: p => p.req }, { name: '5xx', color: 'var(--bad)', get: p => p.r5xx }], { unit: '/min', title: 'Requests per minute' })}
        ${lines(pts, step, [{ name: 'median', color: 'var(--good)', get: p => p.p50 }, { name: 'p95', color: 'var(--acc)', get: p => p.p95 }], { unit: ' ms', title: 'Response time' })}
      </div>
      ${d.missing_minutes ? `<p class="mut small">${d.missing_minutes} minutes without a sample in the last 24 hours: the app was restarting (a deploy) or not running. Gaps break the lines above.</p>` : ''}

      <h3 class="sub">People · last ${web.days} days</h3>
      <div class="kpis">
        ${kpi(num(web.online), 'on the website now (5 min)', 'live')}
        ${kpi(num(web.today.visitors), 'website visitors today', '', `${num(web.today.views)} page views`)}
        ${kpi(num(web.people), `website people · ${web.days} d`, '', `${num(web.views)} page views`)}
        ${kpi(num(app.today), 'app users today (DAU)', 'live')}
        ${kpi(num(app.wau), 'app users · 7 days')}
        ${kpi(num(app.mau), 'app users · 30 days (MAU)', '', app.mau ? `stickiness ${Math.round(100 * app.today / app.mau)}% (DAU/MAU)` : '')}
        ${kpi(num(app.installs), 'app installs seen', '', 'since counting began')}
        ${kpi(num(push.total), 'phones with notifications', '', `${num(push.seen_7d)} opened the app in 7 days`)}
      </div>
      <div class="card">${days(web.series.map((s, i) => ({ day: s.day, web: s.visitors, app: app.series[i] ? app.series[i].active : 0 })), { key: 'web', name: 'website visitors' }, { key: 'app', name: 'app users' })}</div>

      <h3 class="sub">Fans · votes and predictions</h3>
      <div class="kpis">
        ${kpi(num(v.round.today + v.mvp.today + v.play.today), 'votes today', '', `${num(v.round.last_7d + v.mvp.last_7d + v.play.last_7d)} in 7 days`)}
        ${kpi(num(v.predictions.today), 'predictions today', '', `${num(v.predictions.last_7d)} in 7 days`)}
        ${kpi(num(v.round.total), 'player of the round · all votes')}
        ${kpi(num(v.mvp.total), 'phase MVP · all votes')}
        ${kpi(num(v.play.total), 'play of the week · all votes')}
        ${kpi(num(v.predictions.total), 'predictions · all')}
      </div>
      <div class="card">${days(m.votes.series.map(s => ({ day: s.day, votes: s.round + s.mvp + s.play, picks: s.predictions })), { key: 'votes', name: 'votes' }, { key: 'picks', name: 'predictions' })}</div>

      <div class="tgrid" style="margin-top:12px">
        <div class="card"><h3>App: platform (30 days)</h3>${list(app.platforms, r => ({ android: '🤖 Android', ios: '🍎 iPhone' }[r[0]] || esc(r[0])))}
          <h3 style="margin-top:14px">App: version (30 days)</h3>${list(app.versions, r => esc(r[0] || 'unknown'))}</div>
        <div class="card"><h3>Notifications: what phones get</h3>${list(Object.entries(push.levels), r => ({ all: 'Everything', team: 'Their club only' }[r[0]] || esc(r[0])))}
          <h3 style="margin-top:14px">Topics switched on</h3>${list(Object.entries(push.topics), r => ({ results: 'Results', news: 'News', votes: 'Votes' }[r[0]] || esc(r[0])))}
          <h3 style="margin-top:14px">Language</h3>${list(Object.entries(push.langs), r => ({ fr: '🇫🇷 French', en: '🇬🇧 English' }[r[0]] || esc(r[0])))}</div>
        <div class="card"><h3>Notifications: club only, by club</h3>${list(push.teams, r => esc(r[0]))}</div>
      </div>
      <p class="mut small" style="margin-top:12px">Server numbers are sampled inside the app once a minute (kept 14 days per minute, then 400 days per hour). If this page does not load at all, the app itself is down: the GitHub “Uptime” check emails you when the site stops answering.
        App users: the app says once a day that it was opened, with its random id (stored only as a hash), the platform and its version; one install = one id, so a reinstall counts as new. Older app builds that do not send it are not counted.
        Votes from the app and from the website are counted together. Nothing here identifies anyone.</p>`;
    box.querySelectorAll('[data-range]').forEach(b => b.onclick = () => { range = b.dataset.range; load(); });
  }

  function open() {
    load();
    clearInterval(timer);
    timer = setInterval(() => { const tab = $('#tab-monitor'); if (!tab || tab.hidden) { clearInterval(timer); return; } if (!document.hidden) load(); }, 60000);
  }
  window.loadMonitor = open;
})();
