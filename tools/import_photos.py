"""Local photo import: drop images in exports/photos_inbox/ and run this. Nothing is published.

    python tools/import_photos.py [folder]

A file is matched to a player by its name: `esg-41.jpg` (the player id) or `Firas Lahyani.jpg` (the name, any capitalisation, accents ignored).
Each image is cropped to a centred square (a little above the middle, to keep the face), resized to 320 px, saved as JPEG in data/photos/
and listed in data/player_photos.json, exactly like an admin-panel upload. data/ is never committed and never deployed, so these photos
stay on this computer: use them to show players a preview and ask for their consent. Files that match nobody, or two players, are reported and skipped.
Put the credit of each photo in a text file next to it (`<same name>.txt`); it is copied to data/photos/credits.txt.
"""
import json
import sys
import time
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import stats  # noqa: E402

EXT = {".jpg", ".jpeg", ".png", ".webp"}
norm = lambda s: " ".join("".join(c for c in unicodedata.normalize("NFD", s.lower()) if c.isalnum() or c == " ").split())


def main():
    inbox = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "exports" / "photos_inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    players = stats.build(keep_hidden=True)["players"]
    by_id = {p["id"]: p for p in players}
    by_name = {}
    for p in players:
        by_name.setdefault(norm(p["name"]), []).append(p)
    out = config.DATA_DIR / "photos"
    out.mkdir(parents=True, exist_ok=True)
    index_file = config.DATA_DIR / "player_photos.json"
    try:
        index = json.loads(index_file.read_text())
    except (OSError, ValueError):
        index = {}
    done = 0
    for f in sorted(inbox.iterdir()):
        if f.suffix.lower() not in EXT:
            continue
        stem = f.stem.strip()
        hit = [by_id[stem.lower()]] if stem.lower() in by_id else by_name.get(norm(stem), [])
        if len(hit) != 1:
            print(f"SKIPPED {f.name}: {'no player with this id or name' if not hit else 'several players share this name, use the player id'}")
            continue
        p = hit[0]
        try:
            im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
        except OSError:
            print(f"SKIPPED {f.name}: not a readable image")
            continue
        side = min(im.size)
        x0, y0 = (im.width - side) // 2, int((im.height - side) * 0.2)
        im.crop((x0, y0, x0 + side, y0 + side)).resize((320, 320), Image.LANCZOS).save(out / f"{p['id']}.jpg", "JPEG", quality=86)
        index[p["id"]] = f"/photo/{p['id']}.jpg?v={int(time.time())}"
        credit = f.with_suffix(".txt")
        if credit.exists():
            with open(out / "credits.txt", "a", encoding="utf-8") as c:
                c.write(f"{p['id']} {p['name']}: {credit.read_text().strip()}\n")
        done += 1
        print(f"ok  {f.name} -> {p['name']} ({p['team']} #{p['number']})")
    index_file.write_text(json.dumps(index, indent=1))
    print(f"{done} photo(s) imported into {out}")


if __name__ == "__main__":
    main()
