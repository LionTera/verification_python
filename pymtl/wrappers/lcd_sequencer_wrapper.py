from os.path import dirname, join, abspath
from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholder, VerilogPlaceholderPass

Bits1 = mk_bits(1)
Bits32 = mk_bits(32)

class LcdSequencer( Component, VerilogPlaceholder ):
    def construct( s ):
        s.lcd_scl              = OutPort( Bits1 )
        s.lcd_sda              = OutPort( Bits1 )
        s.bcp_u2u_status       = InPort( Bits32 )
        s.lcd_search           = InPort( Bits1 )
        s.lcd_update           = InPort( Bits1 )
        s.lcd_enable           = InPort( Bits1 )
        s.lcd_active           = OutPort( Bits1 )

        base = abspath( join( dirname(__file__), "..", ".." ) )

        s.set_metadata(
        VerilogPlaceholderPass.src_file,
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_sequencer.v" )
        )

        s.set_metadata(
        VerilogPlaceholderPass.top_module,
        "lcd_sequencer"
        )
        s.set_metadata(
        VerilogPlaceholderPass.params,
        {
        "I2C_BAUD": 100000,
        "FCLK": 50000000,
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
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_pram.v" ),
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
        ]
        )

        s.set_metadata(
        VerilogPlaceholderPass.v_include,
        [
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl" )
        ]
        )
