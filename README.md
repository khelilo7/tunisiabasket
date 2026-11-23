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
Players are identified by team + jersey number, so spelling differences between PDFs don't split them. When numbers change (phase 2 re-registered many players) see "Jersey numbers" below.

## Jersey numbers that change (roster.json `numbers`, admin Players tab `#`)
The sheets print a number, not a person, so a player who changes number, or a newcomer who takes the number of somebody who left, would be mixed up with the number's old owner (his games, his name). A **number rule** settles it: *from `from` to `to` (both optional, inclusive), number N of team T on the sheets is the player `id`*. Rows it covers take that player's id and name and **take no part in naming anybody else**, so nobody's past statistics move.
- **Change a player's number:** Players tab, `#` on his row, new number and the date of the first game with it (a game of 11 Nov: 2026-11-11). His statistics and profile stay; the number he leaves is free.
- **Add a player on a number somebody wore:** delete the old player first (🗑: a deleted player wears nothing, his number is free at once; a signing who never played is removed completely), then "Add a player". The newcomer gets an id of his own (`usm-108` for a second #8) and a rule from the date you give, so the old player keeps his games.
- The rules made in the admin are in `data/roster.json` (listed under "Number changes", with Undo). Rules that ship with the code, like the phase 2 corrections of J12, are in `assets/roster.json` (`numbers`) and apply on every deploy.
- **A game printed with the wrong day** (the scoreboard clock): `POST /admin/api/game-date {"id": ..., "date": "YYYY-MM-DD"}` writes `data/game_dates.json`; `assets/game_dates.json` ships corrections with the code (J12 ESR-CSS and JSM-USA are 11 Nov, not 10).
`tests/test_numbers.py` checks all of this.

## Official data (data/official.json)
Federation results for matchdays 1-11 and team names. The standings page is computed from it (2 pts win, 1 pt loss). The order is the FTBB's law, written out in `ranking.py` (General Regulations of 10/08/2024, articles 182 to 184 and 194; link in the footnote of every table), **applied only once the phase is over** (every game of the double round-robin has a result: `ranking.complete()`); while the phase is being played the table is ordered by the points, then by the point difference of all the games (`ranking.provisional()`), and every row carries `final` (false until the last round; the footnote then says so). Once it is over: points first; teams level on points are separated by the point difference of the games between them (two teams), or by a second table with only the games among them (three or more), then the goal average (a division) of those games, then the point difference of all the games; a pair left over starts again. A result may carry `"forfeit": CODE` (that team loses 0 point and ranks last among the teams level). Test: `tests/test_tiebreak.py`
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

## One-team sheets (assets/partial_games.json)
Sometimes the only record of a game is a hand-kept sheet for ONE team (no minutes, turnovers, fouls, +/-, nothing for the opponent): J1 ES Goulette 68-80 Club Africain is one.
It is **not** a full box score: it is listed in the games list as "Partial box score", counts in the team's "Box scores" column and has its own match page (linked from the two teams' pages), but it never enters the standings, the team averages or ratings, and its game MVP is chosen among the winning team's recorded players by PIR without turnovers and fouls (unknown for everyone), then points; a sheet of the losing team has none.
Each player listed gets one row in his game log, and his averages (player page, leaders, MVP race) count it for points, rebounds, assists, steals, blocks and shooting; the race still ranks by PIR and impact, which come only from the games where they are known. Anything the sheet does not give (minutes, turnovers, fouls, +/-, PIR, rating) stays **unknown, never 0**, and
is averaged over the games where it is known. If a real box score of the same game is uploaded later, it replaces the sheet automatically (no double counting).
To add one: a game in `assets/partial_games.json` (id, matchday, home, away, `recorded` = the team on the sheet, date, players with number, name and the counted stats; attempts only
where the sheet proves them) or in `data/partial_games.json` (live data). It is ignored unless an official result for that matchday and pair exists. `tests/test_partial_game.py` checks all of this.
A sheet can also cover only SOME players (e.g. one player's own spreadsheet, like Abbassi's J1, J3 and J4 for CS Sfaxien). It is *incomplete* when its players' points do not add up to the official score of the team: it then has no team total, **no game MVP** and does not count in the team's "Box scores" column. A player may carry `"est": [...]` (any of fgm, fga, p3m, p3a, ftm, fta, ast, stl, blk, tov, pf) for values that are NOT on the sheet but estimated (his average in his full box scores, adjusted so that 2 x 2P + 3 x 3P + FT = points): they are shown with a `~` and a tooltip on the match page and in his game log, and his averages include them. Points and rebounds are never estimated. `tests/test_partial_estimates.py` checks this.

## Box scores compiled from a video (`video_sheet.py`)
A full two-team box score typed up from a TV broadcast ("FULL TIME ... (from video).pdf", compiled by Tunisia Basket; J1 ESS 77-62 SN, J3 ESS 74-69 DSG and J9 ESS 68-58 JSM are the first) is a **normal box score**: standings, averages, leaders, ratings and PIR count it. It is stored with `"source": "video"`, so the match page carries a banner ("Compiled from the broadcast video": minutes and +/- are estimates), and a real box score of the same game (text layer or OCR) **replaces it automatically**.
The admin upload recognises these PDFs (they carry "Compiled by Tunisia Basket" / "(from video)") and reads them exactly: matchday from "Journée N", no date on the sheet so the matchday's date is used (approximate, so not shown). The "Player unknown" and "Team/Coach" rows (shots whose shooter could not be identified, turnovers, team rebounds) are not players: they are kept on the team as `not_attributed`, never in a profile, so a team's totals on the site are the sum of its named players. If that row carries points (J1: 2 free throws the video skipped), the points check counts them (`not_attributed.pts`): named players + unnamed = the official score, otherwise the game is refused.
To add one by hand: `python tools/send_games.py --site https://tunisiabasket.com` sends the JSON files of `exports/games_inbox/` (here `video-j1-ess-sn.json`, `video-j3-ess-dsg.json`, `video-j9-ess-jsm.json`; files already sent are moved to `exports/games_sent/`). `tests/test_video_sheet.py` (fixtures `tests/fixtures/video_ess_*.pdf`) checks all of this.

**Round sheets "Final: video analysis"** (`FIBA Box Score JSK vs ESR (final).pdf`, J13 JSK 69-60 ESR is the first) have another layout (the OCR cannot read it): `python tools/video_analysis_sheet.py SHEET.pdf --date YYYY-MM-DD` reads the columns by position (blank = 0; minutes `~31`; attempts are lower bounds; +/- and EF are not on the sheet, +/- is stored as 0), runs the same checks and writes `exports/games_inbox/video-jN-<home>-<away>.json`; then `python tools/send_games.py --site https://tunisiabasket.com video-jN-....json` (only that file). Stored as `source: "video"`, so a real box score replaces it later. As soon as a game has a full box score on the site, analysts can no longer start it (video list or live): `POST /analytics/api/games` answers 422. Test: `tests/test_video_analysis_sheet.py`.

**Cup and play-off / play-out (prepared, shown with demonstration data).** `cup.py` (`data/cup.json`, admin tab 🏆 Cup): the Coupe is a single-game knockout of Pro A and Nationale 1 clubs (plus any club added for it); the admin pastes the first round (`HOME, AWAY[, date]`, `BYE` for a club that waits) and the whole bracket to the final is built, every round filling itself as results come in. The page `/coupe` (`/en/cup`) draws a bracket with connectors on a computer and a round-by-round list on a phone, tags each club Pro A / N1, flags **upsets** (a lower division beating a higher one) and crowns the winner. `finals.py` (`data/finals.json`, admin tab 🔥 Play-off/out): the six best clubs play the play-off, the six others the play-out. **Format as announced (not yet confirmed for 2026-27, the page says so):** play-off = mini-league of six, home and away, with the regular-season points carried over; its first four (`qualify`, 4) go to the **super play-off**: semi-finals 1st v 4th and 2nd v 3rd, then a final, each a **best of five** (first to three wins; the better ranked club hosts games 1, 2 and 5; the admin button *Set up the super play-off* builds it; its sides are `S:playoff:N`, shown as provisional seeds until the play-off is over); play-out = mini-league of six, the last two (`relegation`, 2) go down to the Nationale 1. Both numbers are settings, so a different regulation is one click away. There are three groups (`playoff`, `super`, `playout`); each is a **league** (table, regular-season points carried over none / half / all, ▲▼ places gained) or a **series** bracket (best of 3/5/7, dots for wins, "qualified" / "in progress"). The page `/playoff-playout` has three tabs, **🔥 Play-off**, **🛟 Play-out** (each stands alone) and **📜 Regular season**: the Play-off tab is ONE page with its two stages side by side (① mini-championship table, ② super play-off bracket with every game's score under its series; on a phone a two-step switch that opens on the stage in progress), (the old Phase 1 / return leg / finals / Cup ribbon is gone; `/api/finals` still sends `journey`). **Carry-over:** the table has a *Report* column and a small note under it explaining that each club keeps the points of its regular season (2 per win, 1 per loss) and adds those of the games played in the group (`carry` setting: full / half / none; the 2025-26 tables show full carry-over, e.g. 28 points after six play-off matchdays). The page also shows the history. , the history that stays visible: the final table with its zones and a **race chart** (rank after every matchday, click a club to follow it; `/api/rank-history`). A **Pro A | National One | 🏆 Cup** switch sits above the tabs, and a 🔥 tab appears in the Pro A tabs once the finals are set up (`/api/competitions`). **Once a play-off or play-out game has been played** (`started` in `/api/finals` and `/api/competitions`) the 🔥 Play-off · Play-out page TAKES THE PLACE of the championship standings: the first tab becomes 🔥, and `/classement` shows it too; the regular season stays under its *Regular season* tab (final table and race chart). The page only draws the latest navigation (`routeSeq`), so a slow earlier render can no longer overwrite it. `python tools/demo_cup_finals.py` (with `DATA_DIR` pointing to a LOCAL folder) fills a demonstration (marked "demo", and it refuses to overwrite real data). Test: `tests/test_cup_finals.py`.
**Logos.** `assets/team-logos-src/<CODE>.png|jpg` are the clubs' own files; `python tools/build_team_logos.py` cleans each one (crops it, removes a non-white background) and puts it on the same round white badge: `static/img/teams/<CODE>.png`. The 11 National One clubs (AMS, ASM, BCM, BS, CAB, CAK, CBM, CSGN, EZS, JAB, SSS) are in; a club without a file shows its initials.
**Standings zones.** The six best teams are the **playoff** (green), the other six the **playout** (red): a coloured bar, a small label per row and a legend (`PLAYOFF_N = 6` in `static/index.html`); the MVP pool is only a small ★ (tooltip "MVP pool"). **Nationale 1** (`nat1.py`, admin tab 🏀 Nationale 1, `data/nat1.json`): the league below the Pro A, results only: the admin types the teams, then the results one by one or pastes a list (`matchday, HOME, AWAY, home score, away score[, date]`, all or nothing), and the site shows the table (2 points for a win, 1 for a loss) and the results by matchday at `/nationale-1` (`/en/national-one`); a switch **Pro A | Nationale 1** sits above the Standings / Games / Calendar tabs. There are no players or box scores for it yet: a player is just a name on a team, so they can be added later without changing the file. Besides teams and results the file holds the **calendar** (`fixtures`: every game with its date; a game with no score shows "to come", then "score missing" once its day has passed; a pairing that is only assumed is flagged "projected") and, optionally, the **federation's own table** (`official`): when it is there it IS the table (we may not have every score, so it cannot be recomputed), otherwise the table is computed from the results. **Promotion to the Pro A** (`FORMAT` in `nat1.py`, card "Comment monter en Pro A" under the table, source link to the FTBB): the formula published for 2025-26 is: the first 8 play the play-off (quarter-finals 1v8, 2v7, 3v6, 4v5 and semi-finals, best of three), the two semi-final winners go up to the Pro A, and they meet in a single game on neutral ground for the Nationale 1 title; places 9-12 play the Coupe de la Ligue. `confirmed` stays false until the federation publishes the 2026-27 regulation, and the card says so. **National One play-off** (tab 🔥 Play-off of the Nationale 1 page, `/nationale-1/playoff`, `/en/national-one/play-off`; `nat1.playoff()`): the bracket draws itself from the table (first eight, qf1 1v8, qf2 4v5, qf3 2v7, qf4 3v6, best of three; sf1 = winners of qf1/qf2, sf2 = qf3/qf4; the final in ONE game on neutral ground), seeds provisional until the last date of the calendar is past, the two semi-final winners shown as promoted to the Pro A, the final's winner as champion. Only the games are stored (`data/nat1.json` → `playoff.games`); admin tab Nationale 1, card *Play-off*: `GAME, qf1, HOME, hs, as[, date]` (ops `playoff_games`, `playoff_clear`). The bracket renderer (`seriesBracket`) is shared with the Pro A super play-off. Season 2026-2027 is built by `python tools/build_nat1_seed.py` (the FTBB calendar grid, the table of 15 November, the scores we know: nothing guessed) and sent with `python tools/send_nat1.py --site https://tunisiabasket.com exports/nat1_2026-2027.json`; the admin tab does the same by hand (paste a calendar, a list of results, the federation's table). **About** (`/a-propos`, `/en/about`): who we are, that it is free, thanks for the engagement. Tests: `tests/test_nat1.py`.
**Team lines (`team_extra.py`).** A federation sheet and the sheets compiled by Tunisia Basket print, under the player tables, *points in the paint, second-chance points, fast-break points, points off turnovers* and *bench points*: the parsers keep them per team
(`team["extra"]`, only the lines the sheet has). The **team page** shows them as **Scoring sources** (per game, with what the opponents scored against the team, ranked like the other team statistics, overall / at home / away, "N sheets with these lines"), the **game page** as a
side-by-side comparison. A team with no sheet carrying them shows "–", never 0. Games already on the site get them when the sheet is read again (`tools/fix_player_stat.py` keeps `extra` and `not_attributed` when it rebuilds a game). **Players:** the player page has an
**Overall / At home / Away** switch (`stats.player_splits`; every game says whether it was at home, from its official result), and the W / L of a game (player log, team history, the form chips of the matchup window) opens its box score. **Menu:** MVP and the player of the round are a tab of the **Players** section (**Players | MVP · Player of the round**, like Games and Calendar are tabs of Standings); the predictions have a page of their own in the menu (and a compact panel at the side of the **Games** page). Tests: `tests/test_team_extra.py`.
**Speed.** `stats.build()` / `build_all_games()` are cached for as long as no data file changes (30 s at most; `NO_STATS_CACHE=1` switches it off; `tests/test_cache.py` checks that no page or API call modifies the cached value). In the page, GET `/api/*` answers are kept for a minute and shared, the likely next pages (Standings, National One, Games, Players, Predictions) are fetched in advance and again when a link is hovered or touched, so switching Pro A / National One or tabs is instant; a thin bar and a dimmed page show when something is really loading. **Club window:** the first time a visitor with no club comes after a deployment, the choice window opens once (Choose / Not now / Never show this again); `FOLLOW_PROMPT` in `static/index.html` names the deployment (change it only to ask everybody again). The Games tab no longer carries a predictions panel; the tabs are 🏆 Standings · 🏀 Games · 📅 Calendar. The team page shows the **bench** (the next three by minutes) under the most-played five, and the calendar shows its dates without any "assumed" warning.
**Corrected full sheets and one-stat fixes.** `python tools/final_sheet.py "FIBA Box Score CA vs ESG 11 novembre (final).pdf" --like exports/games_inbox/hand-j12-ca-esg.json` reads a corrected French-layout box score (Tirs Tot., LF, Rebonds, Ev), keeps the game id, date and player names of the version it replaces (`--like`), runs every check (points, rebounds, FG = 2P + 3P, the printed Ev of each player, the totals line) and rewrites that file; `send_games.py` then replaces the game on the site (same id). The "Equipe/Coach" row is stored as `not_attributed` (team turnovers count for the team). `python tools/fix_player_stat.py --site https://tunisiabasket.com --game ID --team CSS --number 21 dreb=3` rebuilds a game from the live site, changes only that stat (reb = oreb + dreb), checks it and writes `exports/games_inbox/fix-ID.json` to send. `python tools/fix_from_csv.py --site https://tunisiabasket.com --game ID board.csv [--set ESS:45:blk=1] [--base fix-ID.json]` does the same from a counting-board CSV: the CSV wins for the columns it has (PTS, FG, 3P, FT, rebounds, AST, STL, BLK, TOV, PF), while minutes, +/-, drawn fouls, DNP rows and names stay as on the site; `--base` stacks it on a fix file already written. `--made-only` is for a CSV that counted only one team's made shots: makes and points come from the CSV, the site's misses stay, rebounds / assists / steals / blocks / turnovers / fouls only go up to the CSV's number, and a player missing from the site's sheet is added with 0 minutes. Tests: `tests/test_final_sheet.py`, `tests/test_fix_from_csv.py`.

**A game counted on the analyst board -> sheet + PDF.** `python tools/count_sheet.py COUNT.csv --id GAME_ID --matchday N --date YYYY-MM-DD --venue "..." --timeline-pdf SHEET.pdf [--names-from SHEET.pdf] [--set TEAM:NUMBER:field=value] [--bench 22:11] [--paint a:b --second a:b --fast a:b --turnover-pts a:b] [--poss a:b]` turns the board's CSV into the game JSON (`exports/games_inbox/GAME_ID.json`, source "claude": the same id rewrites an earlier version, for example the provisional video sheet) and into a FIBA box score PDF laid out like the federation's (`exports/FIBA Box Score X vs Y (final).pdf`; needs `pip install reportlab`, the site does not). A typed cell that contradicts the points is refused (`--set` corrects it); the 5-minute scores, largest lead, longest run, lead changes, ties and time in the lead come from the scoring timeline of a video sheet; lines nobody counted print as "-". Test: `tests/test_count_sheet.py`.

## Player of the round (`rounds.py`)
A fan vote for the best player of ONE matchday, like the phase MVP vote but per round. **The admin opens it** (admin panel, 🏆 MVP tab, "Player of the round"), and only once **every game of the matchday has its official result** and at least one game has a player of the game (a box score, or the winner's one-team sheet): the candidates are the players of the game, one per game, and the ballot is frozen when the vote opens (the admin can add the players of games whose stats arrive later, never remove anyone). One vote open at a time, with an optional deadline (Tunisian time); the admin closes it, and can **crown** a winner (otherwise the player with most votes wins once it is closed; tie: better PIR, then points; nobody if nobody voted).
Votes follow the phase MVP rules: one final vote per browser, 8 per network, crawlers refused, only hashes stored in `data/votes.db` (table `round_votes`, which refuses changes and deletions); settings in `data/rounds.json`. On the site the vote is on the MVP page, and the **home page shows it instead of the phase MVP card** once the phase vote is over (while the round is open, and for 3 days after it ends with its winner); the winners of earlier rounds are listed on the MVP page. `GET /api/round`, `POST /api/round/vote`, admin `GET/POST /admin/api/rounds`; `tests/test_rounds.py` checks all of this.

## Home banner: next games, then results (`stats.banner`)
The banner of the home page shows the games that are **going to be played next** (tap your winner to predict). **Predictions close at 12:00 (Tunisian time) on the first game day** of the matchday (`predict.CLOSE_HOUR`): from then on the banner shows the games without any prediction ("Predictions are closed") and a click on a game still gives the expected starting fives and the team stats, until the results are out. A game that has not been played stays on the banner through its own day. Once the admin has entered the results of a matchday, the banner shows them as results (final score, a link to the box score when the site has one) for **one more day** after the game date (`stats.RESULTS_DAYS = 1`), then moves on to the next matchday and its predictions. Dates are Tunisian dates; a game moved with the admin's schedule follows its own date; a game whose date has passed and that has no result yet is dropped (nothing to show). The choice is made by the server (`/api/planning` carries `banner`, never cached) and checked by `tests/test_banner.py`.

## Expected starting five and absent players (`lineups.py`, `absences.py`)
Click a game of the next-games banner on the home page: the comparison window also shows the **expected starting five** of both teams (guards first, with position, number and per-game points, rebounds, assists). It is a prediction: the five players with the highest starter score (1 point per start this season + 2 more per start in the team's last 5 games). It is **unlocked by a prediction**: until the visitor has tapped the team they think will win, the window shows a lock message (when predictions are closed, or the game cannot be predicted, it is shown anyway). To show it to everyone, set `locked = false` in `openMatchup` (static/index.html).
In the admin, **Players** tab: the 🤕 button of a player marks him as **not playing** (injured, suspended...; optional note that only the admin sees, kept with the date in `data/absences.json`); "Back in the squad" undoes it. Such a player is left out of the expected five and the next one moves up; nothing else changes (stats, rankings, profile), and the public API never exposes the list or the notes. `GET /api/lineups?home=JSK&away=USM` returns the two fives; `tools/starting_five_image.py` uses the same rule. `tests/test_absences.py` checks it.

## Teams and calendar
`/#/team/<CODE>`: standing, match history (click a match for its stats; matches without a box score show the
result only), next matches and players. `/#/planning`: matchdays J12-J22. The DATES are the federation's official ones (`assets/calendar.json`, confirmed for J11-J22).
Until the official fixtures are known the PAIRINGS are PROJECTED as the mirror of phase 1 (same order, home/away swapped). To use the real ones, create `data/fixtures.json`:
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

## Menu
An icon and a word per page (Home, Live, Standings, Players, MVP, **Predictions** (highlighted, with a red dot while there are games left to pick), News once there is some). Next to the menu: **My club** (the follow window, shows the chosen club's logo) and, on a phone, a 🎯 Predictions button; About, Analytics and Admin are small links in the footer. On a computer the language, season and theme are behind the gear; on a phone the menu is a **bottom bar** (Home, Standings, Live, Players, More) and **More** opens a sheet with MVP, Predictions, News and the same settings. The icons are drawn in `seo.py` (`ICONS`), so the menu needs no files; the red dot of Live follows `/api/live`.

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
- **Brand:** `static/img/` (favicons, app icons, share image) and `static/img/brand/` (the SVG logos: `logo-primary*.svg`, `logo-header*.svg`, `social-icon.svg`, `mark*.svg`), `static/site.webmanifest`. All of it is drawn by `tools/make_logo.py` (a basketball with the flag's disc, crescent and star; lettering in Barlow Condensed, SIL OFL, `assets/brand/fonts/`, turned into outlines so no font is loaded): `pip install fonttools uharfbuzz resvg-py pillow`, then `python tools/make_logo.py` rewrites the SVGs, the PNG / ICO / share image files and the header markup (`assets/brand/mark.svg.html`, `wordmark.svg.html`, pasted inline in the header of `static/index.html`; its red follows the theme through `--logo-red`). The earlier badge artwork is kept as `assets/brand/logo-source.jpg`.
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
  **📣 Announce a game** (top of the News tab): pick a played game, then ✍ *Write the news* (a result item filled in with the score, the game MVP’s line and a box-score link),
  🖼 *Score image* (both clubs, the score, the headline), or 📸 *Player photo image*: choose a player of that game, upload a recent photo (it becomes the background, nothing is uploaded to the server),
  type a free headline (“Homme du match”, “Il a dominé”…), tick the stat tiles, place the photo (zoom, sliders or drag), download the PNG and copy the post text.
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
**Readable numbers:** days are Tunisian days (UTC+1, the server's clock does not matter), the tab has a **day-by-day table** (visitors, page views, pages per visit, new people, a bar per day, weekends greyed, the last 14 days and "show all"), each total says
how it moved against the same number of days before, pages are shown by name (a player id becomes his name, a game its two teams), and busy hours are in Tunisia time.
**Clubs:** a visitor may, optionally, **follow a club** (window opened from the card on the home page, the star on a team page or the button in the footer; no pop-up of its own, "not now" is remembered 30 days). The choice is kept on his device (his club is highlighted
in the standings) and counted per club in `data/traffic.db` (table `follows`: one row per browser code, stored as a keyed hash, latest choice wins, bots and the admin ignored, a few changes per device and day at most). The Traffic tab's **Clubs** table shows followers,
new followers, readers and page views of each club's page and its players' pages: the answer to "which club is the most active on the site".
**Social pages** (`social.py`): Facebook, YouTube, Instagram and X appear as round brand icons in the footer and as big labelled buttons in a **Follow Tunisia Basket** card on the About page (the contact card of the home page, "a tip, a correction, a missing result?", only has a small Facebook logo) (separate from the "follow a club" choice, which has its own card and the **My club** button of the header). Their addresses are shipped in `assets/social.json` (YouTube is set) and can be changed by the admin at the bottom of the Traffic tab (`data/social.json`, which wins; https only; an empty one hides its icon, so nothing
points to a page that does not exist). Tests: `tests/test_follow_social.py`.

## Licence
The source code is released under the **MIT licence** (`LICENSE`). The licence does not cover the Tunisia Basket name and emblem, the club names and logos
(they belong to their owners), or the data from the federation: see `NOTICE.md`. Open-source libraries keep their own licences.

## Getting found on Google (what the code does, and what only the owner can do)
- **Code**: crawlable server-side pages in French and English with hreflang, a sitemap (players, teams, games), per-page titles/descriptions that start with the search words
  (“Tunisian Basketball Stats…”, “Basket tunisien…”), structured data (WebSite with its other names, Organization with a square logo, SportsTeam, Person, SportsEvent), and the icon set:
  The favicons use a simplified mark (`mark-small.svg`: one seam and a bigger flag disc), because the fine seams turn to mush at 16-48 px; the home page also links it as an SVG icon.
- **Owner, once** (Google Search Console, free): add `https://tunisiabasket.com` as a property (DNS record at the domain), submit `https://tunisiabasket.com/sitemap.xml`, then use *URL inspection →
  Request indexing* on `/`, `/en/`, `/classement`, `/joueurs`. The search-result icon is refreshed only when Google re-fetches the home page: it can take days to weeks.
  Do the same in Bing Webmaster Tools (it also feeds DuckDuckGo and others).
- **Ranking** depends mostly on other sites linking to yours: link to tunisiabasket.com from the Facebook page (About / website field), clubs’ pages and groups, forums, sports bloggers,
  anyone who shares a player’s stats page. Fresh content (results and box scores soon after each matchday) also helps.

## Analytics: counting a game by hand (/analytics)
A second role, weaker than the admin: an **analyst** signs in at `/analytics` with their own token and counts a game while watching it. Every player of both clubs is on screen
(the players of the site); one click adds a made shot (+1 / +2 / +3), a missed one (✗1 / ✗2 / ✗3), an offensive or defensive rebound, an assist, a steal, a block, a turnover or a foul.
Undo, a list of the last actions with "remove", the score on top, and a CSV of the box score. Every click is saved at once in `data/analytics/<game>.json`.
- **A name for every analyst, one sheet per name:** the sign-in asks for a **name** (compulsory) as well as the token. Every action is stamped with it (`by`), every change is written to the game's **change log** (who, when, what: added, changed A → B, removed, undone, sent, approved), and two analysts with two names each get **their own version** of the same game (`j12-ca-esg--analyst-one`, `j12-ca-esg--analyst-two`): an analyst sees only his own versions, the admin sees them all. The same token can be used by everybody; the name is what separates them.
- **Games to count from the video:** the board has a closed list "Games without a full box score" (every played game with no box score or only a one-team / some-players sheet, from every matchday). An analyst **adds to his board** the ones he wants (＋ Add to my board); the server accepts only such a game (`POST /analytics/api/games {"video": true}` is refused with 422 for a game that has a full box score or no official result). His games are listed in two groups: **current** and **from video** (a video game is never live; it is counted, sent and approved like the others).
- **Full history, editable:** under the players the page lists **every** action in game order (newest first, filter box): ✎ changes the player, the action or the time (or takes the clock off), 🗑 removes it, and "Add an action" puts one at a chosen time. Substitutions can be edited too. Minutes and +/- follow the corrected times.
- **The admin edits every version:** in the Analytics tab each version shows its analyst, its change log and "Open and edit this version" (the admin may also add to or correct a version waiting for approval; every change is logged as Admin). Only **one version of a game** is on the site (approving another version takes the first one off) and on the Live page.
- **Token:** `sudo proastats-admin new-analytics-token` on the server (or `python manage.py new-analytics-token`): shown once, only its hash is stored (`data/analytics_token.json`; `ANALYTICS_TOKEN` in the environment overrides it). It opens `/analytics` and nothing else: never `/admin`. Same protections as the admin login (lockout, HttpOnly cookie, cross-site refusal). A logged-in admin can use `/analytics` too. The page and its answers are `noindex` and `robots.txt` disallows them.
- **Nothing an analyst enters is public.** "Send for approval" (matchday and date) puts the game in the admin's **Analytics** tab, with the box score and a check against the official result. The admin approves (it is published), sends it back with a reason (the analyst edits and sends it again) or removes it from the site later.
- **Board v2 (`static/analytics.html`):** the **five on the court are listed first** (big rows, minutes and +/-), the bench is folded below (⇄ substitutes: tap it on the player who goes off or comes on). A new game opens with **"Start the game"**: the five most likely to start for
  each club (`lineups.expected_five`: starts this season and in the last games, absences left out; filled up with the most-used players), one tap on **Start** or **Change**. The **clock** is a big readout with a Start/Stop button, a quarter stepper (‹ Q2 ›, a pulsing "Next: Q3" when
  the quarter ends), −10 s / −1 s / +1 s / +10 s to match the TV clock, a typed time (tap it: 6:32 or 632) and the space bar to start or stop. **Phone:** one team at a time (two tabs with the score), the score and clock stay on screen, tap a player and use the big **action pad** at
  the bottom (+1 +2 +3, ✗1 ✗2 ✗3, OR DR AST STL BLK TOV PF); each player row shows his line (FG 3/5 · 3P 1/2 · R 4 · A 2...). **Team lines:** after a made basket a bar offers the tags **Paint** (2-pointers), **2nd chance**, **Fast break**, **Off turnover**
  (any can be changed later in the history); they build "points in the paint / second chance / fast break / off turnovers", and **bench points** come from the first five marked. The lines show under each team's name, in "Team lines CSV" (menu ⋯) and travel with the
  published sheet (`extra`). Tests: `tests/test_board_v2.py`.
- **Who is on the court (optional):** each team has a bar "Pick the five": tap the five players on the court (● on the court, ○ bench). To substitute, tap the player who comes on or goes off and choose who replaces him (two taps; "Change the five" for several at once). Each change is stamped with the **game clock** and kept as a `lineup` event (undo and remove work on it). From these the page shows every player's **time on the court** (it ticks with the clock; the clock is not started or stopped by a substitution) and his **+/-** (points of both teams while he was on). The CSV gains MIN and +/- columns, the time is counted up to where the clock stood when the game is sent, and the approved sheet carries `min` and `pm` (the site does not use them yet). A stat added for a player on the bench is counted anyway, with a hint to bring him on.
- **Live (proof of concept):** in the admin **Analytics** tab, "Being counted now" lists the games an analyst is counting; **Go live** makes one public on the site's **Live** page (`/direct`, `/en/live`) while it is being counted: score, the clock as of the last stamped action, the five on the court with time and +/-, the box score so far and the last plays, refreshed every 5 seconds from `GET /api/live` (never cached, and only those fields: nothing else of the analyst's file). The admin decides: nothing is live unless switched on, and a game stops being live when it is sent for approval. The menu shows a pulsing dot on Live while a game is on. The page is `noindex` for now.
- **What approval publishes:** two one-team sheets in `data/partial_games.json` (see "One-team sheets"): minutes and +/- stay unknown (never 0; fouls drawn too unless the analyst counted them with the **FD** button), the game never enters standings, team totals, the MVP race or the fan vote, and a real box score of the same game replaces it. It is ignored until the official result of that matchday exists. `tests/test_analytics.py` checks all of this.


## Live scores read from the Diwan Sport broadcast (`livescore.py`, `tools/live_reader.py`)
Diwan Sport agreed that the site may read the score of its broadcasts. A Mac plays the game(s) in a browser signed in to Diwan Sport, and **the reader** reads the scoreboard
graphic on the screen every 2 s (score, quarter, clock) and sends only those numbers to the site. Nothing is recorded: each capture is read in memory and dropped.
- **On the server, once:** `sudo proastats-admin new-livescore-token` (or `python manage.py new-livescore-token`): shown once, only its hash is stored (`data/livescore_token.json`;
  `LIVESCORE_TOKEN` in the environment also works). It only lets the reader send readings to `POST /api/livescore` (5 wrong tokens from one address: locked out 10 minutes).
- **On the Mac, once:** `brew install tesseract`, the repository with its `.venv`, and the **Screen Recording** permission for the app that runs the reader (System Settings >
  Privacy & Security > Screen & System Audio Recording; quit and reopen that app after switching it on).
- **Match day:** open each game on diwansport.com, big enough to read (half a screen per game is plenty; two or three games side by side work), keep the scoreboard visible
  (no window on top of it), then run `.venv/bin/python tools/live_reader.py --token XXXX-XXXX-XXXX-XXXX` and leave it running. It finds every scoreboard on the screen by its
  colours, reads the team codes on it (or `--teams ESS-DSG`), and prints each score it sends. The calendar gives the matchday and which club is at home (`--matchday N` if it cannot).
- **Filters:** the reader sends a score only when two captures agree; a score never goes down, except a correction seen for 10 s; a jump of more than 6 points is a misread unless
  the scoreboard was away a while (started mid-game, replays, a dropped stream: then three captures must agree). The server refuses again a lower score or a jump of more than 8,
  except after a gap. The final is sent at 00:00 in the 4th quarter or an overtime, or when the broadcast cuts away in its last 5 seconds with the scores not level; if play goes on
  the game opens again.
- **What fans see:** the game on the **Live** page of the site and the app (score, quarter, clock, the score changes, biggest lead, longest run, head to head), marked
  "Score read automatically from the broadcast"; it leaves the page 15 minutes after the last reading, or 45 minutes after the final. An analyst counting the same game wins.
- **Taking a game off Live:** stopping the reader (the app's Stop, closing its Terminal window, Ctrl-C) takes its games off at once (`POST /api/livescore/stop`). To take
  off one ended game and keep reading the others: the app's **Remove a game…** (also offered when the reader is stopped and a game is still on Live), or
  `~/TunisiaBasketLive/games.sh list` then `games.sh remove <id>` (`live_reader.py --live` / `--remove ID`). A removed game comes back only when the game moves on (a basket,
  a new quarter, the clock running), not for a window still showing the final score. Readings without a matchday join the game already on Live between the two clubs (its
  final puts the result in the calendar, which no longer offers that fixture).
  **Pushes:** the end of each quarter to the phones that follow one of the two clubs, the final score to every phone with results on (same key as the official result, so it
  is sent once). The official result and the box score still come from the admin.
- **Test on a recording:** `.venv/bin/python tools/live_reader.py --file "Diwan Sport(1).mp4" --start 3700 --show --matchday 14 --server http://localhost:5055 --token ...`
  plays the video in a window and reads it in real time, with no screen permission needed. Tests: `tests/test_livescore.py`.

## Announcing the play-off, sources of a game, analytics, honours (November 2026)

- **Nothing changes until the admin announces.** `finals.json` has an `announced` flag (Admin → 🔥 Play-off/out → *Announce: the play-off and the play-out start*) and `nat1.json` a `playoff_on` flag (Admin → Nationale 1 → Play-off card). Until then the public site is unchanged however much is prepared: no Play-off tab, the championship standings stay, `/playoff-playout` and `/nationale-1/playoff` only say they start at the end of the regular season (the admin looks at them with `?preview=1`). From the announcement the 🔥 page takes the place of the championship standings (the regular season stays under its tab). `/api/competitions` carries `finals`, `started`, `nat1_playoff`. The Cup is not gated (an empty bracket says "draw soon").
- **Sources of a game** (`game_sources.py`, `admin_sources.py`, Admin → 🔀 Sources, `data/game_sources/<id>.json`): every version of a box score sent for a game id is kept as a source (the first resend also keeps the published one as "published before"). The admin compares them player by player and stat by stat, then publishes one source or a MIX (base + picks `TEAM|NUMBER|stat`, `TEAM|NUMBER|*` = on the sheet or not, `TEAM||points`); the result goes through `validate()` (422 + problems, "publish anyway" forces). A chosen game is LOCKED: a later push (`tools/send_games.py`) only adds a source flagged "new" and says so; unlock to publish the latest again. Two files that look like the same game (same teams, same matchday) can be attached as sources of one. Test: `tests/test_game_sources.py`.
- **Pictures:** the next-matchday and fans' pictures print each game's kick-off time (and its own day when it differs) when the schedule has one (`/admin/api/matchday` → `next.games[].time/date`), and the caption lists the programme.
- **Analytics:** the "games to count from the video" list and the video games are gone. Any game of any round (first phase included) can be opened from the board's matchday picker to edit it; an old game (it has an official result, or its date is past) is flagged `old` and is never live (`/admin/api/analytics/<id>/live` answers 409, `live_games()` skips it).
- **Honours** (`honours.py`, `assets/honours.json`): a small line on a team page (Tunisian championship and Cup titles, with the seasons in a tooltip) and a side note for an African Champions Cup or BAL title and for a lost final (runner-up) of those two, plus the Arab Club Championship and the Maghreb Championship (wins and lost finals; third and fourth places are never shown; only JSK's 2003 Maghreb title could be verified, no list of editions exists online); the league and Cup list only wins, years are season ends (2026 = 2025-26). Source: Wikipedia palmarès pages (they warn their own sourcing is thin), to be checked. Test: `tests/test_honours.py`.
- **A bug to remember:** a function declared twice in a page script silently replaces the first (the finals' `raceChart` once broke the MVP / Player of the round page); `tests/test_repo_hygiene.py` now fails on a duplicate top-level name.
- **Game posters** (`tools/game_images.py`, macOS): `python tools/game_images.py mvp --game ID --team JSK --number 2 --photo PHOTO.jpg` (the game MVP) and `... thriller --game ID --photo PHOTO.jpg --headline "..."` (the result of a close game) write 1080x1350 posters in the new brand to `exports/`. The numbers come from the box score on the live site; the players are cut out of the photo with Apple's Vision framework (`tools/cutout_mask.swift`, nothing to install) and put on the poster's own background.
- **Ranking law** (`ranking.py`, `tests/test_tiebreak.py`): every table (Pro A, play-off / play-out, National One) is ordered as the FTBB's General Regulations of 10/08/2024 write it, but only at the last round of its phase (until then: points, then point difference, then points scored) (art. 182-184, 194; sources and the steps in the module's docstring); a small footnote with the link sits under the tables (`lawNote()` in `static/index.html`). Where the law is silent the module says what it does.
- **Analyst board, more actions:** technical foul on a player (counts as one of his fouls), injury, ejection (confirmed; the substitution window opens and he cannot come back on), and a team row per club: team rebounds and turnovers (the sheet's "Team / Coach" row), timeouts (the clock stops), technical fouls on the coach or the bench, with the team totals under it. The clock no longer starts by itself after a free throw, a technical, a timeout, an injury or an ejection (`DEAD` in `static/analytics.html`). Team events are stored like a lineup (`pid: null`, `team`), see `team_tally()`; the public Live page shows them (plays, timeouts and technicals in the team stats, EJ / injury flags).
- **A bug fixed:** the board kept the half-done state of one game (the five being picked, the selected player) when another game was opened; with the same club the substitution buttons then only ticked players. The state is reset when the game changes (`S.shown`).
- **Pictures:** `tools/brand.py` (header and footer of every poster tool) and the admin canvases draw the new mark and `wordmark-dark.svg`. `static/admin-cutout.js` takes the player out of an uploaded photo in the browser (MediaPipe Interactive Segmenter, Apache-2.0, vendored in `static/vendor/mediapipe/` with its notice: you click on the player, a second click adds a second one): Game MVP (photo) and Player photo images have an "extract the player" option. `static/admin-nat1img.js`: National One results of a matchday and standings (`/api/nat1`). `exports/brand-sheet.png` is the identity on one page (made by `tools/make_logo.py`).

## History: past seasons (`history.py`, `assets/history`, pages `/historique` and `/en/history`)
The league's past, read-only and shipped with the code: **champions** since 1955-56 (`champions.json`, with the final's score where known), **how each season was played** (`formats.json`: the play-off, play-out
and super play-off changed almost every year, so every season carries its own text in English and French and its own phases), and per season (`seasons/<season>.json`) the tables, round-robin scores, barrage ties and
series from Wikipedia (English and French pages) and the press. `history.view(season)` groups the phases under one English name each (`phase_name`; the page translates it), marks each game that has a box
score and lists the box scores of that season. `GET /api/history` and `GET /api/history/<season>`; pages `/historique[/2018-2019]` and `/en/history[/...]`, in the sitemap, with a **🕘 History** tab beside Pro A / National One / Cup.
* **Box scores.** `assets/history/games/*.json` are loaded by `stats.load_games` like any other game (so the season switch, the player pages and the team pages work for them). They come from the PDFs the FTBB
  published on its old statistics pages (kept by the Internet Archive) and from the 2021-22 Google Drive sheet: `python tools/archive_ftbb.py` downloads them (slowly, the Archive refuses fast bulk downloads),
  `python tools/import_history.py` reads them with the site's importer (`extractor.py`; `french_parser.py` reads the French-language sheets of 2017-19) and keeps a game only when every consistency check passes
  (points, rebounds, shooting, minutes); the others are listed in `exports/history_raw/problems.json`. Club codes are made canonical from the club's name (`french_parser.canon`).
* **Season pages.** `python tools/history_wikipedia.py DIR` (English pages: 2014-15, 2019-20, 2021-22 to 2024-25 and the champions list) and `python tools/history_wikifr.py DIR` (French pages: 2016-17 to 2018-19,
  2020-21, 2025-26; `--force` replaces a season already built) write `assets/history/seasons/`. The two scripts keep Wikipedia's order for tables (the page's own tie-break) and drop a date that precedes the first game of its round.
* **What is not there:** a season shows only what the files hold. 2015-16 has only the final (press report); the play-out tables of 2017-18 and 2018-19 are missing from the Wikipedia pages; seasons before
  2014-15 list the champion only. Box scores on the site: 2016-17 (5), 2017-18 (40), 2018-19 (42), 2021-22 (113: the whole season from the FTBB's Google Sheet, tabs 1ère phase, P-OFF and P-OUT: regular season, play-off, super play-off with the final, play-out, super play-out and Cup); the FTBB's archived pages list 121 files and the
  2021-22 sheet 237 Drive links (131 distinct box scores); 242 distinct files were read in all and 202 passed every check (200 games once duplicates are merged) (the rest are scans too poor to read, sheets with printed errors, a national U23 friendly...:
  `exports/history_raw/problems.json`). No box score could be found online for 2019-20, 2020-21 and 2022-23 to 2025-26 (the FTBB's statistics page points to a spreadsheet that still holds 2021-22); their results come from Wikipedia. The three French sheet layouts of 2016-19 are in
  `french_parser.py`; `NO_HISTORY_GAMES=1` leaves the past seasons out of `stats.load_games` (the test suite does, except `tests/test_history.py` and `tests/test_seo.py`).
* **Players across seasons.** A jersey number only identifies a player within a season: `stats.load_games` names the players of each season on their own (CA #1 of 2018 is not CA #1 of 2026), so the past
  seasons never rename or merge the players of the current one.
* Test: `tests/test_history.py`.

## League records (`records.py`, page `/historique/records`, `/en/history/records`)
The best single-game performances (points, rebounds, assists, steals, blocks, threes, free throws, PIR) of players, the best team games (points scored, biggest win, highest-scoring
game, team threes, assists, rebounds), the best season averages (at least 5 games with a box score) and the all-time records (most titles, longest title streak, unbeaten through a
phase). Player records come from every box score the site holds (this season's and the past seasons' in `assets/history/games`); team scores and margins also use every result
without a box score (this season's official results and the history pages, back to 2014-15); titles come from the champions since 1955-56. No list of Tunisian league records
could be found online (FTBB, press, Afrobasket, Proballers were searched), so these are the site's own, and the page says over which seasons they are counted.
**A record broken or equalled is shown on the game's page** (`/api/games/<id>` carries `records`: each record the game set or equalled, against every game played before it,
with the previous holder), from the 31st game on. Values a sheet cannot hold (a misread 99) are left out (`PLAYER_STATS` caps); a two-legged tie given as one aggregate score
(2023-24 third place, 144-74) is stored as `aggregate`, never as a game. `GET /api/records`. Test: `tests/test_records.py`.

## Mobile app (`mobile/`) and the hidden Fantasy game (`fantasy.py`)
**The app** is a native React Native app (Expo, Expo Router; Android first, then iOS; phones and tablets), not a wrapper of the website: see `mobile/README.md`. It reads the public
API only (no admin in the app). For it the server has `GET /api/schedule` (every matchday of the season in one call: results with their box score's id and MVP, games to play with date
and time) and answers the public API with `Access-Control-Allow-Origin: *` (GET only, no credentials; the fantasy routes also accept POST), which the app's web preview needs.
The old Capacitor wrapper (`mobile/www`, never in git) is gone. The website shares the app's look (night navy, glass cards, pill navigation, Barlow Condensed for titles and
numbers, served from `static/fonts/`).
**Fantasy Pro A** is hidden: every `/api/fantasy/*` route answers 404 unless the server runs with `FANTASY=1`, and the app shows its tab only when built with
`EXPO_PUBLIC_FANTASY=1`. Rules, scoring and chips are in the docstring of `fantasy.py`; squads, leagues and players' choices live in `DATA_DIR/fantasy.json`; no account, a device's
random id and a nickname (a login can come later). `FANTASY_TEST=1` lets a squad be saved for a matchday already played (local testing on real results). Test: `tests/test_fantasy.py`.
**Players across clubs:** `assets/roster.json` maps Naiem Dhifallah's earlier numbers (Club Africain #7 2016-18, ES Sahel #7 2018-19, Grombalia then Ezzahra #77 in 2021-22) to his
ES Radès profile (`esr-77`), so his 49-point game of 13 Oct 2021 (sheet: "DHIFALLAH N") is credited to him.

## Privacy policy (`privacy.py`, pages `/confidentialite` and `/en/privacy`)
One text (French and English) for the website, its crawler version and the app (More → Privacy); the store listings link to it. It describes what the code records (traffic.py, mvp.py, predict.py, follows, the app's local storage): change it when that changes, with `UPDATED`. `GET /api/privacy?lang=fr|en`.
