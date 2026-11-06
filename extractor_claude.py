"""Read a box-score PDF (scanned image, no text layer) with Claude vision -> structured game dict.

Needs ANTHROPIC_API_KEY. Every result is validated: player points must sum to the team total
(and rebounds to OR+DR). If not, we retry once, then flag the game for review instead of
silently storing bad numbers.
"""
import base64
import datetime
import io
import os

import anthropic
import pdfplumber

MODEL = os.environ.get("EXTRACT_MODEL", "claude-sonnet-5-5")

NUM = {"type": "integer"}
PLAYER = {
    "type": "object",
    "properties": {
        "number": {"type": "integer", "description": "jersey number (without the * starter mark)"},
        "name": {"type": "string", "description": "player name exactly as printed, without (C)"},
        "starter": {"type": "boolean", "description": "true if the number has a * in front"},
        "captain": {"type": "boolean", "description": "true if (C) follows the name"},
        "dnp": {"type": "boolean", "description": "true if the row says DNP (did not play)"},
        "min": {"type": "string", "description": "minutes as MM:SS, empty if DNP"},
        **{k: NUM for k in ("fgm", "fga", "p2m", "p2a", "p3m", "p3a", "ftm", "fta", "oreb", "dreb", "reb",
                            "ast", "tov", "stl", "blk", "pf", "fd", "pm", "pts")},
    },
    "required": ["number", "name", "dnp"],
}
TEAM = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "short code in brackets after the team name, e.g. JSK"},
        "name": {"type": "string"},
        "coach": {"type": "string"},
        "total_points": {"type": "integer", "description": "PTS value of the Totals row"},
        "players": {"type": "array", "items": PLAYER,
                    "description": "every player row in order; exclude the Team/Coach and Totals rows"},
    },
    "required": ["code", "name", "total_points", "players"],
}
TOOL = {
    "name": "record_box_score",
    "description": "Record the full box score of one basketball game.",
    "input_schema": {
        "type": "object",
        "properties": {
            "competition": {"type": "string"},
            "date": {"type": "string", "description": "game date as YYYY-MM-DD"},
            "teams": {"type": "array", "items": TEAM, "description": "the two teams in the order printed"},
        },
        "required": ["date", "teams"],
    },
}

PROMPT = (
    "This is a FIBA / Genius Sports basketball box score. Transcribe it exactly using the tool. "
    "Columns per player: No, Name, Min, FG M/A, 2P M/A, 3P M/A, FT M/A, OR, DR, TOT, AS, TO, ST, BS, "
    "PF, FD, +/-, PTS. Ignore the percentage columns. Copy each number carefully; do not compute or guess. "
    "For made/attempted like '2/7' give made=2, attempted=7 (fgm/fga, p2m/p2a, p3m/p3a, ftm/fta). "
    "'+/-' can be negative. For DNP rows set dnp=true and leave the stats out."
)


def _page_png(pdf_path, page=0, dpi=200) -> bytes:
    with pdfplumber.open(pdf_path) as pdf:
        img = pdf.pages[page].to_image(resolution=dpi).original.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _validate(game):
    problems = []
    if len(game["teams"]) != 2:
        problems.append(f"expected 2 teams, got {len(game['teams'])}")
    for t in game["teams"]:
        s = sum(p.get("pts", 0) for p in t["players"] if not p.get("dnp"))
        if s != t["total_points"]:
            problems.append(f"{t['code']}: player points {s} != team total {t['total_points']}")
        for p in t["players"]:
            if not p.get("dnp") and p.get("reb", 0) != p.get("oreb", 0) + p.get("dreb", 0):
                problems.append(f"{t['code']} #{p['number']} {p['name']}: rebounds don't add up")
            if not p.get("dnp") and p.get("fgm", 0) != p.get("p2m", 0) + p.get("p3m", 0):
                problems.append(f"{t['code']} #{p['number']} {p['name']}: FG != 2P+3P")
    return problems


def _clean(raw):
    g = {"competition": raw.get("competition", ""), "date": raw["date"], "teams": []}
    datetime.date.fromisoformat(g["date"])
    for t in raw["teams"]:
        players = []
        for p in t["players"]:
            q = {"number": p["number"], "name": p["name"].replace("(C)", "").strip(),
                 "starter": bool(p.get("starter")), "captain": bool(p.get("captain")),
                 "dnp": bool(p.get("dnp"))}
            if not q["dnp"]:
                mm, _, ss = (p.get("min") or "0:00").partition(":")
                q["min"] = round(int(mm or 0) + int(ss or 0) / 60, 2)
                for k in ("fgm", "fga", "p2m", "p2a", "p3m", "p3a", "ftm", "fta", "oreb", "dreb", "reb",
                          "ast", "tov", "stl", "blk", "pf", "fd", "pm", "pts"):
                    q[k] = int(p.get(k, 0))
            players.append(q)
        g["teams"].append({"code": t["code"].upper(), "name": t["name"].title(), "coach": t.get("coach", ""),
                           "points": t["total_points"], "players": players})
    return g


def extract(pdf_path):
    """Returns (game_dict, problems). problems == [] means all checks passed."""
    client = anthropic.Anthropic()
    png = base64.b64encode(_page_png(pdf_path)).decode()
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png}},
        {"type": "text", "text": PROMPT},
    ]
    game, problems = None, []
    for attempt in range(2):
        msgs = [{"role": "user", "content": content}]
        if attempt and problems:
            msgs[0]["content"] = content + [{"type": "text", "text":
                "A previous attempt failed these consistency checks, so some numbers were misread. "
                "Re-read the image carefully and fix them: " + "; ".join(problems)}]
        resp = client.messages.create(model=MODEL, max_tokens=8000, tools=[TOOL],
                                      tool_choice={"type": "tool", "name": "record_box_score"}, messages=msgs)
        raw = next(b.input for b in resp.content if b.type == "tool_use")
        game = _clean(raw)
        problems = _validate({"teams": [{**t, "total_points": t["points"]} for t in game["teams"]]})
        if not problems:
            break
    return game, problems


if __name__ == "__main__":
    import json
    import sys
    g, probs = extract(sys.argv[1])
    print(json.dumps(g, indent=1, ensure_ascii=False))
    print("PROBLEMS:", probs or "none")
