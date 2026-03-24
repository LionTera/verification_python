from os.path import dirname, join, abspath
from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholder, VerilogPlaceholderPass

Bits1  = mk_bits(1)
Bits3  = mk_bits(3)
Bits4  = mk_bits(4)
Bits5  = mk_bits(5)
Bits10 = mk_bits(10)
Bits14 = mk_bits(14)
Bits32 = mk_bits(32)
Bits64 = mk_bits(64)

class BpfControl( Component, VerilogPlaceholder ):
    def construct( s ):
        # PyMTL already provides implicit clk/reset ports.
        # Do not redeclare s.clk or s.reset.

        s.bpf_enb              = InPort( Bits1 )
        s.bpf_start            = InPort( Bits1 )
        s.bpf_start_addr       = InPort( Bits10 )

        s.bpf_return           = OutPort( Bits1 )
        s.bpf_active           = OutPort( Bits1 )

        s.bpf_iram_raddr       = OutPort( Bits10 )
        s.bpf_iram_rdata       = InPort( Bits64 )
        s.bpf_iram_rd          = OutPort( Bits1 )

        s.bpf_acc              = InPort( Bits32 )
        s.bpf_pc               = OutPort( Bits32 )

        s.bpf_s1_stall         = OutPort( Bits1 )
        s.bpf_s2_stall         = InPort( Bits1 )
        s.bpf_eop_fault        = InPort( Bits1 )
        s.bpf_div_0            = InPort( Bits1 )
        s.bpf_alu_eq_0         = InPort( Bits1 )
        s.bpf_alu_negative     = InPort( Bits1 )

        s.bpf_pram_rd          = OutPort( Bits1 )
        s.bpf_access_len       = OutPort( Bits3 )

        s.bpf_ld_acc           = OutPort( Bits1 )
        s.bpf_ldh_acc          = OutPort( Bits1 )
        s.bpf_ldb_acc          = OutPort( Bits1 )
        s.bpf_ld_x             = OutPort( Bits1 )

        s.bpf_st_acc           = OutPort( Bits1 )
        s.bpf_st_x             = OutPort( Bits1 )
        s.bpf_st_sc_ind        = OutPort( Bits1 )

        s.bpf_ret_acc          = OutPort( Bits1 )
        s.bpf_ret_k            = OutPort( Bits1 )
        s.bpf_ret_0            = OutPort( Bits1 )

        s.bpf_a_mode_k         = OutPort( Bits1 )
        s.bpf_a_mode_x_k       = OutPort( Bits1 )
        s.bpf_a_mode_sc        = OutPort( Bits1 )
        s.bpf_a_mode_sc_ind    = OutPort( Bits1 )

        s.bpf_alu_op           = OutPort( Bits4 )
        s.bpf_alu_in_k         = OutPort( Bits1 )
        s.bpf_alu_in_x         = OutPort( Bits1 )
        s.bpf_alu_shift        = OutPort( Bits1 )
        s.bpf_alu_mul          = OutPort( Bits1 )
        s.bpf_alu_div          = OutPort( Bits1 )

        s.bpf_sel_imm          = OutPort( Bits1 )
        s.bpf_sel_plen         = OutPort( Bits1 )
        s.bpf_sel_sc_pad       = OutPort( Bits1 )
        s.bpf_sel_pmem         = OutPort( Bits1 )
        s.bpf_sel_pmem_4lsb    = OutPort( Bits1 )
        s.bpf_sel_alu          = OutPort( Bits1 )
        s.bpf_sel_acc2x        = OutPort( Bits1 )
        s.bpf_sel_x2acc        = OutPort( Bits1 )
        s.bpf_sel_pc2acc       = OutPort( Bits1 )

        s.bpf_k_s1             = OutPort( Bits32 )
        s.bpf_k_s2             = OutPort( Bits32 )
        s.bpf_k_s3             = OutPort( Bits32 )

        base = abspath( join( dirname(__file__), "..", ".." ) )

        s.set_metadata(
            VerilogPlaceholderPass.src_file,
            join( base, "bpf_test/u2u_v401/tf_bpf/rtl/bpf_control.v" )
        )

        s.set_metadata(
            VerilogPlaceholderPass.top_module,
            "bpf_control"
        )

        s.set_metadata(
            VerilogPlaceholderPass.params,
            {
                "BPF_IRAM_ADDR_W": 10,
                "BPF_PRAM_ADDR_W": 14,
                "BPF_SRAM_ADDR_W": 5,
            }
        )

        s.set_metadata(
            VerilogPlaceholderPass.v_libs,
            [
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
                join( base, "bpf_test/u2u_v401/tf_bpf/rtl/lcd_sequencer.v" ),
            ]
        )

        s.set_metadata(
            VerilogPlaceholderPass.v_include,
            [
                join( base, "bpf_test/u2u_v401/tf_bpf/rtl" )
            ]
        )