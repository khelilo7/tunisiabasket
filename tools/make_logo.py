"""Builds the Tunisia Basket logo files from code, so every size is the same drawing.

    pip install fonttools uharfbuzz resvg-py pillow        (only for this script; the site itself needs nothing)
    python tools/make_logo.py        writes static/img/brand/*.svg, the header wordmark (assets/brand/wordmark.svg.html) and the PNG / ICO / share image files of static/img

The lettering is Barlow Condensed (SIL Open Font License, assets/brand/fonts/): the letters are turned into outlines, so the logo looks the same on every device and no font is loaded.
The mark is a basketball with the Tunisian flag's disc, crescent and star at its centre. Colours: the flag red and the site's dark navy.
"""
import math
from io import BytesIO
from pathlib import Path

import resvg_py
import uharfbuzz as hb
from PIL import Image, ImageFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "brand" / "fonts"
OUT = ROOT / "static" / "img" / "brand"
RED, NAVY, WHITE, INK = "#D9323A", "#0B101A", "#FFFFFF", "#0B101A"
BRIGHT_RED = "#EE4B52"                    # the red used on the dark background: a little lighter so it keeps its contrast


# ------------------------------------------------------------------ lettering
class Face:
    def __init__(self, name):
        self.file = str(FONTS / name)
        self.tt = TTFont(self.file)
        self.gs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt["head"].unitsPerEm
        self.cap = self.tt["OS/2"].sCapHeight
        blob = hb.Blob.from_file_path(self.file)
        self.hbfont = hb.Font(hb.Face(blob))

    def shape(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hbfont, buf, {"kern": True})
        return [(self.order[i.codepoint], p.x_advance, p.x_offset) for i, p in zip(buf.glyph_infos, buf.glyph_positions)]

    def width(self, text, size, tracking=0.0):
        k = size / self.upem
        gl = self.shape(text)
        return sum(a for _, a, _ in gl) * k + tracking * (len(gl) - 1)

    def path(self, text, x, baseline, size, tracking=0.0):
        """SVG path data of the text with its left edge at x and its baseline at y; the tracking is in the same units as the size."""
        k, pen_x, parts = size / self.upem, x, []
        for name, adv, off in self.shape(text):
            pen = SVGPathPen(self.gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
            self.gs[name].draw(TransformPen(pen, (k, 0, 0, -k, pen_x + off * k, baseline)))
            parts.append(pen.getCommands())
            pen_x += adv * k + tracking
        return " ".join(p for p in parts if p)


BOLD, SEMI = Face("BarlowCondensed-ExtraBold.ttf"), Face("BarlowCondensed-SemiBold.ttf")


# ------------------------------------------------------------------ the mark
def fill(c):
    """A colour as an SVG attribute; the inline header version passes var(--logo-red), which only works in a style."""
    return f'style="fill:{c}"' if c.startswith("var(") else f'fill="{c}"'


def star(cx, cy, R, rot=-90):
    pts = []
    for i in range(10):
        r = R if i % 2 == 0 else R * 0.382
        a = math.radians(rot + i * 36)
        pts.append(f"{cx + r * math.cos(a):.2f},{cy + r * math.sin(a):.2f}")
    return "M" + " L".join(pts) + "Z"


def crescent(c1, r1, c2, r2):
    """A crescent opening to the right: the circle (c1, r1) minus the circle (c2, r2), both on the horizontal axis."""
    d = c2 - c1
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(r1 * r1 - a * a)
    x = c1 + a
    return f"M{x:.2f},{-h:.2f} A{r1},{r1} 0 1 0 {x:.2f},{h:.2f} A{r2},{r2} 0 1 1 {x:.2f},{-h:.2f}Z"


SHADE = {RED: "#B01F27", BRIGHT_RED: "#CF3840", "var(--logo-red)": "var(--logo-red-dark)"}          # the darker red of the ball's shadow side
TILT = -14                                                                                              # the seams lean, the flag stays upright: the ball turns while the emblem looks at you


def mark(uid, cx, cy, R, seam=1.0, ball=RED, disc=WHITE, glyph=RED, simple=False, mono=False):
    """The ball, centred on (cx, cy) with radius R. `seam` thickens the seams for tiny sizes. The seams are cut out of the ball, so it works on any background.
    A thin darker crescent on the lower right gives it volume without a gradient; the seams lean by TILT degrees."""
    k, w = R / 100, 9.5 * seam
    seams = (
        "M-104,-31 Q0,6 104,-31",                 # upper seam: a smile that frames the disc
        "M-104,31 Q0,-6 104,31",                  # lower seam
        "M44,-106 Q80,0 44,106",                  # the side seam that gives the ball its turn
    )
    g, tilt, shade = 1.0, TILT, True
    if simple:                                   # tiny sizes (favicons): one seam and a bigger flag disc, the fine lines would only turn into mush
        seams, w, g, tilt, shade = (seams[2],), 15.0, 1.12, 0, False
    if mono:                                     # one colour: the flag disc is cut out of the ball too, the crescent and the star stay in the ball's colour
        shade, glyph = False, ball
    cut = (f'<circle r="{42 * g:.1f}" fill="#000"/>' if mono else "") + f'<g transform="rotate({tilt})">' + "".join(f'<path d="{s}" stroke="#000" stroke-width="{w:.1f}" fill="none" stroke-linecap="round"/>' for s in seams) + "</g>"
    shadow = (f'<clipPath id="{uid}c"><circle r="100"/></clipPath><circle r="100" {fill(SHADE.get(ball, ball))} mask="url(#{uid})"/>'
              f'<g clip-path="url(#{uid}c)"><circle cx="-5" cy="-6" r="100" {fill(ball)} mask="url(#{uid})"/></g>') if shade else f'<circle r="100" {fill(ball)} mask="url(#{uid})"/>'
    return (f'<g transform="translate({cx} {cy}) scale({k:.4f})">'
            f'<mask id="{uid}" maskUnits="userSpaceOnUse" x="-110" y="-110" width="220" height="220"><rect x="-110" y="-110" width="220" height="220" fill="#fff"/>{cut}</mask>'
            f'{shadow}'
            + ("" if mono else f'<circle r="{42 * g:.1f}" {fill(disc)}/>') +
            f'<g transform="scale({g})"><path d="{crescent(-4, 26, 3.5, 21)}" {fill(glyph)}/>'
            f'<path d="{star(7, 0, 11)}" {fill(glyph)}/></g></g>')


# ------------------------------------------------------------------ lock-ups
def tagline(x, baseline, size, color, slash_color, width=None):
    """PRO A / STATS & SCORES in spaced capitals. With `width` the size is chosen so the line is exactly that wide (it lines up with the wordmark above it); returns (svg, size)."""
    a, b = "PRO A", "STATS & SCORES"
    track, gap_em, slash_em, n = 0.16, 1.15, 0.3, len(a) + len(b) - 2
    if width:
        unit = (SEMI.width(a, 1000) + SEMI.width(b, 1000)) / 1000
        size = width / (unit + track * n + 2 * gap_em + slash_em)
    tr, gap = track * size, gap_em * size
    wa = SEMI.width(a, size, tr)
    sx = x + wa + gap
    h = size * SEMI.cap / SEMI.upem
    svg = (f'<path d="{SEMI.path(a, x, baseline, size, tr)}" fill="{color}"/>'
           f'<path d="M{sx:.2f},{baseline:.2f} L{sx + size * slash_em:.2f},{baseline - h:.2f}" stroke="{slash_color}" stroke-width="{size * 0.11:.2f}" stroke-linecap="round"/>'
           f'<path d="{SEMI.path(b, sx + size * slash_em + gap, baseline, size, tr)}" fill="{color}"/>')
    return svg, size


def wordmark_stack(x, y_top, cap, color_a, color_b, tagline_color, slash_color):
    """TUNISIA over BASKET, both lines the same width (the tracking of the narrower one is opened up), with the tagline fitted to that width underneath. Returns (svg, width, height)."""
    size = cap / BOLD.cap * BOLD.upem
    wt, wb = BOLD.width("TUNISIA", size), BOLD.width("BASKET", size)
    width = max(wt, wb)
    tr_t, tr_b = (width - wt) / 6, (width - wb) / 5
    base1, base2 = y_top + cap, y_top + cap * 2 + cap * 0.14
    tag_h = None
    # the tagline's cap height follows from the width it must fill, so measure it first
    _, t_size = tagline(0, 0, 0, "#000", "#000", width)
    tag_h = t_size * SEMI.cap / SEMI.upem
    base3 = base2 + cap * 0.30 + tag_h
    tag, _ = tagline(x, base3, 0, tagline_color, slash_color, width)
    svg = (f'<path d="{BOLD.path("TUNISIA", x, base1, size, tr_t)}" fill="{color_a}"/>'
           f'<path d="{BOLD.path("BASKET", x, base2, size, tr_b)}" fill="{color_b}"/>{tag}')
    return svg, width, base3 - y_top


def svg_doc(w, h, body, bg=None, title="Tunisia Basket"):
    rect = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" width="{w:g}" height="{h:g}" role="img" aria-label="{title}"><title>{title}</title>{rect}{body}</svg>\n'


def primary(dark=False, bg=True):
    """The main logo: the mark, then TUNISIA / BASKET and the tagline."""
    pad, D = 70, 250
    cap = 92
    txt, tw, th = wordmark_stack(0, 0, cap, WHITE if dark else INK, WHITE if dark else INK, "#9AA6C0" if dark else "#59647F", BRIGHT_RED if dark else RED)
    gap = 56
    H = max(D, th) + pad * 2
    cy = H / 2
    body = (mark("pm", pad + D / 2, cy, D / 2 - 2, ball=BRIGHT_RED if dark else RED) +
            f'<g transform="translate({pad + D + gap} {cy - th / 2:.2f})">{txt}</g>')
    W = pad * 2 + D + gap + tw
    return svg_doc(round(W), round(H), body, (NAVY if dark else WHITE) if bg else None)


def header_line(dark=True, with_tagline=True, bg=True):
    """The website header lock-up: the mark, TUNISIA BASKET on one line, and the tagline under it (optional)."""
    D, cap = 120, 62
    size = cap / BOLD.cap * BOLD.upem
    tr = size * 0.012
    w1, w2 = BOLD.width("TUNISIA ", size, tr), BOLD.width("BASKET", size, tr)
    c1, c2 = (WHITE, BRIGHT_RED) if dark else (INK, RED)
    gap, pad = 30, 40
    tag_cap = 15
    t_size = tag_cap / SEMI.cap * SEMI.upem
    block_h = cap + (34 + tag_cap if with_tagline else 0)
    H = max(D, block_h) + pad * 2
    top = H / 2 - block_h / 2
    x = pad + D + gap
    body = mark("hm", pad + D / 2, H / 2, D / 2, ball=BRIGHT_RED if dark else RED)
    body += f'<path d="{BOLD.path("TUNISIA", x, top + cap, size, tr)}" fill="{c1}"/><path d="{BOLD.path("BASKET", x + w1, top + cap, size, tr)}" fill="{c2}"/>'
    if with_tagline:
        tag, _ = tagline(x, top + cap + 34 + tag_cap, t_size, "#9AA6C0" if dark else "#59647F", BRIGHT_RED if dark else RED)
        body += tag
    W = x + w1 + w2 + pad
    return svg_doc(round(W), round(H), body, (NAVY if dark else WHITE) if bg else None)


def social_icon(size=512):
    """The square app / social icon: the mark on the navy, with the rounded corners phones expect."""
    r = size * 0.225
    body = f'<rect width="{size}" height="{size}" rx="{r:.1f}" fill="{NAVY}"/>' + mark("si", size / 2, size / 2, size * 0.355, ball=BRIGHT_RED)
    return svg_doc(size, size, body)


def mark_only(seam=1.0, uid="mo", ball=RED, simple=False, mono=False):
    return svg_doc(220, 220, mark(uid, 110, 110, 104, seam, ball=ball, simple=simple, mono=mono))


def wordmark_inline():
    """TUNISIA BASKET as outlines for the site header: the first word takes the page's text colour (currentColor), the second the logo red (var(--logo-red))."""
    cap = 62
    size = cap / BOLD.cap * BOLD.upem
    tr = size * 0.012
    w1, w2 = BOLD.width("TUNISIA ", size, tr), BOLD.width("BASKET", size, tr)
    W, H = round(w1 + w2), cap + 2
    return (f'<svg class="wm" viewBox="0 0 {W} {H}" aria-hidden="true" focusable="false"><path fill="currentColor" d="{BOLD.path("TUNISIA", 0, cap, size, tr)}"/>'
            f'<path style="fill:var(--logo-red)" d="{BOLD.path("BASKET", w1, cap, size, tr)}"/></svg>'), W / H


def render(svg, w, h=None, bg=None):
    return Image.open(BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg, width=w, height=h or w, background=bg)))).convert("RGBA")


def rasters(files):
    """The PNG, ICO and JPEG files of static/img, drawn from the same SVG code."""
    img = ROOT / "static" / "img"
    for n in (16, 32, 48, 96, 192):                               # favicons: the simple mark on a transparent square
        render(files["mark-small.svg"], n).save(img / f"favicon-{n}.png")
    render(files["mark-small.svg"], 96).save(ROOT / "static" / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    for n in (192, 512):                                          # the app icons of the manifest: the rounded social icon
        render(files["social-icon.svg"], n).save(img / f"icon-{n}.png")
    apple = svg_doc(180, 180, f'<rect width="180" height="180" fill="{NAVY}"/>' + mark("ap", 90, 90, 66, ball=BRIGHT_RED))          # full bleed: iOS rounds the corners itself
    render(apple, 180).convert("RGB").save(img / "apple-touch-icon.png")
    render(files["mark.svg"], 96).save(img / "logo-96.png")
    render(files["mark.svg"], 512).save(img / "logo.png")
    og = Image.new("RGB", (1200, 630), NAVY)                      # the share image: the dark logo with a soft glow of the flag red behind the mark
    glow = Image.radial_gradient("L").resize((1040, 1040)).point(lambda v: int(max(0, 255 - v * 1.42) * 0.34))
    og.paste(Image.new("RGB", glow.size, RED), (330 - 520, 315 - 520), glow)
    lg = render(primary(True, bg=False), 1000, round(1000 * 390 / 829))
    og.paste(lg, ((1200 - lg.width) // 2, (630 - lg.height) // 2), lg)
    og.save(img / "og-image.jpg", quality=93)


def wordmark_file(dark):
    """TUNISIA BASKET on one line, transparent background, for the picture generators of the admin (drawn on a canvas) and the posters."""
    cap = 62
    size = cap / BOLD.cap * BOLD.upem
    tr = size * 0.012
    w1, w2 = BOLD.width("TUNISIA ", size, tr), BOLD.width("BASKET", size, tr)
    c1, c2 = (WHITE, BRIGHT_RED) if dark else (INK, RED)
    body = f'<path d="{BOLD.path("TUNISIA", 0, cap, size, tr)}" fill="{c1}"/><path d="{BOLD.path("BASKET", w1, cap, size, tr)}" fill="{c2}"/>'
    return svg_doc(round(w1 + w2), cap + 2, body)


def brand_sheet(files):
    """exports/brand-sheet.png: the identity on one page (logos, clear space, smallest sizes, colours, lettering)."""
    W_, H_ = 2400, 1800
    sheet = Image.new("RGB", (W_, H_), (244, 246, 250))
    from PIL import ImageDraw
    d = ImageDraw.Draw(sheet)
    f = lambda face, px: ImageFont.truetype(str(FONTS / face), px)
    black, semi = "BarlowCondensed-ExtraBold.ttf", "BarlowCondensed-SemiBold.ttf"
    d.text((90, 70), "TUNISIA BASKET", font=f(black, 74), fill=INK)
    d.text((90, 156), "VISUAL IDENTITY  ·  PRO A STATS & SCORES", font=f(semi, 30), fill=(89, 100, 127))
    sheet.paste(render(files["logo-primary.svg"], 1020, round(1020 * 390 / 829), bg="#FFFFFF"), (90, 230))
    sheet.paste(render(files["logo-primary-dark.svg"], 1020, round(1020 * 390 / 829)), (1290, 230))
    # clear space: the height of the star's circle (the flag disc) around the mark, drawn on the mark
    d.text((90, 780), "CLEAR SPACE", font=f(semi, 26), fill=(89, 100, 127))
    m = render(files["mark.svg"], 300)
    cx0, cy0 = 90 + 120, 890
    d.rectangle((cx0 - 60, cy0 - 60, cx0 + 360, cy0 + 360), outline=(217, 50, 58), width=3)
    sheet.paste(m, (cx0, cy0), m)
    d.text((90, 1250), "Keep free around the mark: one flag disc (0.42 of its radius × 2).", font=f(semi, 24), fill=INK)
    # smallest sizes
    d.text((700, 780), "SMALLEST SIZES", font=f(semi, 26), fill=(89, 100, 127))
    x = 700
    for px in (96, 64, 48, 32, 24, 16):
        src = files["mark.svg"] if px >= 48 else files["mark-small.svg"]
        im = render(src, px)
        sheet.paste(im, (x, 850 + (96 - px)), im)
        d.text((x, 960), f"{px}px", font=f(semi, 22), fill=INK)
        x += px + 40
    d.text((700, 1010), "Below 48 px: the simplified mark.", font=f(semi, 24), fill=INK)
    # one-colour versions
    d.text((700, 1080), "ONE COLOUR", font=f(semi, 26), fill=(89, 100, 127))
    sheet.paste(render(files["mark-black.svg"], 110, bg="#FFFFFF"), (700, 1130))
    inv = Image.new("RGB", (130, 130), NAVY)
    inv.paste(render(files["mark-white.svg"], 110), (10, 10), render(files["mark-white.svg"], 110))
    sheet.paste(inv, (860, 1120))
    # colours
    d.text((1290, 780), "COLOURS", font=f(semi, 26), fill=(89, 100, 127))
    for i, (name, hexv, rgb) in enumerate([("Flag red", RED, (217, 50, 58)), ("Bright red (on dark)", BRIGHT_RED, (238, 75, 82)), ("Night", NAVY, (11, 16, 26)), ("Mist", "#9AA6C0", (154, 166, 192)), ("White", WHITE, (255, 255, 255))]):
        x0 = 1290 + i * 215
        d.rounded_rectangle((x0, 840, x0 + 190, 1010), radius=16, fill=rgb, outline=(210, 214, 224), width=2)
        d.text((x0, 1030), name, font=f(semi, 24), fill=INK)
        d.text((x0, 1062), hexv.upper(), font=f(semi, 24), fill=(89, 100, 127))
    # lettering
    d.text((1290, 1130), "LETTERING", font=f(semi, 26), fill=(89, 100, 127))
    d.text((1290, 1170), "Barlow Condensed ExtraBold", font=f(black, 64), fill=INK)
    d.text((1290, 1250), "Barlow Condensed SemiBold  ·  PRO A  /  STATS & SCORES", font=f(semi, 36), fill=(89, 100, 127))
    d.text((1290, 1310), "SIL Open Font License", font=f(semi, 24), fill=(89, 100, 127))
    # in use
    d.text((90, 1380), "IN USE", font=f(semi, 26), fill=(89, 100, 127))
    hd = render(files["logo-header.svg"], 1100, round(1100 * files["_header_ratio"]))
    sheet.paste(hd, (90, 1430))
    ic = render(files["social-icon.svg"], 300)
    sheet.paste(ic, (1290, 1430), ic)
    (ROOT / "exports").mkdir(exist_ok=True)
    sheet.save(ROOT / "exports" / "brand-sheet.png")


def facebook():
    """The Facebook page pictures: exports/facebook-profile.png (1080x1080, shown as a circle: the mark sits well inside it) and exports/facebook-cover.png (1640x624; the phone shows
    only the middle 78% of the width and the top and bottom are trimmed, so the lock-up stays inside that safe area)."""
    from PIL import ImageDraw, ImageFilter
    out = ROOT / "exports"
    out.mkdir(exist_ok=True)

    def backdrop(w, h, glow_at, glow_r):
        bg = Image.new("RGB", (w, h), NAVY)
        top = Image.new("RGB", (w, h), (20, 28, 48))
        mask = Image.linear_gradient("L").resize((w, h)).transpose(Image.FLIP_TOP_BOTTOM)
        bg = Image.composite(top, bg, mask.point(lambda v: int(v * 0.55)))
        g = Image.new("L", (w, h), 0)
        ImageDraw.Draw(g).ellipse((glow_at[0] - glow_r, glow_at[1] - glow_r, glow_at[0] + glow_r, glow_at[1] + glow_r), fill=95)
        bg.paste(Image.new("RGB", (w, h), RED), (0, 0), g.filter(ImageFilter.GaussianBlur(glow_r * 0.55)))
        return bg

    # profile: the mark, centred, with a quiet glow of the flag red behind it
    prof = backdrop(1080, 1080, (540, 540), 420)
    m = render(mark_only(1.0, "fp", BRIGHT_RED), 700)
    prof.paste(m, (190, 190), m)
    prof.save(out / "facebook-profile.png")
    # cover: court lines as a faint texture, the lock-up in the middle of the safe area, the address under it
    W_, H_ = 1640, 624
    cov = backdrop(W_, H_, (560, 330), 520)
    lines = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
    d = ImageDraw.Draw(lines)
    for r in (150, 250, 350):
        d.ellipse((1240 - r, 312 - r, 1240 + r, 312 + r), outline=(255, 255, 255, 18), width=3)          # a centre circle running off the right edge
    d.line((1240, 0, 1240, H_), fill=(255, 255, 255, 18), width=3)
    cov = cov.convert("RGBA")
    cov.alpha_composite(lines)
    hdr = header_line(True, True, bg=False)
    vb = hdr.split('viewBox="0 0 ')[1].split('"')[0].split()
    lw = 940
    lg = render(hdr, lw, round(lw * float(vb[1]) / float(vb[0])))
    cov.alpha_composite(lg, ((W_ - lw) // 2, (H_ - lg.height) // 2 - 22))
    f = ImageFont.truetype(str(FONTS / "BarlowCondensed-SemiBold.ttf"), 38)
    dd = ImageDraw.Draw(cov)
    text = "TUNISIABASKET.COM"
    wd = sum(dd.textlength(c, font=f) for c in text) + 8 * (len(text) - 1)
    x = (W_ - wd) / 2
    for c in text:
        dd.text((x, H_ - 118), c, font=f, fill=(154, 166, 192, 255))
        x += dd.textlength(c, font=f) + 8
    cov.convert("RGB").save(out / "facebook-cover.png")


def mark_inline():
    """The mark for the site header: its red follows the theme (var(--logo-red))."""
    return f'<svg class="bm" viewBox="0 0 220 220" aria-hidden="true" focusable="false">{mark("lgm", 110, 110, 104, ball="var(--logo-red)", glyph="var(--logo-red)")}</svg>'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "logo-primary.svg": primary(False), "logo-primary-dark.svg": primary(True), "logo-header.svg": header_line(True), "logo-header-light.svg": header_line(False),
        "social-icon.svg": social_icon(), "mark.svg": mark_only(), "mark-black.svg": mark_only(1.0, "mk", INK, mono=True), "mark-white.svg": mark_only(1.0, "mw", WHITE, mono=True), "wordmark-dark.svg": wordmark_file(True), "wordmark-light.svg": wordmark_file(False), "mark-small.svg": mark_only(1.0, "ms", simple=True), "mark-dark.svg": mark_only(1.0, "md", BRIGHT_RED),
    }
    for name, svg in files.items():
        (OUT / name).write_text(svg)
    inline, ratio = wordmark_inline()
    (ROOT / "assets" / "brand" / "wordmark.svg.html").write_text(inline)
    (ROOT / "assets" / "brand" / "mark.svg.html").write_text(mark_inline())
    rasters(files)
    hdr = header_line(True)
    files_for_sheet = {**files, "_header_ratio": float(hdr.split('viewBox="0 0 ')[1].split('"')[0].split()[1]) / float(hdr.split('viewBox="0 0 ')[1].split('"')[0].split()[0])}
    brand_sheet(files_for_sheet)
    facebook()
    print("wrote", ", ".join(files), "and assets/brand/wordmark.svg.html (aspect %.3f), then the PNG / ICO / share files of static/img" % ratio)


if __name__ == "__main__":
    main()
