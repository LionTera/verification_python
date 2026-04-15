# `test_bpf_env_ingress_drop_model`

## Purpose

Model a more realistic ingress decision before packets are handed to the BPF engine.

This test does **not** claim that `bpf_env` itself validates Ethernet CRC or destination MAC. Instead, it adds a testbench-side ingress model that decides:

- whether a frame is valid enough to enter BPF
- or whether it should be dropped and counted as packet loss

## Ingress Policy

The ingress model checks:

- Ethernet frame length
- Ethernet FCS / CRC
- destination MAC address
- EtherType

If a frame passes ingress:

- the frame payload without FCS is loaded into PRAM
- the BPF program is started

If a frame fails ingress:

- `bpf_packet_loss` is asserted for one cycle
- the packet-loss counter increments
- BPF execution is not started for that frame

## Traffic Sequence

1. Good TCP frame to accepted destination port
2. TCP frame with bad CRC
3. TCP frame with wrong destination MAC
4. TCP frame with unsupported EtherType
5. Too-short frame
6. Good TCP frame to rejected destination port
7. Good UDP frame

Expected final totals:

- accept counter = `1`
- reject counter = `2`
- packet-loss counter = `4`

## Why This Test Matters

This is closer to a real system boundary:

- some frames are allowed into BPF and counted as accept/reject
- some frames are dropped before BPF and counted as packet loss

That lets you distinguish:

- BPF decision logic
- ingress drop policy
- packet-loss accounting

## How To Run

```bash
pytest -s tests/integration/test_bpf_env_ingress_drop_model.py --bpf-reports --bpf-waveform
```

Open:

```bash
gtkwave reports/test_bpf_env_ingress_drop_model.verilator1.vcd
```

Also inspect:

- `reports/bpf_ingress_drop_model.md`
- `reports/bpf_ingress_drop_model.csv`

## Recommended Signals

- `tb_cycle_counter`
- `clk`
- `bpf_packet_loss`
- `packet_loss_counter`
- `bpf_start`
- `bpf_active`
- `bpf_return`
- `bpf_accept`
- `accept_counter`
- `reject_counter`
- `bpf_pram_wr`
- `bpf_pram_waddr`
- `bpf_pram_wdata`

## How To Read It

For dropped frames:

- `bpf_packet_loss` pulses
- `packet_loss_counter` increments
- there is no `bpf_start` pulse for that frame

For accepted ingress frames:

- `bpf_pram_wr` shows the packet loading into PRAM
- `bpf_start` pulses
- `bpf_return` eventually pulses
- `bpf_accept` reflects the BPF result

So you can now separate:

- frame dropped before BPF
- frame processed and rejected by BPF
- frame processed and accepted by BPF
