from os.path import dirname, join, abspath
from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholder, VerilogPlaceholderPass

Bits1 = mk_bits(1)
Bits32 = mk_bits(32)
Bits16 = mk_bits(16)
Bits2 = mk_bits(2)

class BpfNpu( Component, VerilogPlaceholder ):
    def construct( s ):
        s.bpf_enb              = OutPort( Bits1 )
        s.bpf_start            = InPort( Bits1 )
        s.bpf_packet_len       = InPort( mk_bits(BPF_PRAM_ADDR_W) )
        s.bpf_return           = OutPort( Bits1 )
        s.bpf_accept           = OutPort( Bits1 )
        s.bpf_reject           = OutPort( Bits1 )
        s.bpf_packet_loss      = InPort( Bits1 )
        s.bpf_ret_value        = OutPort( Bits32 )
        s.bpf_active           = OutPort( Bits1 )
        s.bpf_mmap_addr        = InPort( Bits16 )
        s.bpf_mmap_wdata       = InPort( Bits32 )
        s.bpf_mmap_wr          = InPort( Bits1 )
        s.bpf_mmap_rdata       = OutPort( Bits32 )
        s.bpf_mmap_rd          = InPort( Bits1 )
        s.bpf_mmap_ack         = OutPort( Bits1 )
        s.bpf_pram_waddr       = InPort( mk_bits(BPF_PRAM_ADDR_W) )
        s.bpf_pram_wdata       = InPort( Bits32 )
        s.bpf_pram_wr          = InPort( Bits1 )
        s.bpf_pram_raddr       = InPort( mk_bits(BPF_PRAM_ADDR_W) )
        s.bpf_pram_rdata       = OutPort( Bits32 )
        s.bpf_pram_bank_rx     = InPort( Bits2 )
        s.bpf_pram_bank_bpf    = InPort( Bits2 )
        s.bpf_pram_bank_tx     = InPort( Bits2 )

        base = abspath( join( dirname(__file__), "..", ".." ) )

        s.set_metadata(
        VerilogPlaceholderPass.src_file,
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_npu.v" )
        )

        s.set_metadata(
        VerilogPlaceholderPass.top_module,
        "bpf_npu"
        )
        s.set_metadata(
        VerilogPlaceholderPass.params,
        {
        "SHIFTER_LATENCY": 1,
        "OMIT_DIVIDER": 0,
        "OMIT_MULTIPLIER": 0,
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
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_sequencer.v" ),
        ]
        )

        s.set_metadata(
        VerilogPlaceholderPass.v_include,
        [
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl" )
        ]
        )
