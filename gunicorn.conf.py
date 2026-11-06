"""Production server settings:  gunicorn -c gunicorn.conf.py app:app
ONE worker on purpose: login sessions, upload jobs and the sync loop live in this process's memory.
Threads give concurrency (reading stats is fast; OCR runs in its own background thread)."""
import os

bind = os.environ.get("BIND", "127.0.0.1:5055")
workers = 1
threads = 8
timeout = 120          # large admin uploads
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
