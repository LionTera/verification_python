from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholderPass, VerilogTranslationImportPass
from pymtl3.passes.PassGroups import DefaultPassGroup

from bpf_control_wrapper import BpfControl

def test_bpf_control_smoke():
    dut = BpfControl()

    dut.elaborate()
    dut.apply( VerilogPlaceholderPass() )
    dut = VerilogTranslationImportPass()( dut )
    dut.apply( DefaultPassGroup() )
    dut.sim_reset()

    print("\n[TEST] Starting smoke test for bpf_control")

    dut.bpf_iram_rdata @= 1
    dut.bpf_eop_fault @= 1

    dut.sim_eval_combinational()
    print("No decision-like outputs detected automatically")

    print("[TEST] Smoke test completed")
