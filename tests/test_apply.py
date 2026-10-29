#!/usr/bin/env python3
"""GUI round-trip test: no-op Apply must not rewrite files, edits must survive."""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from importlib.machinery import SourceFileLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "mango-config")
FIX = os.path.join(ROOT, "tests", "fixtures")


def digest(profile_dir):
    h = hashlib.sha256()
    for root, dirs, files in os.walk(profile_dir):
        dirs[:] = [d for d in dirs if d != ".autobak"]
        for name in sorted(files):
            if not name.endswith(".conf"):
                continue
            path = os.path.join(root, name)
            h.update(os.path.relpath(path, profile_dir).encode())
            h.update(open(path, "rb").read())
    return h.hexdigest()


def counts(profile_dir):
    out = {"binds": 0, "rules": 0, "outputs": 0}
    for root, dirs, files in os.walk(profile_dir):
        dirs[:] = [d for d in dirs if d != ".autobak"]
        for name in files:
            if not name.endswith(".conf"):
                continue
            for line in open(os.path.join(root, name), encoding="utf-8"):
                if line.startswith("bind"):
                    out["binds"] += 1
                elif line.startswith("window_rule="):
                    out["rules"] += 1
                elif line.startswith("monitor_rule="):
                    out["outputs"] += 1
    return out


def run_one(profile_dir, label):
    mc = SourceFileLoader("mango_config_apply", APP).load_module()
    prof = mc.discover_profile(profile_dir)
    mc.configure_profile(prof)
    before_hash = digest(profile_dir)
    before_counts = counts(profile_dir)

    app = mc.App(profile=prof, tab="keys", no_reload=True)
    app.register(None)
    app.do_activate()
    app._validate_config = lambda: (True, "")
    app._reload_mango = lambda: True

    app.on_apply(None)
    hash1 = digest(profile_dir)
    app.on_apply(None)
    hash2 = digest(profile_dir)
    assert before_hash == hash1, "%s: no-op Apply rewrote files" % label
    assert hash1 == hash2, "%s: second Apply changed files" % label
    assert counts(profile_dir) == before_counts, "%s: rows disappeared" % label

    target = next((c for c in app.controls if c["key"] == "border_radius"), None)
    if target is not None:
        widget = target["widget"]
        old = int(widget.get_value())
        widget.set_value(old + 1)
        app.on_apply(None)
        app.on_apply(None)
        line = next(l.strip() for l in open(target["path"], encoding="utf-8")
                    if l.strip().startswith("border_radius"))
        assert line == "border_radius=%d" % (old + 1), "%s: edit not saved: %s" % (label, line)
        assert counts(profile_dir) == before_counts, "%s: rows changed after edit" % label

    app.win.destroy()
    print("ok - %s (stable, edits persist, rows intact)" % label)


def main():
    if len(sys.argv) == 2:
        run_one(sys.argv[1], os.path.basename(sys.argv[1].rstrip("/")))
        return 0
    with tempfile.TemporaryDirectory() as td:
        for name in ("flat", "single", "dms"):
            dest = os.path.join(td, name)
            shutil.copytree(os.path.join(FIX, name), dest)
            subprocess.run([sys.executable, __file__, dest], check=True)
    print("\nAll apply tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
