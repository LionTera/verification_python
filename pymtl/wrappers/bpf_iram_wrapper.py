from os.path import dirname, join, abspath
from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholder, VerilogPlaceholderPass

Bits1 = mk_bits(1)
Bits10 = mk_bits(10)
Bits64 = mk_bits(64)

class BpfIram( Component, VerilogPlaceholder ):
    def construct( s ):
        s.rd_clk = InPort( Bits1 )
        s.rd_addr = InPort( Bits10 )
        s.rd_data = OutPort( Bits64 )
        s.wr_clk = InPort( Bits1 )
        s.wr_addr = InPort( Bits10 )
        s.wr_data = InPort( Bits64 )
        s.wr = InPort( Bits1 )
        s.be = InPort( Bits1 )

        base = abspath( join( dirname(__file__), "..", ".." ) )

        s.set_metadata(
            VerilogPlaceholderPass.src_file,
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_iram.v" ),
        )
        s.set_metadata(
            VerilogPlaceholderPass.top_module,
            "bpf_iram",
        )
        s.set_metadata(
            VerilogPlaceholderPass.params,
            {
            "ADDR_W": 10,
            "DATA_W": 64,
            "NUM_WORDS": 1024,
            },
        )
        s.set_metadata(
            VerilogPlaceholderPass.v_libs,
            [
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_control.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_div.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_dp.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_env.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_mult.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_npu.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_pram.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_shift.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_sram.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_env.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_i2c_master.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_iram.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu_env.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_sequencer.v" ),
            ],
        )
        s.set_metadata(
            VerilogPlaceholderPass.v_include,
            [
                join( base, "bpf_test/u2u_v401/tf_bpf/rtl" ),
            ],
        )
