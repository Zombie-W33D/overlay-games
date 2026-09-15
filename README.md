# overlay-games

Game controller for the **trusted click-through** desktop-overlay project
([hyprland-clickthrough](https://github.com/Zombie-W33D/hyprland-clickthrough)).

It decides *which* games are set up to render as see-through desktop overlays:
a simple GUI (or CLI) to add and remove **Steam games** and **local games**
without hand-editing the Hyprland Lua config.

## What it does

Each registered game is wired into the two places that make an overlay work:

1. **Hyprland rendering rules** — adds the game's `WM_CLASS` to the
   `OVERLAY_GAMES` registry block in `~/.config/hypr/game-overlays.lua`. A
   generic loop turns every entry into the float/size/move/suppress-fullscreen
   rule and into the quickshell-avoidance audit's `is_overlay_window()` check.
2. **Click-through trust** — for *local* (non-Steam) games, adds a `^class$`
   rule to the root-owned allowlist `/etc/hypr/clickthrough.conf` (via `pkexec`
   when needed). Steam games are already covered by the default
   `steam_app_.*` rule.

After every change it runs `hyprctl reload` and
`hyprctl trusted-clickthrough reload`, so the change is live immediately.

### Widget mode

Idle/desktop-pet games (many idle Steam games, "hover to expand" games) size
themselves by cursor hover. Registering them as normal overlays makes the
quickshell-avoidance audit fight their resizes (visible bouncing). Check
**widget mode** in the GUI (or pass `--widget`) to keep float + transparency +
click-through but let the game own its size — no full-screen enforcement, no
bounce. Entry became: `..., widget = true`.

### Known limitations (widget mode)

- **Auto-focus is a little buggy in both modes** — a hovered overlay window
  (widget or regular overlay) may not be focused immediately. It's rarer on a
  regular (non-widget) launch, but happens sometimes in both. The same
  workaround kicks it into a reliable state from then on: a few manual focus
  changes. Note for later investigation.
- **No quickshell auto-avoid** — widget games are never resized/moved to line
  up with the bar. Deliberate: games that don't support dynamic resize get
  messed up by forced repositions, which causes jittering. Trade-off: an
  expanded widget can temporarily cover the bar strip.

> Steam launch options are **not** touched by this tool — set them once per game
> in Steam → Properties → Launch options:
> `WINE_LAYERED_OVERLAY_ALPHA=1 WINE_LAYERED_OVERLAY_INPUT_SHAPE=1 %command%`

## Requirements

- Hyprland build with the trusted click-through patch (see the parent project)
- Python 3.10+ and PySide6 (`pip install -r requirements.txt`)
- `pkexec` present when the tool needs to edit the root-owned allowlist

## Usage

### GUI

```
./overlay-games            # or: python3 main.py
```

- **Right pane** lists installed Steam games (scanned from every
  `libraryfolders.vdf` Steam library). Select one and **Register →**.
- **Left pane** shows what's registered. Select an entry and **← Unregister**.
- **Add local game…** registers a non-Steam game by window class. The dialog can
  pull the class from a currently running window. Local games get their class
  written into the click-through allowlist (polkit prompt appears if needed).

### CLI

```
# list registered games (add --installed to also list the Steam library)
./overlay-games list --installed

# register / unregister a Steam app
./overlay-games add --steam 4126220
./overlay-games remove --steam 4126220

# register an idle/desktop-pet game as a widget (keeps float + click-through,
# lets the game size itself by cursor hover — no full-screen enforcement)
./overlay-games add --steam 2348540 --widget

# register / unregister a local game by window class
./overlay-games add --local VampireSurvivorsLike --name "My Local Game"
./overlay-games remove --local VampireSurvivorsLike
```

Useful flags: `--config <lua>` / `--trust <conf>` point at non-default files
(handy for testing against a copy), `--no-reload` skips the hyprctl reload.

## Layout

```
overlay_games/
  lua_registry.py  # read/write the OVERLAY_GAMES block between -- >> overlay-games-tool:begin << markers
  trust_conf.py    # read/write the allowlist block (pkexec for root-owned files)
  steam.py         # discover installed Steam games from appmanifests
  actions.py       # add/remove orchestration + reload
  hypr.py          # live window discovery (class picker) + hyprctl helpers
  cli.py           # command line interface
  gui.py           # PySide6 interface
```

## Manual fallback

Everything this tool edits is still fully editable by hand:

- `game-overlays.lua`: add a line to the `OVERLAY_GAMES` registry block, or
  add both an `o.window(... game_overlay_rules())` rule *and* an
  `is_overlay_window()` check yourself.
- `/etc/hypr/clickthrough.conf`: append a `^class$` regex line for non-Steam
  classes (`steam_app_.*` already matches all Steam games).

The parent project's README documents the full manual procedure.