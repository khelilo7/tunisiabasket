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

## Licence
The source code is released under the **MIT licence** (`LICENSE`). The licence does not cover the Tunisia Basket name and emblem, the club names and logos
(they belong to their owners), or the data from the federation: see `NOTICE.md`. Open-source libraries keep their own licences.
