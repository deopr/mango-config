# Changelog

## 0.5.0 — 2026-11-18

A Material 3 remaster of the whole app, plus the pending parsing fixes.

### New look

- Dark-first Material 3 design whose accent is generated from Mango's live
  `focus_color`, with tonal surfaces, containers, outlines and state layers
  derived from it. The light palette is used when the desktop does not prefer
  dark; `MANGO_CONFIG_THEME=light|dark` overrides the choice.
- New custom app bar with the Mango logo, an engine chip (DMS or Mango), the
  version, and native window controls.
- Reworked 244 px navigation drawer: grouped categories, icons, pill-shaped
  selection, and a search field that filters pages by name or description.
- Every page now has an icon tile, Material typography, and a path chip that
  shows the relevant config file relative to the config folder.
- Settings are grouped into filled cards with accent bars, hover rows, and
  optional descriptions. Inputs, spin buttons, dropdowns, switches, check
  chips, sliders, popovers, expanders, keycaps, and scrollbars all follow the
  same Material treatment.
- Restyled every custom page: bars and presets, tiling layouts and tag badges,
  monitor cards, colour cards, wallpaper previews, window rules, keybind
  groups, and the countdown guard dialog.
- The action bar keeps status on the left and gives Reload and Apply fixed
  positions on the right. Status messages use success and error colours.
- Empty states are now explicit cards instead of bare labels.

### Fixes

- Monitor and window rules written as `monitor_rule = ...` or
  `window_rule = ...` (spaces around `=`) are recognized again. Previously the
  editor treated the restored rule as invisible and appended a second,
  incomplete rule.
- Width and height are only written together with refresh, because Mango
  rejects a monitor rule that sets them without it.
- Keybinds written as `bind = SUPER, Return, spawn, kitty` are parsed again.
  The Keybinds page now lists all 80 binds from the DMS-adapted config instead
  of showing an empty page.
- Keyboard **Variant** and **Options** fields expand to the full row width, so
  placeholders and long values are readable.
- Fixed the Night light and Default apps navigation icons on icon themes that
  lack the original names.

## 0.4.3 — 2026-11-14

Monitor and window rule parsing fixes.

- Rule lines written as `monitor_rule = ...` or `window_rule = ...` (spaces
  around `=`) are now recognized. Previously the editor treated the restored
  rule as invisible and appended a second, incomplete rule.
- Width and height are only written together with refresh, because Mango
  rejects a monitor rule that sets them without it. The page note now says so.
- Added regression tests for spaced rule lines and for dropping an incomplete
  resolution instead of writing an invalid rule.

## 0.4.2 — 2026-11-14

Monitor-rule scale fix.

- The monitor-rule editor now defaults **Scale** to `1.0` when the rule has
  no scale. Previously it defaulted to `0` and GTK clamped the spin button to
  its `0.01` minimum, so applying the page silently added `scale:0.01` to
  every rule. That made the logical screen 100× too large and could take the
  output down with it.
- Applying monitor rules no longer adds a `scale` key unless one existed or
  you actually changed the value.

## 0.4.1 — 2026-11-14

Tiling IPC fix for Mango 0.18.5.

- `mmsg dispatch` now receives one comma-joined payload
  (`focusmon,HDMI-A-1`, `setlayout,tile`) instead of separate argv entries.
  This is the syntax required by current Mango and fixes the Tiling page's
  “could not focus … unknown function” error.
- Added a regression test that checks the exact argv passed to `mmsg`.

## 0.4.0 — 2026-11-14

Bars, tiling presets, and a layout CLI.

- New **Bar** page under Desktop for both mangobar and Waybar. Each bar gets a
  live running/stopped card with start, stop and restart buttons, quick
  top-level settings (height, layer, position, margins), current module
  summary, and confirmed presets. Presets keep a timestamped copy in
  `.autobak` before replacing `config.jsonc` and `style.css`.
- Five mangobar and four Waybar presets, including Catppuccin Mocha, Rosé Pine
  Moon and Tokyo Night palettes. Credited sources are linked on each card.
  Waybar presets use `ext/workspaces` and a `custom/layout` module instead of
  Hyprland-only modules.
- New **Tiling** page under Desktop with live per-monitor layout symbols, tag
  badges, family-grouped layout cards, and a filter. Clicking a card focuses
  the selected monitor with `mmsg dispatch focusmon` and applies
  `setlayout` to its current tag.
- Tiling defaults can be saved per monitor. The page maintains a clearly
  marked `tag_rule = id:*, monitor_name:…, layout_name:…` block at the end of
  `config.conf`, preserving all other rules and comments.
- New `mango-config --print-layout` prints the focused monitor's layout
  symbol for Waybar's `custom/layout` module.
- The global Apply footer now hides on the Bar and Tiling pages, since those
  pages write their own files or apply through IPC immediately.
- Reader tests now cover nested JSONC updates, preset writes and backups, the
  managed tiling block, CLI version and `--print-layout`.

## 0.3.1 — 2026-11-03

Keyboard map and XKB layout page.

- Keybinds now opens with a compact US-ANSI keyboard reference. Keys that
  appear in a bind are tinted; click `Super` to filter the existing grouped
  list to every Super shortcut, then click another key to narrow it to that
  chord. Click the key again (or Clear) to remove the filter.
- New **Keyboard** page under Input for `xkb_rules_layout`,
  `xkb_rules_variant` and `xkb_rules_options`, with the active Mango layout
  read through IPC. The layout setting is added only when it is missing and
  the user actually changes the dropdown.

## 0.3.0 — 2026-11-01

Brightness, default apps, and wallpaper fitting.

- New **Brightness** page under Display: a live 0–100 slider backed by a local
  `light-brightness` helper, `brightnessctl`, `light`, or a writable sysfs
  backlight. It reports the active backend and never edits the Mango config.
- New **Default apps** page under Behavior: choose the terminal, file manager
  and web browser for XDG links and folders. It writes
  `~/.config/mimeapps.list`, preserves other entries, and backs the file up
  first. Mango keybinds are left alone.
- Wallpaper now supports Fill, Fit, Stretch, Center and Tile, plus 90° rotation
  and horizontal/vertical flips. The preview uses the monitor shape, and the
  selected fit is baked into a monitor-sized image before applying, so portrait
  or mismatched images no longer surprise you.
- Fuzzel quick pick and normal wallpaper apply now share the same fit/render
  path. Wallpaper options are remembered between launches.
- Tests cover desktop-entry/mimeapps editing, brightness parsing, wallpaper
  options, all fit modes, rotation/flips, and an end-to-end wallpaper apply
  through a fake helper.

## 0.2.3 — 2026-10-31

Full three- and four-key chords.

- The shortcut editor now uses one **Combo** field. Type the whole chord
  directly, such as `SUPER+CTRL+P` or `SUPER+SHIFT+ALT+T`; the app splits it
  into modifiers and the final key when writing the config.
- Keycap summaries and search render every modifier, so three- and four-key
  chords stay visible on the grouped action card.
- Existing one- and two-key bindings still round-trip without being rewritten,
  including bindings with no modifiers.
- Tests now cover loading, adding and preserving three- and four-key chords,
  plus stable repeat Apply.

## 0.2.2 — 2026-10-31

Group multiple shortcuts under one action.

- Keybinds with the same action and args now appear once as a single card,
  showing every key combo plus a shortcut count. For example, `Super+Return`
  and `Super+T` for kitty no longer need two separate rows.
- Each card can add or remove shortcuts and edit the shared action/args in
  place. Newly added shortcuts are inserted beside their action instead of at
  the end of the file.
- Keybind search and counts understand actions versus shortcuts, and the
  updated screenshot shows the grouped layout.
- GUI tests cover grouping, adding/removing a shortcut, insertion order and
  stable repeat Apply.

## 0.2.1 — 2026-10-31

Restore the expanded window-rule editor.

- The Window rules page now has a collapsible help card explaining what rules
  are and listing every editable variable.
- Each rule exposes `app_id`, `title`, floating, fullscreen, open silently,
  global, overlay, terminal, width, height, monitor, tags, and the
  blur/border/shadow/radius/animation effect toggles.
- Rules can be added, edited, expanded/collapsed and deleted directly. Explicit
  deletes are applied; untracked lines and unknown keys are still preserved.
- Validation now rejects unknown window-rule options so a typo cannot be
  written silently.
- GUI tests cover field edits, adding/deleting rules, blank-rule dropping and
  stable repeat Apply.

## 0.2.0 — 2026-10-31

Add Wallpaper and Night light pages.

- New **Wallpaper** page under Appearance: filenames on the left, live image
  preview on the right, search, current-wallpaper marker, and a Fuzzel
  text-only quick pick.
- Wallpaper applies through `light-wallpaper` when available (keeping palette
  and shell sync), with a `swaybg` fallback for other setups.
- New **Night light** page under Display: enable/disable gammastep and set a
  color temperature from 2000K to 6500K. Settings are remembered; apply is
  live and session-only.
- Wallpaper and Night light are separate from the global Apply flow and never
  rewrite Mango config.
- Version/docs/tests updated; wallpaper scanning and new page construction are
  covered by the test suite.

## 0.1.1 — 2026-10-29

Fix window rules handling:

- Rules tab now finds rules files in subdirectories (`dms/`, `cfg/`) even when no
  `window_rule=` line exists yet to score them by content (`WINDOWRULES` no longer
  stays `None`).
- Apply no longer deletes `window_rule=` lines that aren't in the in-memory pool;
  untracked rules are preserved as-is.
- `is_floating` is only written when it was originally present or the Floating
  switch is on, instead of being force-added to every rule.
- Blank rules (no `app_id`/`title`) are skipped on Apply instead of written out.

## 0.1.0 — 2026-10-29

First public release.

- Single-file GTK4 settings app for the Mango Wayland compositor.
- Tabs for layout, theme colors, base colors, cursor, mouse, touchpad, outputs,
  window rules and keybinds.
- Config auto-discovery: follows `source=` / `source_optional=` from
  `config.conf` and classifies files by content. Works with single-file, split
  and DMS-generated configs.
- Safe Apply: timestamped backups in `.autobak/`, validation with `mango -p`,
  automatic rollback on errors, and reload through the Mango IPC socket.
- Inline 10-second display guard for output changes, with automatic revert.
- Keybind editor with search, grouped accordion sections, keycap combos and
  per-bind editing.
- `--config-dir`, `--tab`, `--no-reload` and `--version` CLI options.
- User-level installer with an opt-in `--migrate-dms` migration.
