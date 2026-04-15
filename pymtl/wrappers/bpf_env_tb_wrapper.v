module bpf_env_tb_wrapper
#(
    parameter SHIFTER_LATENCY = 1,
    parameter OMIT_DIVIDER = 0,
    parameter OMIT_MULTIPLIER = 0
)
(
    input                        clk,
    input                        reset,
    output                       bpf_enb,
    input                        bpf_start,
    input       [13:0]           bpf_packet_len,
    output                       bpf_return,
    output                       bpf_accept,
    output                       bpf_reject,
    input                        bpf_packet_loss,
    output      [31:0]           bpf_ret_value,
    output                       bpf_active,
    input       [15:0]           bpf_mmap_addr,
    input       [31:0]           bpf_mmap_wdata,
    input                        bpf_mmap_wr,
    output      [31:0]           bpf_mmap_rdata,
    input                        bpf_mmap_rd,
    output                       bpf_mmap_ack,
    input       [13:0]           bpf_pram_waddr,
    input       [31:0]           bpf_pram_wdata,
    input                        bpf_pram_wr,
    input       [13:0]           bpf_pram_raddr,
    output      [31:0]           bpf_pram_rdata,
    input       [1:0]            bpf_pram_bank_rx,
    input       [1:0]            bpf_pram_bank_bpf,
    input       [1:0]            bpf_pram_bank_tx,
    output      [31:0]           bpf_acc,
    output      [31:0]           bpf_pc,
    output      [31:0]           bpf_x,
    output reg  [31:0]           tb_cycle_counter
);

always @(posedge clk or posedge reset) begin
    if (reset) tb_cycle_counter <= 32'd0;
    else tb_cycle_counter <= tb_cycle_counter + 32'd1;
end

bpf_env
#(
    .SHIFTER_LATENCY(SHIFTER_LATENCY),
    .OMIT_DIVIDER(OMIT_DIVIDER),
    .OMIT_MULTIPLIER(OMIT_MULTIPLIER)
)
u_bpf_env
(
    .clk(clk),
    .reset(reset),
    .bpf_enb(bpf_enb),
    .bpf_start(bpf_start),
    .bpf_packet_len(bpf_packet_len),
    .bpf_return(bpf_return),
    .bpf_accept(bpf_accept),
    .bpf_reject(bpf_reject),
    .bpf_packet_loss(bpf_packet_loss),
    .bpf_ret_value(bpf_ret_value),
    .bpf_active(bpf_active),
    .bpf_mmap_addr(bpf_mmap_addr),
    .bpf_mmap_wdata(bpf_mmap_wdata),
    .bpf_mmap_wr(bpf_mmap_wr),
    .bpf_mmap_rdata(bpf_mmap_rdata),
    .bpf_mmap_rd(bpf_mmap_rd),
    .bpf_mmap_ack(bpf_mmap_ack),
    .bpf_pram_waddr(bpf_pram_waddr),
    .bpf_pram_wdata(bpf_pram_wdata),
    .bpf_pram_wr(bpf_pram_wr),
    .bpf_pram_raddr(bpf_pram_raddr),
    .bpf_pram_rdata(bpf_pram_rdata),
    .bpf_pram_bank_rx(bpf_pram_bank_rx),
    .bpf_pram_bank_bpf(bpf_pram_bank_bpf),
    .bpf_pram_bank_tx(bpf_pram_bank_tx)
);

assign bpf_acc = u_bpf_env.bpf_npu.bpf_acc;
assign bpf_pc  = u_bpf_env.bpf_npu.bpf_pc;
assign bpf_x   = u_bpf_env.bpf_npu.bpf_dp.x_reg;

endmodule
