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
check("CLI version", out.returncode == 0 and out.stdout.strip() == "mango-config 0.2.1",
      out.stdout + out.stderr)
out = subprocess.run([sys.executable, APP, "--help"], capture_output=True, text=True)
check("CLI help", out.returncode == 0 and "--config-dir" in out.stdout and "--tab" in out.stdout)
check("CLI help lists new tabs",
      "wallpaper" in out.stdout and "night" in out.stdout, out.stdout)

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
check("wallpaper scan: missing dir", mc._wallpaper_files("/no/such/wallpapers") == [])

if failures:
    print("\n%d test(s) failed" % len(failures))
    sys.exit(1)
print("\nAll discovery tests passed.")
