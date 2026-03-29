# `test_bpf_env_packet_header_walk`

## Purpose

Provide a learning-oriented test with a real multi-step BPF program that inspects several packet-header fields before accepting the packet.

## Packet Under Test

This test uses a TCP packet with distinctive values so the packet can be recognized in both the report and the waveform.

### Human-Readable Packet Structure

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
  window     = 4096
  payload    = de ad be ef
```

## Program Under Test

The test first probes the RTL to discover which packet byte offsets are visible for:

- IPv4 protocol
- TCP destination-port low byte
- TCP sequence-number low byte
- TCP acknowledgment-number low byte
- TCP first payload byte

Then it builds and runs this final program:

```text
ldb [protocol_offset]
jeq #6, jt 0, jf 8
ldb [dst_port_low_offset]
jeq #0x78, jt 0, jf 6
ldb [seq_low_offset]
jeq #0x04, jt 0, jf 4
ldb [ack_low_offset]
jeq #0xd4, jt 0, jf 2
ldb [payload_first_offset]
jeq #0xde, jt 1, jf 0
ret #0
ret #0xa5
```

## What It Verifies

- multi-instruction classic-BPF control flow
- multiple header field loads in one program
- conditional branching on several packet fields
- correlation between packet contents, probe offsets, and final execution
- waveform visibility for both packet loading and instruction execution

## Expected Result

- `returned == True`
- `accepted == True`
- `ret_value == 0xA5`
- trace, report, and waveform artifacts are generated when enabled

## How To Use This Test For Learning

Run:

```bash
BPF_WAVEFORM=1 pytest -s tests/integration/test_bpf_env_packet_header_walk.py
```

Open:

```bash
gtkwave reports/test_bpf_env_packet_header_walk.verilator1.vcd
```

Also inspect:

- `reports/bpf_packet_header_walk.md`
- `reports/bpf_packet_header_walk.csv`

## Recommended Signals

- `clk`
- `reset`
- `bpf_start`
- `bpf_active`
- `bpf_return`
- `bpf_accept`
- `bpf_ret_value`
- `bpf_packet_len`
- `bpf_pram_waddr`
- `bpf_pram_wdata`
- `bpf_pram_wr`
- `bpf_pram_raddr`
- `bpf_pram_rdata`
- `bpf_mmap_addr`
- `bpf_mmap_wdata`
- `bpf_mmap_wr`
- `bpf_mmap_ack`

## How To Read The Waveform

1. Use the report's `Packet Memory Words` table to identify which PRAM writes correspond to Ethernet, IPv4, and TCP fields.
2. Watch `bpf_mmap_wr`, `bpf_mmap_addr`, and `bpf_mmap_wdata` to see the multi-step BPF program being written.
3. Find the `bpf_start` pulse.
4. While `bpf_active=1`, watch `bpf_pram_raddr` and `bpf_pram_rdata` to see the packet reads used by the program.
5. Finish at `bpf_return`, `bpf_accept`, and `bpf_ret_value`.
