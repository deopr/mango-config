#!/usr/bin/env python3
"""Move sourced DMS config fragments to the Mango config root.

Only files that are actually pulled in by config.conf (source= or
source_optional=) are moved. Unsourced files, including dms/binds.conf, are
left alone. Every change is backed up under .autobak/migrate-<timestamp>/ and
the whole migration is rolled back if `mango -p` rejects the result.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

SOURCE_RE = re.compile(r"^(\s*)(source_optional|source)(\s*=\s*)(.+)$")


def expand_source(value, config_dir):
    value = value.strip().strip('"').strip("'")
    home = os.path.expanduser("~")
    value = value.replace("${HOME}", home).replace("$HOME", home)
    if value.startswith("~"):
        return os.path.normpath(os.path.expanduser(value))
    if value.startswith("./"):
        return os.path.normpath(os.path.join(config_dir, value[2:]))
    if os.path.isabs(value):
        return os.path.normpath(value)
    guess = os.path.join(config_dir, value)
    return os.path.normpath(guess if os.path.exists(guess) else value)


def inside(path, directory):
    path = os.path.realpath(path)
    directory = os.path.realpath(directory)
    try:
        return os.path.commonpath([path, directory]) == directory
    except ValueError:
        return False


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text or "")


def validate(config_dir, mango_bin):
    conf = os.path.join(config_dir, "config.conf")
    try:
        res = subprocess.run([mango_bin, "-p", "-c", conf],
                             capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        return None, "mango binary not found: " + mango_bin
    except Exception as ex:
        return None, "validator failed: %s" % ex
    out = strip_ansi((res.stdout or "") + (res.stderr or "")).strip()
    bad = res.returncode != 0 or re.search(
        r"\berror\b|unknown keyword|exceeds|invalid", out, re.I)
    return (not bad), out[:500]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Flatten sourced DMS fragments into the Mango config root.")
    ap.add_argument("--config-dir", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mango-bin", default=os.environ.get("MANGO_BIN", "mango"))
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args(argv)

    config_dir = os.path.abspath(os.path.expanduser(args.config_dir))
    conf = os.path.join(config_dir, "config.conf")
    dms_dir = os.path.join(config_dir, "dms")
    if not os.path.isfile(conf):
        print("error: no config.conf in " + config_dir, file=sys.stderr)
        return 2
    if not os.path.isdir(dms_dir):
        print("Nothing to migrate: no dms/ directory in " + config_dir)
        return 0

    lines = open(conf, encoding="utf-8").readlines()
    sourced = set()
    for raw in lines:
        m = SOURCE_RE.match(raw.rstrip("\n"))
        if m:
            sourced.add(os.path.realpath(expand_source(m.group(4), config_dir)))

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = os.path.join(config_dir, ".autobak", "migrate-" + stamp)
    plan_by_src = {}
    planned_dests = set()
    legacy = []
    skipped = []

    for idx, raw in enumerate(lines):
        m = SOURCE_RE.match(raw.rstrip("\n"))
        if not m:
            continue
        raw_value = m.group(4).strip()
        if "$" in raw_value and "$HOME" not in raw_value and "${HOME}" not in raw_value:
            skipped.append(raw_value + " (unresolved variable)")
            continue
        src = expand_source(raw_value, config_dir)
        if not os.path.isfile(src) or not inside(src, dms_dir):
            continue
        base = os.path.basename(src)
        dest = os.path.join(config_dir, base)
        if dest in planned_dests:
            skipped.append(base + " (another sourced file maps to the same target)")
            continue
        if os.path.exists(dest):
            if os.path.realpath(dest) in sourced:
                skipped.append(base + " (target is already sourced; not overwritten)")
                continue
            move_aside = os.path.join(backup_dir, "legacy", base)
            legacy.append((dest, move_aside))
        planned_dests.add(dest)
        entry = plan_by_src.setdefault(src, {
            "src": src, "dest": dest, "base": base, "indices": [], "prefixes": []})
        entry["indices"].append(idx)
        entry["prefixes"].append(m.group(1) + m.group(2) + m.group(3))

    plan = list(plan_by_src.values())
    if not plan:
        print("Nothing to migrate: no sourced files inside dms/.")
        for item in skipped:
            print("  skipped: " + item)
        return 0

    print("Flatten plan (config: %s):" % config_dir)
    for item in plan:
        print("  %s -> %s" % (os.path.relpath(item["src"], config_dir), item["base"]))
    for _dest, move_aside in legacy:
        print("  legacy target -> %s" % os.path.relpath(move_aside, config_dir))
    for item in skipped:
        print("  skipped: " + item)

    if args.dry_run:
        print("Dry run: no files changed.")
        return 0

    os.makedirs(os.path.join(backup_dir, "dms"), exist_ok=True)
    shutil.copy2(conf, os.path.join(backup_dir, "config.conf"))
    for item in plan:
        shutil.copy2(item["src"], os.path.join(backup_dir, "dms", item["base"]))

    moved = []
    new_lines = list(lines)
    try:
        for dest, move_aside in legacy:
            os.makedirs(os.path.dirname(move_aside), exist_ok=True)
            shutil.move(dest, move_aside)
        for item in plan:
            shutil.move(item["src"], item["dest"])
            moved.append(item)
            for idx, prefix in zip(item["indices"], item["prefixes"]):
                new_lines[idx] = prefix + "./" + item["base"] + "\n"

        tmp = conf + ".migrate-tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(new_lines)
        os.replace(tmp, conf)

        if not args.no_validate:
            ok, out = validate(config_dir, args.mango_bin)
            if ok is False:
                raise RuntimeError(out or "mango -p rejected the migrated config")
            if ok is None:
                print("warning: " + out + " (skipping validation)")
    except Exception as ex:
        print("error: %s — rolling back" % ex, file=sys.stderr)
        for item in moved:
            if os.path.exists(item["dest"]):
                shutil.move(item["dest"], item["src"])
        shutil.copy2(os.path.join(backup_dir, "config.conf"), conf)
        for dest, move_aside in legacy:
            if os.path.exists(move_aside):
                shutil.move(move_aside, dest)
        print("Rolled back. Backup kept at " + backup_dir, file=sys.stderr)
        return 1

    print("Migrated %d file(s). Backup: %s" % (len(plan), backup_dir))
    print("Reload Mango (or apply anything in mango-config) to use the new layout.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
