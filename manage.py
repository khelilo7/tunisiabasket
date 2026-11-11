"""Admin management.   python manage.py new-token   |   new-analytics-token   |   status   |   log   |   backup   (full, verified backup of the data folder into ./backups)"""
import sys

import auth

cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
if cmd == "new-token":
    t = auth.new_token()
    auth.set_token(t)
    print("New admin token (shown once, only its hash is stored; everybody is logged out):\n")
    print("    " + t + "\n")
    print("Log in at /admin with it. Keep it private; run this command again to replace it.")
elif cmd == "new-analytics-token":
    import analytics
    t = auth.new_token()
    analytics.set_token(t)
    print("New analytics token (shown once, only its hash is stored; every analyst is logged out):\n")
    print("    " + t + "\n")
    print("Analysts sign in at /analytics with it. It never opens /admin. Run this command again to replace it.")
elif cmd == "status":
    import analytics
    print("admin token configured:", auth.token_configured())
    print("analytics token configured:", analytics.token_configured())
elif cmd == "log":
    print(auth.LOG_FILE.read_text() if auth.LOG_FILE.exists() else "(no admin activity yet)")
elif cmd == "backup":
    import subprocess
    sys.exit(subprocess.call([sys.executable, str(__import__("pathlib").Path(__file__).parent / "tools" / "backup_data.py"), *sys.argv[2:]]))
else:
    print(__doc__)
