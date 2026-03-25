from os.path import dirname, join, abspath
from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholder, VerilogPlaceholderPass

Bits1 = mk_bits(1)
Bits8 = mk_bits(8)
Bits16 = mk_bits(16)
Bits32 = mk_bits(32)

class LcdMpuEnv( Component, VerilogPlaceholder ):
    def construct( s ):
        s.lcd_scl = InPort( Bits1 )
        s.lcd_sda = InPort( Bits1 )
        s.bcp_u2u_status = InPort( Bits32 )
        s.lcd_search = InPort( Bits1 )
        s.lcd_update = InPort( Bits1 )
        s.lcd_enable = InPort( Bits1 )
        s.lcd_active = OutPort( Bits1 )
        s.lcd_return = OutPort( Bits1 )
        s.lcd_ret_value = OutPort( Bits32 )
        s.lcd_mmap_addr = InPort( Bits16 )
        s.lcd_mmap_wdata = InPort( Bits32 )
        s.lcd_mmap_wr = InPort( Bits1 )
        s.lcd_mmap_rdata = OutPort( Bits32 )
        s.lcd_mmap_rd = InPort( Bits1 )
        s.lcd_mmap_ack = OutPort( Bits1 )
        s.s2u_wr = InPort( Bits1 )
        s.s2u_addr = InPort( Bits8 )
        s.s2u_din = InPort( Bits32 )

        base = abspath( join( dirname(__file__), "..", ".." ) )

        s.set_metadata(
            VerilogPlaceholderPass.src_file,
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu_env.v" ),
        )
        s.set_metadata(
            VerilogPlaceholderPass.top_module,
            "lcd_mpu_env",
        )
        s.set_metadata(
            VerilogPlaceholderPass.params,
            {
            "I2C_ADDR": 39,
            "I2C_BAUD": 100000,
            "FCLK": 50000000,
            "U2U_VER": 0,
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
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_i2c_master.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_iram.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu.v" ),
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_sequencer.v" ),
            ],
        )
        s.set_metadata(
            VerilogPlaceholderPass.v_include,
            [
                join( base, "bpf_test/u2u_v401/tf_bpf/rtl" ),
            ],
        )
