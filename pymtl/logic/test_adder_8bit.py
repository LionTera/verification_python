import random
from pymtl3 import *
from full_adder_8bit_wrapper import FullAdder8bit

def test_random_8bit():
    dut = FullAdder8bit()
    dut.verilog_compile = True
    dut.elaborate()
    dut = VerilogTranslationImportPass()( dut )
    dut.apply( DefaultPassGroup() )
    dut.sim_reset()

    for i in range(100): # Run 100 random tests
        # 1. Generate Random Inputs
        ref_a   = random.randint(0, 255)
        ref_b   = random.randint(0, 255)
        ref_cin = random.randint(0, 1)

        # 2. Apply to Hardware
        dut.a   @= ref_a
        dut.b   @= ref_b
        dut.cin @= ref_cin
        dut.sim_eval_combinational()

        # 3. Golden Model (Python Math)
        # We simulate the 9-bit result to check sum and carry
        total = ref_a + ref_b + ref_cin
        exp_sum  = total & 0xFF      # Lower 8 bits
        exp_cout = (total >> 8) & 1  # 9th bit (carry)

        # 4. Assert
        assert dut.sum == exp_sum, f"Failed at {ref_a}+{ref_b}: HW {dut.sum} != Ref {exp_sum}"
        assert dut.cout == exp_cout, f"Carry failed at {ref_a}+{ref_b}"

    print("Successfully verified 100 random 8-bit additions!")