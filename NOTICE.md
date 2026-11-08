# What the MIT licence covers, and what it does not

The MIT licence in `LICENSE` covers the **source code** of this repository. It does **not** cover:
- **The Tunisia Basket name and emblem** (`static/img/`, `assets/brand/`): all rights reserved. Please do not present another site as Tunisia Basket.
- **Club names and logos** and other third-party material described below: they belong to their owners.

# Third-party material

## Club names and logos
The names and logos of the Pro A clubs (in `assets/team-logos-src/` and `static/img/teams/`) belong to their respective owners. They are used only to
identify the teams in results and statistics. Tunisia Basket is an independent project and is not affiliated with the Tunisian Basketball Federation
(FTBB) or with any club. A rights holder who wants a logo removed can ask and it will be taken down.

## Player photos
The player photos (`static/img/players/<player id>.jpg`, listed in `assets/player_photos.json`) are cropped from club announcements, federation and press pictures supplied by the
site owner, and belong to their photographers, clubs and the players shown. They are published here as a **preview, so that players can see them and approve**: a player, a club or a
rights holder who wants a photo removed can ask and it is taken down at once (delete the file and its line in `assets/player_photos.json`, or use the admin panel). They are not covered by the MIT licence.
- `esg-41` (Bouguerra Abderahmen): photo by Zafer Batık on Wikimedia Commons, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), cropped from
  [File:Abderahmen Bouguerra 78 20260826 (4).JPG](https://commons.wikimedia.org/wiki/File:Abderahmen_Bouguerra_78_20260826_(4).JPG). The crop is shared under the same licence.

## Competition data
Results, standings and box scores come from the federation's public match sheets and result graphics (`seed/`, `tests/`). The statistics derived from them
(ratings, MVP, positions, lineups) are our own calculations.

## Software the site is built on
| Package | Licence |
|---|---|
| Flask, Werkzeug, Jinja2, MarkupSafe, ItsDangerous, Click, Blinker | BSD-3-Clause / BSD |
| requests, urllib3, idna, charset-normalizer, certifi | Apache-2.0 / MIT / BSD-3-Clause / MPL-2.0 (certifi, unmodified) |
| pdfplumber, pdfminer.six | MIT |
| pypdfium2 | BSD-3-Clause / Apache-2.0 |
| NumPy | BSD-3-Clause and others (permissive) |
| Pillow | MIT-CMU |
| gunicorn | MIT |

Used at the server: Tesseract OCR (Apache-2.0), Caddy (Apache-2.0), Ubuntu. All are permissive: they do not require this project's code to be published.
