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
env = {**os.environ, "DATA_DIR": tempfile.mkdtemp(prefix="proa-test-"), "NO_HISTORY_GAMES": "1"}      # the box scores of past seasons (assets/history) are off, except for tests/test_history.py
failed = []
for name in ("smoke.py", "test_repo_hygiene.py", "test_stats.py", "test_tiebreak.py", "test_cache.py", "test_positions.py", "test_identity.py", "test_bios.py", "test_traffic.py", "test_monitor.py", "test_follow_social.py", "test_nat1.py", "test_natteam.py", "test_cup_finals.py", "test_history.py", "test_past_season.py", "test_archive.py", "test_records.py", "test_fantasy.py", "test_mvp.py", "test_ballot.py", "test_predict.py", "test_roster.py", "test_content.py", "test_roster_base.py", "test_numbers.py", "test_team_splits.py", "test_team_extra.py", "test_partial_game.py", "test_partial_estimates.py", "test_video_sheet.py", "test_video_analysis_sheet.py", "test_final_sheet.py", "test_count_sheet.py", "test_fix_from_csv.py", "test_game_fixes.py", "test_absences.py", "test_banner.py", "test_rounds.py", "test_plays_notify.py", "test_analytics.py", "test_livescore.py", "test_board_v2.py", "test_import_photos.py", "test_import_game.py", "test_game_sources.py", "test_honours.py", "test_photo_assets.py", "test_upload_photos.py", "test_matchup.py", "test_backup.py", "test_seo.py", "test_i18n.py", "test_security.py", "test_results_images.py", "test_ocr.py"):
    print(f"\n=== {name}")
    run_env = {k: v for k, v in env.items() if k != "NO_HISTORY_GAMES"} if name in ("test_history.py", "test_past_season.py", "test_archive.py", "test_records.py", "test_seo.py") else env
    if subprocess.run([sys.executable, str(root / "tests" / name)], cwd=root, env=run_env).returncode:
        failed.append(name)
shutil.rmtree(env["DATA_DIR"], ignore_errors=True)
print("\nRESULT:", "FAILED: " + ", ".join(failed) if failed else "all checks passed")
sys.exit(1 if failed else 0)
