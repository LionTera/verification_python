# `test_bpf_env_packet_header_probe`

## Purpose

Provide a learning-oriented test that makes the packet header easy to correlate across:

- the Python packet builder
- the generated markdown report
- the PRAM write activity in the waveform

## Packet Under Test

This test uses a TCP packet with deliberately distinctive field values so they are easy to recognize in memory and in GTKWave.

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

```text
ret #1
```

The BPF program is intentionally trivial. The point of this test is packet visibility, not BPF decision logic.

## What It Verifies

- the packet is loaded into packet RAM correctly
- the packet memory words are visible in the generated report
- the waveform contains enough top-level PRAM/MMAP activity to follow the transaction
- the DUT still executes to completion under a known-good program

## Expected Result

- `returned == True`
- `accepted == True`
- `ret_value == 1`
- a CSV trace is generated
- a markdown report is generated
- when waveform dumping is enabled, a VCD is generated

## How To Use This Test For Learning

Run:

```bash
BPF_WAVEFORM=1 pytest -s tests/integration/test_bpf_env_packet_header_probe.py
```

Open:

```bash
gtkwave reports/test_bpf_env_packet_header_probe.verilator1.vcd
```

Also inspect:

- `reports/bpf_packet_header_probe.md`
- `reports/bpf_packet_header_probe.csv`

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

1. Start with `bpf_pram_wr`, `bpf_pram_waddr`, and `bpf_pram_wdata`.
2. Compare each write against the `Packet Memory Words` table in `reports/bpf_packet_header_probe.md`.
3. Confirm the early writes correspond to:
   - destination MAC
   - source MAC
   - EtherType
   - IPv4 header
   - TCP header
   - payload
4. Then find the `bpf_mmap_wr` pulses that load the `ret #1` instruction.
5. Find the `bpf_start` pulse.
6. Follow execution until `bpf_return` goes high.
7. Confirm the final verdict with `bpf_accept=1` and `bpf_ret_value=1`.

## Most Useful Correlation

The main value of this test is:

- the report tells you which 4-byte packet chunk should be written at each PRAM address
- the waveform shows when those writes actually happen

That makes it the easiest test in the current suite for learning how packet data reaches the DUT.
