import glob
import os
import re

from .paths import STEAM_ROOT

# Steam's own tool entries (Proton, runtimes, redistributables) are installed
# like games but are not games — filter them out of the picker.
_TOOL_RE = re.compile(
    r"Proton|Steam Linux Runtime|Steamworks Common Redistributables|"
    r"Steam Controller Configs|SteamPlay",
    re.I,
)


class SteamLibraryError(Exception):
    pass


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def library_paths():
    """Return every steamapps/ dir listed in libraryfolders.vdf, plus the default."""
    vdf = os.path.join(STEAM_ROOT, "steamapps", "libraryfolders.vdf")
    paths = [os.path.join(STEAM_ROOT, "steamapps")]
    text = _read(vdf)
    if text:
        for p in re.findall(r'"path"\s+"([^"]*)"', text):
            paths.append(os.path.join(p, "steamapps"))
    return list(dict.fromkeys(paths))


def _parse_acf(text):
    appid = re.search(r'"appid"\s+"(\d+)"', text)
    name = re.search(r'"name"\s+"((?:[^"\\]|\\.)*)"', text)
    installdir = re.search(r'"installdir"\s+"((?:[^"\\]|\\.)*)"', text)
    if not appid:
        return None
    return {
        "appid": appid.group(1),
        "name": name.group(1) if name else "Unknown",
        "installdir": installdir.group(1) if installdir else "",
    }


def installed_games(include_tools=False):
    """All installed Steam games as [{appid, name, installdir}, ...]."""
    games = {}
    for appdir in library_paths():
        for acf in sorted(glob.glob(os.path.join(appdir, "appmanifest_*.acf"))):
            g = _parse_acf(_read(acf))
            if g:
                games[g["appid"]] = g
    out = list(games.values())
    if not include_tools:
        out = [g for g in out if not _TOOL_RE.search(g["name"])]
    return sorted(out, key=lambda g: g["name"].lower())


def app_by_id(appid):
    for g in installed_games(include_tools=False):
        if g["appid"] == str(appid):
            return g
    return None