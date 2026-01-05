#!/usr/bin/env sh
set -eu

repo_root=$(cd "$(dirname "$0")/.." && pwd)
src_root="$repo_root/src"
out_dir="${OUTPUT_DIR:-$repo_root/dist/modules}"
mkdir -p "$out_dir"

modules="${MODULES:-algo_sdk algo_dto}"
if [ "$#" -gt 0 ]; then
  modules="$*"
fi
package_version="${PACKAGE_VERSION:-0.0.0}"

if [ -x "$repo_root/.venv/bin/python" ]; then
  py="$repo_root/.venv/bin/python"
elif [ -x "$repo_root/.venv/Scripts/python.exe" ]; then
  py="$repo_root/.venv/Scripts/python.exe"
else
  echo "No .venv python found. Create .venv first." >&2
  exit 1
fi

timestamp=$(date +"%Y%m%d-%H%M%S")

"$py" - <<PY
import os
import shutil
import tempfile
import zipfile

repo_root = r"$repo_root"
src_root = os.path.join(repo_root, "src")
out_dir = r"$out_dir"
modules = "$modules".split()
aliases = {"algo_sdk_dto": "algo_dto"}
timestamp = "$timestamp"
package_version = "$package_version"


def stage_module(name: str):
    resolved = aliases.get(name, name)
    src = os.path.join(src_root, resolved)
    if not os.path.isdir(src):
        raise SystemExit(f"Module not found: {resolved} (expected at {src})")
    staging = tempfile.mkdtemp(prefix="algo-pack-")
    dest = os.path.join(staging, resolved)
    shutil.copytree(src, dest)
    for root, dirs, files in os.walk(dest):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file.endswith(".pyc"):
                os.remove(os.path.join(root, file))
    return staging, resolved


for name in modules:
    staging, resolved = stage_module(name)
    package_name = resolved.replace("_", "-")
    setup_path = os.path.join(staging, "setup.py")
    with open(setup_path, "w", encoding="ascii") as fh:
        fh.write(
            "from setuptools import setup, find_packages\\n\\n"
            f"setup(name=\\\"{package_name}\\\", "
            f"version=\\\"{package_version}\\\", "
            "packages=find_packages(), include_package_data=True)\\n"
        )
    zip_path = os.path.join(
        out_dir, f"{package_name}-{package_version}-{timestamp}.zip"
    )
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(staging):
            for file in files:
                full = os.path.join(root, file)
                rel = os.path.relpath(full, staging)
                zf.write(full, rel)
    shutil.rmtree(staging)
    print(f"Created {zip_path}")
PY
