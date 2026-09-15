import argparse
import json
import subprocess
import sys


def running_windows():
    """[(class, title), ...] of the live windows, useful for picking local games."""
    try:
        r = subprocess.run(["hyprctl", "-j", "clients"], capture_output=True, text=True)
        if r.returncode != 0:
            return []
        data = json.loads(r.stdout)
    except (OSError, ValueError):
        return []
    seen = {}
    for w in data:
        cls = w.get("class") or ""
        title = w.get("title") or ""
        if cls and not cls.startswith("__"):
            seen.setdefault(cls, title)
    return sorted((c, t) for c, t in seen.items())


def find_class_hint(name):
    lower = name.lower()
    for cls, title in running_windows():
        if lower in cls.lower() or lower in title.lower():
            return cls
    return None