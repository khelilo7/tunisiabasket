"""Central file locations.

* DATA_DIR   runtime data (games, official results, admin hash, logs, uploads). NEVER in git. Move it with the
             DATA_DIR environment variable (production: /opt/proastats/shared/data; tests: a temp folder).
* ASSETS_DIR files the code needs (digit templates for reading the federation images). In git.
* SEED_DIR   starting data copied into an empty DATA_DIR on first run. In git.
"""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR") or ROOT / "data").resolve()
ASSETS_DIR = ROOT / "assets"
SEED_DIR = ROOT / "seed"


def ensure_data():
    """First run on an empty data folder: copy the seed (official results, the 48 games read so far, sync state)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not (DATA_DIR / "official.json").exists() and SEED_DIR.exists():
        for src in SEED_DIR.rglob("*"):
            dst = DATA_DIR / src.relative_to(SEED_DIR)
            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
            elif not dst.exists():
                shutil.copy2(src, dst)
