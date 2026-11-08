# Tunisia Basket

Web app that reads FIBA box-score PDFs from a public Google Drive folder, turns them into
player stats, rates every performance and names the MVP. Fully free: no paid API needed.

## Run
```bash
brew install tesseract                      # free OCR engine, only needed for scanned PDFs (Ubuntu: apt install tesseract-ocr)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py new-token        # creates your admin token (shown once)
.venv/bin/python app.py                     # http://localhost:5055  (first run copies seed/ into data/)
```
Tests: `.venv/bin/python tests/run_all.py`.
The app checks the Drive folder every 10 minutes (`SYNC_INTERVAL_MIN`) and adds new PDFs; the
"Sync" button does it on demand. Another folder: `DRIVE_FOLDER_ID`. Season start (for last-resort dates): `SEASON_START`.
Upload files by hand (PDFs, images, ZIPs) in the admin tool: `/admin`.

## How a PDF is read (extractor.py)
1. PDF has a text layer -> `text_parser.py` (exact).
2. Scanned image -> `ocr_parser.py`: Tesseract on every table cell, 3-10 reads voted, then repaired with the
   box score's arithmetic (REB=OR+DR, PTS=2*2P+3*3P+FT, column sums = Totals, EF, and sum(+/-) = 5 x margin).
3. `validate.py` re-checks everything. A game that fails goes to `data/review/` (visible in the admin tool) and is NOT shown in the app.
Check OCR accuracy any time: `.venv/bin/python tests/test_ocr.py`.

## Ratings (stats.py)
PIR = PTS+REB+AST+STL+BLK+FD - missed FG - missed FT - TOV - fouls. Rating 0-99 = 45 + 2.5 x PIR.
Game MVP = best PIR (+2 if the team won) among the WINNING team's players. Season MVP = best average among the top 4 teams' players who played at least 70% of their team's games (the NBA rule; the same rule decides who appears in the league leaders).
Players are identified by team + jersey number, so spelling differences between PDFs don't split them.

## Official data (data/official.json)
Federation results for matchdays 1-11 and team names. The standings page is computed from it (2 pts win, 1 pt loss)
and it is the source of truth for scores: a box score whose total differs keeps its player stats but shows the
official score plus a note. Game MVP = best player of the WINNING team. Season MVP = best average impact among
players of the top 4 teams (`MVP_TOP_TEAMS` in stats.py). Add new matchdays to `results` in that file.

## Admin tool (http://localhost:5055/admin)
Drop box-score PDFs (several at once, multi-page ok), box-score images, federation "Score Final" result images,
or a ZIP containing any of those. Each file is converted to JSON with the same code as the Drive sync
(text layer -> exact, scan/image -> Tesseract) and shown for review: consistency checks, the matching official
result, duplicate warnings, an editable matchday/date and the raw JSON. Nothing is saved until you press Save:
- box score -> `data/games/<id>.json` (optionally also adds the official result for its matchday)
- result image -> `data/official.json` (editable table; the matchday is read from the header)
- "Needs review" lists games the Drive sync could not verify so you can fix and approve them.
Uploaded originals are kept in `data/uploads/`.
Result images use `assets/digit_templates.npz` (digit shapes learned from the 11 labelled images; retrain with
`python tools/train_digits.py` after adding labelled images). Tests: `tests/test_results_images.py`, `tests/test_ocr.py`.

## Security (auth.py)
Only the admin can upload, save data or run a sync; everything else in the app is read-only for visitors.
- Set or rotate the admin token: `python manage.py new-token` (shown once; only a salted scrypt hash is stored in
  `data/admin_token.json`, mode 600). Hosting platform? set `ADMIN_TOKEN` in the environment instead.
- Log in at `/admin`: the token is exchanged for a session in an HttpOnly, SameSite=Strict cookie (Secure on HTTPS,
  8 hours). The Sync button in the app only appears for a logged-in admin; `POST /api/sync` and every `/admin/api/*`
  call return 401 without a session.
- 5 wrong tokens from one address in 10 minutes -> locked out for the rest of the window. Cross-site requests are refused.
- Every login, upload, save and sync is written to `data/admin.log` (`python manage.py log`).
- If you put the app on the internet, serve it over HTTPS (reverse proxy such as Caddy/nginx or the host's HTTPS);
  over plain HTTP anyone on the same network could read the token while you log in.

## Teams and calendar
`/#/team/<CODE>`: standing, match history (click a match for its stats; matches without a box score show the
result only), next matches and players. `/#/planning`: matchdays J12-J22. Until the official calendar is known it is
PROJECTED as the mirror of phase 1 (same order, home/away swapped). To use the real one, create `data/fixtures.json`:
`{"fixtures": [{"matchday": 12, "home": "CA", "away": "ESG"}, ...]}`. Results for J12+ added in the admin replace their fixtures.

## Deploying
How it fits together, and how to set up a new server from scratch: `deploy/DEPLOY.md`.
Production runs `gunicorn -c gunicorn.conf.py app:app` (one worker on purpose) behind Caddy and Cloudflare.

## Repository layout
`app.py` web app and API · `stats.py` ratings/MVP/standings/planning · `auth.py` admin security · `admin.py` upload tool ·
`extractor.py`, `text_parser.py`, `ocr_parser.py`, `results_parser.py`, `validate.py` PDF/image readers · `drive_sync.py` Google Drive sync ·
`config.py` all file paths · `static/` pages · `assets/` digit templates · `seed/` starting data (copied into an empty data folder on first run) ·
`data/` live data (git-ignored; move with `DATA_DIR`) · `tests/` checks (`python tests/run_all.py`, `bash tests/test_release.sh`) ·
`deploy/` server scripts · `.github/workflows/` CI, Deploy (with approval), Rollback.

## Court maps and positions
- **Team page:** a half court with the team's five most-played players (by total minutes), placed by position.
- **Match page:** a full court with both starting fives, then the bench and the full stat sheet.
- The marker number is selectable (rating, points, rebounds, assists, steals, blocks, PIR, minutes, +/-, shooting %); its colour is the rating tier.
- **Positions are inferred**, because box scores do not list them: a "bigness" score from rebounds, blocks, assists, steals and three-point share
  per 36 minutes, turned into a percentile (PG ... C). The five players of a lineup are arranged PG, SG, SF, PF, C in that order, so every spot is used once.
  Corrections made in the admin tool (Player positions) are stored in `data/positions.json` and always win.
- **Light / dark mode:** the sun/moon button in the header; the first visit follows the device setting and the choice is remembered.

## Search engines (SEO), languages and logos
- **Real URLs**, one per page, in two languages. **French is the default** (no prefix): `/equipe/CA`, `/joueur/ca-24-omar-abada`, `/match/<id>`, `/classement`, `/calendrier`.
  English lives under `/en/`: `/en/team/CA`, `/en/player/...`, `/en/game/...`. Older addresses (`/fr/equipe/CA`, `/team/CA`, `/#/team/CA`) redirect to the current ones.
- For every URL the server sends what crawlers need **before any JavaScript runs** (`seo.py`): its own `<title>` and description, canonical and
  `hreflang` links, Open Graph / Twitter cards (the share image is `static/img/og-image.jpg`), JSON-LD (WebSite, SportsTeam, Person, SportsEvent) and a plain
  HTML version of the page with real links. The app replaces that content when it loads.
- `/sitemap.xml` (every team, player and game in both languages, with `hreflang` pairs) and `/robots.txt` are generated from the data. `/admin` is `noindex`.
  Canonical links use the address the visitor used; set `SITE_URL=https://yourdomain` to force one.
- After deploying, submit `https://yourdomain/sitemap.xml` in Google Search Console and Bing Webmaster Tools (verify the domain with a DNS TXT record in Cloudflare).
- **Languages:** French (default) and English, chosen with the selector in the header (remembered: a visitor who picked English lands on `/en/`; search engines and deep links are never redirected). Texts live in the
  `FR` dictionary, `SENT` sentence builders and `META` titles at the top of the script in `static/index.html`, and in `T` in `seo.py`.
  `tests/test_i18n.py` fails if a string has no French translation. To add a language, add it to `LANGS`/`SLUGS` (seo.py), to `parsePath` in `static/index.html`, and to the dictionaries; `DEFAULT` in seo.py and in the script sets the main language.
- **Brand:** `static/img/` (logo, favicons, app icons, share image), `static/site.webmanifest`; the original artwork is `assets/brand/logo-source.jpg`.
- **Team logos:** the clubs' own logos are in `assets/team-logos-src/<CODE>.<png|jpg>`. `python tools/build_team_logos.py` crops each to its real content, removes
  non-white backgrounds, scales every logo to the same size and centres it on a round white badge: `static/img/teams/<CODE>.png` (256 px).
  To change a logo, replace its source file and run the script again. The logos belong to the clubs.

## Phase MVP: stats race and fan vote (mvp.py)
Page `/course-mvp` (`/en/mvp-race`). A phase is 11 matchdays (phase 1 = J1-J11). Candidates are the players of the top 4 teams who played at least 70% of
their team's games in the phase. Two separate things:
- **Stats race**: every candidate ranked by average impact over the phase (PIR + 2 per win), with a chart of each leader's running average after every matchday.
  It shows the best player so far and decides nothing.
- **Current MVP**: the crowned player, else the player with the most votes, else (no votes yet) the stats leader. It is the banner of the MVP page and a card on the home page,
  which also names the best player by stats when that is someone else. The MVP page's list is ordered by votes first (only the three on the ballot can have any), then by stats.
  On the page the current MVP is the banner at the top, the three ballot players sit under it, then the top-10 list; the stats-race chart is folded under the list and opens on click.
- **Fan vote**: fans choose among the best 3 of the stats race, at most one player per club (the best of each club, walking down the stats ranking); the list shows those three first, then everybody else by votes and stats. The three names freeze at the first vote and change only from the admin MVP tab (never touching a vote): see `deploy/DEPLOY.md`, "Changing the MVP ballot without losing a vote". **The phase MVP is decided by the votes alone** (most votes; a tie goes to the better stats; if nobody
  voted, the stats leader). One final vote per browser (a random code in the browser's storage, kept only as a hash), at most 8 browsers per network, crawlers refused.
  Stored in `data/votes.db` (mode 600); no address or browser string is saved. There are no accounts, so a determined person can still vote from several browsers
  or phones: treat the result as a popularity vote, not an audit.
Voting has a **deadline** (phase 1: Wednesday 11 November 2026, 12:00 Tunisian time, set in `assets/mvp_awards.json`; change it in the admin panel, tab MVP, which
saves to `data/mvp.json` and wins over the repo file). Nobody is crowned while voting is open. When the deadline passes (or the admin closes voting) the most-voted
player becomes the phase MVP automatically; the admin can also crown a player by hand. The per-network cap uses the visitor's real address (`CF-Connecting-IP`, or
the proxy's forwarded address), not the proxy's.

**Photos.** Every player shows a round avatar (players list, player page, MVP race): the photo when there is one, otherwise a neutral silhouette
(`static/img/players/generic.svg`) with the team badge. Three photos ship with the code (`static/img/players/<id>.jpg`, `assets/player_photos.json`). The others are
added from the admin panel, Players tab, 📷 on the player's row: the browser crops a square and the server stores it in `data/photos/` (outside the code, so deployments
never touch it; listed in `data/player_photos.json`, included in the backups). Publish only photos you have the right to use.
**Preview photos (local only).** `python tools/import_photos.py` imports every image dropped in `exports/photos_inbox/` (named by player id, `esg-41.jpg`, or by name, `Firas Lahyani.jpg`)
the same way, and `python tools/photo_sources.py` lists search links for every player. Both write into `data/` and `exports/`, which git ignores and deployments never copy, so such photos
stay on this computer until you decide otherwise: use them to show players a preview and ask for their consent first.
To let players see them on the live site: `python tools/upload_photos.py --site https://tunisiabasket.com` (asks for the admin token; `--dry-run` lists first). It sends the photos through the
admin panel into the site's own data folder: never into git (the repository is public, so a committed photo stays in its history), kept across deployments, included in the backups.
`--remove` takes every uploaded photo down again, for example if a player does not consent.
**Match predictions.** The Predictions page (`predict.py`, `/pronostics`, `/en/predictions`) lets everybody pick the winner of each game of the next matchday: one final pick per game and
browser, closing when the matchday's date starts (Tunisian time, nothing to set). What the crowd thinks is shown as percentages only (never counts or totals) and only for the games
the visitor has picked; the server enforces it. The admin MVP tab shows the real counts. Picks live in `data/votes.db` with the MVP votes, and the database refuses to change
or delete any vote or pick (SQLite triggers), so nothing can erase them after a deployment.
**Backups.** Votes, visits, games and settings are backed up nightly (kept 7 days, then one a month) and the votes and visits every 6 hours when something changed (kept 2 days), verified and restorable (`tools/backup_data.py`, `python manage.py backup`,
`deploy/DEPLOY.md` > Backups).

## Home page: next games banner (assets/calendar.json)
The banner at the top is a carousel of the next games (up to 12, one at a time, moving every few seconds; arrows, dots and swipe also work). The pairings come from the
calendar (`stats.planning()`; for J12-J22 the mirror of phase 1, which matches the games already published) and the dates from `assets/calendar.json` (the federation
calendar; `data/calendar.json` can override single dates). Clicking a game opens a comparison built from the games played so far (`/api/matchup`): record, standing,
scoring, shooting, rebounds, assists, steals, blocks, turnovers, form, the previous meeting and the key players. The "best player so far" card and the fan-vote card sit
below it.

## Home page, games, results and news (admin tabs 📅 Games and 📰 News)
- **Home**: the next matchday's banner (featured games first by rank, with kick-off time and a ⭐ badge), the latest news with their label, the latest games (box scores and results typed by hand,
  updated the moment they are saved), and the Facebook contact card. Standings and the MVP race have their own pages; the league leaders are at the top of the Players page.
- **📅 Games**: per game a kick-off time, its own date (only if it is not on the matchday's date) and a featured rank (1 first). *Enter result* writes the official result (standings,
  calendar and latest games update at once) with an optional note and up to four stat lines; a full box score uploaded later takes over. Files: `data/schedule.json`, `data/result_notes.json`.
- **📰 News**: a title, text, a label (Official, Injury, Transfer, Result, Info, Interview), a date, pin on top, and an optional English version. Shown on the home page (latest four) and on the
  News page (horizontal cards, a lead story, filter by label, “Read more”). Each item can carry a player (photo + club badge) or a club logo as its picture.
  **🖼 Facebook image** (on each item, or from the form before publishing): a ready-to-post PNG (portrait, square or wide, French or English) and the post text to copy. File: `data/news.json`. All three files live in the data folder: kept across deployments and in the backups.
- **Facebook**: the page link is in the footer, on the home page and the news page, with a discreet invitation to send missing box scores (footer line, and under results without a box score).

## Admin: players, rosters and images

> **Roster facts that ship with the code** live in `assets/roster.json`: `merges` (one person printed under several numbers or spellings on the federation sheets), `renames` and `transfers`.
> They apply on every copy of the site as soon as it is deployed. The admin's own changes stay in `data/roster.json` and are added on top; the admin never copies the shipped ones into it.
Two more tabs in the admin panel (`/admin`).
**👥 Players**: per team, edit height, weight and birth date (saved in `data/players_info.json`, which overrides `assets/players_info.json`; a typed value is
official and drops the "estimated" mark; an empty field clears it). **Add a player** for a new signing with no box score yet (he shows on the team and Players
pages with zero games and is not ranked; real statistics take over once a box score has the same team and number). **Delete** hides a player from the whole site
(rankings, leaders, MVP race, pages) but keeps every box score, and **Restore** brings him back. **Rename** changes how a name is shown. **Transfer** marks that a
player moved: the site shows him in the new team (keeping his history and a "Transfer CA → JSK" line on his page); box scores that later appear under the new
team and number are linked to his profile automatically; if a different profile with games already uses that number you must tick "same person" to merge them.
Transfers can be undone. All of this lives in `data/roster.json` and is audited in `data/admin.log`.
**🖼️ Images**: draws 1080 px PNGs in the browser (nothing is uploaded) from the live numbers, in French or English: player vs player, team vs team (record, scoring,
shooting, rebounds, assists, steals, blocks, turnovers; team shooting figures come from the box scores we have), the MVP race, and the league leaders (one
category as a top 5/10, or the top 3 of every category in one image).
**Facebook images by matchday** (same tab, `static/admin-matchday.js`, data from `/admin/api/matchday`): pick a matchday, then the results (with each game's MVP), the standings after it with
the moves since the previous matchday (▲ ▼), the best players of the matchday on any stat (rating, points, rebounds, assists, steals, blocks, threes, +/-), the game MVPs, a game sheet
(the score, then both teams' players ranked by the stat you choose), the next matchday's programme, and the fans' predictions (percentages only). Each image comes with a ready-to-paste
post text that ends with a question, to get people commenting (French or English, with the hashtags).

## Visitor statistics
The site counts its own visits, privately: no cookies and no IP address stored (`traffic.py`). Each page view records the page, the country
(Cloudflare's country header: it appears as soon as the DNS records are Proxied, no firewall step needed), the referring site, the device type and the language, plus a visitor code
that is a daily-changing hash (so people are counted once per day and cannot be traced). Crawlers and the admin's own visits are ignored. The numbers
Besides the daily code there is a second, **returning-visitor code**: a random id the browser keeps, stored only as a hash and never derived from the address.
It tells a new person from one who comes back (new = came on one day, returning = 2+ days). It is one browser, not one human: a phone and a computer count twice and
clearing the browser data makes someone look new. The numbers are in the admin panel, tab **Traffic** (today, online now, 7/30/90/365 days, countries, pages, referrers, devices). They live in `data/traffic.db`
and are kept 400 days. For a second opinion, Cloudflare's free dashboard (Analytics & Logs > Traffic) also shows requests and bandwidth.

## Licence
The source code is released under the **MIT licence** (`LICENSE`). The licence does not cover the Tunisia Basket name and emblem, the club names and logos
(they belong to their owners), or the data from the federation: see `NOTICE.md`. Open-source libraries keep their own licences.

## Getting found on Google (what the code does, and what only the owner can do)
- **Code**: crawlable server-side pages in French and English with hreflang, a sitemap (players, teams, games), per-page titles/descriptions that start with the search words
  (“Tunisian Basketball Stats…”, “Basket tunisien…”), structured data (WebSite with its other names, Organization with a square logo, SportsTeam, Person, SportsEvent), and the icon set:
  `tools/make_favicons.py` rebuilds `favicon.ico` and `img/favicon-{16,32,48,96,192}.png` from the emblem of the logo (the full logo’s text is unreadable at 48 px).
- **Owner, once** (Google Search Console, free): add `https://tunisiabasket.com` as a property (DNS record at the domain), submit `https://tunisiabasket.com/sitemap.xml`, then use *URL inspection →
  Request indexing* on `/`, `/en/`, `/classement`, `/joueurs`. The search-result icon is refreshed only when Google re-fetches the home page: it can take days to weeks.
  Do the same in Bing Webmaster Tools (it also feeds DuckDuckGo and others).
- **Ranking** depends mostly on other sites linking to yours: link to tunisiabasket.com from the Facebook page (About / website field), clubs’ pages and groups, forums, sports bloggers,
  anyone who shares a player’s stats page. Fresh content (results and box scores soon after each matchday) also helps.
