import re

BEGIN = "-- >> overlay-games-tool:begin <<"
END = "-- >> overlay-games-tool:end <<"

# One registry entry per line:
#   { kind = "steam", class = "steam_app_123", name = "Some Game" }
#   { kind = "local", class = "My App", name = "My App", widget = true }
_ENTRY = re.compile(
    r'\{\s*kind\s*=\s*"([^"]*)"\s*,\s*class\s*=\s*"([^"]*)"\s*,\s*name\s*=\s*"([^"]*)"'
    r'(?:\s*,\s*widget\s*=\s*(true|false))?\s*\}'
)


class RegistryError(Exception):
    pass


def read_entries(lua_path):
    try:
        with open(lua_path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return []
    m = _block(text)
    if not m:
        return []
    entries = []
    for line in m.group(1).splitlines():
        hit = _ENTRY.search(line)
        if hit:
            entries.append({
                "kind": hit.group(1),
                "class": hit.group(2),
                "name": hit.group(3),
                "widget": hit.group(4) == "true",
            })
    return entries


def write_entries(lua_path, entries):
    with open(lua_path, encoding="utf-8") as f:
        text = f.read()
    if BEGIN not in text:
        raise RegistryError(
            "no managed registry block in %s\n"
            "The config must contain the '%s' markers (see game-overlays.lua.example)." % (lua_path, BEGIN)
        )
    start = text.index(BEGIN)
    end = text.index(END, start)
    block = _render(entries)
    tail = text[end + len(END):]
    if tail and not tail.startswith("\n"):
        tail = "\n" + tail
    new_text = text[:start] + block + tail
    with open(lua_path, "w", encoding="utf-8") as f:
        f.write(new_text)


def _render(entries):
    lines = [BEGIN, "OVERLAY_GAMES = {"]
    for e in entries:
        cls = e["class"].replace("\\", "\\\\").replace('"', '\\"')
        name = e["name"].replace("\\", "\\\\").replace('"', '\\"')
        kind = "steam" if e["kind"] == "steam" else "local"
        widget = ", widget = true" if e.get("widget") else ""
        lines.append('  { kind = "%s", class = "%s", name = "%s"%s },' % (kind, cls, name, widget))
    lines.append("}")
    lines.append(END)
    return "\n".join(lines)


def _block(text):
    return re.search(re.escape(BEGIN) + r"(.*?)" + re.escape(END), text, re.S)


def steamp_class(appid):
    return "steam_app_%s" % appid


def is_steam_class(class_name):
    return bool(re.fullmatch(r"steam_app_\d+", class_name or ""))