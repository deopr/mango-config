#!/usr/bin/env bash
# End-to-end installer tests. Uses throwaway directories only.
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'FAIL - %s\n' "$*" >&2; exit 1; }
ok() { printf 'ok - %s\n' "$*"; }
assert_file() { [[ -f "$1" ]] || fail "missing file: $1"; }
assert_no_file() { [[ ! -e "$1" ]] || fail "unexpected file: $1"; }
assert_grep() { grep -q -- "$1" "$2" || fail "missing '$1' in $2"; }

BIN="$TMP/bin"
DATA="$TMP/share"
DESK="$DATA/applications/io.github.deopr.MangoConfig.desktop"
ICON="$DATA/icons/hicolor/scalable/apps/io.github.deopr.MangoConfig.svg"

# 1. install with a single-file config
CONF="$TMP/conf-single"
mkdir -p "$CONF"
printf 'border_radius=10\n' > "$CONF/config.conf"
"$ROOT/scripts/install.sh" --config-dir "$CONF" --bin-dir "$BIN" --data-dir "$DATA" > "$TMP/install.log"
assert_file "$BIN/mango-config"
[[ -x "$BIN/mango-config" ]] || fail "binary is not executable"
"$BIN/mango-config" --version | grep -q '^mango-config 0.3.0$' || fail "version output"
assert_file "$DESK"
assert_file "$ICON"
assert_grep "Exec=\"$BIN/mango-config\"" "$DESK"
assert_grep 'Icon=io.github.deopr.MangoConfig' "$DESK"
assert_grep 'StartupWMClass=io.github.deopr.MangoConfig' "$DESK"
assert_grep 'Config detected' "$TMP/install.log"
ok "install (single-file config)"

# 2. uninstall keeps the config
"$ROOT/scripts/install.sh" --uninstall --config-dir "$CONF" --bin-dir "$BIN" --data-dir "$DATA" > /dev/null
assert_no_file "$BIN/mango-config"
assert_no_file "$DESK"
assert_no_file "$ICON"
assert_file "$CONF/config.conf"
ok "uninstall keeps config"

# 3. DMS migration
CONF="$TMP/conf-dms"
cp -a "$ROOT/tests/fixtures/dms" "$CONF"
MANGO_BIN=/bin/true "$ROOT/scripts/install.sh" --config-dir "$CONF" --migrate-dms \
    --bin-dir "$BIN" --data-dir "$DATA" > "$TMP/migrate.log"
for name in layout input cursor outputs windowrules colors; do
    assert_file "$CONF/$name.conf"
    assert_no_file "$CONF/dms/$name.conf"
    assert_grep "^source=./$name.conf$" "$CONF/config.conf"
done
assert_file "$CONF/dms/binds.conf"
assert_grep '^source=./binds.conf$' "$CONF/config.conf"
assert_grep '^source=./noctalia.conf$' "$CONF/config.conf"
! grep -Eq '^[[:space:]]*source.*dms/' "$CONF/config.conf" || fail "dms sources remain"
assert_file "$CONF/binds.conf"
[[ $(grep -c '^bind=' "$CONF/binds.conf") -eq 2 ]] || fail "user binds changed"
legacy_backup=$(find "$CONF/.autobak" -maxdepth 1 -type d -name 'migrate-*' -print -quit)
[[ -n "$legacy_backup" ]] || fail "no migration backup"
assert_file "$legacy_backup/config.conf"
ok "DMS migration"

# 4. second migration is a no-op
OUT=$(MANGO_BIN=/bin/true "$ROOT/scripts/migrate_dms.py" --config-dir "$CONF")
printf '%s\n' "$OUT" | grep -q 'Nothing to migrate' || fail "second migration was not a no-op"
ok "migration is idempotent"

# 5. collision: an unsourced legacy file is moved aside, not overwritten
CONF="$TMP/conf-collision"
cp -a "$ROOT/tests/fixtures/dms" "$CONF"
printf 'cursor_size=99\n' > "$CONF/cursor.conf"
MANGO_BIN=/bin/true "$ROOT/scripts/install.sh" --config-dir "$CONF" --migrate-dms \
    --bin-dir "$BIN" --data-dir "$DATA" > /dev/null
assert_grep '^cursor_size=26$' "$CONF/cursor.conf"
[[ -n "$(find "$CONF/.autobak" -type f -path '*/legacy/cursor.conf' -print -quit)" ]] \
    || fail "legacy cursor.conf was not backed up"
ok "collision handling"

# 6. validation failure rolls everything back
CONF="$TMP/conf-rollback"
cp -a "$ROOT/tests/fixtures/dms" "$CONF"
before=$(sha256sum "$CONF/config.conf" | cut -d' ' -f1)
if MANGO_BIN=/bin/false "$ROOT/scripts/install.sh" --config-dir "$CONF" --migrate-dms \
    --bin-dir "$BIN" --data-dir "$DATA" > "$TMP/rollback.log" 2>&1; then
    fail "migration should have failed with /bin/false"
fi
after=$(sha256sum "$CONF/config.conf" | cut -d' ' -f1)
[[ "$before" == "$after" ]] || fail "config.conf was not restored"
for name in layout input cursor outputs windowrules colors; do
    assert_file "$CONF/dms/$name.conf"
    assert_no_file "$CONF/$name.conf"
done
ok "rollback on validation failure"

# 7. dry run changes nothing
CONF="$TMP/conf-dry"
cp -a "$ROOT/tests/fixtures/dms" "$CONF"
OUT=$(MANGO_BIN=/bin/true "$ROOT/scripts/migrate_dms.py" --config-dir "$CONF" --dry-run)
printf '%s\n' "$OUT" | grep -q 'Flatten plan' || fail "dry run did not print a plan"
assert_file "$CONF/dms/layout.conf"
assert_no_file "$CONF/layout.conf"
ok "dry run"

# 8. missing config: warn, still install, do not create config
CONF="$TMP/conf-missing"
"$ROOT/scripts/install.sh" --config-dir "$CONF" --bin-dir "$BIN" --data-dir "$DATA" > "$TMP/missing.log" 2>&1
assert_file "$BIN/mango-config"
assert_no_file "$CONF"
assert_grep 'no Mango config found' "$TMP/missing.log"
ok "missing config warning"

# 9. --no-desktop
CONF="$TMP/conf-nodesk"
mkdir -p "$CONF"
printf 'border_radius=10\n' > "$CONF/config.conf"
rm -f "$DESK" "$ICON"
"$ROOT/scripts/install.sh" --config-dir "$CONF" --bin-dir "$BIN" --data-dir "$DATA" \
    --no-desktop > /dev/null
assert_file "$BIN/mango-config"
assert_no_file "$DESK"
assert_no_file "$ICON"
ok "--no-desktop"

printf '\nAll installer tests passed.\n'
