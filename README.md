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

### Steam launch options + GE-Proton

Registering a Steam game can **also** write the two runtime settings that make
the overlay render correctly into Steam itself:

1. Launch options:
   `WINE_LAYERED_OVERLAY_ALPHA=1 WINE_LAYERED_OVERLAY_INPUT_SHAPE=1 %command%`
2. Force the per-game compatibility tool to **GE-Proton** (the name is copied
   from whichever GE-Proton is already configured for another game, e.g.
   Crusaders Quest).

The GUI checkbox **Steam: launch options + *GE-Proton*** (on by default when a
GE-Proton tool is detected) does both; the CLI equivalent is
`./overlay-games add --steam APPID --steam-setup`.

> **Steam keeps its config in memory and rewrites these files when it exits.**
> If Steam is running when you register, the write may be silently overwritten
> on the next Steam exit. **Fully quit Steam (Steam menu → Exit) before
> registering with the setup box checked**, then relaunch Steam and start the
> game. Verify afterwards with `./overlay-games list --steam-setup`.
>
> The manual fallback for a single game: Steam → Properties → Launch options
> `WINE_LAYERED_OVERLAY_ALPHA=1 WINE_LAYERED_OVERLAY_INPUT_SHAPE=1 %command%`,
> and Properties → Compatibility → force GE-Proton.

### Known limitations (widget mode)

- **Auto-focus is a little buggy in both modes** — a hovered overlay window
  (widget or regular overlay) may not be focused immediately. It's rarer on a
  regular (non-widget) launch, but happens sometimes in both. The same
  workaround kicks it into a reliable state from then on: a few manual focus
  changes. Note for later investigation.
- **Cursor warp to screen center on focus-out** — sometimes when focus changes
  from the game to something else, the mouse jumps to the center of the
  screen. Fix soon.
- **No quickshell auto-avoid** — widget games are never resized/moved to line
  up with the bar. Deliberate: games that don't support dynamic resize get
  messed up by forced repositions, which causes jittering. Trade-off: an
  expanded widget can temporarily cover the bar strip.

## Confirmed working games

Games verified on this setup, in the mode they're registered in (live
registry: `~/.config/hypr/game-overlays.lua`).

### Featured overlay (full-screen, see-through)

| Game | Window class |
| --- | --- |
| Crusaders Quest: Hero Town | `steam_app_4126220` |
| Idlemon | `steam_app_4122700` |
| Desktop Raid | `steam_app_3122460` |
| Tiny Monster Haven | `steam_app_3669020` |

### Widget mode (self-sizing, `--widget` / widget checkbox)

| Game | Window class |
| --- | --- |
| Idle Waters | `steam_app_2963540` |
| Berserk B.I.T.S | `steam_app_2348540` |
| Loafing Town | `steam_app_3625210` |
| My Little Life | `steam_app_2834600` |
| Mushroom Nook | `steam_app_4211860` |
| Rogue AI: Idle Domination | `steam_app_3894900` |
| Cozy Mining | `steam_app_4283650` |
| dEscape | `steam_app_2390060` |
| The Dream Globe | `steam_app_3820130` |
| Your Big, Cute Monster Farm | `steam_app_3659410` |
| Village Tale | `steam_app_3447510` |
| Little Aviary | `steam_app_3437350` |

## Requirements

- Hyprland build with the trusted click-through patch (see the parent project)
- Python 3.10+ and PySide6 (`pip install -r requirements.txt`)
- `pkexec` present when the tool needs to edit the root-owned allowlist

## Usage

### GUI

```
./overlay-games            # or: python3 main.py
```

- **Left pane** lists installed Steam games (scanned from every
  `libraryfolders.vdf` Steam library). Select one and **Register →**.
- **Right pane** shows what's registered. Select an entry and **← Unregister**.
- **Add local game…** registers a non-Steam game by window class. The dialog can
  pull the class from a currently running window. Local games get their class
  written into the click-through allowlist (polkit prompt appears if needed).

### CLI

```
# list registered games (add --installed to also list the Steam library)
./overlay-games list --installed

# verify the launch options + compat tool Steam actually has for registered games
./overlay-games list --steam-setup

# register / unregister a Steam app
./overlay-games add --steam 4126220
./overlay-games remove --steam 4126220

# register an idle/desktop-pet game as a widget (keeps float + click-through,
# lets the game size itself by cursor hover — no full-screen enforcement)
./overlay-games add --steam 2348540 --widget

# also write Steam launch options + force GE-Proton (GUI equivalent: the
# "Steam: launch options + GE-Proton" checkbox when registering)
./overlay-games add --steam 4126220 --steam-setup

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
  steam_config.py  # write Steam launch options + GE-Proton mapping (config.vdf/localconfig.vdf)
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