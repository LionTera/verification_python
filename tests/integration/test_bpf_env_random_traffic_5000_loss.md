# `test_bpf_env_random_traffic_5000_loss`

## Purpose

Run a large deterministic traffic stream through one DUT instance:

- `5000` packets total
- exact random seed for reproducibility
- exactly `250` one-cycle packet-loss injections
- mixed accepted and rejected traffic

This is a stress-style learning test. The main goal is to correlate:

- packet writes into PRAM
- BPF start/return behavior
- `bpf_packet_loss` pulses
- `packet_loss_counter` updates
- golden-model expectations saved in the report

## Traffic Model

The test generates packets with a deterministic RNG seed:

- TCP packets with destination-port low byte `0x78` -> expected accept
- TCP packets with destination-port low byte `0xBB` -> expected reject
- UDP packets -> expected reject

Each packet also varies fields such as:

- source IP
- source port
- sequence number
- acknowledgment number
- payload

So the stream is not one repeated packet. It is a reproducible packet sequence.

## Packet-Loss Model

The test randomly selects exactly `250` packet indices out of `5000`.

For each selected packet:

- `bpf_packet_loss` is asserted for `1` cycle
- then deasserted

Expected packet-loss counter result:

```text
250
```

Because the RTL counter increments once per cycle while `bpf_packet_loss=1`, this test maps one selected packet to one counted loss pulse.

## Filter Program

Like the mixed-traffic test, this test first probes the RTL to discover:

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

- accept only TCP packets whose destination-port low byte is `0x78`
- reject other TCP packets
- reject UDP packets

## Golden Model In The Report

When `BPF_REPORTS=1` is enabled, the report contains:

- final DUT result section
- golden loss-event table:
  - packet index
  - assert cycle
  - release cycle
  - expected loss counter after each pulse
- packet-stream golden-model table for all `5000` packets:
  - packet index
  - packet kind
  - expected accept/reject
  - whether loss was injected
  - loss assert cycle
  - start pulse cycle
  - return cycle
  - expected accept/reject/loss counters after that packet
  - raw packet bytes

This gives you the exact cycle numbers to search in GTKWave.

## How To Run

Main artifacts only:

```bash
BPF_REPORTS=1 BPF_WAVEFORM=1 pytest -s tests/integration/test_bpf_env_random_traffic_5000_loss.py
```

If you also want probe artifacts:

```bash
BPF_REPORTS=1 BPF_WAVEFORM=1 BPF_FULL_ARTIFACTS=1 pytest -s tests/integration/test_bpf_env_random_traffic_5000_loss.py
```

Open:

```bash
gtkwave reports/test_bpf_env_random_traffic_5000_loss.verilator1.vcd
```

Also inspect:

- `reports/bpf_random_traffic_5000_loss.md`
- `reports/bpf_random_traffic_5000_loss.csv`

## Recommended Signals

Top-level behavior:

- `clk`
- `reset`
- `bpf_start`
- `bpf_active`
- `bpf_return`
- `bpf_accept`
- `bpf_ret_value`
- `bpf_packet_loss`
- `bpf_packet_len`

Packet load/write path:

- `bpf_pram_wr`
- `bpf_pram_waddr`
- `bpf_pram_wdata`

Packet read path:

- `bpf_pram_raddr`
- `bpf_pram_rdata`

MMAP / program path:

- `bpf_mmap_wr`
- `bpf_mmap_rd`
- `bpf_mmap_addr`
- `bpf_mmap_wdata`
- `bpf_mmap_rdata`
- `bpf_mmap_ack`

Internal counters and control, if visible:

- `packet_loss_counter`
- `accept_counter`
- `reject_counter`
- `bpf_state`
- `bpf_state_str`
- `bpf_pc`
- `bpf_acc`

## How To Read The Waveform

1. Open the report and locate a row in `Golden Loss Events`.
2. Jump in GTKWave to that `Assert Cycle`.
3. Confirm:
   - `bpf_packet_loss` goes high
   - `packet_loss_counter` increments by one, if visible
4. Then inspect the matching packet’s `Start Pulse Cycle` from the packet-stream table.
5. Around that region, confirm:
   - `bpf_pram_wr` bursts before the packet starts
   - `bpf_start` pulses
   - `bpf_active` goes high
   - `bpf_return` eventually pulses
   - `bpf_accept` matches the report’s expected accept value
6. Compare counter growth over time:
   - `accept_counter`
   - `reject_counter`
   - `packet_loss_counter`

## Practical Note

A waveform for `5000` packets is large. For learning and debugging:

- use the report’s cycle numbers to jump directly to interesting regions
- start with loss-event rows rather than trying to browse the whole waveform sequentially
