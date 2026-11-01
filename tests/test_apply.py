#!/usr/bin/env python3
"""GUI round-trip test: no-op Apply must not rewrite files, edits must survive."""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
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
    if mc.BINDS and os.path.isfile(mc.BINDS):
        with open(mc.BINDS, "a", encoding="utf-8") as fh:
            fh.write("bind=,F9,spawn,no-mod-test\n")
            fh.write("bind=SUPER+CTRL,P,spawn,group-test\n")
            fh.write("bind=SUPER+SHIFT+ALT,T,spawn,group-test\n")
    before_hash = digest(profile_dir)
    before_counts = counts(profile_dir)

    app = mc.App(profile=prof, tab="keys", no_reload=True)
    app.register(None)
    app.do_activate()
    app._validate_config = lambda: (True, "")
    app._reload_mango = lambda: True

    assert hasattr(app, "wall_list") and app.wall_list is not None, "%s: wallpaper page missing" % label
    assert hasattr(app, "wall_search"), "%s: wallpaper search missing" % label
    assert hasattr(app, "wall_mode") and hasattr(app, "wall_rotate"), (
        "%s: wallpaper fit controls missing" % label)
    assert hasattr(app, "wall_flip_h") and hasattr(app, "wall_flip_v"), (
        "%s: wallpaper flip controls missing" % label)
    assert hasattr(app, "night_scale"), "%s: night light page missing" % label
    assert hasattr(app, "night_apply"), "%s: night light apply missing" % label
    assert hasattr(app, "bright_scale"), "%s: brightness page missing" % label
    assert hasattr(app, "bright_refresh"), "%s: brightness refresh missing" % label
    assert hasattr(app, "app_dropdowns") and len(app.app_dropdowns) == 3, (
        "%s: default app preferences missing" % label)
    assert hasattr(app, "apps_apply"), "%s: default apps save button missing" % label

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

    test_groups = [g for g in getattr(app, "kb_cards", [])
                   if g["e_act"].get_text() == "spawn"
                   and g["e_args"].get_text() == "group-test"]
    assert len(test_groups) == 1, "%s: duplicate keybind actions were not grouped" % label
    test_group = test_groups[0]
    assert len(test_group["combos"]) == 2, "%s: grouped shortcuts missing" % label
    assert {c["e_combo"].get_text() for c in test_group["combos"]} == {
        "SUPER+CTRL+P", "SUPER+SHIFT+ALT+T"}, "%s: multi-key chords were not loaded" % label
    added = test_group["add_shortcut"]()
    added["e_combo"].set_text("SUPER+CTRL+ALT+K")
    test_group["combos"][0]["remove"].emit("clicked")
    app.on_apply(None)
    bind_text = open(mc.BINDS, encoding="utf-8").read()
    grouped_lines = [line for line in bind_text.splitlines()
                     if line.startswith("bind=") and line.endswith("spawn,group-test")]
    assert len(grouped_lines) == 2, "%s: grouped shortcut edit did not save" % label
    assert "bind=SUPER+SHIFT+ALT,T,spawn,group-test" in grouped_lines, (
        "%s: four-key chord was not preserved" % label)
    assert "bind=SUPER+CTRL+ALT,K,spawn,group-test" in grouped_lines, (
        "%s: four-key shortcut was not added" % label)
    assert counts(profile_dir)["binds"] == before_counts["binds"], (
        "%s: grouped bind count changed: before=%r after=%r lines=%r" %
        (label, before_counts, counts(profile_dir), grouped_lines))
    stable_hash = digest(profile_dir)
    app.on_apply(None)
    assert digest(profile_dir) == stable_hash, "%s: grouped bind Apply is not stable" % label

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


def test_wallpaper_apply():
    """A wallpaper apply renders the fit options, then calls the helper."""
    mc = SourceFileLoader("mango_config_wall_apply", APP).load_module()
    if mc.GdkPixbuf is None:
        print("ok - wallpaper apply skipped (GdkPixbuf unavailable)")
        return
    with tempfile.TemporaryDirectory() as td:
        wall_dir = os.path.join(td, "wallpapers")
        state_dir = os.path.join(td, "state")
        os.makedirs(wall_dir)
        os.makedirs(state_dir)
        source = os.path.join(wall_dir, "test.png")
        pb = mc.GdkPixbuf.Pixbuf.new(mc.GdkPixbuf.Colorspace.RGB, False, 8, 120, 60)
        pb.fill(0x33aa88ff)
        mc._save_wallpaper_pixbuf(pb, source)
        log = os.path.join(td, "helper.log")
        helper = os.path.join(td, "helper.py")
        with open(helper, "w", encoding="utf-8") as fh:
            fh.write("#!/usr/bin/env python3\n"
                     "import sys\n"
                     "open(%r, 'w', encoding='utf-8').write('\\n'.join(sys.argv[1:]))\n" % log)
        os.chmod(helper, 0o755)

        mc.WALLPAPER_DIR = wall_dir
        mc.WALLPAPER_STATE = os.path.join(state_dir, "wallpaper")
        mc.WALLPAPER_OPTIONS = os.path.join(state_dir, "wallpaper-options.json")
        mc.WALLPAPER_RENDERED = os.path.join(state_dir, "wallpaper-rendered.png")
        mc.WALLPAPER_LINK = os.path.join(state_dir, "wall-current")
        mc.APP_STATE_DIR = state_dir
        mc.DEFAULT_APPS_FILE = os.path.join(td, "mimeapps.list")
        mc._light_wallpaper = lambda: helper
        mc._brightness_probe = lambda: (None, None, "test mode")
        mc.APP_ID = "io.github.deopr.MangoConfigWallTest"

        profile_dir = os.path.join(td, "config")
        shutil.copytree(os.path.join(FIX, "flat"), profile_dir)
        prof = mc.discover_profile(profile_dir)
        mc.configure_profile(prof)
        app = mc.App(profile=prof, tab="wallpaper", no_reload=True)
        app.register(None)
        app.do_activate()
        assert app.wall_rows, "wallpaper list did not see the test image"
        app.wall_list.select_row(app.wall_rows[0])
        app.wall_mode.set_selected(2)  # Stretch
        app._apply_wallpaper(source)

        ctx = mc.GLib.MainContext.default()
        deadline = time.time() + 10
        while time.time() < deadline:
            while ctx.pending():
                ctx.iteration(False)
            if os.path.isfile(log) and os.path.isfile(mc.WALLPAPER_STATE):
                break
            time.sleep(0.02)
        assert os.path.isfile(log), "wallpaper helper was not called"
        called = open(log, encoding="utf-8").read().strip()
        assert called == mc.WALLPAPER_RENDERED, (
            "wallpaper helper received the wrong path: %r" % called)
        assert os.path.isfile(mc.WALLPAPER_RENDERED), "rendered wallpaper missing"
        assert open(mc.WALLPAPER_STATE, encoding="utf-8").read().strip() == source
        options = mc._wallpaper_options()
        assert options["mode"] == "stretch" and options["source"] == source
        assert mc._current_wallpaper_source() == source
        app.win.destroy()
        print("ok - wallpaper apply renders options and calls helper")


def main():
    if len(sys.argv) == 2:
        run_one(sys.argv[1], os.path.basename(sys.argv[1].rstrip("/")))
        return 0
    with tempfile.TemporaryDirectory() as td:
        for name in ("flat", "single", "dms"):
            dest = os.path.join(td, name)
            shutil.copytree(os.path.join(FIX, name), dest)
            subprocess.run([sys.executable, __file__, dest], check=True)
    test_wallpaper_apply()
    print("\nAll apply tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
