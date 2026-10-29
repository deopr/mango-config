# Config discovery

`mango-config` does not assume a fixed file layout. At startup it builds a
profile from the files Mango itself would load.

## 1. Find the main file

The app looks for `<config-dir>/config.conf`. If only `config.toml` exists, it
shows a warning and disables Apply, because the editor is line-based.

The default config directory is `~/.config/mango`. Override it with
`--config-dir DIR` or `MANGO_CONFIG_DIR=DIR`.

## 2. Follow includes

Every `source=` and `source_optional=` line is resolved the same way Mango
resolves it:

- `./file.conf` is relative to the **main config directory**
  (`~/.config/mango`), not the including file.
- `~/file.conf` expands to your home directory.
- Absolute paths are used as-is.
- Missing `source_optional` files are skipped.
- Cycles are ignored.
- Sources containing unresolved `$variables` are skipped with a warning.

Files are visited in include order. Later files win for scalar options; that
matches Mango's own application order.

## 3. Classify files by content

Each sourced file is scanned for top-level keys:

| Role | Detected by |
|---|---|
| layout | `border_radius`, `border_px`, `gap_inner_*`, `gap_outer_*`, `smart_gaps`, … |
| input | `mouse_*`, `axis_scroll_factor`, `tap_*`, `trackpad_*`, … |
| cursor | `cursor_size`, `cursor_theme` |
| outputs | `monitor_rule` |
| rules | `window_rule` |
| binds | any key starting with `bind` |
| colors | any key ending in `_color` |

The file with the most matching keys wins for each role. Ties go to the file
loaded later. If a role has no keys, a sourced conventional file
(`layout.conf`, `input.conf`, `binds.conf`, …) is used so that adding a first
entry still works.

Theme colors and base colors are handled separately:

- **base** = the file that last defines `border_color`, `focus_color` or
  `urgent_color` (the effective values).
- **theme** = the file with the most additional `*_color` keys, preferring
  names containing `theme`, `noctalia` or `color`.

Both can point at the same file.

## 4. Profiles this produces

| Setup | Result |
|---|---|
| Single `config.conf` with everything inline | every role points at `config.conf` |
| Flat split files (`layout.conf`, …) | roles point at the matching files |
| DMS (`source=./dms/*.conf`) | roles point inside `dms/`; no migration needed |
| Absolute `~/.config/mango/noctalia.conf` | theme role points there |

## 5. Writing safely

- Apply reads the resolved files again, and **only changes keys that already
  exist**. A control whose key is absent is skipped instead of inventing a
  default.
- Adding a monitor rule, window rule or bind is explicit and appends a line to
  the role's file.
- Unchanged values are not rewritten, so a no-op Apply leaves files
  byte-identical.
- Files are snapshotted first, validated with `mango -p`, and restored on error.

## 6. Flat vs DMS migration

`scripts/install.sh --migrate-dms` moves only the fragments that are sourced
from `dms/` into the config root and rewrites those source lines. It refuses to
overwrite a target that is already sourced, backs up everything first, and
rolls back if validation fails.

The app itself never moves files; discovery is read-only until you press Apply.
