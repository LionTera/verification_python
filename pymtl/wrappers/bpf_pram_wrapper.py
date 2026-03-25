from os.path import dirname, join, abspath
from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholder, VerilogPlaceholderPass

Bits1 = mk_bits(1)
Bits14 = mk_bits(14)
Bits32 = mk_bits(32)

class BpfPram( Component, VerilogPlaceholder ):
    def construct( s ):
        s.rd_addr_a = InPort( Bits14 )
        s.rd_addr_b = InPort( Bits14 )
        s.rd_data_a = OutPort( Bits32 )
        s.rd_data_b = OutPort( Bits32 )
        s.wr_addr = InPort( Bits14 )
        s.wr_data = InPort( Bits32 )
        s.wr = InPort( Bits1 )

        base = abspath( join( dirname(__file__), "..", ".." ) )

        s.set_metadata(
            VerilogPlaceholderPass.src_file,
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_pram.v" ),
        )
        s.set_metadata(
            VerilogPlaceholderPass.top_module,
            "bpf_pram",
        )
        s.set_metadata(
            VerilogPlaceholderPass.params,
            {
            "ADDR_W": 14,
            "DATA_W": 32,
            "NUM_WORDS": 4096,
            },
        )
        s.set_metadata(
            VerilogPlaceholderPass.v_libs,
            [
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_control.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_div.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_dp.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_env.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_iram.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_mult.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_npu.v" ),
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
