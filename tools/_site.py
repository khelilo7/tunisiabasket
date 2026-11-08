"""Shared by the tools that talk to a running site's admin panel: log in once, keep the session."""
import getpass
import os
import sys

import requests


def login(site):
    token = os.environ.get("ADMIN_TOKEN") or getpass.getpass(f"Admin token for {site} (not shown): ")
    s = requests.Session()
    s.headers["Origin"] = site
    r = s.post(f"{site}/admin/api/login", json={"token": token}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Login refused ({r.status_code}).")
    return s
