# BPF RTL/TB Analysis Summary

- RTL directory: `bpf_test/u2u_v401/tf_bpf/rtl`
- TB directory: `bpf_test/u2u_v401/tf_bpf/tb`
- RTL modules found: **16**
- TB modules found: **7**

## Executive Summary

- Could not infer a single DUT from the TB automatically.
- RTL top candidates (no parents in RTL hierarchy): **bpf_control, bpf_shifter**
- Could not infer RTL top module, so packet interface inference is limited.

## RTL Modules

### `bpf_control`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_control.v`
- Ports: input clk 1, input reset 1, input bpf_enb 1, input bpf_start 1, input bpf_start_addr [BPF_IRAM_ADDR_W-1:0], output bpf_return 1, output bpf_active 1, output bpf_iram_raddr [BPF_IRAM_ADDR_W-1:0], input bpf_iram_rdata [63:0], output bpf_iram_rd 1, input bpf_acc [31:0], output bpf_pc [31:0], ...
- Instantiates: None detected

### `bpf_div`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_div.v`
- Ports: input clk 1, input reset 1, input start 1, output active 1, input x [W-1:0], input y [W-1:0], output q [W-1:0], output r [W-1:0]
- Instantiates: None detected

### `bpf_dp`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_dp.v`
- Ports: input clk 1, input reset 1, input bpf_start 1, input bpf_packet_len [BPF_PRAM_ADDR_W-1:0], output bpf_accept 1, output bpf_ret_value [31:0], output bpf_pram_a [BPF_PRAM_ADDR_W-1:0], output bpf_pram_b [BPF_PRAM_ADDR_W-1:0], input bpf_pram_rdata_a [31:0], input bpf_pram_rdata_b [31:0], output bpf_pram_rd_a 1, output bpf_pram_rd_b 1, ...
- Instantiates: bpf_dp (bpf_shifter), bpf_mult (bpf_mult), bpf_div (bpf_div)

### `bpf_env`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_env.v`
- Ports: input clk 1, input reset 1, output bpf_enb 1, input bpf_start 1, input bpf_packet_len [BPF_PRAM_ADDR_W-1:0], output bpf_return 1, output bpf_accept 1, output bpf_reject 1, input bpf_packet_loss 1, output bpf_ret_value [31:0], output bpf_active 1, input bpf_mmap_addr [15:0], ...
- Instantiates: bpf_env (bpf_npu)

### `bpf_iram`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_iram.v`
- Ports: input rd_clk 1, input rd_addr [ADDR_W-1:0], output rd_data [DATA_W-1:0], input wr_clk 1, input wr_addr [ADDR_W-1:0], input wr_data [DATA_W-1:0], input wr 1, input be 1
- Instantiates: None detected

### `bpf_mult`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_mult.v`
- Ports: input clk 1, input reset 1, input start 1, output active 1, input x [IN_W-1:0], input y [IN_W-1:0], output z [OUT_W-1:0], output z_eq_0 1
- Instantiates: None detected

### `bpf_npu`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_npu.v`
- Ports: input clk 1, input reset 1, output bpf_enb 1, input bpf_start 1, input bpf_packet_len [BPF_PRAM_ADDR_W-1:0], output bpf_return 1, output bpf_accept 1, output bpf_reject 1, input bpf_packet_loss 1, output bpf_ret_value [31:0], output bpf_active 1, input bpf_mmap_addr [15:0], ...
- Instantiates: bpf_npu (bpf_control), bpf_dp (bpf_dp), bpf_iram (bpf_iram), bpf_sram (bpf_sram), bpf_pram (bpf_pram_b0), bpf_pram (bpf_pram_b1), bpf_pram (bpf_pram_b2)

### `bpf_pram`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_pram.v`
- Ports: input clk 1, input rd_addr_a [ADDR_W-1:0], input rd_addr_b [ADDR_W-1:0], output rd_data_a [DATA_W-1:0], output rd_data_b [DATA_W-1:0], input wr_addr [ADDR_W-1:0], input wr_data [DATA_W-1:0], input wr 1
- Instantiates: None detected

### `bpf_shifter`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_shift.v`
- Ports: input clk 1, input reset 1, input start 1, output active 1, input x [31:0], input y [31:0], input lrn 1, output z [31:0]
- Instantiates: None detected

### `bpf_sram`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_sram.v`
- Ports: input clk 1, input rd_addr [ADDR_W-1:0], output rd_data [DATA_W-1:0], input wr_addr [ADDR_W-1:0], input wr_data [DATA_W-1:0], input wr 1
- Instantiates: None detected

### `lcd_env`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_env.v`
- Ports: input clk 1, input reset 1, inout lcd_scl 1, inout lcd_sda 1, input bcp_u2u_status [31:0], input lcd_search 1, input lcd_update 1, input lcd_enable 1, output lcd_active 1, input lcd_mmap_addr [15:0], input lcd_mmap_wdata [31:0], input lcd_mmap_wr 1, ...
- Instantiates: lcd_env (lcd_sequencer)

### `lcd_i2c_master`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_i2c_master.v`
- Ports: input clk 1, input reset 1, inout i2c_scl 1, inout i2c_sda 1, input i2c_master_a [6:0], input i2c_master_wd [7:0], input i2c_master_wr 1, output i2c_master_done 1, output i2c_master_ack 1
- Instantiates: None detected

### `lcd_iram`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_iram.v`
- Ports: input rd_clk 1, input rd_addr [ADDR_W-1:0], output rd_data [DATA_W-1:0], input wr_clk 1, input wr_addr [ADDR_W-1:0], input wr_data [DATA_W-1:0], input wr 1, input be 1
- Instantiates: None detected

### `lcd_mpu`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu.v`
- Ports: input clk 1, input reset 1, inout lcd_scl 1, inout lcd_sda 1, input bcp_u2u_status [31:0], input lcd_search 1, input lcd_update 1, input lcd_enable 1, output lcd_active 1, output lcd_return 1, output lcd_ret_value [31:0], input lcd_mmap_addr [15:0], ...
- Instantiates: lcd_mpu (bpf_control), bpf_dp (bpf_dp), lcd_iram (lcd_iram), bpf_sram (bpf_sram), bpf_sram (u2u_s2u_ram), lcd_i2c_master (lcd_i2c_master)

### `lcd_mpu_env`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu_env.v`
- Ports: input clk 1, input reset 1, inout lcd_scl 1, inout lcd_sda 1, input bcp_u2u_status [31:0], input lcd_search 1, input lcd_update 1, input lcd_enable 1, output lcd_active 1, output lcd_return 1, output lcd_ret_value [31:0], input lcd_mmap_addr [15:0], ...
- Instantiates: lcd_mpu_env (lcd_mpu)

### `lcd_sequencer`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_sequencer.v`
- Ports: input clk 1, input reset 1, inout lcd_scl 1, inout lcd_sda 1, input bcp_u2u_status [31:0], input lcd_search 1, input lcd_update 1, input lcd_enable 1, output lcd_active 1
- Instantiates: lcd_sequencer (lcd_i2c_master), bpf_div (bpf_div)

## RTL Top Candidates

- `bpf_control` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_control.v`
- `bpf_shifter` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_shift.v`

## TB to RTL Connectivity

- No direct TB→RTL instantiations detected

## TB Structure and Stimulus Clues

### `pcap2rgmii` tasks/functions
- `function:fcs_swap_invert`

### `tb_bpf` tasks/functions
- `init_instruction_mem`
- `init_packet_mem`
- `init_dut_signals`
- `function:void`
- `function:void`

### `tb_div` tasks/functions
- `function:void`

### `tb_lcd` tasks/functions
- `wait_scl`
- `wait_half_scl`
- `init_instruction_mem`
- `run_test`
- `function:void`
- `function:void`

### `tb_pcap` tasks/functions
- `function:void`

### `tb_shift` tasks/functions
- `function:void`

### File/vector activity
- `pcap2rgmii`: file/vector IO detected
- `tb_bpf`: file/vector IO detected
- `tb_lcd`: file/vector IO detected

### Packet-related lines found in TB

#### `m_i2c_slave`
- Line 5: `// Description: write only i2c model                                        //`
- Line 42: `reg  [7:0] data;       // received i2c data`
- Line 53: ``define S_I2C_DATA  4'd5`
- Line 54: ``define S_I2C_DACK  4'd6      // data phase ack`
- Line 63: `data      <= 8'd0;`
- Line 97: `if (addr == I2C_ADDR) begin  // address match, goto ack`
- Line 100: `i2c_state <= `S_I2C_IDLE;     // address mismatch, stop`
- Line 103: `//      $display("i2c %02x mon rd: mismatch addr %02x",I2C_ADDR,addr);`
- Line 105: `//      $display("i2c %02x mon wr: mismatch addr %02x",I2C_ADDR,addr);`
- Line 118: `i2c_state <= `S_I2C_DATA;`
- Line 128: ``S_I2C_DATA: begin`
- Line 131: `data      <= sreg;                // get data`
- Line 135: `i2c_state <= `S_I2C_DATA;`
- Line 159: `$display("i2c %02x mon read : addr %02x, data %02x",`
- Line 160: `I2C_ADDR, addr, data);`

#### `pcap2rgmii`
- Line 5: `// Description:                                                               //`
- Line 16: `// File Header`
- Line 29: `// 16 |                            SnapLen                            |`
- Line 35: `// Packet Record`
- Line 44: `//  8 |                    Captured Packet Length                     |`
- Line 46: `// 12 |                    Original Packet Length                     |`
- Line 49: `//    /                          Packet Data                          /`
- Line 50: `//    /                        variable length                        /`
- Line 59: `parameter preamble_len = 16,`
- Line 67: `output reg        sop,       // pulse with first character`
- Line 68: `output            eop,       // pulse with last  character`
- Line 70: `output reg [15:0] len,       // payload length`
- Line 71: `input      [15:0] ipg_len,   // inter packet gap (delay after CRC)`
- Line 82: `// pcap packet buffers`
- Line 83: `reg    [7:0] f_hdr [0:23];   // pcap file header`

#### `tb_bpf`
- Line 49: `integer tb_packet_length;`
- Line 50: `integer tb_inst_length;`
- Line 56: `reg     [7:0] tb_pram [0:(1 << BPF_PRAM_ADDR_W)-1];    // packet memory mirror`
- Line 69: `reg  [BPF_PRAM_ADDR_W-1:0] bpf_packet_len;`
- Line 71: `reg                        bpf_accept;       // accept/reject packet`
- Line 76: `reg                 [63:0] bpf_iram_wdata;`
- Line 79: `// packet storage - byte address`
- Line 81: `reg                 [31:0] bpf_pram_wdata;`
- Line 113: `$display("    - packet length = %-d (0x%h)", tb_packet_length, tb_packet_length);`
- Line 116: `while (i < tb_packet_length) begin`
- Line 126: `$display("    - program length = %-d", tb_inst_length);`
- Line 129: `while (i < tb_inst_length) begin`
- Line 161: `// initialize instruction memory with debug data`
- Line 170: `// '-b' flag: bypass bpfc validation (allows more than 16 scratch pad words)`
- Line 191: `bpf_iram_wdata  = inst;`

#### `tb_lcd`
- Line 70: `reg   [7:0] tb_i2c_master_wd;   // i2c write data`
- Line 78: `reg   [7:0] tb_d;               // i2s write data`
- Line 92: `tb_i2c_master_wd = 0;   // i2c write data`
- Line 104: `// mismatched address`
- Line 144: `// data phase`
- Line 161: `//--- address mismatch`
- Line 179: `//--- address mismatch`
- Line 253: `reg  [31:0] seq_lcd_mmap_wdata;  // memory mapped access`
- Line 255: `wire [31:0] seq_lcd_mmap_rdata;  // memory mapped access`
- Line 266: `reg         seq_data_dir_0to1;       // MAC0 to MAC1`
- Line 267: `reg         seq_data_dir_1to0;       // MAC1 to MAC0`
- Line 268: `reg   [8:1] seq_dipsw;               // top-left dipsw`
- Line 275: `seq_data_dir_0to1,           // 1b  rp_con[11] direction left ->right`
- Line 276: `seq_data_dir_1to0,           // 1b  rp_con[18] direction right->left`
- Line 277: `seq_dipsw};                  // 8b  dipswitch status`

#### `tb_pcap`
- Line 10: `//string fname = "tcp-4846-connect-disconnect.pcap";`
- Line 11: `//string fname = "tcp-9661-closed.pcap";`
- Line 20: `wire        sop;`
- Line 21: `wire        eop;`
- Line 23: `wire [15:0] len;`
- Line 24: `wire [15:0] ipg_len;`
- Line 35: `wire [13:0] mon_prmble_len;     // length of preamble`
- Line 38: `wire [15:0] mon_len;            // Length of payload`
- Line 39: `wire [15:0] mon_frmtype;        // if non-null: type field instead length`
- Line 47: `wire        mon_len_err;`
- Line 55: `wire        mon_data_only;`
- Line 67: `wire        gen_sop;`
- Line 68: `wire        gen_eop;`
- Line 74: `integer     tb_mon_bytes;`
- Line 75: `reg         tb_mon_valid;`

## Inferred Packet Interface

- Inferred RTL top for packet analysis: `None`
- No packet-related top ports detected by name

## Recommended Verification Approach

1. Use the likely DUT module above as the PyMTL import target, not the TB module.
2. Mirror the TB packet stimulus pattern in Python: either drive the DUT ports directly, or reproduce the TB task behavior cycle by cycle.
3. Start with a smoke test that resets the DUT, sends one short packet/vector, and checks one clear observable output.
4. Only after the smoke test works, add deeper checks for the internal logic you want to verify.

