# `test_bpf_env_smoke`

## Purpose

Verify the minimal Linux/Verilator/PyMTL bring-up path for `bpf_env`.

## Packet Under Test

- Ethernet frame only
- intentionally short
- enough to exercise packet loading and DUT execution

### Human-Readable Packet Structure

```text
Ethernet Header (14 bytes)
  dst_mac    = 00:11:22:33:44:55
  src_mac    = 66:77:88:99:aa:bb
  eth_type   = 0x0800  (IPv4)

Payload
  not present

Note:
  This packet is intentionally shorter than a full IPv4 header.
  The test is only checking basic DUT bring-up and execution.
```

## Program Under Test

```text
ret #1
```

## What It Verifies

- DUT builds successfully
- RTL imports through Verilator
- a one-instruction BPF program can be loaded
- the DUT runs to completion
- the DUT returns a non-zero accept value
- the CSV execution trace file is created

## Expected Result

- `returned == True`
- `accepted == True`
- `ret_value == 1`

## Optional Waveform

If you want a VCD for this test, build the DUT with:

```python
build_bpf_env(waveform="reports/bpf_env_smoke")
```

This produces a Verilator VCD with the requested base filename.

## Waveform Guide

Recommended run command:

```bash
BPF_WAVEFORM=1 pytest -s tests/integration/test_bpf_env_smoke.py
```

Open the waveform:

```bash
gtkwave reports/test_bpf_env_smoke.verilator1.vcd
```

Recommended signals:

- `clk`
- `reset`
- `bpf_start`
- `bpf_active`
- `bpf_return`
- `bpf_accept`
- `bpf_ret_value`
- `bpf_pram_waddr`
- `bpf_pram_wdata`
- `bpf_pram_wr`
- `bpf_mmap_addr`
- `bpf_mmap_wdata`
- `bpf_mmap_wr`

How to read it:

1. Watch `bpf_pram_wr` for packet RAM writes.
2. Watch `bpf_mmap_wr` for BPF program writes.
3. Find the `bpf_start` pulse.
4. Confirm the DUT completes with `bpf_return=1` and `bpf_accept=1`.
