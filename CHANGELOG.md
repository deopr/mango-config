# Changelog

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
