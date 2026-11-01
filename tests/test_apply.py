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
    if mc.WINDOWRULES and os.path.isfile(mc.WINDOWRULES):
        with open(mc.WINDOWRULES, "a", encoding="utf-8") as fh:
            fh.write("window_rule=app_id:^(unknown-key-test)$,is_floating:1,future_setting:keep\n")
    before_hash = digest(profile_dir)
    before_counts = counts(profile_dir)

    app = mc.App(profile=prof, tab="keys", no_reload=True)
    app.register(None)
    app.do_activate()
    app._validate_config = lambda: (True, "")
    app._reload_mango = lambda: True

    assert hasattr(app, "wall_list") and app.wall_list is not None, "%s: wallpaper page missing" % label
    assert hasattr(app, "wall_search"), "%s: wallpaper search missing" % label
    assert hasattr(app, "night_scale"), "%s: night light page missing" % label
    assert hasattr(app, "night_apply"), "%s: night light apply missing" % label

    app.on_apply(None)
    hash1 = digest(profile_dir)
    app.on_apply(None)
    hash2 = digest(profile_dir)
    assert before_hash == hash1, "%s: no-op Apply rewrote files" % label
    assert hash1 == hash2, "%s: second Apply changed files" % label
    assert counts(profile_dir) == before_counts, "%s: rows disappeared" % label
    rule_text = open(mc.WINDOWRULES, encoding="utf-8").read() if mc.WINDOWRULES else ""
    assert "future_setting:keep" in rule_text, "%s: unknown rule key was dropped" % label

    if getattr(app, "wr_rows", None) and mc.WINDOWRULES:
        edit_rule = app.wr_rows[0]
        edit_rule["title"].set_text("Edited")
        edit_rule["text"]["width"].set_text("0.5")
        edit_rule["toggles"]["no_blur"].set_active(True)

        new_rule = app.add_wr_rule()
        new_rule["app"].set_text("^(test-window)$")
        new_rule["title"].set_text("Test")
        new_rule["toggles"]["is_term"].set_active(True)
        new_rule["text"]["tags"].set_text("1|3")

        doomed = app.add_wr_rule()
        doomed["app"].set_text("^(delete-me)$")
        doomed["toggles"]["is_global"].set_active(True)
        doomed["remove"].emit("clicked")

        app.add_wr_rule()  # blank rules must be dropped
        app.on_apply(None)
        after_rules = open(mc.WINDOWRULES, encoding="utf-8").read()
        assert "title:Edited" in after_rules, "%s: title edit was not saved" % label
        assert "width:0.5" in after_rules, "%s: width edit was not saved" % label
        assert "no_blur:1" in after_rules, "%s: toggle was not saved" % label
        assert "app_id:^(test-window)$" in after_rules, "%s: new rule missing" % label
        assert "tags:1|3" in after_rules, "%s: tags missing" % label
        assert "delete-me" not in after_rules, "%s: deleted rule came back" % label
        assert "matches every window" not in after_rules, "%s: blank rule written" % label
        assert counts(profile_dir)["rules"] == before_counts["rules"] + 1, (
            "%s: unexpected rule count after UI edits" % label)
        stable_hash = digest(profile_dir)
        app.on_apply(None)
        assert digest(profile_dir) == stable_hash, "%s: rule Apply is not stable" % label

    expected_counts = counts(profile_dir)
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
        assert counts(profile_dir) == expected_counts, "%s: rows changed after edit" % label

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
