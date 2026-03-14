module full_adder_8bit (
    input  logic [7:0] a,
    input  logic [7:0] b,
    input  logic       cin,
    output logic [7:0] sum,
    output logic       cout
);
    // In Verilog, {cout, sum} concatenates the two into a 9-bit result
    assign {cout, sum} = a + b + cin;
endmodule