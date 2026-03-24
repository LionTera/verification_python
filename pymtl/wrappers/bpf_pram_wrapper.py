from os.path import dirname, join, abspath
from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholder, VerilogPlaceholderPass

Bits1 = mk_bits(1)

class BpfPram( Component, VerilogPlaceholder ):
    def construct( s ):
        s.rd_addr_a            = InPort( mk_bits(ADDR_W) )
        s.rd_addr_b            = InPort( mk_bits(ADDR_W) )
        s.rd_data_a            = OutPort( mk_bits(DATA_W) )
        s.rd_data_b            = OutPort( mk_bits(DATA_W) )
        s.wr_addr              = InPort( mk_bits(ADDR_W) )
        s.wr_data              = InPort( mk_bits(DATA_W) )
        s.wr                   = InPort( Bits1 )

        base = abspath( join( dirname(__file__), "..", ".." ) )

        s.set_metadata(
        VerilogPlaceholderPass.src_file,
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_pram.v" )
        )

        s.set_metadata(
        VerilogPlaceholderPass.top_module,
        "bpf_pram"
        )
        s.set_metadata(
        VerilogPlaceholderPass.params,
        {
        "ADDR_W": 14,
        "DATA_W": 32,
        "NUM_WORDS": 4096,
        }
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
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_package.sv" ),
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_shift.v" ),
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_sram.v" ),
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_utils.v" ),
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_env.v" ),
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_i2c_master.v" ),
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_iram.v" ),
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_messages.v" ),
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu.20230901.v" ),
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu.v" ),
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu_env.v" ),
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_sequencer.v" ),
        ]
        )

        s.set_metadata(
        VerilogPlaceholderPass.v_include,
        [
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl" )
        ]
        )
