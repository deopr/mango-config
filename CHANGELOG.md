# Changelog

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
