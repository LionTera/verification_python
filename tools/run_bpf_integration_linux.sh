#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python tools/check_bpf_env_linux.py

if ! command -v verilator >/dev/null 2>&1; then
  echo "verilator is not installed or not on PATH" >&2
  exit 1
fi

python -m py_compile \
  pymtl/wrappers/bpf_env_wrapper.py \
  tests/bpf_env/bpf_python_tb.py \
  tests/bpf_env/dut_builders.py \
  tests/bpf_env/packets.py \
  tests/integration/test_bpf_env_smoke.py \
  tests/integration/test_bpf_env_accept_reject.py \
  tests/integration/test_bpf_env_tcp_port_filter.py \
  tests/integration/test_bpf_env_tcp.py

if [[ "${BPF_WAVEFORM:-}" != "" ]]; then
  echo "Waveforms enabled via BPF_WAVEFORM=${BPF_WAVEFORM}"
fi

pytest -s -m integration tests/integration/test_bpf_env_smoke.py tests/integration/test_bpf_env_accept_reject.py tests/integration/test_bpf_env_tcp_port_filter.py tests/integration/test_bpf_env_tcp.py
