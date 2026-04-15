# `test_bpf_env_mixed_traffic_counters`

## Purpose

Run a mixed sequence of packets through one DUT instance so you can see all three counter classes change over time in one waveform:

- accepted packets
- rejected packets
- packet-loss cycles

## Why This Is A Good Approach

Yes, this is the right approach if your goal is to learn and verify behavior over time.

Instead of checking only one final event, this test gives you a time sequence where:

- some packets are accepted
- some packets are rejected
- some iterations inject `bpf_packet_loss`

That makes the waveform much easier to interpret because the counters and top-level outputs change in a visible pattern.

## Traffic Sequence

The test runs these items in order:

1. TCP packet to accepted destination port, no packet loss
2. TCP packet to rejected destination port, no packet loss
3. UDP packet, no packet loss
4. TCP accepted packet, with 2 packet-loss cycles
5. TCP rejected packet, with 1 packet-loss cycle
6. TCP accepted packet, with 3 packet-loss cycles

Expected final totals:

- accept counter = `3`
- reject counter = `3`
- packet-loss counter = `6`

## Filter Program

The test dynamically probes the RTL to discover:

- IPv4 protocol byte offset
- TCP destination-port low-byte offset

Then it builds this filter:

```text
ldb [protocol_offset]
jeq #6, jt 0, jf 2
ldb [dst_port_low_offset]
jeq #0x78, jt 1, jf 0
ret #0
ret #1
```

Meaning:

- only TCP packets with destination-port low byte `0x78` are accepted
- TCP packets with another destination-port byte are rejected
- UDP packets are rejected

## How To Run

```bash
BPF_WAVEFORM=1 pytest -s tests/integration/test_bpf_env_mixed_traffic_counters.py
```

Open:

```bash
gtkwave reports/test_bpf_env_mixed_traffic_counters.verilator1.vcd
```

Also inspect:

- `reports/bpf_mixed_traffic_counters.md`
- `reports/bpf_mixed_traffic_counters.csv`

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

- `accept_counter`
- `reject_counter`
- `packet_loss_counter`
- `bpf_state`
- `bpf_state_str`

## How To Verify It

1. In the waveform, identify each packet iteration by the packet load followed by `bpf_start`.
2. Watch `bpf_pram_wr`, `bpf_pram_waddr`, and `bpf_pram_wdata` change as each packet is written.
3. Watch `bpf_packet_loss` pulse on the iterations that inject loss.
4. If internal signals are visible, confirm:
   - `accept_counter` increments on accepted packets
   - `reject_counter` increments on rejected packets
   - `packet_loss_counter` increments by the number of asserted loss cycles
5. Compare the console output and report against the waveform after each traffic item.

## What To Expect In The Waveform

You should see a changing pattern, not a single repeated run:

- packet contents change between TCP-accept, TCP-reject, and UDP packets
- `bpf_accept` changes between `1` and `0`
- `bpf_packet_loss` pulses only on selected traffic items
- the counters step upward over time in different categories
