# `test_bpf_env_tcp`

## Purpose

Verify that a structured TCP packet can be loaded into packet RAM and processed by the DUT.

## Packet Under Test

- Ethernet + IPv4 + TCP SYN packet
- source port `1234`
- destination port `80`

### Human-Readable Packet Structure

```text
Ethernet Header (14 bytes)
  dst_mac    = 02:00:00:00:00:02
  src_mac    = 02:00:00:00:00:01
  eth_type   = 0x0800  (IPv4)

IPv4 Header (20 bytes)
  version    = 4
  ihl        = 20 bytes
  total_len  = 40 bytes
  ttl        = 64
  protocol   = 6       (TCP)
  src_ip     = 192.168.1.10
  dst_ip     = 192.168.1.20

TCP Header (20 bytes)
  src_port   = 1234
  dst_port   = 80
  seq_num    = 1
  ack_num    = 0
  flags      = SYN
  window     = 4096
  payload    = empty
```

## Program Under Test

```text
ret #1
```

## What It Verifies

- packet construction helper is valid enough for the DUT
- packet RAM loading works for a normal L2/L3/L4 packet
- the DUT can process a realistic TCP packet

## Expected Result

- `returned == True`
- `accepted == True`
- packet length is at least the minimum Ethernet+IPv4+TCP header size

## Waveform Guide

Run with waveform dumping enabled:

```bash
BPF_WAVEFORM=1 pytest -s tests/integration/test_bpf_env_tcp.py
```

Open the waveform:

```bash
gtkwave reports/test_bpf_env_tcp.verilator1.vcd
```

Recommended signals:

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

How to follow the packet:

1. Packet words are written into packet RAM with `bpf_pram_wr`.
2. The BPF program is written through `bpf_mmap_wr`.
3. `bpf_start` marks the beginning of execution.
4. While `bpf_active=1`, the DUT is processing the packet.
5. `bpf_return`, `bpf_accept`, and `bpf_ret_value` show the outcome.
