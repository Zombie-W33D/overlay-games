import glob
import os
import re
import subprocess

from .paths import STEAM_ROOT

LAUNCH_OPTIONS = "WINE_LAYERED_OVERLAY_ALPHA=1 WINE_LAYERED_OVERLAY_INPUT_SHAPE=1 %command%"
PRIORITY = "250"


class SteamConfigError(Exception):
    pass


def steam_is_running():
    try:
        return bool(subprocess.run(["pgrep", "-x", "steam"], capture_output=True, text=True).stdout.split())
    except OSError:
        return False


def localconfig_candidates():
    return sorted(glob.glob(os.path.join(STEAM_ROOT, "userdata", "*", "config", "localconfig.vdf")))


def config_vdf_path():
    p = os.path.join(STEAM_ROOT, "config", "config.vdf")
    return p if os.path.isfile(p) else None


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _block(text, key, from_pos=0):
    """Locate the '{...}' block whose header is the standalone token "key".

    Returns (open_idx, after_close) where text[open_idx:after_close] is the
    block including both braces, or None."""
    lt = len(text)
    needle = '"%s"' % key
    search_from = from_pos
    while True:
        i = text.find(needle, search_from)
        if i == -1:
            return None
        if i > 0 and text[i - 1] not in " \t\r\n":
            search_from = i + 1
            continue
        j = i + len(needle)
        k = j
        while k < lt and text[k] in " \t\r\n":
            k += 1
        if text[k:k + 1] != "{":
            search_from = i + 1
            continue
        depth = 1
        p = k + 1
        in_str = False
        while p < lt and depth:
            c = text[p]
            if in_str:
                if c == "\\":
                    p += 2
                    continue
                if c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
            p += 1
        return (k, p)
    return None


def _close_of(block_text):
    """Index of the block's own closing '}' (its last non-whitespace char)."""
    for i in range(len(block_text) - 1, -1, -1):
        if not block_text[i].isspace():
            return i
    return -1


def _set_value(block_text, key, value):
    """Replace key's value inside a block's inner text (text that starts right
    after '{' and ENDS WITH the closing '}'), or append it just before the
    closing brace keeping that line's indentation."""
    newval = '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')
    pat = re.compile(r'("' + re.escape(key) + r'"\s*)("(?:[^"\\]|\\.)*")')
    if pat.search(block_text):
        return pat.sub(lambda m: m.group(1) + newval, block_text, count=1)
    idx = _close_of(block_text)
    k = idx
    while k > 0 and block_text[k - 1] in " \t":
        k -= 1
    lead = block_text[k:idx]
    return block_text[:k] + lead + '"%s"\t\t%s\n' % (key, newval) + lead + block_text[idx:]


def _insert_entry(block_text, entry_lines):
    """Append a new '"{appid}"\n{\n...\n}' entry before the block's closing
    brace, keeping the closing brace's indentation."""
    idx = _close_of(block_text)
    k = idx
    while k > 0 and block_text[k - 1] in " \t":
        k -= 1
    lead = block_text[k:idx]
    body = "".join(lead + ln + "\n" for ln in entry_lines)
    return block_text[:k] + body + lead + block_text[idx:]


def _entry_block(block_text, appid):
    """(open_idx, after_close) of the appid's entry within block_text, or None."""
    return _block(block_text, appid)


def _entry_inner(entry):
    """Full text of an entry block, e.g. '{...}'. Returns (header, inner_with_close)
    where inner_with_close starts after '{' and ends with the closing '}'."""
    open_idx = entry.index("{")
    return entry[:open_idx + 1], entry[open_idx + 1:]


def _pick_localconfig(appid):
    candidates = localconfig_candidates()
    if not candidates:
        raise SteamConfigError("no Steam local config found (unexpected?)")
    for path in candidates:
        text = _read(path)
        apps = _block(text, "apps")
        if not apps:
            continue
        open_idx, after_close = apps
        if _block(text[open_idx + 1:after_close - 1], appid) is not None:
            return path
    return candidates[0]


def get_launch_options(appid):
    path = _pick_localconfig(appid)
    text = _read(path)
    apps = _block(text, "apps")
    if not apps:
        return ""
    open_idx, after_close = apps
    apps_block = text[open_idx:after_close]
    entry = _entry_block(apps_block, appid)
    if not entry:
        return ""
    eo, ep = entry
    _, inner = _entry_inner(apps_block[eo:ep])
    m = re.search(r'("LaunchOptions"\s*)("(?:[^"\\]|\\.)*")', inner)
    return m.group(2)[1:-1].replace('\\"', '"').replace("\\\\", "\\") if m else ""


def set_launch_options(appid, value=LAUNCH_OPTIONS):
    path = _pick_localconfig(appid)
    text = _read(path)
    apps = _block(text, "apps")
    if not apps:
        raise SteamConfigError("%s has no apps section" % path)
    ao, ap = apps
    apps_block = text[ao:ap]

    entry = _entry_block(apps_block, appid)
    if entry:
        eo, ep = entry
        entry_block = apps_block[eo:ep]
        header, inner = _entry_inner(entry_block)
        inner = _set_value(inner, "LaunchOptions", value)
        apps_block = apps_block[:eo] + header + inner + apps_block[ep:]
    else:
        apps_block = _insert_entry(
            apps_block,
            ['"%s"' % appid, "{", '\t"LaunchOptions"\t\t"%s"' % value, "}"],
        )

    _write(path, text[:ao] + apps_block + text[ap:])
    return path


def set_compat_tool(appid, tool_name):
    path = config_vdf_path()
    if not path:
        raise SteamConfigError("no Steam config.vdf found")
    text = _read(path)
    cm = _block(text, "CompatToolMapping")
    if not cm:
        raise SteamConfigError("no CompatToolMapping section in %s" % path)
    co, cp = cm
    cm_block = text[co:cp]

    entry = _entry_block(cm_block, appid)
    if entry:
        eo, ep = entry
        entry_block = cm_block[eo:ep]
        header, inner = _entry_inner(entry_block)
        inner = _set_value(inner, "name", tool_name)
        inner = _set_value(inner, "config", "")
        inner = _set_value(inner, "priority", PRIORITY)
        cm_block = cm_block[:eo] + header + inner + cm_block[ep:]
    else:
        cm_block = _insert_entry(
            cm_block,
            ['"%s"' % appid, "{",
             '\t"name"\t\t"%s"' % tool_name,
             '\t"config"\t\t""',
             '\t"priority"\t\t"%s"' % PRIORITY, "}"],
        )

    _write(path, text[:co] + cm_block + text[cp:])
    return path


def get_compat_tool(appid):
    path = config_vdf_path()
    if not path:
        return ""
    text = _read(path)
    cm = _block(text, "CompatToolMapping")
    if not cm:
        return ""
    co, cp = cm
    cm_block = text[co:cp]
    entry = _entry_block(cm_block, appid)
    if not entry:
        return ""
    eo, ep = entry
    _, inner = _entry_inner(cm_block[eo:ep])
    m = re.search(r'("name"\s*)("(?:[^"\\]|\\.)*")', inner)
    return m.group(2)[1:-1].replace('\\"', '"') if m else ""


def state(appid):
    return {"launch": get_launch_options(appid), "tool": get_compat_tool(appid)}


def detect_ge_proton():
    """Return the GE-Proton compat tool name Steam already uses, or None."""
    path = config_vdf_path()
    if not path:
        return None
    text = _read(path)
    cm = _block(text, "CompatToolMapping")
    if not cm:
        return None
    co, cp = cm
    cm_block = text[co:cp]
    for appid in ("4126220",):
        entry = _entry_block(cm_block, appid)
        if entry:
            eo, ep = entry
            _, inner = _entry_inner(cm_block[eo:ep])
            m = re.search(r'("name"\s*)("(?:[^"\\]|\\.)*")', inner)
            if m and "GE-Proton" in m.group(2):
                return m.group(2)[1:-1]
    for m in re.finditer(r'("name"\s*)("(?:[^"\\]|\\.)*GE-Proton[^"\n]*")', cm_block):
        name = m.group(2)[1:-1]
        if "GE-Proton" in name:
            return name
    return None


def apply_steam_setup(appid, tool_name=None):
    """Write launch options + GE-Proton compat mapping for a Steam app.

    Returns a human-readable summary. Steam rewrites these files when it
    exits, so if it is running the change may not survive until restart."""
    tool_name = tool_name or detect_ge_proton()
    if not tool_name:
        raise SteamConfigError(
            "no GE-Proton found in %s\nSet a GE-Proton compatibility tool for "
            "a game in Steam first, then retry." % (config_vdf_path() or "config.vdf")
        )
    lp_path = set_launch_options(appid)
    cm_path = set_compat_tool(appid, tool_name)
    msg = "Steam launch options + GE-Proton (%s) written (%s, %s)." % (tool_name, lp_path, cm_path)
    if steam_is_running():
        msg += (" Steam is running and rewrites these files on exit, so fully quit "
                "Steam and relaunch it (then start the game) to make it stick.")
    return msg