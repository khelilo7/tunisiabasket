"""One place that runs the Tesseract program, tuned for many tiny parallel calls.

Tesseract starts its own OpenMP threads. Running many copies at once (we OCR hundreds of small cells in parallel) on a
machine with few CPUs, such as a 2-vCPU server or a CI runner, makes those threads fight each other and a single
call can take minutes. OMP_THREAD_LIMIT=1 keeps each copy to one thread; our own worker pool provides the parallelism.
"""
import os
import subprocess

ENV = {**os.environ, "OMP_THREAD_LIMIT": "1"}
TIMEOUT = 60  # seconds per call (normally ~0.05 s); one retry before giving up


def workers() -> int:
    """Parallel Tesseract calls: about two per CPU, at most 8."""
    return max(2, min(8, (os.cpu_count() or 2) * 2))


def run(args, data: bytes) -> str:
    """Run `tesseract stdin stdout <args>` on PNG bytes and return the text."""
    cmd = ["tesseract", "stdin", "stdout", *args]
    for attempt in (1, 2):
        try:
            r = subprocess.run(cmd, input=data, capture_output=True, timeout=TIMEOUT, env=ENV, check=False)
            return r.stdout.decode(errors="ignore").strip()
        except subprocess.TimeoutExpired:
            if attempt == 2:
                raise
    return ""
