"""Run every check with a throwaway data folder.  python tests/run_all.py   (needs the tesseract program installed)"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if not shutil.which("tesseract"):
    sys.exit("tesseract is not installed (macOS: brew install tesseract, Ubuntu: apt install tesseract-ocr)")
env = {**os.environ, "DATA_DIR": tempfile.mkdtemp(prefix="proa-test-")}
failed = []
for name in ("smoke.py", "test_repo_hygiene.py", "test_stats.py", "test_positions.py", "test_identity.py", "test_bios.py", "test_traffic.py", "test_mvp.py", "test_ballot.py", "test_predict.py", "test_roster.py", "test_content.py", "test_roster_base.py", "test_numbers.py", "test_partial_game.py", "test_partial_estimates.py", "test_video_sheet.py", "test_absences.py", "test_banner.py", "test_rounds.py", "test_analytics.py", "test_import_photos.py", "test_import_game.py", "test_photo_assets.py", "test_upload_photos.py", "test_matchup.py", "test_backup.py", "test_seo.py", "test_i18n.py", "test_security.py", "test_results_images.py", "test_ocr.py"):
    print(f"\n=== {name}")
    if subprocess.run([sys.executable, str(root / "tests" / name)], cwd=root, env=env).returncode:
        failed.append(name)
shutil.rmtree(env["DATA_DIR"], ignore_errors=True)
print("\nRESULT:", "FAILED: " + ", ".join(failed) if failed else "all checks passed")
sys.exit(1 if failed else 0)
