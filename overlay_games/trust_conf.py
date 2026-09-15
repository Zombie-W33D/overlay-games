import os
import re
import shlex
import subprocess
import tempfile

BEGIN = "# >> overlay-games-tool:begin <<"
END = "# >> overlay-games-tool:end <<"

# The allowlist default already covers every Steam game:
STEAM_DEFAULT = "steam_app_.*"


class TrustError(Exception):
    pass


def read_rules(path):
    text = _read(path)
    m = re.search(re.escape(BEGIN) + r"\n(.*?)\n[ \t]*" + re.escape(END), text, re.S)
    if not m:
        return []
    return [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]


def write_rules(path, rules):
    text = _read(path)
    block = "\n".join([BEGIN] + rules + [END]) + "\n"
    if BEGIN in text:
        start = text.index(BEGIN)
        end = text.index(END, start)
        new_text = text[:start] + block + text[end + len(END):]
    else:
        new_text = text.rstrip("\n") + "\n\n# Managed by the overlay-games tool (do not edit by hand)\n" + block
    _write(path, new_text)


def add_class(path, class_name):
    rules = read_rules(path)
    rule = "^%s$" % class_name
    if rule in rules:
        return False
    rules.append(rule)
    write_rules(path, rules)
    return True


def remove_class(path, class_name):
    rules = read_rules(path)
    rule = "^%s$" % class_name
    if rule not in rules:
        return False
    rules.remove(rule)
    write_rules(path, rules)
    return True


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _write(path, content):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return
    except PermissionError:
        pass
    _write_as_root(path, content)


def _write_as_root(path, content):
    fd, tmp = tempfile.mkstemp(suffix=".conf", prefix="overlay-games-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        cmd = ["pkexec", "install", "-m", "644", "-o", "root", "-g", "root",
               "-D", tmp, path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise TrustError(
                "could not write %s (direct and via pkexec): %s"
                % (path, (r.stderr or "").strip() or "pkexec rejected/absent")
            )
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def needs_sudo_check(path):
    return os.path.exists(path) and not os.access(path, os.W_OK)