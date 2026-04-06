"""Quick environment check for Linux-based BPF verification runs."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    Path("bpf_test/u2u_v401/tf_bpf/rtl/bpf_env.v"),
    Path("bpf_test/u2u_v401/tf_bpf/rtl/bpf_package.sv"),
    Path("pymtl/wrappers/bpf_env_wrapper.py"),
    Path("tests/bpf_env/bpf_python_tb.py"),
    Path("tests/bpf_env/dut_builders.py"),
    Path("tests/integration/test_bpf_env_smoke.py"),
]


def main() -> int:
    print(f"repo_root={REPO_ROOT}")
    print(f"python={sys.executable}")
    print(f"verilator={shutil.which('verilator') or 'MISSING'}")

    missing = False
    for rel_path in REQUIRED_PATHS:
        full_path = REPO_ROOT / rel_path
        status = "OK" if full_path.exists() else "MISSING"
        print(f"{status:7} {rel_path}")
        if not full_path.exists():
            missing = True

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
