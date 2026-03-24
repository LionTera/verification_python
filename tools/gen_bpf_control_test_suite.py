#!/usr/bin/env python3
import argparse
from pathlib import Path

HELPERS = '''from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholderPass, VerilogTranslationImportPass
from pymtl3.passes.PassGroups import DefaultPassGroup
from pymtl.wrappers.bpf_control_wrapper import BpfControl

def mk_dut():
    dut = BpfControl()
    dut.elaborate()
    dut.apply( VerilogPlaceholderPass() )
    dut = VerilogTranslationImportPass()( dut )
    dut.apply( DefaultPassGroup() )
    dut.sim_reset()
    return dut
'''

SMOKE = '''from tests.bpf_env.bpf_control_test_helpers import mk_dut

def test_bpf_control_smoke():
    dut = mk_dut()
    assert int(dut.bpf_active) in (0, 1)
'''

def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="tests")
    args = ap.parse_args()

    root = Path(args.outdir).resolve()
    write(root / "__init__.py", "")
    write(root / "bpf_env" / "__init__.py", "")
    write(root / "bpf_env" / "bpf_control_test_helpers.py", HELPERS)
    write(root / "unit" / "test_bpf_control_smoke.py", SMOKE)
    print(f"[OK] test scaffold under: {root}")

if __name__ == "__main__":
    main()
