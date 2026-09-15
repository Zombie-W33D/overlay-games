import shlex
import subprocess

from . import lua_registry, trust_conf


class ActionError(Exception):
    pass


def reload_hypr(config_only=True):
    """hyprctl reload [+ configerrors]. Returns (ok, message)."""
    cmd = ["hyprctl", "reload"] + (["config-only"] if config_only else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        return False, out or "hyprctl reload failed"
    err = subprocess.run(["hyprctl", "configerrors"], capture_output=True, text=True)
    problems = (err.stdout or "").strip().splitlines()
    if problems:
        return False, "\n".join(problems)
    return True, ""


def reload_trust():
    r = subprocess.run(["hyprctl", "trusted-clickthrough", "reload"], capture_output=True, text=True)
    if r.returncode != 0:
        raise ActionError((r.stdout or r.stderr or "").strip() or "trusted-clickthrough reload failed")


def _write_registry(lua_path, entries):
    try:
        lua_registry.write_entries(lua_path, entries)
    except lua_registry.RegistryError as e:
        raise ActionError(str(e))


def add_steam(lua_path, appid, name=None):
    entries = lua_registry.read_entries(lua_path)
    cls = lua_registry.steamp_class(appid)
    if any(e["class"] == cls for e in entries):
        raise ActionError("already registered: %s" % cls)
    entries.append({"kind": "steam", "class": cls, "name": name or ("Steam " + str(appid))})
    _write_registry(lua_path, entries)
    return cls


def remove_steam(lua_path, appid):
    entries = lua_registry.read_entries(lua_path)
    cls = lua_registry.steamp_class(appid)
    kept = [e for e in entries if e["class"] != cls]
    if len(kept) == len(entries):
        raise ActionError("not registered: %s" % cls)
    _write_registry(lua_path, kept)
    return cls


def add_local(lua_path, trust_path, class_name, name):
    class_name = class_name.strip()
    name = (name or class_name).strip()
    if not class_name:
        raise ActionError("a window class is required")
    for bad in ('"', "\\", " ", "^", "$"):
        if bad in class_name:
            raise ActionError("class must be a plain window class (no %r)" % bad)
    entries = lua_registry.read_entries(lua_path)
    if any(e["class"] == class_name for e in entries):
        raise ActionError("already registered: %s" % class_name)
    entries.append({"kind": "local", "class": class_name, "name": name})
    _write_registry(lua_path, entries)
    trust_conf.add_class(trust_path, class_name)
    return class_name


def remove_local(lua_path, trust_path, class_name):
    entries = lua_registry.read_entries(lua_path)
    kept = [e for e in entries if e["class"] != class_name]
    if len(kept) == len(entries):
        raise ActionError("not registered: %s" % class_name)
    _write_registry(lua_path, kept)
    trust_conf.remove_class(trust_path, class_name)
    return class_name


def add_entry(lua_path, trust_path, kind, class_name, name=None):
    if kind == "steam":
        appid = class_name.split("_")[-1] if class_name.startswith("steam_app_") else class_name
        return add_steam(lua_path, appid, name)
    return add_local(lua_path, trust_path, class_name, name or class_name)


def remove_entry(lua_path, trust_path, class_name):
    if lua_registry.is_steam_class(class_name):
        return remove_steam(lua_path, class_name.split("_")[-1])
    return remove_local(lua_path, trust_path, class_name)