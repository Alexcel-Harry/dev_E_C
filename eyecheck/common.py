import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile


def redact(text):
    text = re.sub(r"(?im)^.*(?:serial(?:\s+number)?|unique\s*id)\s*[:=].*$", "[identifier redacted]", text)
    text = re.sub(r"/home/[^/\s]+", "/home/USER", text)
    return text


def command(argv, timeout=15):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, errors="replace")
        return {"status": "ok" if p.returncode == 0 else "error", "returncode": p.returncode,
                "stdout": redact(p.stdout), "stderr": redact(p.stderr)}
    except FileNotFoundError:
        return {"status": "missing", "error": f"Missing executable: {argv[0]}"}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": f"Exceeded {timeout} seconds"}


def write_report(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix=".eyecheck-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, allow_nan=False)
            f.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def stats(values):
    values = sorted(float(x) for x in values if math.isfinite(x))
    if not values:
        return {"n": 0, "min": None, "median": None, "p95": None, "max": None}
    def quantile(q):
        i = (len(values) - 1) * q
        lo = int(i)
        hi = min(lo + 1, len(values) - 1)
        return values[lo] + (values[hi] - values[lo]) * (i - lo)
    return {"n": len(values), "min": values[0], "median": quantile(.5),
            "p95": quantile(.95), "max": values[-1]}


def positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("must be finite and positive")
    return value
