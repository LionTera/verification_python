# BPF Implementation View

- RTL directory: `bpf_test/u2u_v401/tf_bpf/rtl`
- Modules found: **16**
- Chosen top: **bpf_control**

## Top Candidates

- `bpf_control` (score=110) from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_control.v`
- `bpf_dp` (score=86) from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_dp.v`
- `bpf_npu` (score=75) from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_npu.v`
- `bpf_shifter` (score=66) from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_shift.v`
- `lcd_mpu` (score=56) from `bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu.v`
- `bpf_env` (score=39) from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_env.v`
- `lcd_mpu_env` (score=26) from `bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu_env.v`
- `lcd_env` (score=21) from `bpf_test/u2u_v401/tf_bpf/rtl/lcd_env.v`
- `lcd_sequencer` (score=21) from `bpf_test/u2u_v401/tf_bpf/rtl/lcd_sequencer.v`
- `bpf_div` (score=16) from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_div.v`

## BPF-Oriented Interpretation

### Interface
- `bpf_env` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_env.v`
- `bpf_npu` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_npu.v`

### Match
- `bpf_control` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_control.v`
- `bpf_dp` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_dp.v`
- `bpf_mult` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_mult.v`
- `lcd_mpu` from `bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu.v`
- `lcd_mpu_env` from `bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu_env.v`
- `lcd_sequencer` from `bpf_test/u2u_v401/tf_bpf/rtl/lcd_sequencer.v`

### Memory
- `bpf_iram` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_iram.v`
- `bpf_pram` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_pram.v`
- `bpf_sram` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_sram.v`
- `lcd_iram` from `bpf_test/u2u_v401/tf_bpf/rtl/lcd_iram.v`

### Unknown
- `bpf_div` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_div.v`
- `bpf_shifter` from `bpf_test/u2u_v401/tf_bpf/rtl/bpf_shift.v`
- `lcd_env` from `bpf_test/u2u_v401/tf_bpf/rtl/lcd_env.v`
- `lcd_i2c_master` from `bpf_test/u2u_v401/tf_bpf/rtl/lcd_i2c_master.v`

## Chosen Top Interface

### Candidate packet input ports
- `input bpf_iram_rdata [63:0]`
- `input bpf_eop_fault 1`

### Candidate packet output ports
- `output bpf_access_len [2:0]`
- `output bpf_sel_plen 1`

### Candidate decision/result ports
- None detected automatically

## Connectivity Tree

- bpf_control

## Module Summary

### `bpf_control`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_control.v`
- Role: **match**
- Packet score: 3
- Decision score: 0
- Ports: input clk 1, input reset 1, input bpf_enb 1, input bpf_start 1, input bpf_start_addr [BPF_IRAM_ADDR_W-1:0], output bpf_return 1, output bpf_active 1, output bpf_iram_raddr [BPF_IRAM_ADDR_W-1:0], input bpf_iram_rdata [63:0], output bpf_iram_rd 1
- Instantiates: None detected

### `bpf_div`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_div.v`
- Role: **unknown**
- Packet score: 0
- Decision score: 0
- Ports: input clk 1, input reset 1, input start 1, output active 1, input x [W-1:0], input y [W-1:0], output q [W-1:0], output r [W-1:0]
- Instantiates: None detected

### `bpf_dp`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_dp.v`
- Role: **match**
- Packet score: 4
- Decision score: 1
- Ports: input clk 1, input reset 1, input bpf_start 1, input bpf_packet_len [BPF_PRAM_ADDR_W-1:0], output bpf_accept 1, output bpf_ret_value [31:0], output bpf_pram_a [BPF_PRAM_ADDR_W-1:0], output bpf_pram_b [BPF_PRAM_ADDR_W-1:0], input bpf_pram_rdata_a [31:0], input bpf_pram_rdata_b [31:0]
- Instantiates: bpf_dp (bpf_shifter), bpf_mult (bpf_mult), bpf_div (bpf_div)

### `bpf_env`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_env.v`
- Role: **interface**
- Packet score: 3
- Decision score: 1
- Ports: input clk 1, input reset 1, output bpf_enb 1, input bpf_start 1, input bpf_packet_len [BPF_PRAM_ADDR_W-1:0], output bpf_return 1, output bpf_accept 1, output bpf_reject 1, input bpf_packet_loss 1, output bpf_ret_value [31:0]
- Instantiates: bpf_env (bpf_npu)

### `bpf_iram`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_iram.v`
- Role: **memory**
- Packet score: 1
- Decision score: 0
- Ports: input rd_clk 1, input rd_addr [ADDR_W-1:0], output rd_data [DATA_W-1:0], input wr_clk 1, input wr_addr [ADDR_W-1:0], input wr_data [DATA_W-1:0], input wr 1, input be 1
- Instantiates: None detected

### `bpf_mult`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_mult.v`
- Role: **match**
- Packet score: 0
- Decision score: 0
- Ports: input clk 1, input reset 1, input start 1, output active 1, input x [IN_W-1:0], input y [IN_W-1:0], output z [OUT_W-1:0], output z_eq_0 1
- Instantiates: None detected

### `bpf_npu`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_npu.v`
- Role: **interface**
- Packet score: 3
- Decision score: 1
- Ports: input clk 1, input reset 1, output bpf_enb 1, input bpf_start 1, input bpf_packet_len [BPF_PRAM_ADDR_W-1:0], output bpf_return 1, output bpf_accept 1, output bpf_reject 1, input bpf_packet_loss 1, output bpf_ret_value [31:0]
- Instantiates: bpf_npu (bpf_control), bpf_dp (bpf_dp), bpf_iram (bpf_iram), bpf_sram (bpf_sram), bpf_pram (bpf_pram_b0), bpf_pram (bpf_pram_b1), bpf_pram (bpf_pram_b2)

### `bpf_pram`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_pram.v`
- Role: **memory**
- Packet score: 1
- Decision score: 0
- Ports: input clk 1, input rd_addr_a [ADDR_W-1:0], input rd_addr_b [ADDR_W-1:0], output rd_data_a [DATA_W-1:0], output rd_data_b [DATA_W-1:0], input wr_addr [ADDR_W-1:0], input wr_data [DATA_W-1:0], input wr 1
- Instantiates: None detected

### `bpf_shifter`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_shift.v`
- Role: **unknown**
- Packet score: 0
- Decision score: 0
- Ports: input clk 1, input reset 1, input start 1, output active 1, input x [31:0], input y [31:0], input lrn 1, output z [31:0]
- Instantiates: None detected

### `bpf_sram`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_sram.v`
- Role: **memory**
- Packet score: 1
- Decision score: 0
- Ports: input clk 1, input rd_addr [ADDR_W-1:0], output rd_data [DATA_W-1:0], input wr_addr [ADDR_W-1:0], input wr_data [DATA_W-1:0], input wr 1
- Instantiates: None detected

### `lcd_env`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_env.v`
- Role: **unknown**
- Packet score: 1
- Decision score: 0
- Ports: input clk 1, input reset 1, inout lcd_scl 1, inout lcd_sda 1, input bcp_u2u_status [31:0], input lcd_search 1, input lcd_update 1, input lcd_enable 1, output lcd_active 1, input lcd_mmap_addr [15:0]
- Instantiates: lcd_env (lcd_sequencer)

### `lcd_i2c_master`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_i2c_master.v`
- Role: **unknown**
- Packet score: 0
- Decision score: 0
- Ports: input clk 1, input reset 1, inout i2c_scl 1, inout i2c_sda 1, input i2c_master_a [6:0], input i2c_master_wd [7:0], input i2c_master_wr 1, output i2c_master_done 1, output i2c_master_ack 1
- Instantiates: None detected

### `lcd_iram`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_iram.v`
- Role: **memory**
- Packet score: 1
- Decision score: 0
- Ports: input rd_clk 1, input rd_addr [ADDR_W-1:0], output rd_data [DATA_W-1:0], input wr_clk 1, input wr_addr [ADDR_W-1:0], input wr_data [DATA_W-1:0], input wr 1, input be 1
- Instantiates: None detected

### `lcd_mpu`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu.v`
- Role: **match**
- Packet score: 1
- Decision score: 0
- Ports: input clk 1, input reset 1, inout lcd_scl 1, inout lcd_sda 1, input bcp_u2u_status [31:0], input lcd_search 1, input lcd_update 1, input lcd_enable 1, output lcd_active 1, output lcd_return 1
- Instantiates: lcd_mpu (bpf_control), bpf_dp (bpf_dp), lcd_iram (lcd_iram), bpf_sram (bpf_sram), bpf_sram (u2u_s2u_ram), lcd_i2c_master (lcd_i2c_master)

### `lcd_mpu_env`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_mpu_env.v`
- Role: **match**
- Packet score: 1
- Decision score: 0
- Ports: input clk 1, input reset 1, inout lcd_scl 1, inout lcd_sda 1, input bcp_u2u_status [31:0], input lcd_search 1, input lcd_update 1, input lcd_enable 1, output lcd_active 1, output lcd_return 1
- Instantiates: lcd_mpu_env (lcd_mpu)

### `lcd_sequencer`
- File: `bpf_test/u2u_v401/tf_bpf/rtl/lcd_sequencer.v`
- Role: **match**
- Packet score: 0
- Decision score: 0
- Ports: input clk 1, input reset 1, inout lcd_scl 1, inout lcd_sda 1, input bcp_u2u_status [31:0], input lcd_search 1, input lcd_update 1, input lcd_enable 1, output lcd_active 1
- Instantiates: lcd_sequencer (lcd_i2c_master), bpf_div (bpf_div)

## How To Use This

1. Start from the chosen top module.
2. Treat parser/load-style modules as packet ingress logic.
3. Treat match/compare-style modules as the filter core.
4. Treat control-style modules as sequencing/FSM/program flow.
5. Treat action/result-style modules as the observable decision boundary.
6. Use the generated wrapper skeleton and smoke test as the first Python integration point.

