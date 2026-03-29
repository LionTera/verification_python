# `test_bpf_env_long_program_with_packet_loss`

## Purpose

Provide a learning-oriented test that combines:

- a longer multi-step BPF program
- packet-header field inspection
- packet-loss injection while the DUT is active

This is meant to help you see both normal packet processing and the packet-loss counter behavior in the same waveform.

## Packet Under Test

```text
Ethernet Header (14 bytes)
  dst_mac    = aa:bb:cc:dd:ee:ff
  src_mac    = 11:22:33:44:55:66
  eth_type   = 0x0800  (IPv4)

IPv4 Header (20 bytes)
  version    = 4
  ihl        = 20 bytes
  total_len  = 44 bytes
  ttl        = 64
  protocol   = 6       (TCP)
  src_ip     = 10.1.2.3
  dst_ip     = 192.0.2.99

TCP Header (20 bytes)
  src_port   = 0x1234
  dst_port   = 0x5678
  seq_num    = 0x01020304
  ack_num    = 0xa1b2c3d4
  flags      = SYN,ACK
  payload    = de ad be ef
```

## Program Under Test

The test first probes the RTL to discover offsets for:

- IPv4 protocol byte
- TCP source-port low byte
- TCP destination-port low byte
- TCP sequence-number low byte
- TCP acknowledgment-number low byte
- TCP payload low byte

Then it builds a longer linear filter:

```text
ldb [protocol_offset]
jeq #0x06, jt 1, jf 0
ret #0
ldb [src_port_low_offset]
jeq #0x34, jt 1, jf 0
ret #0
ldb [dst_port_low_offset]
jeq #0x78, jt 1, jf 0
ret #0
ldb [seq_low_offset]
jeq #0x04, jt 1, jf 0
ret #0
ldb [ack_low_offset]
jeq #0xd4, jt 1, jf 0
ret #0
ldb [payload_low_offset]
jeq #0xef, jt 1, jf 0
ret #0
ldb [dst_port_low_offset]
jeq #0x78, jt 1, jf 0
ret #0
ret #0x5a
```

## Packet-Loss Injection

After `bpf_start`, the test waits until `bpf_active=1`, then:

- asserts `bpf_packet_loss`
- holds it high for `5` cycles
- deasserts it

Expected packet-loss counter result:

```text
5
```

## What It Verifies

- longer linear classic-BPF execution
- repeated packet field loads during one run
- active-time packet-loss injection
- packet-loss MMAP counter behavior during real execution
- correlation between packet load, execution, and counter activity in one waveform

## Expected Result

- `returned == True`
- `accepted == True`
- `ret_value == 0x5A`
- packet-loss counter reads back `5`

## How To Run

```bash
BPF_WAVEFORM=1 pytest -s tests/integration/test_bpf_env_long_program_with_packet_loss.py
```

Open:

```bash
gtkwave reports/test_bpf_env_long_program_with_packet_loss.verilator1.vcd
```

## Recommended Signals

- `clk`
- `reset`
- `bpf_start`
- `bpf_active`
- `bpf_return`
- `bpf_accept`
- `bpf_ret_value`
- `bpf_packet_loss`
- `bpf_packet_len`
- `bpf_pram_waddr`
- `bpf_pram_wdata`
- `bpf_pram_wr`
- `bpf_pram_raddr`
- `bpf_pram_rdata`
- `bpf_mmap_addr`
- `bpf_mmap_wdata`
- `bpf_mmap_wr`
- `bpf_mmap_rd`
- `bpf_mmap_rdata`
- `bpf_mmap_ack`

If internal signals are visible, also add:

- `packet_loss_counter`
- `accept_counter`
- `reject_counter`
- `bpf_state`
- `bpf_state_str`

## How To Read The Waveform

1. Watch `bpf_pram_wr` to see the packet loaded into PRAM.
2. Watch `bpf_mmap_wr` to see the longer BPF program written into IRAM/MMAP.
3. Find the `bpf_start` pulse.
4. Once `bpf_active=1`, find the `bpf_packet_loss` high window.
5. If internal signals are present, confirm `packet_loss_counter` increments during those 5 cycles.
6. Follow the rest of execution until `bpf_return=1`.
7. Confirm the final result is accept with `ret_value=0x5A`.
