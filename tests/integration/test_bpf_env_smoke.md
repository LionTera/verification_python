# `test_bpf_env_smoke`

## Purpose

Verify the minimal Linux/Verilator/PyMTL bring-up path for `bpf_env`.

## Packet Under Test

- Ethernet frame only
- intentionally short
- enough to exercise packet loading and DUT execution

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
