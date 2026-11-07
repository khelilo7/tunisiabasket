"""Search-engine side of the site: real URLs, per-page titles/descriptions, social cards, structured data, sitemap.

The page itself is a single-page app (static/index.html). For every URL this module supplies what a crawler needs
before any JavaScript runs: <title>, description, canonical + language alternates, Open Graph / Twitter tags,
JSON-LD, and a plain HTML version of the page content (which the app replaces once it loads).

Languages: French is the default (no prefix) and English lives under /en/..., with translated URL words (team -> equipe, ...).
"""
import json
import os
import re
import time
import unicodedata
from html import escape as esc
from pathlib import Path

from flask import request

import config
import stats

DEFAULT = "fr"          # the main language: its addresses have no prefix (/equipe/CA); the others do (/en/team/CA)
LANGS = ("fr", "en")
SLUGS = {
    "en": {"standings": "standings", "players": "players", "games": "games", "planning": "planning", "mvp": "mvp-race",
           "team": "team", "player": "player", "game": "game"},
    "fr": {"standings": "classement", "players": "joueurs", "games": "matchs", "planning": "calendrier", "mvp": "course-mvp",
           "team": "equipe", "player": "joueur", "game": "match"},
}
LIST_PAGES = ("home", "standings", "players", "games", "planning", "mvp")
ITEM_PAGES = ("team", "player", "game")
SITE = "Tunisia Basket"
OG_LOCALE = {"en": "en_US", "fr": "fr_FR"}

# Words used in titles, descriptions and the crawler version of each page.
T = {
    "en": {
        "season_word": "season", "regular": "regular season", "standings": "Standings", "players": "Players", "games": "Games",
        "planning": "Planning", "home": "Home", "team": "Team", "mvp_race": "MVP race", "latest": "Latest games", "results": "Results",
        "upcoming": "Upcoming matches", "roster": "Players", "w": "W", "l": "L", "pts": "Pts", "diff": "Diff", "gp": "GP", "reb": "REB",
        "ast": "AST", "rating": "Rating", "min": "MIN", "game_log": "Game log", "starters": "Box score",
        "opp": "Opponent", "score": "Score", "matchday": "Matchday", "projected": "projected",
        "h_title": "Tunisia Basket – Tunisian Pro A basketball scores, standings and player stats",
        "h_desc": "Scores, standings, box scores, player stats and the MVP race of the Tunisian Pro A basketball league, {season} {word}. Current MVP: {mvp}.",
        "h_h1": "Tunisian Pro A basketball: scores, standings and stats",
        "st_title": "Pro A basketball standings {season} – Tunisia Basket",
        "st_desc": "Full Tunisian Pro A basketball standings for the {season} regular season: wins, losses, points and goal difference. Leader: {lead}.",
        "pl_title": "Pro A player stats {season}: points, rebounds, assists – Tunisia Basket",
        "pl_desc": "Per-game averages and ratings for every Tunisian Pro A basketball player in {season}: points, rebounds, assists, steals, blocks and shooting.",
        "g_title": "Pro A results and box scores {season} – Tunisia Basket",
        "g_desc": "Every Tunisian Pro A basketball game of {season} with the final score, full box score, starting fives and the game MVP.",
        "pn_title": "Pro A calendar {phase} – upcoming matches – Tunisia Basket",
        "pn_desc": "The Tunisian Pro A basketball calendar for the second phase of the {season} regular season, matchday by matchday.",
        "t_title": "{name} ({code}) – results, stats and calendar | Tunisia Basket",
        "t_desc": "{name} Pro A basketball: {wl}, number {rank} in the standings. Results, box scores, the most-played five, player stats and the upcoming calendar.",
        "p_title": "{name} ({team}) – stats {season} | Tunisia Basket",
        "p_desc": "{name}, {team} #{num}: {pts} points, {reb} rebounds and {ast} assists per game over {gp} games in the {season} Pro A season. Rating {rating}/99.",
        "m_title": "{a} {sa}–{sb} {b} – box score, {md} | Tunisia Basket",
        "m_desc": "{a} vs {b} ({sa}–{sb}), Tunisian Pro A basketball {md}: full box score, starting fives and player stats.{mvp}",
        "mvp_nav": "MVP", "mv_votes": "fan votes", "mv_phase1": "Phase 1 MVP", "mv_leader": "Race leader", "mv_h1": "MVP race – phase 1 (J1–J11)",
        "mv_title": "MVP race and fan vote – phase 1 – Tunisia Basket",
        "mv_desc": "Who is the MVP of the first phase of the Tunisian Pro A basketball league? The race matchday by matchday, the stats and the fans' vote. {who}",
        "mvp_game": " Game MVP: {name}.", "not_found": "Page not found – Tunisia Basket",
        "legal": "© {year} Tunisia Basket · Independent site, not affiliated with the Tunisian Basketball Federation or the clubs. Club names and logos belong to their owners.",
    },
    "fr": {
        "season_word": "saison", "regular": "saison régulière", "standings": "Classement", "players": "Joueurs", "games": "Matchs",
        "planning": "Calendrier", "home": "Accueil", "team": "Équipe", "mvp_race": "Course au MVP", "latest": "Derniers matchs", "results": "Résultats",
        "upcoming": "Prochains matchs", "roster": "Joueurs", "w": "V", "l": "D", "pts": "Pts", "diff": "Diff", "gp": "MJ", "reb": "REB",
        "ast": "PD", "rating": "Note", "min": "MIN", "game_log": "Journal des matchs", "starters": "Feuille de match",
        "opp": "Adversaire", "score": "Score", "matchday": "Journée", "projected": "projeté",
        "h_title": "Tunisia Basket – Scores, classement et statistiques de la Pro A tunisienne de basket",
        "h_desc": "Résultats, classement, feuilles de match, statistiques des joueurs et course au MVP du championnat tunisien de basket Pro A, {word} {season}. MVP actuel : {mvp}.",
        "h_h1": "Basket Pro A tunisien : résultats, classement et statistiques",
        "st_title": "Classement Pro A basket {season} – Tunisia Basket",
        "st_desc": "Classement complet de la Pro A tunisienne de basket pour la saison régulière {season} : victoires, défaites, points et différence. Leader : {lead}.",
        "pl_title": "Statistiques des joueurs Pro A {season} : points, rebonds, passes – Tunisia Basket",
        "pl_desc": "Moyennes par match et notes de chaque joueur de la Pro A tunisienne de basket en {season} : points, rebonds, passes décisives, interceptions, contres et adresse.",
        "g_title": "Résultats et feuilles de match Pro A {season} – Tunisia Basket",
        "g_desc": "Tous les matchs de la Pro A tunisienne de basket {season} avec le score final, la feuille de match complète, les cinq de départ et le MVP du match.",
        "pn_title": "Calendrier Pro A {phase} – prochains matchs – Tunisia Basket",
        "pn_desc": "Le calendrier de la Pro A tunisienne de basket pour la deuxième phase de la saison régulière {season}, journée par journée.",
        "t_title": "{name} ({code}) – résultats, statistiques et calendrier | Tunisia Basket",
        "t_desc": "{name} en Pro A de basket : {wl}, {rank} au classement. Résultats, feuilles de match, cinq majeur, statistiques des joueurs et prochain calendrier.",
        "p_title": "{name} ({team}) – statistiques {season} | Tunisia Basket",
        "p_desc": "{name}, {team} n°{num} : {pts} points, {reb} rebonds et {ast} passes décisives par match en {gp} matchs de Pro A {season}. Note {rating}/99.",
        "m_title": "{a} {sa}–{sb} {b} – feuille de match, {md} | Tunisia Basket",
        "m_desc": "{a} contre {b} ({sa}–{sb}), Pro A tunisienne de basket {md} : feuille de match complète, cinq de départ et statistiques des joueurs.{mvp}",
        "mvp_nav": "MVP", "mv_votes": "votes des fans", "mv_phase1": "MVP de la phase 1", "mv_leader": "Leader de la course", "mv_h1": "Course au MVP – phase 1 (J1–J11)",
        "mv_title": "Course au MVP et vote des fans – phase 1 – Tunisia Basket",
        "mv_desc": "Qui est le MVP de la première phase de la Pro A tunisienne de basket ? La course journée par journée, les statistiques et le vote des fans. {who}",
        "mvp_game": " MVP du match : {name}.", "not_found": "Page introuvable – Tunisia Basket",
        "legal": "© {year} Tunisia Basket · Site indépendant, non affilié à la Fédération Tunisienne de Basket-Ball ni aux clubs. Les noms et logos des clubs appartiennent à leurs propriétaires.",
    },
}


# ---------------------------------------------------------------- URLs
def slugify(text):
    s = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def player_ref(p):
    """URL piece for a player: '<id>-<name>' (e.g. ca-24-omar-abada); the id alone is enough to find them."""
    return f"{p['id']}-{slugify(p['name'])}"


def player_id(ref):
    m = re.match(r"^([a-z0-9]+-\d+)", ref or "")
    return m.group(1) if m else ref


def path(lang, page, arg=None):
    pre = "" if lang == DEFAULT else f"/{lang}"
    if page == "home":
        return pre + "/"
    base = f"{pre}/{SLUGS[lang][page]}"
    return f"{base}/{arg}" if arg else base


def base_url():
    return (os.environ.get("SITE_URL") or request.url_root).rstrip("/")


def alternates(page, arg=None):
    b = base_url()
    alts = {lang: b + path(lang, page, arg) for lang in LANGS}
    alts["x-default"] = alts[DEFAULT]
    return alts


def parse_path(p):
    """'/en/team/CA' -> ('en', 'team', 'CA'); '/equipe/CA' -> ('fr', 'team', 'CA'); None if it is not one of our pages."""
    lang = DEFAULT
    for other in LANGS:
        if other != DEFAULT and (p == f"/{other}" or p.startswith(f"/{other}/")):
            lang, p = other, p[len(other) + 1:] or "/"
    parts = [x for x in p.split("/") if x]
    if not parts:
        return lang, "home", None
    rev = {v: k for k, v in SLUGS[lang].items()}
    page = rev.get(parts[0])
    if not page or len(parts) > 2:
        return None
    if page in ITEM_PAGES:
        return (lang, page, parts[1]) if len(parts) == 2 else None
    return (lang, page, None) if len(parts) == 1 else None


# ---------------------------------------------------------------- page data
def _lead(d):
    return d["standings"][0]["name"] if d["standings"] else "-"


def _links(lang, items):
    return "".join(f'<li><a href="{esc(h)}">{esc(t)}</a></li>' for h, t in items)


def _standings_table(lang, d):
    t = T[lang]
    rows = "".join(f'<tr><td>{r["rank"]}</td><td><a href="{path(lang, "team", r["code"])}">{esc(r["name"])}</a></td><td>{r["w"]}</td><td>{r["l"]}</td><td>{r["pts"]}</td><td>{r["diff"]:+d}</td></tr>'
                   for r in d["standings"])
    return f'<table><thead><tr><th>#</th><th>{t["team"]}</th><th>{t["w"]}</th><th>{t["l"]}</th><th>{t["pts"]}</th><th>{t["diff"]}</th></tr></thead><tbody>{rows}</tbody></table>'


def _players_table(lang, players, limit=60):
    t = T[lang]
    rows = "".join(f'<tr><td><a href="{path(lang, "player", player_ref(p))}">{esc(p["name"])}</a></td><td>{esc(p["team"])}</td><td>{p["gp"]}</td><td>{p["pts"]}</td><td>{p["reb"]}</td><td>{p["ast"]}</td><td>{p["rating"]}</td></tr>'
                   for p in players[:limit])
    return f'<table><thead><tr><th>{t["players"]}</th><th>{t["team"]}</th><th>{t["gp"]}</th><th>PTS</th><th>{t["reb"]}</th><th>{t["ast"]}</th><th>{t["rating"]}</th></tr></thead><tbody>{rows}</tbody></table>'


def _game_items(lang, games):
    out = []
    for g in games:
        a, b = g["teams"]
        out.append((path(lang, "game", g["id"]), f'{a["name"]} {a["points"]}–{b["points"]} {b["name"]} ({g.get("matchday") or ""})'))
    return out


def _org_jsonld(lang):
    b = base_url()
    return {"@context": "https://schema.org", "@type": "WebSite", "name": SITE, "url": b + path(lang, "home"),
            "inLanguage": lang, "publisher": {"@type": "Organization", "name": SITE, "url": b + "/", "logo": b + "/img/logo.png"}}


def meta(lang, page, arg=None):
    """Everything the shell needs for one URL, or None when the page does not exist."""
    t = T[lang]
    d = stats.build()
    season = d["season"] or ""
    b = base_url()
    out = {"status": 200, "arg": arg, "og_type": "website", "jsonld": [_org_jsonld(lang)]}
    pool = [p for p in d["players"] if p["mvp_eligible"]]

    if page == "home":
        mvp = pool[0]["name"] if pool else "-"
        out.update(title=t["h_title"], description=t["h_desc"].format(season=season, word=t["season_word"], mvp=mvp),
                   ssr=f'<h1>{t["h_h1"]}</h1><p>{esc(t["h_desc"].format(season=season, word=t["season_word"], mvp=mvp))}</p>'
                       f'<h2>{t["standings"]}</h2>{_standings_table(lang, d)}<h2>{t["mvp_race"]}</h2>{_players_table(lang, pool[:5], 5)}'
                       f'<h2>{t["latest"]}</h2><ul>{_links(lang, _game_items(lang, list(reversed(d["games"]))[:8]))}</ul>')
    elif page == "mvp":
        import mvp
        r = mvp.race(1)
        top = r["winner"] or r["leader"]
        who = f'{t["mv_phase1"] if r["winner"] else t["mv_leader"]}: {top["name"]} ({top["team"]}).' if top else ""
        rows = "".join(f'<tr><td>{c["rank"]}</td><td><a href="{path(lang, "player", player_ref(c))}">{esc(c["name"])}</a></td><td>{esc(c["team"])}</td>'
                       f'<td>{c["pts"]}</td><td>{c["reb"]}</td><td>{c["ast"]}</td><td>{c["votes"]}</td><td>{c["score"]}</td></tr>' for c in r["candidates"][:10])
        out.update(title=t["mv_title"], description=t["mv_desc"].format(who=who).strip(),
                   ssr=f'<h1>{t["mv_h1"]}</h1><p>{esc(who)}</p><table><thead><tr><th>#</th><th>{t["players"]}</th><th>{t["team"]}</th><th>PTS</th><th>{t["reb"]}</th>'
                       f'<th>{t["ast"]}</th><th>{t["mv_votes"]}</th><th>Score</th></tr></thead><tbody>{rows}</tbody></table>')
    elif page == "standings":
        out.update(title=t["st_title"].format(season=season), description=t["st_desc"].format(season=season, lead=_lead(d)),
                   ssr=f'<h1>{t["standings"]} {season}</h1>{_standings_table(lang, d)}')
    elif page == "players":
        out.update(title=t["pl_title"].format(season=season), description=t["pl_desc"].format(season=season),
                   ssr=f'<h1>{t["players"]} {season}</h1>{_players_table(lang, d["players"], 80)}')
    elif page == "games":
        out.update(title=t["g_title"].format(season=season), description=t["g_desc"].format(season=season),
                   ssr=f'<h1>{t["games"]} {season}</h1><ul>{_links(lang, _game_items(lang, list(reversed(d["games"]))))}</ul>')
    elif page == "planning":
        plan = stats.planning()
        mds = plan["matchdays"]
        phase = f'J{mds[0]["matchday"]}–J{mds[-1]["matchday"]}' if mds else ""
        body = "".join(f'<h2>J{m["matchday"]}</h2><ul>' + "".join(
            f'<li><a href="{path(lang, "team", g["home"])}">{esc(g["home"])}</a> – <a href="{path(lang, "team", g["away"])}">{esc(g["away"])}</a>'
            f'{" " + str(g["home_score"]) + "–" + str(g["away_score"]) if g["played"] else ""}</li>' for g in m["games"]) + "</ul>" for m in mds)
        out.update(title=t["pn_title"].format(phase=phase), description=t["pn_desc"].format(season=season),
                   ssr=f'<h1>{t["planning"]} {phase}</h1>{body}')
    elif page == "team":
        code = (arg or "").upper()
        v = stats.team_view(code)
        if not v:
            return None
        st = v["standing"] or {"w": 0, "l": 0, "rank": "-"}
        w, l, rk = st["w"], st["l"], st["rank"]
        if lang == "en":
            wl = f'{w} win{"" if w == 1 else "s"} and {l} loss{"" if l == 1 else "es"}'
            rank = rk
        else:
            wl = f'{w} victoire{"" if w <= 1 else "s"} et {l} défaite{"" if l <= 1 else "s"}'
            rank = f'{rk}{"er" if rk == 1 else "e"}'
        desc = t["t_desc"].format(name=v["name"], wl=wl, rank=rank)
        res = "".join(f'<li>J{r["matchday"]} {"vs" if r["home"] else "@"} <a href="{path(lang, "team", r["opp"])}">{esc(r["opp_name"])}</a> {r["pf"]}–{r["pa"]}'
                      + (f' (<a href="{path(lang, "game", r["game_id"])}">{t["starters"]}</a>)' if r["game_id"] else "") + "</li>" for r in reversed(v["results"]))
        up = "".join(f'<li>J{u["matchday"]} {"vs" if u["home"] else "@"} {esc(u["opp_name"])}</li>' for u in v["upcoming"])
        out.update(title=t["t_title"].format(name=v["name"], code=v["code"]), description=desc, arg=v["code"],
                   jsonld=[_org_jsonld(lang), {"@context": "https://schema.org", "@type": "SportsTeam", "name": v["name"], "sport": "Basketball",
                                               "logo": f"{b}/img/teams/{v['code']}.png", "url": b + path(lang, "team", v["code"]),
                                               "memberOf": {"@type": "SportsOrganization", "name": "Pro A", "sport": "Basketball"}}],
                   ssr=f'<h1>{esc(v["name"])} ({v["code"]})</h1><p>{esc(desc)}</p><h2>{t["results"]}</h2><ul>{res}</ul><h2>{t["upcoming"]}</h2><ul>{up}</ul>'
                       f'<h2>{t["roster"]}</h2>{_players_table(lang, v["players"], 30)}')
    elif page == "player":
        pid = player_id(arg)
        p = next((x for x in d["players"] if x["id"] == pid), None)
        if not p:
            return None
        ref = player_ref(p)
        desc = t["p_desc"].format(name=p["name"], team=p["team"], num=p["number"], pts=p["pts"], reb=p["reb"], ast=p["ast"], gp=p["gp"],
                                  season=season, rating=p["rating"])
        log = "".join(f'<li>{esc(r.get("matchday") or "")} vs <a href="{path(lang, "game", r["game_id"])}">{esc(r["opp"])}</a> '
                      f'{r["pts"]} pts, {r["reb"]} reb, {r["ast"]} ast</li>' for r in reversed(p["log"]))
        out.update(title=t["p_title"].format(name=p["name"], team=p["team"], season=season), description=desc, arg=ref, redirect_arg=ref,
                   og_type="profile",
                   jsonld=[_org_jsonld(lang), {"@context": "https://schema.org", "@type": "Person", "name": p["name"], "jobTitle": "Basketball player",
                                               "url": b + path(lang, "player", ref), "memberOf": {"@type": "SportsTeam", "name": p["team"], "sport": "Basketball"}}],
                   ssr=f'<h1>{esc(p["name"])} ({esc(p["team"])})</h1><p>{esc(desc)}</p><h2>{t["game_log"]}</h2><ul>{log}</ul>')
    elif page == "game":
        g = next((x for x in stats.build_all_games() if x["id"] == arg), None)
        if not g:
            return None
        a, bb = g["teams"]
        mvp = t["mvp_game"].format(name=g["mvp"]["name"].title()) if g.get("mvp") else ""
        md = g.get("matchday") or ""
        title = t["m_title"].format(a=a["name"], sa=a["points"], sb=bb["points"], b=bb["name"], md=md)
        desc = t["m_desc"].format(a=a["name"], b=bb["name"], sa=a["points"], sb=bb["points"], md=md, mvp=mvp)

        def box(team):
            rows = "".join(f'<tr><td>{esc(p["name"].title())}</td><td>{round(p["min"])}</td><td>{p["pts"]}</td><td>{p["reb"]}</td><td>{p["ast"]}</td></tr>'
                           for p in team["players"] if not p.get("dnp"))
            return f'<h2>{esc(team["name"])} {team["points"]}</h2><table><thead><tr><th>{t["players"]}</th><th>{t["min"]}</th><th>PTS</th><th>{t["reb"]}</th><th>{t["ast"]}</th></tr></thead><tbody>{rows}</tbody></table>'
        event = {"@context": "https://schema.org", "@type": "SportsEvent", "name": f'{a["name"]} – {bb["name"]}', "sport": "Basketball",
                 "url": b + path(lang, "game", g["id"]),
                 "homeTeam": {"@type": "SportsTeam", "name": a["name"]}, "awayTeam": {"@type": "SportsTeam", "name": bb["name"]}}
        if not g.get("date_approx") and g.get("date"):
            event["startDate"] = g["date"]
        out.update(title=title, description=desc, og_type="article", jsonld=[_org_jsonld(lang), event],
                   ssr=f'<h1>{esc(a["name"])} {a["points"]}–{bb["points"]} {esc(bb["name"])}</h1><p>{esc(desc)}</p>{box(a)}{box(bb)}')
    else:
        return None
    out.setdefault("redirect_arg", None)
    return out


def not_found_meta(lang):
    return {"status": 404, "arg": None, "og_type": "website", "jsonld": [], "title": T[lang]["not_found"], "description": "",
            "ssr": "<h1>404</h1>", "robots": "noindex", "redirect_arg": None}


def head_html(lang, page, m):
    """The per-page <head> tags (title, description, canonical, alternates, social cards, JSON-LD)."""
    b = base_url()
    arg = m.get("arg")
    canonical = b + path(lang, page, arg)
    alts = alternates(page, arg)
    other = [x for x in LANGS if x != lang][0]
    image = b + "/img/og-image.jpg"
    parts = [
        f'<title>{esc(m["title"])}</title>',
        f'<meta name="description" content="{esc(m["description"], quote=True)}">',
        f'<link rel="canonical" href="{esc(canonical)}">',
        *[f'<link rel="alternate" hreflang="{k}" href="{esc(v)}">' for k, v in alts.items()],
        f'<meta property="og:type" content="{m["og_type"]}">', f'<meta property="og:site_name" content="{SITE}">',
        f'<meta property="og:title" content="{esc(m["title"], quote=True)}">', f'<meta property="og:description" content="{esc(m["description"], quote=True)}">',
        f'<meta property="og:url" content="{esc(canonical)}">', f'<meta property="og:image" content="{esc(image)}">',
        '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">',
        f'<meta property="og:locale" content="{OG_LOCALE[lang]}"><meta property="og:locale:alternate" content="{OG_LOCALE[other]}">',
        '<meta name="twitter:card" content="summary_large_image">', f'<meta name="twitter:title" content="{esc(m["title"], quote=True)}">',
        f'<meta name="twitter:description" content="{esc(m["description"], quote=True)}">', f'<meta name="twitter:image" content="{esc(image)}">',
    ]
    if m.get("robots"):
        parts.append(f'<meta name="robots" content="{m["robots"]}">')
    for ld in m["jsonld"]:
        parts.append('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    return "\n".join(parts)


_template = {"mtime": 0, "text": ""}


def nav_html(lang):
    t = T[lang]
    return "".join(f'<a href="{path(lang, p)}" data-p="{p}">{esc(label)}</a>' for p, label in
                   (("home", t["home"]), ("mvp", t["mvp_nav"]), ("players", t["players"]), ("games", t["games"]), ("standings", t["standings"]), ("planning", t["planning"])))


def shell(lang, page, m):
    """index.html with this page's head tags and crawler content filled in."""
    f = Path(__file__).parent / "static" / "index.html"
    mt = f.stat().st_mtime
    if _template["mtime"] != mt:
        _template.update(mtime=mt, text=f.read_text())
    return (_template["text"].replace("{{LANG}}", lang).replace("{{HOME}}", path(lang, "home"))
            .replace("{{REGULAR}}", esc(T[lang]["regular"][0].upper() + T[lang]["regular"][1:]))
            .replace("{{LEGAL}}", esc(T[lang]["legal"].format(year=time.gmtime().tm_year)))
            .replace("<!--NAV-->", nav_html(lang)).replace("<!--HEAD-->", head_html(lang, page, m))
            .replace("<!--SSR-->", m.get("ssr", "")))


# ---------------------------------------------------------------- sitemap and robots
def sitemap_xml():
    b = base_url()
    d = stats.build()
    files = [config.DATA_DIR / "official.json", *config.DATA_DIR.glob("games/*.json")]
    last = max((f.stat().st_mtime for f in files if f.exists()), default=0)
    lastmod = time.strftime("%Y-%m-%d", time.gmtime(last)) if last else None
    entries = [("home", None), ("standings", None), ("players", None), ("games", None), ("planning", None), ("mvp", None)]
    entries += [("team", c) for c in stats.load_official()["teams"]]
    entries += [("player", player_ref(p)) for p in d["players"]]
    entries += [("game", g["id"]) for g in d["games"]]
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for page, arg in entries:
        alts = alternates(page, arg)
        for lang in LANGS:
            out.append("<url>")
            out.append(f"<loc>{esc(b + path(lang, page, arg))}</loc>")
            if lastmod:
                out.append(f"<lastmod>{lastmod}</lastmod>")
            out.append("".join(f'<xhtml:link rel="alternate" hreflang="{k}" href="{esc(v)}"/>' for k, v in alts.items()))
            out.append("</url>")
    out.append("</urlset>")
    return "\n".join(out)


def robots_txt():
    return f"User-agent: *\nDisallow: /admin\nAllow: /\n\nSitemap: {base_url()}/sitemap.xml\n"
