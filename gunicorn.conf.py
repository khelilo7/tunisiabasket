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


def post_fork(server, worker):
    """Memory hygiene on Linux (glibc), where a threaded Python server's resident memory tends to creep up even without a leak:
    glibc gives every thread its own memory arena and keeps freed pages. Cap the arenas, and hand freed memory back every 5 minutes.
    Does nothing (silently) on systems without glibc, such as a Mac."""
    try:
        import ctypes
        import threading
        import time
        libc = ctypes.CDLL("libc.so.6")
        libc.mallopt(-8, 2)                      # M_ARENA_MAX = 2

        def trim():
            while True:
                time.sleep(300)
                libc.malloc_trim(0)
        threading.Thread(target=trim, daemon=True, name="malloc-trim").start()
    except (OSError, AttributeError):
        pass
