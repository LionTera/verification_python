from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholderPass, VerilogTranslationImportPass
from pymtl3.passes.PassGroups import DefaultPassGroup

from pymtl.wrappers.bpf_env_wrapper import BpfEnv


def build_bpf_env():
    dut = BpfEnv()
    dut.elaborate()
    dut.apply( VerilogPlaceholderPass() )
    dut = VerilogTranslationImportPass()( dut )
    dut.apply( DefaultPassGroup() )
    dut.sim_reset()
    return dut
