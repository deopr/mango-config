#!/usr/bin/env python3
import os
import subprocess
import sys
import tempfile
from importlib.machinery import SourceFileLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "mango-config")
FIX = os.path.join(ROOT, "tests", "fixtures")
mc = SourceFileLoader("mango_config_under_test", APP).load_module()

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok - " + name)
    else:
        print("FAIL - " + name + (" : " + detail if detail else ""))
        failures.append(name)


def roles(path):
    p = mc.discover_profile(path)
    return p, {k: (os.path.basename(v) if v else None) for k, v in p.paths.items()}


p, r = roles(os.path.join(FIX, "flat"))
check("flat: no error", not p.error, p.error)
check("flat: layout", r["layout"] == "layout.conf", str(r))
check("flat: input", r["input"] == "input.conf", str(r))
check("flat: cursor", r["cursor"] == "cursor.conf", str(r))
check("flat: outputs", r["outputs"] == "outputs.conf", str(r))
check("flat: rules", r["rules"] == "windowrules.conf", str(r))
check("flat: binds", r["binds"] == "binds.conf", str(r))
check("flat: colors", r["colors"] == "colors.conf", str(r))
check("flat: not dms", not p.dms)

p, r = roles(os.path.join(FIX, "single"))
check("single: all roles in config.conf",
      all(v == "config.conf" for v in r.values()), str(r))
check("single: not dms", not p.dms)

p, r = roles(os.path.join(FIX, "dms"))
check("dms: detected", p.dms)
check("dms: layout", r["layout"] == "layout.conf" and "/dms/" in p.paths["layout"], str(r))
check("dms: input", "/dms/" in (p.paths["input"] or ""), str(r))
check("dms: cursor", "/dms/" in (p.paths["cursor"] or ""), str(r))
check("dms: outputs", "/dms/" in (p.paths["outputs"] or ""), str(r))
check("dms: rules", "/dms/" in (p.paths["rules"] or ""), str(r))
check("dms: binds outside dms", r["binds"] == "binds.conf", str(r))
check("dms: base colors use effective later file", r["colors"] == "noctalia.conf", str(r))
check("dms: theme", r["theme"] == "noctalia.conf", str(r))

with tempfile.TemporaryDirectory() as td:
    open(os.path.join(td, "config.toml"), "w").write("[general]\n")
    p, r = roles(td)
    check("toml only: reports error", bool(p.error), p.error)
    check("toml only: no roles", all(v is None for v in p.paths.values()), str(r))

with tempfile.TemporaryDirectory() as td:
    p, r = roles(td)
    check("missing config: reports error", bool(p.error), p.error)

with tempfile.TemporaryDirectory() as td:
    open(os.path.join(td, "config.conf"), "w").write(
        "border_radius=4\nsource_optional=./does-not-exist.conf\n")
    p, r = roles(td)
    check("missing optional source is ignored", not p.error, p.error)
    check("missing optional source: inline layout wins", r["layout"] == "config.conf", str(r))

out = subprocess.run([sys.executable, APP, "--version"], capture_output=True, text=True)
check("CLI version", out.returncode == 0 and out.stdout.strip() == "mango-config 0.3.0",
      out.stdout + out.stderr)
out = subprocess.run([sys.executable, APP, "--help"], capture_output=True, text=True)
check("CLI help", out.returncode == 0 and "--config-dir" in out.stdout and "--tab" in out.stdout)
check("CLI help lists new tabs",
      all(t in out.stdout for t in ("wallpaper", "night", "brightness", "apps")),
      out.stdout)

with tempfile.TemporaryDirectory() as td:
    for name in ("b.png", "a.JPG", "notes.txt", "sub.png"):
        path = os.path.join(td, name)
        if name == "sub.png":
            os.mkdir(path)
        else:
            open(path, "w").write("x")
    files = mc._wallpaper_files(td)
    check("wallpaper scan: images only, sorted", [
        os.path.basename(p) for p in files] == ["a.JPG", "b.png"], str(files))
check("brightness parse percent", mc._brightness_parse("42%") == 42)
check("brightness parse decimal", mc._brightness_parse("41.6") == 42)
check("brightness parse invalid", mc._brightness_parse("no reading") is None)
check("brightness parse clamps", mc._brightness_parse("150") == 100)
check("brightness number keeps raw", mc._brightness_number("937") == 937.0)

sample_mime = (
    "# keep this comment\n"
    "[Default Applications]\n"
    "inode/directory=old-files.desktop;\n"
    "text/html=firefox.desktop;\n"
    "\n"
    "[Added Associations]\n"
    "inode/directory=old-files.desktop;\n"
)
updated_mime = mc._mimeapps_set_defaults(sample_mime, {
    "inode/directory": "org.gnome.Nautilus.desktop",
    "x-scheme-handler/terminal": "kitty.desktop",
})
check("mimeapps replaces existing key", "inode/directory=org.gnome.Nautilus.desktop;" in updated_mime)
check("mimeapps adds missing key", "x-scheme-handler/terminal=kitty.desktop;" in updated_mime)
check("mimeapps preserves comment", "# keep this comment" in updated_mime)
check("mimeapps preserves untouched key", "text/html=firefox.desktop;" in updated_mime)
check("mimeapps preserves other sections", "[Added Associations]" in updated_mime)
check("mimeapps no duplicate default key",
      updated_mime.count("inode/directory=org.gnome.Nautilus.desktop;") == 1)
check("mimeapps creates missing section",
      mc._mimeapps_set_defaults("", {"inode/directory": "x.desktop;"}).startswith(
          "[Default Applications]\n"))

desktop_text = (
    "[Desktop Entry]\n"
    "Name=Test Terminal\n"
    "Exec=test-term\n"
    "Terminal=true\n"
    "Categories=System;TerminalEmulator;\n"
    "MimeType=x-scheme-handler/terminal;\n"
)
desktop_app = mc._parse_desktop_entry(desktop_text, "test-term.desktop")
check("desktop entry parses", desktop_app is not None and
      desktop_app["name"] == "Test Terminal" and desktop_app["terminal"])
check("desktop hidden entry skipped", mc._parse_desktop_entry(
    desktop_text + "Hidden=true\n", "hidden.desktop") is None)
check("desktop role matching",
      [a["id"] for a in mc._desktop_apps_for_role([desktop_app], "terminal")]
      == ["test-term.desktop"])

with tempfile.TemporaryDirectory() as td:
    log = os.path.join(td, "set.log")
    helper = os.path.join(td, "light-brightness")
    script = (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if sys.argv[1] == 'get':\n"
        "    print('57%')\n"
        "else:\n"
        "    open(LOG, 'w', encoding='utf-8').write(' '.join(sys.argv[1:]))\n"
    ).replace("LOG", repr(log))
    with open(helper, "w", encoding="utf-8") as fh:
        fh.write(script)
    os.chmod(helper, 0o755)
    backend = {"kind": "helper", "label": "test helper", "command": helper}
    value, error = mc._brightness_read(backend)
    check("brightness helper read", value == 57 and not error, error)
    ok, message = mc._brightness_set(backend, 35)
    check("brightness helper set", ok and message == 35, str(message))
    check("brightness helper set command",
          open(log, encoding="utf-8").read().strip() == "set 35")

with tempfile.TemporaryDirectory() as td:
    old_file, old_state = mc.DEFAULT_APPS_FILE, mc.APP_STATE_DIR
    try:
        mc.DEFAULT_APPS_FILE = os.path.join(td, "mimeapps.list")
        mc.APP_STATE_DIR = os.path.join(td, "state")
        open(mc.DEFAULT_APPS_FILE, "w", encoding="utf-8").write(
            "[Default Applications]\n"
            "inode/directory=old.desktop;\n"
            "x-scheme-handler/terminal=oldterm.desktop;\n"
            "[Added Associations]\n"
            "inode/directory=old.desktop;\n")
        ok, message = mc._save_default_apps({
            "inode/directory": "org.gnome.Nautilus.desktop",
            "x-scheme-handler/terminal": "kitty.desktop",
        })
        saved = open(mc.DEFAULT_APPS_FILE, encoding="utf-8").read()
        check("default apps save succeeds", ok, message)
        check("default apps writes associations",
              "inode/directory=org.gnome.Nautilus.desktop;" in saved and
              "x-scheme-handler/terminal=kitty.desktop;" in saved)
        check("default apps preserves added associations",
              "[Added Associations]" in saved and
              "inode/directory=old.desktop;" in saved)
        backups = os.listdir(os.path.join(mc.APP_STATE_DIR, "backups"))
        check("default apps backs up existing file", len(backups) == 1, str(backups))
        ok, message = mc._save_default_apps({
            "inode/directory": "org.gnome.Nautilus.desktop",
            "x-scheme-handler/terminal": "kitty.desktop",
        })
        check("default apps repeat apply is stable", not ok and message == "No changes")
    finally:
        mc.DEFAULT_APPS_FILE, mc.APP_STATE_DIR = old_file, old_state

with tempfile.TemporaryDirectory() as td:
    old_options = mc.WALLPAPER_OPTIONS
    try:
        mc.WALLPAPER_OPTIONS = os.path.join(td, "wallpaper.json")
        mc._save_wallpaper_options(mode="stretch", rotation=270,
                                   flip_h=True, flip_v=False,
                                   source="/tmp/example.png",
                                   rendered="/tmp/rendered.png")
        opts = mc._wallpaper_options()
        check("wallpaper options persist",
              opts["mode"] == "stretch" and opts["rotation"] == 270 and
              opts["flip_h"] and not opts["flip_v"] and
              opts["source"] == "/tmp/example.png")
        open(mc.WALLPAPER_OPTIONS, "w", encoding="utf-8").write(
            '{"mode": "not-a-mode", "rotation": 45}\n')
        opts = mc._wallpaper_options()
        check("wallpaper options sanitize invalid values",
              opts["mode"] == "fill" and opts["rotation"] == 0)
    finally:
        mc.WALLPAPER_OPTIONS = old_options

if mc.GdkPixbuf is not None:
    pb = mc.GdkPixbuf.Pixbuf.new(mc.GdkPixbuf.Colorspace.RGB, False, 8, 108, 192)
    pb.fill(0x00aa00ff)
    for mode in mc.WALLPAPER_MODES:
        composed = mc._compose_wallpaper(pb, mode, 0, False, False, 320, 180)
        check("wallpaper %s output size" % mode,
              (composed.get_width(), composed.get_height()) == (320, 180))
    rotated = mc._compose_wallpaper(pb, "fit", 90, True, True, 320, 180)
    check("wallpaper rotate/flip output size",
          (rotated.get_width(), rotated.get_height()) == (320, 180))
    fit = mc._compose_wallpaper(pb, "fit", 0, False, False, 320, 180)
    check("wallpaper fit letterboxes", fit.get_has_alpha() and fit.get_width() == 320)
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "portrait.png")
        mc._save_wallpaper_pixbuf(pb, src)
        rendered = mc._render_wallpaper(
            src, {"mode": "stretch", "rotation": 0, "flip_h": False,
                  "flip_v": False}, width=320, height=180,
            path=os.path.join(td, "rendered.png"))
        check("wallpaper render writes png",
              os.path.getsize(os.path.join(td, "rendered.png")) > 0 and
              (rendered.get_width(), rendered.get_height()) == (320, 180))

check("wallpaper scan: missing dir", mc._wallpaper_files("/no/such/wallpapers") == [])

if failures:
    print("\n%d test(s) failed" % len(failures))
    sys.exit(1)
print("\nAll discovery tests passed.")
