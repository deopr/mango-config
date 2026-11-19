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

check("keyboard token: super", mc.kb_bind_tokens("SUPER", "P") == {"super", "p"})
check("keyboard token: aliases",
      mc.kb_bind_tokens("MOD4+CONTROL", "Page_Up") == {"super", "ctrl", "pageup"})
check("keyboard token: no mods", mc.kb_bind_tokens("", "F9") == {"f9"})
check("keyboard map: rows have valid key widths",
      all(sum(span for _label, _token, span in row) in (13, 15)
          for row in mc.KB_MAIN_ROWS))


class _BindParser:
    BIND_RE = mc.App.BIND_RE


bind_parser = _BindParser()
check("bind parse: spaced equals",
      mc.App._kb_parts(bind_parser, "bind = SUPER, Return, spawn, kitty")
      == ("bind", "SUPER", "Return", "spawn", "kitty"))
check("bind parse: compact equals",
      mc.App._kb_parts(bind_parser, "bind=SUPER,e,spawn,firefox")
      == ("bind", "SUPER", "e", "spawn", "firefox"))
check("bind parse: spaced no args",
      mc.App._kb_parts(bind_parser, "bind = SUPER, q, killclient,")
      == ("bind", "SUPER", "q", "killclient", ""))
check("bind parse: flag with spaced equals",
      mc.App._kb_parts(bind_parser, "bindl = SUPER, x, spawn, lock")
      == ("bindl", "SUPER", "x", "spawn", "lock"))

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
check("CLI version", out.returncode == 0 and out.stdout.strip() == "mango-config 0.5.0",
      out.stdout + out.stderr)
out = subprocess.run([sys.executable, APP, "--help"], capture_output=True, text=True)
check("CLI help", out.returncode == 0 and "--config-dir" in out.stdout and "--tab" in out.stdout)
check("CLI help lists new tabs",
      all(t in out.stdout for t in ("wallpaper", "night", "brightness", "apps",
                                    "keyboard", "bar", "tiling",
                                    "--print-layout")),
      out.stdout)
out = subprocess.run([sys.executable, APP, "--print-layout"],
                     capture_output=True, text=True)
check("CLI print layout", out.returncode == 0 and len(out.stdout.strip()) > 0,
      out.stdout + out.stderr)

with tempfile.TemporaryDirectory() as td:
    log = os.path.join(td, "argv.log")
    fake = os.path.join(td, "mmsg")
    with open(fake, "w", encoding="utf-8") as fh:
        fh.write(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "open(%r, 'w', encoding='utf-8').write('\\n'.join(sys.argv[1:]))\n"
            "print(json.dumps({'success': True}))\n" % log)
    os.chmod(fake, 0o755)
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = td + ":" + old_path
    try:
        ok, message = mc._mmsg_dispatch("focusmon", "HDMI-A-1")
        seen = open(log, encoding="utf-8").read().splitlines()
    finally:
        os.environ["PATH"] = old_path
    check("mmsg dispatch comma-joins args",
          ok and seen == ["dispatch", "focusmon,HDMI-A-1"],
          message + " " + repr(seen))

class _SpinStub:
    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value


class _EntryStub:
    def __init__(self, text):
        self.text = text

    def get_text(self):
        return self.text


class _DropdownStub:
    def __init__(self, selected=0):
        self.selected = selected

    def get_selected(self):
        return self.selected


def _rule_stub(scale=1.0, present_scale=False, refresh=60.0):
    keys = {"name", "width", "height", "refresh", "x", "y"}
    if present_scale:
        keys.add("scale")
    return {
        "name": _EntryStub("HDMI-A-1"),
        "spins": {
            "width": _SpinStub(1920), "height": _SpinStub(1080),
            "refresh": _SpinStub(refresh), "x": _SpinStub(0),
            "y": _SpinStub(0), "scale": _SpinStub(scale),
        },
        "rr": _DropdownStub(),
        "sw": {},
        "orig": "",
        "extra": {},
        "keys": keys,
    }


check("monitor rule scale defaults to 1.0",
      mc._rule_number({}, "scale", 1.0) == 1.0
      and mc._rule_number({"scale": "0.5"}, "scale", 1.0) == 0.5
      and mc._rule_number({"scale": "bad"}, "scale", 1.0) == 1.0)
check("rule parser accepts spaces around =",
      mc._rule_value("monitor_rule = name:HDMI-A-1, width:1920", "monitor_rule")
      == "name:HDMI-A-1, width:1920"
      and mc._rule_value("window_rule = app_id:Steam", "window_rule")
      == "app_id:Steam"
      and mc._rule_value("# monitor_rule = name:DP-1", "monitor_rule") is None)
line = mc.App._monitor_line(None, _rule_stub())
check("monitor rule omits unset scale", "scale" not in line, line)
line = mc.App._monitor_line(None, _rule_stub(scale=1.5, present_scale=True))
check("monitor rule keeps explicit scale", "scale:1.5" in line, line)
line = mc.App._monitor_line(None, _rule_stub(refresh=0))
check("monitor rule drops resolution without refresh",
      "width" not in line and "height" not in line and "refresh" not in line, line)

sample_bar = """// keep this comment
{
    "height": 34, // root height
    "modules": {
        "height": 99,
        "layer": "overlay"
    },
    "layer": "top",
}
"""
updated_bar = mc._set_jsonc_top_level(
    sample_bar, {"height": 44, "layer": "bottom"})
bar_data = mc._parse_jsonc(updated_bar, {})
check("JSONC update keeps comments", "keep this comment" in updated_bar)
check("JSONC update changes root keys",
      bar_data.get("height") == 44 and bar_data.get("layer") == "bottom",
      str(bar_data))
check("JSONC update leaves nested keys",
      bar_data.get("modules", {}).get("height") == 99 and
      bar_data.get("modules", {}).get("layer") == "overlay", str(bar_data))

tiling_text = mc._tiling_text_with_rules(
    "source=./layout.conf\n\n# personal tail\n",
    {"HDMI-A-1": "tile", "DP-1": "fair"})
check("tiling block writes wildcard rules",
      "id:*, monitor_name:HDMI-A-1, layout_name:tile" in tiling_text and
      "id:*, monitor_name:DP-1, layout_name:fair" in tiling_text, tiling_text)
check("tiling block preserves surrounding config",
      "source=./layout.conf" in tiling_text and "# personal tail" in tiling_text)
check("tiling block reads back",
      mc._tiling_rules_from_text(tiling_text) ==
      {"HDMI-A-1": "tile", "DP-1": "fair"})
removed = mc._tiling_text_with_rules(tiling_text, {"HDMI-A-1": "tile"})
check("tiling block removal is surgical",
      "DP-1" not in removed and "HDMI-A-1" in removed and
      "personal tail" in removed, removed)

with tempfile.TemporaryDirectory() as td:
    old_home = os.environ.get("XDG_CONFIG_HOME")
    old_mangobar = os.environ.pop("MANGOBAR_CONFIG", None)
    os.environ["XDG_CONFIG_HOME"] = td
    try:
        cfg_dir = os.path.join(td, "waybar")
        os.makedirs(cfg_dir)
        cfg = os.path.join(cfg_dir, "config.jsonc")
        open(cfg, "w", encoding="utf-8").write(sample_bar)
        ok, message = mc._bar_quick_save(
            "waybar", {"height": 40, "layer": "bottom", "position": "bottom"})
        saved = mc._parse_jsonc(open(cfg, encoding="utf-8").read(), {})
        check("bar quick save writes root options",
              ok and saved.get("height") == 40 and
              saved.get("layer") == "bottom" and
              saved.get("position") == "bottom", message + " " + str(saved))
        check("bar quick save keeps nested modules",
              saved.get("modules", {}).get("height") == 99, str(saved))
        backups = os.listdir(os.path.join(cfg_dir, ".autobak"))
        check("bar quick save backs up", len(backups) == 1, str(backups))

        style_path = os.path.join(cfg_dir, "style.css")
        open(style_path, "w", encoding="utf-8").write("/* old style */\n")
        preset = next(p for p in mc.BAR_PRESETS
                      if p["id"] == "waybar-catppuccin")
        ok, message = mc._bar_apply_preset(preset)
        preset_cfg = mc._read_jsonc(cfg, {})
        style = open(style_path, encoding="utf-8").read()
        check("bar preset writes config",
              ok and "custom/layout" in preset_cfg.get("modules-left", []),
              message)
        check("bar preset writes palette",
              ok and "#89b4fa" in style and "#1e1e2e" in style)
        check("bar preset backups both files",
              len(os.listdir(os.path.join(cfg_dir, ".autobak"))) >= 2)
    finally:
        if old_home is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = old_home
        if old_mangobar is not None:
            os.environ["MANGOBAR_CONFIG"] = old_mangobar

with tempfile.TemporaryDirectory() as td:
    cfg = os.path.join(td, "config.conf")
    open(cfg, "w", encoding="utf-8").write("source=./layout.conf\n")
    ok, message = mc._tiling_save_default("HDMI-A-1", "tile", path=cfg)
    text = open(cfg, encoding="utf-8").read()
    check("tiling default save", ok and "layout_name:tile" in text, message)
    ok, message = mc._tiling_save_default("HDMI-A-1", None, path=cfg)
    text = open(cfg, encoding="utf-8").read()
    check("tiling default remove",
          ok and "mango-config tiling defaults" not in text, message)
    ok, message = mc._tiling_save_default("bad,name", "tile", path=cfg)
    check("tiling default rejects bad monitor", not ok, message)
    ok, message = mc._tiling_save_default("HDMI-A-1", "nope", path=cfg)
    check("tiling default rejects bad layout", not ok, message)

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
