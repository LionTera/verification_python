#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

required_files=(
  "bpf_test/u2u_v401/tf_bpf/rtl/bpf_env.v"
  "pymtl/wrappers/bpf_env_wrapper.py"
  "tests/bpf_env/bpf_python_tb.py"
  "tests/bpf_env/dut_builders.py"
  "tests/integration/test_bpf_env_smoke.py"
)

for path in "${required_files[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "Missing required path: $path" >&2
    exit 1
  fi
done

if ! command -v verilator >/dev/null 2>&1; then
  echo "verilator is not installed or not on PATH" >&2
  exit 1
fi

python -m py_compile \
  pymtl/wrappers/bpf_env_wrapper.py \
  tests/bpf_env/bpf_python_tb.py \
  tests/bpf_env/dut_builders.py \
  tests/integration/test_bpf_env_smoke.py

pytest -s tests/integration/test_bpf_env_smoke.py
