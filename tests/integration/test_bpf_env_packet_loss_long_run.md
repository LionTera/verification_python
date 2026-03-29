# `test_bpf_env_packet_loss_long_run`

## Purpose

Exercise the DUT over multiple iterations while injecting packet-loss cycles, so the packet-loss counter can be checked in a longer and more realistic run.

## Packet Under Test

This test reuses one TCP packet for all iterations.

### Human-Readable Packet Structure

```text
Ethernet Header (14 bytes)
  dst_mac    = 02:00:00:00:00:02
  src_mac    = 02:00:00:00:00:01
  eth_type   = 0x0800  (IPv4)

IPv4 Header (20 bytes)
  version    = 4
  ihl        = 20 bytes
  total_len  = 48 bytes
  ttl        = 64
  protocol   = 6       (TCP)
  src_ip     = 192.168.1.10
  dst_ip     = 192.168.1.20

TCP Header (20 bytes)
  src_port   = 0x1234
  dst_port   = 0x5678
  seq_num    = 0x01020304
  ack_num    = 0xa1b2c3d4
  payload    = de ad be ef ca fe ba be
```

## Program Under Test

```text
ret #1
```

The BPF program always accepts. The point of this test is not BPF decision logic. It is long-run counter behavior.

## Loss Injection Schedule

```text
[0, 2, 1, 0, 4, 3]
```

Meaning:

- iteration 0: inject 0 loss cycles
- iteration 1: inject 2 loss cycles
- iteration 2: inject 1 loss cycle
- iteration 3: inject 0 loss cycles
- iteration 4: inject 4 loss cycles
- iteration 5: inject 3 loss cycles

Total expected packet-loss count:

```text
0 + 2 + 1 + 0 + 4 + 3 = 10
```

## What It Verifies

- repeated DUT execution over multiple iterations
- accept counter increments once per completed packet
- reject counter stays at zero
- packet-loss counter increments once per cycle with `bpf_packet_loss=1`
- MMAP clear/readback behavior remains correct in a longer run

## Expected Result

- accept counter = `6`
- reject counter = `0`
- packet-loss counter = `10`

## How To Run

```bash
BPF_WAVEFORM=1 pytest -s tests/integration/test_bpf_env_packet_loss_long_run.py
```

Open the waveform:

```bash
gtkwave reports/test_bpf_env_packet_loss_long_run.verilator1.vcd
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
- `bpf_mmap_addr`
- `bpf_mmap_wdata`
- `bpf_mmap_wr`
- `bpf_mmap_rd`
- `bpf_mmap_rdata`
- `bpf_mmap_ack`
- `bpf_pram_waddr`
- `bpf_pram_wdata`
- `bpf_pram_wr`

If internal RTL signals are visible, also add:

- `accept_counter`
- `reject_counter`
- `packet_loss_counter`
- `bpf_state`
- `bpf_state_str`

## How To Read The Waveform

1. Watch the early `bpf_pram_wr` pulses for packet load.
2. Watch `bpf_mmap_wr` when the trivial program and control registers are written.
3. For each iteration, find the `bpf_packet_loss` high pulse before `bpf_start`.
4. If internal signals are present, confirm `packet_loss_counter` increments during those pulses.
5. Then follow `bpf_start`, `bpf_active`, `bpf_return`, and `bpf_accept` for each packet execution.
6. At the end, compare MMAP readback values with the expected final counters.
