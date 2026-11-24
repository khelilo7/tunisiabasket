"""Who scored, from the commentator's words: the scoring team's player named next to a success word, in the seconds around the basket.

The commentary is transcribed by Whisper (tools/live_scorer.py) into Tunisian Arabic words with their time. A player is found by the consonant skeleton of his
name, which is the same in Arabic and Latin spelling:

    شبوح -> "Sbh" <- Chabbouh        سليمان -> "slmn" <- Slimane        الراجدي -> "rjd" ~ Rachdi "rSd" (one letter apart)
    أيمن -> "'mn" <- Aymen            معين -> "mn" <- Mouin  (a name starting with a vowel keeps a mark, so they differ)

The scorer is the name said next to a success word ("ينجح فيها شبوح", "يكمل معين", "كملها ادم سليمان"), not one next to a miss ("يضيع"), said during this play:
after the previous basket and up to a few seconds after the scoreboard changed (the board is updated by hand, sometimes 15-30 s late, while the commentator
speaks when the ball goes in). Tested on a whole game (ESS-DSG, J14): the right player for 85 % of the baskets.

No dependency: pure Python, so the server's tests can run it too.
"""
import re

# ---------------------------------------------------------------- consonant skeletons
AR = {"ب": "b", "ت": "t", "ث": "t", "ج": "j", "ح": "h", "خ": "x", "د": "d", "ذ": "d", "ر": "r", "ز": "z", "س": "s", "ش": "S",
      "ص": "s", "ض": "d", "ط": "t", "ظ": "d", "غ": "g", "ف": "f", "ق": "k", "ك": "k", "ل": "l", "م": "m", "ن": "n", "ه": "h",
      "پ": "b", "چ": "S", "ڤ": "f", "گ": "g"}                          # every other letter (vowels, hamza, ain, ta marbuta) is dropped
VOWEL_START = "اأإآع"
PREFIXES = ("وبال", "فال", "بال", "كال", "وال", "لل", "ال", "و", "ف", "ب", "ل", "ك")
GENERIC = {"mhmd", "'hmd", "hmd"}                                    # "Mohamed", "Ahmed": too common to say who it is
COMMON = {"احسن", "أحسن", "حسن", "الحسن", "باحسن", "فرصة"}           # everyday words that look like a short name
SUCCESS = re.compile(r"ينجح|نجح|يكمل|كمل|يسجل|سجل|تلايث|ثلاثي|دانك|يحط|حطها|يزيد|ملاه")
MISS = re.compile(r"يضيع|ضيع|ضاع|يضيعها|ضيعها")


def _collapse(s):
    return re.sub(r"(.)\1+", r"\1", s)


def ar_skeleton(word):
    word = re.sub(r"[^؀-ۿ]", "", word)
    if not word:
        return ""
    mark = "'" if word[0] in VOWEL_START else ""
    return mark + _collapse("".join(AR.get(ch, "") for ch in word))


def ar_variants(word):
    """The word and the word without its usual prefixes (و, ب, ل, ال, لل, بال...)."""
    out = {word}
    for p in PREFIXES:
        if word.startswith(p) and len(word) - len(p) >= 3:
            out.add(word[len(p):])
    return out


def lat_skeleton(name):
    s = name.lower().strip()
    s = re.sub(r"[éèêë]", "e", s)
    mark = "'" if s[:1] in ("a", "e", "i", "o", "u") else ""
    s = re.sub(r"ic$|ić$|ich$", "tS", s)                  # Radunic -> Radunitch
    s = re.sub(r"c(?=[eiy])", "s", s)                    # Racil: a soft c is an s
    for a, b in (("ch", "S"), ("sh", "S"), ("kh", "x"), ("gh", "g"), ("dh", "d"), ("th", "t"), ("ph", "f"), ("ou", ""),
                 ("q", "k"), ("c", "k"), ("p", "b"), ("v", "f"), ("x", "ks")):
        s = s.replace(a, b)
    s = re.sub(r"[aeiouyw'\-\s]", "", s)
    return mark + _collapse(s)


def lev(a, b):
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[-1]


def aliases(roster):
    """{index in roster: [(skeleton, weight)]}: the surname 1.0, the other names 0.6; a player with no game this season counts less.
    By player, not by number: a season roster can have two players who wore the same number."""
    out = {}
    for i, p in enumerate(roster):
        if not p.get("name"):
            continue
        parts = [w for w in re.split(r"\s+", (p.get("name") or "").strip()) if w]
        al = [(lat_skeleton(parts[-1]), 1.0)] if parts else []
        al += [(lat_skeleton(w), 0.6) for w in parts[:-1]]
        rare = 0.5 if p.get("gp") == 0 else 1.0
        out[i] = [(s, w * rare) for s, w in al if len(s.replace("'", "")) >= 2 and s not in GENERIC]
    return out


def sim(s, skel):
    if s == skel:
        return 1.0
    core = len(skel.replace("'", ""))
    if core >= 3 and lev(s, skel) <= 1:                  # الراجدي "rjd" ~ Rachdi "rSd"
        return 0.75
    if core >= 5 and s[:3] == skel[:3] and lev(s, skel) <= 2:   # رادونيج "rdnj" ~ Radunic "rdntS"
        return 0.6
    return 0.0


def match(text, al):
    if text in COMMON:
        return 0.0
    best = 0.0
    for v in ar_variants(text):
        s = ar_skeleton(v)
        if len(s.replace("'", "")) < 2:
            continue
        for skel, w in al:
            best = max(best, sim(s, skel) * w)
    return best


def who_scored(words, roster, t_board, t_from=None):
    """words: [{"t": seconds, "w": word}] (any time base, the same as t_board and t_from). roster: [{"id"?, "number", "name", "gp"?}] of the scoring team.
    t_from: the earliest moment this basket can have happened (just after the previous one). Returns
    {"player", "number", "score", "conf", "said", "scores"}: the best player (his roster entry; None if no name was heard), how strongly, how far ahead of
    the second (0.5-1), when the commentator named him (the basket is a second or two before), and every player's score (by number)."""
    t_from = t_board - 35 if t_from is None else t_from
    al = aliases(roster)
    toks = [w["w"] for w in words]
    scores, peak = {}, {}
    for k, w in enumerate(words):
        cands = [toks[k]] + ([toks[k] + toks[k + 1]] if k + 1 < len(toks) else [])   # "عبد الرحمن" = Abderrahmen
        for n, a in al.items():
            m = max(match(c, a) for c in cands)
            if not m:
                continue
            when = 1.0 if t_from <= w["t"] <= t_board + 7 else 0.15     # said during this play, not the previous one
            anchor = 0.0
            for s in range(max(0, k - 4), min(len(toks), k + 5)):
                if s != k and SUCCESS.search(toks[s]):
                    anchor = max(anchor, (3.0 if s < k else 2.5) / abs(s - k))   # "ينجح فيها شبوح" / "معين يكمل"
            missed = any(MISS.search(toks[s]) for s in range(k + 1, min(len(toks), k + 4)))
            late = 1.0 + 0.6 * max(0.0, min(1.0, (w["t"] - t_from) / max(t_board - t_from, 1)))   # the latest call in the play counts more
            c = m * when * late * (1 + anchor) * (0.25 if missed else 1.0)
            scores[n] = scores.get(n, 0) + c
            if c > peak.get(n, (0, None))[0]:
                peak[n] = (c, w["t"])
    if not scores:
        return {"player": None, "number": None, "score": 0.0, "conf": 0.0, "said": None, "scores": {}}
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    return {"player": roster[best], "number": roster[best].get("number"), "score": round(float(top), 2), "conf": round(float(top / (top + second)), 2),
            "said": float(peak[best][1]), "scores": {f"{roster[i].get('number')} {roster[i]['name']}": round(float(v), 2) for i, v in ranked[:5]}}


def sure(result, min_score=4.0, min_conf=0.6):
    """Is the answer good enough to show without a check? (Below: the basket goes to the admin's list to confirm.)"""
    return bool(result["player"] is not None and result["score"] >= min_score and result["conf"] >= min_conf)
