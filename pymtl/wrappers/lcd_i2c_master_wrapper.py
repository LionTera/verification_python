from os.path import dirname, join, abspath
from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholder, VerilogPlaceholderPass

Bits1 = mk_bits(1)
Bits7 = mk_bits(7)
Bits8 = mk_bits(8)

class LcdI2cMaster( Component, VerilogPlaceholder ):
    def construct( s ):
        s.i2c_scl = InPort( Bits1 )
        s.i2c_sda = InPort( Bits1 )
        s.i2c_master_a = InPort( Bits7 )
        s.i2c_master_wd = InPort( Bits8 )
        s.i2c_master_wr = InPort( Bits1 )
        s.i2c_master_done = OutPort( Bits1 )
        s.i2c_master_ack = OutPort( Bits1 )

        base = abspath( join( dirname(__file__), "..", ".." ) )

        s.set_metadata(
            VerilogPlaceholderPass.src_file,
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_i2c_master.v" ),
        )
        s.set_metadata(
            VerilogPlaceholderPass.top_module,
            "lcd_i2c_master",
        )
        s.set_metadata(
            VerilogPlaceholderPass.params,
            {
            "I2C_BAUD": 100000,
            "FCLK": 50000000,
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
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_pram.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_shift.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_sram.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_env.v" ),
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
