from os.path import dirname, join, abspath
from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholder, VerilogPlaceholderPass

Bits1 = mk_bits(1)
Bits32 = mk_bits(32)
Bits3 = mk_bits(3)
Bits4 = mk_bits(4)

class BpfDp( Component, VerilogPlaceholder ):
    def construct( s ):
        s.bpf_start            = InPort( Bits1 )
        s.bpf_packet_len       = InPort( mk_bits(BPF_PRAM_ADDR_W) )
        s.bpf_accept           = OutPort( Bits1 )
        s.bpf_ret_value        = OutPort( Bits32 )
        s.bpf_pram_a           = OutPort( mk_bits(BPF_PRAM_ADDR_W) )
        s.bpf_pram_b           = OutPort( mk_bits(BPF_PRAM_ADDR_W) )
        s.bpf_pram_rdata_a     = InPort( Bits32 )
        s.bpf_pram_rdata_b     = InPort( Bits32 )
        s.bpf_pram_rd_a        = OutPort( Bits1 )
        s.bpf_pram_rd_b        = OutPort( Bits1 )
        s.bpf_sram_raddr       = OutPort( mk_bits(BPF_SRAM_ADDR_W) )
        s.bpf_sram_rdata       = InPort( Bits32 )
        s.bpf_sram_rd          = OutPort( Bits1 )
        s.bpf_sram_waddr       = OutPort( mk_bits(BPF_SRAM_ADDR_W) )
        s.bpf_sram_wdata       = OutPort( Bits32 )
        s.bpf_sram_wr          = OutPort( Bits1 )
        s.bpf_acc              = OutPort( Bits32 )
        s.bpf_pc               = InPort( Bits32 )
        s.bpf_s1_stall         = InPort( Bits1 )
        s.bpf_s2_stall         = OutPort( Bits1 )
        s.bpf_eop_fault        = OutPort( Bits1 )
        s.bpf_div_0            = OutPort( Bits1 )
        s.bpf_alu_eq_0         = OutPort( Bits1 )
        s.bpf_alu_negative     = OutPort( Bits1 )
        s.bpf_pram_rd          = InPort( Bits1 )
        s.bpf_access_len       = InPort( Bits3 )
        s.bpf_ld_acc           = InPort( Bits1 )
        s.bpf_ldh_acc          = InPort( Bits1 )
        s.bpf_ldb_acc          = InPort( Bits1 )
        s.bpf_ld_x             = InPort( Bits1 )
        s.bpf_st_acc           = InPort( Bits1 )
        s.bpf_st_x             = InPort( Bits1 )
        s.bpf_st_sc_ind        = InPort( Bits1 )
        s.bpf_ret_acc          = InPort( Bits1 )
        s.bpf_ret_k            = InPort( Bits1 )
        s.bpf_ret_0            = InPort( Bits1 )
        s.bpf_a_mode_k         = InPort( Bits1 )
        s.bpf_a_mode_x_k       = InPort( Bits1 )
        s.bpf_a_mode_sc        = InPort( Bits1 )
        s.bpf_a_mode_sc_ind    = InPort( Bits1 )
        s.bpf_alu_op           = InPort( Bits4 )
        s.bpf_alu_in_k         = InPort( Bits1 )
        s.bpf_alu_in_x         = InPort( Bits1 )
        s.bpf_alu_shift        = InPort( Bits1 )
        s.bpf_alu_mul          = InPort( Bits1 )
        s.bpf_alu_div          = InPort( Bits1 )
        s.bpf_sel_imm          = InPort( Bits1 )
        s.bpf_sel_plen         = InPort( Bits1 )
        s.bpf_sel_sc_pad       = InPort( Bits1 )
        s.bpf_sel_pmem         = InPort( Bits1 )
        s.bpf_sel_pmem_4lsb    = InPort( Bits1 )
        s.bpf_sel_alu          = InPort( Bits1 )
        s.bpf_sel_acc2x        = InPort( Bits1 )
        s.bpf_sel_x2acc        = InPort( Bits1 )
        s.bpf_sel_pc2acc       = InPort( Bits1 )
        s.bpf_k_s1             = InPort( Bits32 )
        s.bpf_k_s2             = InPort( Bits32 )
        s.bpf_k_s3             = InPort( Bits32 )

        base = abspath( join( dirname(__file__), "..", ".." ) )

        s.set_metadata(
        VerilogPlaceholderPass.src_file,
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_dp.v" )
        )

        s.set_metadata(
        VerilogPlaceholderPass.top_module,
        "bpf_dp"
        )
        s.set_metadata(
        VerilogPlaceholderPass.params,
        {
        "BPF_IRAM_ADDR_W": 10,
        "BPF_PRAM_ADDR_W": 14,
        "BPF_SRAM_ADDR_W": 5,
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
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_sequencer.v" ),
        ]
        )

        s.set_metadata(
        VerilogPlaceholderPass.v_include,
        [
        join( base, "bpf_test/u2u_v401/tf_bpf/rtl" )
        ]
        )
