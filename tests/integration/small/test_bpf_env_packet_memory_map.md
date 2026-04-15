# `test_bpf_env_packet_memory_map`

## Purpose

Provide a dedicated memory-map learning test that shows where packet fields land in PRAM and verifies the generated field map against known packet values.

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

```text
ret #1
```

The BPF program is trivial because this test is focused on packet placement in memory, not filter behavior.

## What It Verifies

- the generated field map names the expected Ethernet, IPv4, and TCP fields
- the raw bytes for those fields match the known packet contents
- the packet memory-word table matches the packet bytes written into PRAM
- the DUT still executes successfully after packet load

## How To Run

```bash
BPF_WAVEFORM=1 pytest -s tests/integration/test_bpf_env_packet_memory_map.py
```

Open:

```bash
gtkwave reports/test_bpf_env_packet_memory_map.verilator1.vcd
```

Also inspect:

- `reports/bpf_packet_memory_map.md`
- `reports/bpf_packet_memory_map.csv`

## How To Verify It

1. In the report, read `Packet Field Map`.
2. Confirm each field lists:
   - byte range
   - raw bytes
   - PRAM word address range
3. In the report, read `Packet Memory Words`.
4. In GTKWave, add:
   - `bpf_pram_waddr`
   - `bpf_pram_wdata`
   - `bpf_pram_wr`
5. Compare the PRAM writes in the waveform against the `Packet Memory Words` table.
6. Use the field map to understand which words contain:
   - destination MAC
   - source MAC
   - EtherType
   - IPv4 fields
   - TCP fields
   - payload

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
- `bpf_mmap_addr`
- `bpf_mmap_wdata`
- `bpf_mmap_wr`
