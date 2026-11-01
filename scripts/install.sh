#!/usr/bin/env bash
# mango-config installer — user-level, no sudo.
set -euo pipefail

VERSION="0.2.3"
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
SRC="$ROOT/mango-config"
DESKTOP_SRC="$ROOT/data/io.github.deopr.MangoConfig.desktop.in"
ICON_SRC="$ROOT/data/io.github.deopr.MangoConfig.svg"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/mango"
BIN_DIR="$HOME/.local/bin"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
MIGRATE_DMS=0
DRY_RUN=0
NO_DESKTOP=0
UNINSTALL=0

usage() {
    cat <<EOF
mango-config $VERSION installer

Usage: $0 [options]

Options:
  --config-dir DIR   Mango config directory (default: ~/.config/mango)
  --bin-dir DIR      where to install the executable (default: ~/.local/bin)
  --data-dir DIR     XDG data directory (default: ~/.local/share)
  --migrate-dms      flatten sourced dms/*.conf fragments into the config root
  --no-desktop       do not install the .desktop entry or icon
  --dry-run          show what would happen, change nothing
  --uninstall        remove the app, desktop entry and icon (keeps config)
  -h, --help         show this help
EOF
}

note() { printf '%s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

run() {
    if ((DRY_RUN)); then
        printf '  +'
        printf ' %q' "$@"
        printf '\n'
    else
        "$@"
    fi
}

expand_path() {
    case "$1" in
        "~") printf '%s\n' "$HOME" ;;
        *)
            if [[ ${1:0:1} == "~" && ${1:1:1} == "/" ]]; then
                printf '%s\n' "$HOME/${1:2}"
            else
                printf '%s\n' "$1"
            fi
            ;;
    esac
}

parse_args() {
    while (($#)); do
        case "$1" in
            --config-dir) (($# >= 2)) || die "--config-dir needs a value"; CONFIG_DIR=$2; shift 2 ;;
            --bin-dir) (($# >= 2)) || die "--bin-dir needs a value"; BIN_DIR=$2; shift 2 ;;
            --data-dir) (($# >= 2)) || die "--data-dir needs a value"; DATA_DIR=$2; shift 2 ;;
            --migrate-dms) MIGRATE_DMS=1; shift ;;
            --no-desktop) NO_DESKTOP=1; shift ;;
            --dry-run) DRY_RUN=1; shift ;;
            --uninstall) UNINSTALL=1; shift ;;
            -h|--help) usage; exit 0 ;;
            *) die "unknown option: $1 (try --help)" ;;
        esac
    done
}

check_gtk() {
    command -v python3 >/dev/null 2>&1 || {
        warn "python3 not found. Install Python 3.10+ before running mango-config."
        return
    }
    if ! python3 - <<'PY' >/dev/null 2>&1
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
PY
    then
        warn "PyGObject with GTK4 is missing. Install it, for example:"
        warn "  Fedora:  sudo dnf install python3-gobject gtk4"
        warn "  Arch:    sudo pacman -S python-gobject gtk4"
        warn "  Ubuntu:  sudo apt install python3-gi gir1.2-gtk-4.0"
    fi
}

main() {
    parse_args "$@"
    CONFIG_DIR=$(expand_path "$CONFIG_DIR")
    BIN_DIR=$(expand_path "$BIN_DIR")
    DATA_DIR=$(expand_path "$DATA_DIR")

    local bin_dst="$BIN_DIR/mango-config"
    local desktop_dst="$DATA_DIR/applications/io.github.deopr.MangoConfig.desktop"
    local icon_dst="$DATA_DIR/icons/hicolor/scalable/apps/io.github.deopr.MangoConfig.svg"

    if ((UNINSTALL)); then
        note "Removing mango-config (configuration is kept):"
        run rm -f "$bin_dst" "$desktop_dst" "$icon_dst"
        note "  binary:  $bin_dst"
        note "  desktop: $desktop_dst"
        note "  icon:    $icon_dst"
        note "Done. Your Mango config was not touched."
        return 0
    fi

    [[ -f "$SRC" ]] || die "mango-config not found at $SRC"
    check_gtk

    note "Installing mango-config $VERSION"
    note "  binary: $bin_dst"
    run mkdir -p "$BIN_DIR"
    run install -m 755 "$SRC" "$bin_dst"

    if ((NO_DESKTOP == 0)); then
        [[ -f "$DESKTOP_SRC" ]] || die "missing desktop template: $DESKTOP_SRC"
        [[ -f "$ICON_SRC" ]] || die "missing icon: $ICON_SRC"
        note "  desktop: $desktop_dst"
        note "  icon:    $icon_dst"
        if ((DRY_RUN)); then
            note "  + write desktop entry"
            note "  + install icon"
        else
            mkdir -p "$(dirname "$desktop_dst")" "$(dirname "$icon_dst")"
            local tmp
            tmp=$(mktemp)
            sed "s|@EXEC@|\"$bin_dst\"|g" "$DESKTOP_SRC" > "$tmp"
            install -m 644 "$tmp" "$desktop_dst"
            rm -f "$tmp"
            install -m 644 "$ICON_SRC" "$icon_dst"
            if command -v update-desktop-database >/dev/null 2>&1; then
                update-desktop-database "$DATA_DIR/applications" >/dev/null 2>&1 || true
            fi
            if command -v gtk-update-icon-cache >/dev/null 2>&1; then
                gtk-update-icon-cache -f -t "$DATA_DIR/icons/hicolor" >/dev/null 2>&1 || true
            fi
        fi
    fi

    local conf="$CONFIG_DIR/config.conf"
    if [[ -f "$conf" ]]; then
        if grep -Eq '^[[:space:]]*source(_optional)?[[:space:]]*=[[:space:]]*.*dms/' "$conf"; then
            note ""
            note "DMS-style config detected: $conf"
            if ((MIGRATE_DMS)); then
                local margs=(--config-dir "$CONFIG_DIR")
                if ((DRY_RUN)); then
                    margs+=(--dry-run)
                fi
                python3 "$SCRIPT_DIR/migrate_dms.py" "${margs[@]}"
            else
                note "The app can read it as-is. To move sourced dms/*.conf fragments"
                note "to the config root, run: $0 --migrate-dms"
            fi
        else
            note ""
            note "Config detected: $conf (the app auto-detects its layout)."
        fi
    elif [[ -f "$CONFIG_DIR/config.toml" ]]; then
        warn "only config.toml found at $CONFIG_DIR — this version edits config.conf; convert it first."
    else
        warn "no Mango config found at $conf"
        warn "start Mango once or copy /etc/mango/config.conf there, then reopen the app."
    fi

    note ""
    note "Done. Run: $bin_dst"
    note "  (make sure $BIN_DIR is on your PATH)"
}

main "$@"
