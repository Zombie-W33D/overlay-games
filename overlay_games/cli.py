import argparse
import sys

from . import actions, lua_registry, steam, trust_conf
from .paths import DEFAULT_LUA, DEFAULT_TRUST


def build_parser():
    p = argparse.ArgumentParser(prog="overlay-games", description=(
        "Manage which games render as trusted click-through desktop overlays "
        "(the hyprland-clickthrough project)."))
    p.add_argument("--config", default=DEFAULT_LUA, help="game-overlays.lua path (default: %(default)s)")
    p.add_argument("--trust", default=DEFAULT_TRUST, help="clickthrough allowlist path (default: %(default)s)")
    p.add_argument("--no-reload", action="store_true", help="skip hyprctl reload after changes")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("gui", help="launch the graphical manager")

    lp = sub.add_parser("list", help="list registered overlay games and installed Steam games")
    lp.add_argument("--installed", action="store_true", help="also list every installed Steam game")

    ap = sub.add_parser("add", help="register a game as an overlay")
    ap.add_argument("--steam", dest="steam_appid", metavar="APPID", help="Steam app id")
    ap.add_argument("--local", dest="local_class", metavar="CLASS", help="window class of a local game")
    ap.add_argument("--name", help="display name")
    ap.add_argument("--widget", action="store_true", help=(
        "idle/desktop-pet game: keep float + click-through but let it size itself "
        "(no full-screen overlay enforcement, no hover bounce)"))

    rp = sub.add_parser("remove", help="unregister a game")
    rp.add_argument("--steam", dest="steam_appid", metavar="APPID", help="Steam app id")
    rp.add_argument("--local", dest="local_class", metavar="CLASS", help="window class of a local game")

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    if not args.command or args.command == "gui":
        from .gui import run
        return run(args)

    if args.command == "list":
        return _list(args)

    if args.command == "add":
        try:
            if args.steam_appid:
                g = steam.app_by_id(args.steam_appid)
                cls = actions.add_steam(args.config, args.steam_appid,
                                        args.name or (g["name"] if g else None),
                                        widget=args.widget)
            elif args.local_class:
                cls = actions.add_local(args.config, args.trust, args.local_class,
                                        args.name or "", widget=args.widget)
            else:
                print("error: add needs --steam APPID or --local CLASS", file=sys.stderr)
                return 2
        except actions.ActionError as e:
            print("error:", e, file=sys.stderr)
            return 2
        print("registered", cls)
        return _reload(args)

    if args.command == "remove":
        try:
            if args.steam_appid:
                cls = actions.remove_steam(args.config, args.steam_appid)
            elif args.local_class:
                cls = actions.remove_local(args.config, args.trust, args.local_class)
            else:
                print("error: remove needs --steam APPID or --local CLASS", file=sys.stderr)
                return 2
        except actions.ActionError as e:
            print("error:", e, file=sys.stderr)
            return 2
        print("removed", cls)
        return _reload(args)

    return 0


def _list(args):
    print("registered overlay games (%s):" % args.config)
    entries = lua_registry.read_entries(args.config)
    if not entries:
        print("  (none)")
    for e in entries:
        tag = "steam" if e["kind"] == "steam" else "local"
        print("  [%s] %-32s %s" % (tag, e["name"], e["class"]))
    if args.installed:
        print("\ninstalled Steam games:")
        for g in steam.installed_games():
            print("  %-9s %s" % (g["appid"], g["name"]))
    return 0


def _reload(args):
    if args.no_reload:
        return 0
    ok, msg = actions.reload_hypr()
    try:
        actions.reload_trust()
    except actions.ActionError:
        pass
    if not ok:
        print("warning: config errors after reload:\n%s" % msg, file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())