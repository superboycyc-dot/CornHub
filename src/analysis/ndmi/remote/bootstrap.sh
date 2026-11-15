#!/usr/bin/env bash
set -euo pipefail
: "${NDMI_WORK_ROOT:?Set NDMI_WORK_ROOT to a persistent directory owned by this user}"
NDMI_PYTHON="${NDMI_PYTHON:-python3.12}"
NDMI_CUDA_MAJOR="${NDMI_CUDA_MAJOR:-none}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../../../.." && pwd)"
cd "$repo_root"
mkdir -p "$NDMI_WORK_ROOT"
"$NDMI_PYTHON" -m venv "$NDMI_WORK_ROOT/venv"
ndmi_python="$NDMI_WORK_ROOT/venv/bin/python"
case "$NDMI_CUDA_MAJOR" in
  none) requirements=src/analysis/ndmi/requirements.txt ;;
  12) requirements=src/analysis/ndmi/requirements-gpu-cu12.txt ;;
  13) requirements=src/analysis/ndmi/requirements-gpu-cu13.txt ;;
  *) printf '%s\n' 'NDMI_CUDA_MAJOR must be none, 12 or 13' >&2; exit 2 ;;
esac
"$ndmi_python" src/analysis/ndmi/remote/network_probe.py --output "$NDMI_WORK_ROOT/network_probe.json"
"$ndmi_python" -m pip install -r "$requirements"
"$ndmi_python" -m unittest discover -s src/analysis/ndmi -p 'test_*.py' -v
"$ndmi_python" src/analysis/ndmi/remote/benchmark.py --synthetic --output "$NDMI_WORK_ROOT/backend_benchmark.json"
"$ndmi_python" -m pip freeze > "$NDMI_WORK_ROOT/deployment_freeze.txt"
"$ndmi_python" src/analysis/ndmi/remote/launch.py --cache "$NDMI_WORK_ROOT/cache" --plan-only
