"""Countries of the players' nationalities (ISO 3166-1 alpha-2 codes), with their English and French names.

Every player is Tunisian unless a profile says otherwise (assets/players_info.json, or the admin: data/players_info.json), so "TN" is the default and
the site only marks the other nationalities. The same codes (with their names) are listed in static/index.html (COUNTRY); tests/test_bios.py checks the two lists agree.
"""
import re

DEFAULT = "TN"
COUNTRIES = {
    "TN": ("Tunisia", "Tunisie"), "DZ": ("Algeria", "Algérie"), "MA": ("Morocco", "Maroc"), "LY": ("Libya", "Libye"), "EG": ("Egypt", "Égypte"),
    "FR": ("France", "France"), "US": ("United States", "États-Unis"), "CA": ("Canada", "Canada"), "GB": ("United Kingdom", "Royaume-Uni"),
    "HR": ("Croatia", "Croatie"), "RS": ("Serbia", "Serbie"), "SI": ("Slovenia", "Slovénie"), "ES": ("Spain", "Espagne"), "IT": ("Italy", "Italie"),
    "SN": ("Senegal", "Sénégal"), "NG": ("Nigeria", "Nigéria"), "CI": ("Ivory Coast", "Côte d’Ivoire"), "GA": ("Gabon", "Gabon"), "CM": ("Cameroon", "Cameroun"),
    "ML": ("Mali", "Mali"), "GN": ("Guinea", "Guinée"), "CD": ("DR Congo", "RD Congo"), "CG": ("Congo", "Congo"), "GH": ("Ghana", "Ghana"),
    "AO": ("Angola", "Angola"), "BF": ("Burkina Faso", "Burkina Faso"), "CV": ("Cape Verde", "Cap-Vert"), "SS": ("South Sudan", "Soudan du Sud"), "RW": ("Rwanda", "Rwanda"),
    "BI": ("Burundi", "Burundi"), "MR": ("Mauritania", "Mauritanie"), "BJ": ("Benin", "Bénin"), "TG": ("Togo", "Togo"), "LB": ("Lebanon", "Liban"),
    "SY": ("Syria", "Syrie"), "PS": ("Palestine", "Palestine"), "JO": ("Jordan", "Jordanie"), "TR": ("Turkey", "Turquie"), "BR": ("Brazil", "Brésil"),
    # more teams the national team can meet (AfroBasket, qualifiers, friendlies)
    "UG": ("Uganda", "Ouganda"), "CF": ("Central African Republic", "République centrafricaine"), "MG": ("Madagascar", "Madagascar"), "KE": ("Kenya", "Kenya"),
    "MZ": ("Mozambique", "Mozambique"), "ZA": ("South Africa", "Afrique du Sud"), "ZW": ("Zimbabwe", "Zimbabwe"), "ZM": ("Zambia", "Zambie"), "ET": ("Ethiopia", "Éthiopie"),
    "SD": ("Sudan", "Soudan"), "TD": ("Chad", "Tchad"), "NE": ("Niger", "Niger"), "GM": ("Gambia", "Gambie"), "SL": ("Sierra Leone", "Sierra Leone"), "LR": ("Liberia", "Libéria"),
    "BW": ("Botswana", "Botswana"), "NA": ("Namibia", "Namibie"), "TZ": ("Tanzania", "Tanzanie"), "DE": ("Germany", "Allemagne"), "GR": ("Greece", "Grèce"), "LT": ("Lithuania", "Lituanie"),
    "CN": ("China", "Chine"), "JP": ("Japan", "Japon"), "IR": ("Iran", "Iran"), "SA": ("Saudi Arabia", "Arabie saoudite"), "QA": ("Qatar", "Qatar"), "AE": ("United Arab Emirates", "Émirats arabes unis"),
}


def clean(v):
    """The nationality typed or stored (one code, 'SN, FR', ['SN', 'FR'], or empty) as a list of known codes, in order, without repeats.
    ValueError for a code that is not in COUNTRIES. Empty means: no nationality given, so Tunisian."""
    if v in (None, "", []):
        return []
    parts = v if isinstance(v, (list, tuple)) else re.split(r"[\s,;/+]+", str(v))
    out = []
    for c in parts:
        c = str(c).strip().upper()
        if not c:
            continue
        if c not in COUNTRIES:
            raise ValueError(f"Unknown country code {c}. Use two letters like SN or US (known: {', '.join(sorted(COUNTRIES))}).")
        if c not in out:
            out.append(c)
    return out


def flag(code):
    """The flag emoji of a country code."""
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code)


def lookup(text):
    """The code of a country typed as a code or as its English or French name ('Nigeria', 'nigéria', 'NG'), or None."""
    t = _fold(text)
    if not t:
        return None
    for code, (en, fr) in COUNTRIES.items():
        if t in (code.lower(), _fold(en), _fold(fr)):
            return code
    return None


def _fold(s):
    import unicodedata
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()).strip()
