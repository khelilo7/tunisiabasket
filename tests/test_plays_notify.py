"""Play of the week (plays.py): the admin's weeks and clips, one final vote per device, shares after voting, the winner kept until the next week, the archive.
Push notifications (notify.py): the app's choice (all / my team / none, topics), the first run only records, then only what is new, to who asked for it."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
os.environ["PUSH"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402
import config  # noqa: E402
import notify  # noqa: E402
import plays  # noqa: E402
import stats  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
ADMIN = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
UA = "Mozilla/5.0 (Linux; Android 14) okhttp/4.12.0"
vid = lambda n: f"{n:032x}"
act = lambda **b: c.post("/admin/api/plays", json=b, headers=ADMIN)
view = lambda v=1: c.get(f"/api/plays?vid={vid(v)}").get_json()


def vote(clip, n=1, ip="203.0.113.5", week=None):
    return c.post("/api/plays/vote", json={"week": week or wid, "clip": clip, "vid": vid(n)}, headers={"User-Agent": UA}, environ_overrides={"REMOTE_ADDR": ip})


# ---------------------------------------------------------------- plays
check(plays.video("https://youtu.be/dQw4w9WgXcQ")["thumb"] == "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg", "a YouTube link gives its thumbnail")
check(plays.video("https://www.youtube.com/shorts/dQw4w9WgXcQ")["kind"] == "youtube", "YouTube shorts")
check(plays.video("https://www.facebook.com/watch/?v=123")["kind"] == "facebook", "a Facebook video")
check(plays.video("https://cdn.example.com/clip.mp4")["kind"] == "file", "a video file")
check(plays.video("http://youtu.be/dQw4w9WgXcQ") is None and plays.video("javascript:alert(1)") is None, "only https video addresses")
check(c.get("/admin-plays.js").status_code == 200, "the admin script is served")
check(c.get("/admin/api/plays").status_code == 401 and c.post("/admin/api/plays", json={"op": "create", "title": "J1"}).status_code == 401, "admin only")
check(view() == {"week": None, "archive": []}, "nothing on show before a vote opens")

r = act(op="create", title="J12").get_json()
wid = r["week"]
check(act(op="add", week=wid, url="https://example.com/page", title="x").status_code == 422, "a link that is not a video is refused")
act(op="add", week=wid, url="https://www.youtube.com/watch?v=aaaaaaaaaaa", title="Dunk", player="Naiem Dhifallah", team="esr")
check(act(op="open", week=wid).status_code == 422, "two clips at least before opening")
act(op="add", week=wid, url="https://youtu.be/bbbbbbbbbbb", title="Block")
clips = [x["id"] for x in c.get("/admin/api/plays", headers=ADMIN).get_json()["weeks"][0]["clips"]]
check(vote(clips[0]).status_code == 403, "no vote on a draft week")
check(view()["week"] is None, "a draft is not shown")
check(act(op="open", week=wid).status_code == 200, "open")
v = view()
check(v["week"]["open"] and len(v["week"]["clips"]) == 2 and v["week"]["clips"][0]["team"] == "ESR", "the open week with its clips")
check(all(x["votes"] is None for x in v["week"]["clips"]), "shares hidden before voting")
check(vote(clips[0]).status_code == 200, "a vote")
check(vote(clips[1]).status_code == 409, "a vote is final")
check(vote("nope", n=2).status_code == 400, "an unknown clip")
check(vote(clips[1], n=3, ip="198.51.100.1").status_code == 200 and vote(clips[1], n=4, ip="198.51.100.2").status_code == 200, "more fans")
v = view()
check(v["week"]["my_vote"] == clips[0] and v["week"]["clips"][1]["vote_share"] == 67 and v["week"]["winner"] is None, "shares after voting, no winner while open")
check(c.post("/api/plays/vote", json={"week": wid, "clip": clips[0], "vid": vid(9)}, headers={"User-Agent": "curl/8"}).status_code == 400, "crawlers refused")
check(act(op="remove", week=wid, clip=clips[0]).status_code == 422 and act(op="delete", week=wid).status_code == 422, "clips and weeks with votes stay")
act(op="close", week=wid)
v = view(7)
check(not v["week"]["open"] and v["week"]["winner"]["id"] == clips[1] and v["week"]["clips"][0]["votes"] == 1, "closed: the most voted clip wins, shares for all")
check(vote(clips[0], n=8, ip="192.0.2.9").status_code == 403, "no vote once closed")
act(op="crown", week=wid, winner=clips[0])
check(view()["week"]["winner"]["id"] == clips[0], "the admin's crown wins")
w2 = act(op="create", title="J13").get_json()["week"]
check(view()["week"]["id"] == wid, "the winner stays on show until the next week opens")
act(op="add", week=w2, url="https://youtu.be/ccccccccccc", title="Three")
act(op="add", week=w2, url="https://cdn.example.com/a.mp4", title="Steal")
act(op="open", week=w2)
v = view()
check(v["week"]["id"] == w2 and v["archive"] and v["archive"][0]["winner"]["id"] == clips[0], "next week on show, last week's winner in the archive")

# ---------------------------------------------------------------- notifications
tok = lambda n: f"ExponentPushToken[abcdefghij{n:04d}]"
reg = lambda **b: c.post("/api/push", json=b)
teams = list(stats.load_official()["teams"])
check(reg(token="nope", level="all").status_code == 400, "a token that is not an Expo one is refused")
check(reg(token=tok(1), level="team").status_code == 400, "level team needs a club")
check(reg(token=tok(1), level="all", lang="en").status_code == 200, "all")
check(reg(token=tok(2), level="team", team=teams[0]).status_code == 200, "my team")
check(reg(token=tok(3), level="all", results=False).status_code == 200, "all but results")
check(reg(token=tok(4), level="team", team="ZZZ").status_code == 400, "an unknown club")
reg(token=tok(5), level="all")
reg(token=tok(5), level="none")
subs = json.loads((config.DATA_DIR / "push.json").read_text())
check(set(subs) == {tok(1), tok(2), tok(3)} and subs[tok(1)]["lang"] == "en", "none forgets the token")
check(c.open("/api/push", method="OPTIONS").headers.get("Access-Control-Allow-Methods") == "GET, POST", "the app's web preview may post its choice")

sent = []
notify._send = lambda msgs: sent.extend(msgs)
os.environ["PUSH"] = "1"
check(notify.check() == 0 and not sent, "the first run only records what is already published")
check(notify.check() == 0, "nothing new, nothing sent")
off = stats.load_official()
home, away = teams[0], teams[1]
off["results"].append({"matchday": 99, "home": home, "away": away, "home_score": 80, "away_score": 70})
orig = stats.load_official
stats.load_official = lambda: off
try:
    n = notify.check()
finally:
    stats.load_official = orig
got = {m["to"]: m for m in sent}
check(n == 2 and set(got) == {tok(1), tok(2)}, f"a new result goes to 'all' and to the home club's fans, not to who turned results off ({sorted(got)})")
check(got.get(tok(1), {}).get("title") == f"{home} 80 – 70 {away}" and "win" in got.get(tok(1), {}).get("body", ""), "the score in the title, in the phone's language")
check(got.get(tok(2), {}).get("data") == {"path": "/scores"}, "a tap opens the scores")
sent.clear()
stats.load_official = lambda: off
try:
    check(notify.check() == 0 and not sent, "never twice")
finally:
    stats.load_official = orig

if fails:
    print("FAIL test_plays_notify:\n  " + "\n  ".join(f for f in fails if f))
    sys.exit(1)
print("ok test_plays_notify")
