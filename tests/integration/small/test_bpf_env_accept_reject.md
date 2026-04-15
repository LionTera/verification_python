# `test_bpf_env_accept_reject`

## Purpose

Verify the simplest accept/reject behavior of the DUT using classic BPF return instructions.

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

## Programs Under Test

Accept path:

```text
ret #1
```

Reject path:

```text
ret #0
```

## What It Verifies

- `RET_K` executes correctly
- non-zero return values map to accept
- zero return values map to reject
- both paths reach `bpf_return`

## Expected Result

For `ret #1`:

- `returned == True`
- `accepted == True`
- `ret_value == 1`

For `ret #0`:

- `returned == True`
- `accepted == False`
- `ret_value == 0`

## Waveform Guide

Run with waveform dumping enabled:

```bash
BPF_WAVEFORM=1 pytest -s tests/integration/test_bpf_env_accept_reject.py
```

Open the VCD:

```bash
gtkwave reports/test_bpf_env_accept_reject.verilator1.vcd
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
- `bpf_mmap_addr`
- `bpf_mmap_wdata`
- `bpf_mmap_wr`
- `bpf_mmap_ack`

How to read it:

1. `bpf_pram_wr` pulses while the packet is loaded into packet RAM.
2. `bpf_mmap_wr` pulses while the BPF program is written.
3. `bpf_start` goes high to begin execution.
4. `bpf_active` stays high while the DUT is processing.
5. `bpf_return` goes high at completion.
6. `bpf_accept` and `bpf_ret_value` show the final result.
