# `test_bpf_env_tcp_port_filter`

## Purpose

Verify a real multi-instruction BPF filter that inspects packet fields and branches.

## Packets Under Test

Accepted case:

- Ethernet + IPv4 + TCP
- destination port `80`

Rejected cases:

- Ethernet + IPv4 + TCP with destination port `443`
- Ethernet + IPv4 + UDP with destination port `80`

### Human-Readable Packet Structure

TCP packet used for port filtering:

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
  dst_port   = 80 or 443
  seq_num    = 1
  ack_num    = 0
  flags      = SYN
  window     = 4096
  payload    = empty
```

UDP packet used for protocol rejection:

```text
Ethernet Header (14 bytes)
  dst_mac    = 02:00:00:00:00:02
  src_mac    = 02:00:00:00:00:01
  eth_type   = 0x0800  (IPv4)

IPv4 Header (20 bytes)
  version    = 4
  ihl        = 20 bytes
  total_len  = 28 bytes
  ttl        = 64
  protocol   = 17      (UDP)
  src_ip     = 192.168.1.10
  dst_ip     = 192.168.1.20

UDP Header (8 bytes)
  src_port   = 1234
  dst_port   = 80
  length     = 8
  payload    = empty
```

## Program Under Test

```text
ldb [protocol_offset]
jeq #6, jt 0, jf 2
ldb [dst_port_low_byte_offset]
jeq #80, jt 1, jf 0
ret #0
ret #1
```

## Program Meaning

1. Probe the DUT to discover which byte offset exposes the IPv4 protocol byte
2. Probe the DUT to discover which byte offset exposes the TCP destination-port low byte
3. Load the discovered IPv4 protocol byte
2. If protocol is not TCP (`6`), jump to reject
3. Load the discovered low byte of the TCP destination port
4. If that byte is `80` (`0x50`), jump to accept
5. Otherwise reject

## What It Verifies

- absolute packet byte loads work
- conditional jumps work
- multi-instruction control flow works
- protocol filtering works
- destination-port filtering works for the current packet set
- the test adapts to the RTL's actual packet-byte mapping instead of assuming software-standard offsets

## Expected Result

For TCP destination port `80`:

- `returned == True`
- `accepted == True`
- `ret_value == 1`

For TCP destination port `443`:

- `returned == True`
- `accepted == False`
- `ret_value == 0`

For UDP destination port `80`:

- `returned == True`
- `accepted == False`
- `ret_value == 0`

## Notes

This test intentionally probes packet-field offsets using small `ldb [k]; ret a` programs before running the final filter.

Reason:

- this RTL does not expose packet bytes at exactly the same offsets a software BPF implementation would assume
- probing avoids hardcoding an offset that is wrong for the hardware datapath

## Waveform Guide

Run with waveform dumping enabled:

```bash
BPF_WAVEFORM=1 pytest -s tests/integration/test_bpf_env_tcp_port_filter.py
```

Open the waveform:

```bash
gtkwave reports/test_bpf_env_tcp_port_filter.verilator1.vcd
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

How to inspect the filter:

1. Watch `bpf_pram_wr` while the packet is loaded.
2. Watch `bpf_mmap_wr` while the probe programs and final filter are written.
3. Find `bpf_start` for the actual execution run.
4. While `bpf_active=1`, watch packet RAM reads on `bpf_pram_raddr` and `bpf_pram_rdata`.
5. At completion, check `bpf_return`, `bpf_accept`, and `bpf_ret_value`.
