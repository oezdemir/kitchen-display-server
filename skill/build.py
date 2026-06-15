#!/usr/bin/env python3
"""Build this skill into an installable .hskill package.

Self-contained: stdlib only (PyYAML used if present, else a tiny parser for the
template's manifest format), plus `pip` for python-runtime skills. No external
tooling and no PATH setup — clone the skill and run `./build.sh` (or this).

Output: dist/<name>-<version>-<target>.hskill
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

PLATFORM_TAGS = {  # target -> pip --platform tags
    "linux-x86_64": ["manylinux_2_28_x86_64", "manylinux_2_17_x86_64", "manylinux2014_x86_64"],
}


def load_manifest(path: str) -> dict:
    text = open(path).read()
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except Exception:
        pass
    # minimal stdlib parser for the template's flat format
    m: dict = {}
    py: dict = {}
    cur = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^\S", line):
            cur = None
            mm = re.match(r"^([\w-]+):\s*(.*)$", line)
            if mm:
                k, v = mm.group(1), mm.group(2).split(" #")[0].strip()
                if k == "python" and not v:
                    cur = "python"
                else:
                    m[k] = v.strip('"').strip("'")
        else:
            mm = re.match(r"^\s+([\w-]+):\s*(.*)$", line)
            if mm and cur == "python":
                py[mm.group(1)] = mm.group(2).split(" #")[0].strip()
    if py:
        reqs = py.get("requirements", "")
        if isinstance(reqs, str) and reqs:
            py["requirements"] = [r.strip().strip('"').strip("'")
                                  for r in reqs.strip("[]").split(",") if r.strip()]
        for k in ("package", "app_wheel", "python_version"):
            if k in py:
                py[k] = str(py[k]).strip('"').strip("'")
        m["python"] = py
    return m


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    target = sys.argv[1] if len(sys.argv) > 1 else "linux-x86_64"
    if target not in PLATFORM_TAGS:
        sys.stderr.write(f"build: unsupported target {target}\n")
        return 1

    man = load_manifest(os.path.join(here, "skill.yaml"))
    name = str(man.get("name") or "").strip()
    if not name:
        sys.stderr.write("build: skill.yaml has no name\n")
        return 1
    version = str(man.get("version", "0.0.0"))
    runtime = man.get("runtime", "shell")

    with tempfile.TemporaryDirectory() as tmp:
        stage = os.path.join(tmp, name)
        os.makedirs(stage)
        for f in ("skill.yaml", "SKILL.md", "secrets.spec"):
            p = os.path.join(here, f)
            if os.path.isfile(p):
                shutil.copy2(p, stage)
        for d in ("bin", "service"):
            if os.path.isdir(os.path.join(here, d)):
                shutil.copytree(os.path.join(here, d), os.path.join(stage, d))

        if runtime == "python":
            py = man.get("python") or {}
            app_glob = py.get("app_wheel")
            wheels = sorted(glob.glob(os.path.join(here, app_glob))) if app_glob else []
            if not wheels:
                sys.stderr.write(f"build: no app wheel matched '{app_glob}' (build the wheel first)\n")
                return 1
            wdir = os.path.join(stage, "wheels")
            os.makedirs(wdir)
            for w in wheels:
                shutil.copy2(w, wdir)
            pyver = str(py.get("python_version", "312"))
            reqs = list(py.get("requirements") or [])
            if reqs:
                plats = []
                for tag in PLATFORM_TAGS[target]:
                    plats += ["--platform", tag]
                subprocess.run(
                    [sys.executable, "-m", "pip", "download", "--only-binary=:all:",
                     "--python-version", pyver, "--implementation", "cp", "--abi", f"cp{pyver}",
                     *plats, "-d", wdir, *reqs],
                    check=True,
                )

        outdir = os.path.join(here, "dist")
        os.makedirs(outdir, exist_ok=True)
        pkg = os.path.join(outdir, f"{name}-{version}-{target}.hskill")
        with tarfile.open(pkg, "w:gz") as tf:
            tf.add(stage, arcname=name)
    print(f"built {pkg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
