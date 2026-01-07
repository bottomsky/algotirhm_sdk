#!/usr/bin/env sh
set -eu

repo_root=$(cd "$(dirname "$0")/.." && pwd)
src_root="$repo_root/src"
out_dir="${OUTPUT_DIR:-$repo_root/dist/modules}"
mkdir -p "$out_dir"

modules="${MODULES:-algo_sdk algo_dto algo_decorators algo_core_service}"
package_version="${PACKAGE_VERSION:-0.0.0}"
format="${FORMAT:-zip}"
bundle_name="${BUNDLE_NAME:-}"

remaining_modules=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --format)
      format="$2"
      shift 2
      ;;
    --bundle-name)
      bundle_name="$2"
      shift 2
      ;;
    --version)
      package_version="$2"
      shift 2
      ;;
    *)
      remaining_modules="$remaining_modules $1"
      shift
      ;;
  esac
done
if [ -n "$remaining_modules" ]; then
  modules="$remaining_modules"
fi

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
import re
import shutil
import subprocess
import tempfile
import zipfile

repo_root = r"$repo_root"
src_root = os.path.join(repo_root, "src")
out_dir = r"$out_dir"
modules = [m for m in re.split(r"[,\s]+", "$modules".strip()) if m]
aliases = {"algo_sdk_dto": "algo_dto"}
timestamp = "$timestamp"
package_version = "$package_version"
format = "$format"
bundle_name = "$bundle_name".strip()

def normalize_package_name(name: str) -> str:
    return name.replace("_", "-")


def module_dependencies(resolved_module: str, version: str) -> list[str]:
    name = normalize_package_name(resolved_module)
    if name == "algo-dto":
        return [
            "pydantic>=2.12.5",
            "numpy>=2.4.0",
        ]
    if name == "algo-decorators":
        return [
            "pydantic>=2.12.5",
            "typing-extensions>=4.12.2; python_version < '3.12'",
        ]
    if name == "algo-sdk":
        return [
            f"algo-decorators>={version}",
            "fastapi>=0.128.0",
            "pydantic>=2.12.5",
            "python-dotenv>=1.2.1",
            "pyyaml>=6.0.3",
            "typing-extensions>=4.12.2; python_version < '3.12'",
            "uvicorn>=0.40.0",
        ]
    if name == "algo-core-service":
        return [
            f"algo-dto>={version}",
            f"algo-sdk>={version}",
        ]
    return []


def merged_dependencies(resolved_modules: list[str], version: str) -> list[str]:
    deps: set[str] = set()
    for m in resolved_modules:
        deps.update(module_dependencies(m, version))
    return sorted(deps)


def build_wheel(staging: str, out_dir: str) -> None:
    try:
        subprocess.check_call(
            [os.fspath(os.sys.executable), "-m", "pip", "--version"],
            cwd=staging,
        )
    except Exception:
        subprocess.check_call(
            [os.fspath(os.sys.executable), "-m", "ensurepip", "--upgrade"],
            cwd=staging,
        )
    subprocess.check_call(
        [
            os.fspath(os.sys.executable),
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "-w",
            out_dir,
        ],
        cwd=staging,
    )


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


def write_setup_py(
    staging: str,
    package_name: str,
    version: str,
    install_requires: list[str],
) -> None:
    setup_path = os.path.join(staging, "setup.py")
    deps_payload = ",\n".join(f"        {dep!r}" for dep in install_requires)
    with open(setup_path, "w", encoding="ascii") as fh:
        fh.write(
            "from setuptools import setup, find_packages\\n\\n"
            "setup(\\n"
            f"    name=\\\"{package_name}\\\",\\n"
            f"    version=\\\"{version}\\\",\\n"
            "    python_requires=\\\">=3.11\\\",\\n"
            "    packages=find_packages(),\\n"
            "    include_package_data=True,\\n"
            "    install_requires=[\\n"
            f"{deps_payload}\\n"
            "    ],\\n"
            ")\\n"
        )


def build_zip(staging: str, out_dir: str, package_name: str) -> str:
    zip_path = os.path.join(out_dir, f"{package_name}-{package_version}-{timestamp}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(staging):
            for file in files:
                full = os.path.join(root, file)
                rel = os.path.relpath(full, staging)
                zf.write(full, rel)
    return zip_path


if bundle_name:
    staging = tempfile.mkdtemp(prefix="algo-pack-")
    try:
        resolved_modules: list[str] = []
        for name in modules:
            resolved = aliases.get(name, name)
            src = os.path.join(src_root, resolved)
            if not os.path.isdir(src):
                raise SystemExit(f"Module not found: {resolved} (expected at {src})")
            dest = os.path.join(staging, resolved)
            shutil.copytree(src, dest)
            resolved_modules.append(resolved)
        for root, dirs, files in os.walk(staging):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for file in files:
                if file.endswith(".pyc"):
                    os.remove(os.path.join(root, file))
        package_name = bundle_name.replace("_", "-")
        deps = merged_dependencies(resolved_modules, package_version)
        write_setup_py(staging, package_name, package_version, deps)
        if format in ("zip", "both"):
            zip_path = build_zip(staging, out_dir, package_name)
            print(f"Created {zip_path}")
        if format in ("whl", "both"):
            build_wheel(staging, out_dir)
            print(f"Created wheel(s) in {out_dir}")
    finally:
        shutil.rmtree(staging)
else:
    for name in modules:
        staging, resolved = stage_module(name)
        try:
            package_name = resolved.replace("_", "-")
            deps = module_dependencies(resolved, package_version)
            write_setup_py(staging, package_name, package_version, deps)
            if format in ("zip", "both"):
                zip_path = build_zip(staging, out_dir, package_name)
                print(f"Created {zip_path}")
            if format in ("whl", "both"):
                build_wheel(staging, out_dir)
                print(f"Created wheel(s) in {out_dir}")
        finally:
            shutil.rmtree(staging)
PY
