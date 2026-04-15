# `test_bpf_env_packet_loss_counter`

## Purpose

Verify that the packet-loss counter in the RTL increments when `bpf_packet_loss` is asserted and can be cleared through MMAP.

## RTL Behavior Under Test

The counter lives at:

- `0x1012` = `BPF_PACKET_LOSS_COUNTER_ADDR`

The RTL behavior is:

- write to `0x1012` clears the counter
- each cycle with `bpf_packet_loss=1` increments the counter by 1

## Program Under Test

```text
ret #1
```

The BPF program is intentionally trivial because this test is focused on the MMAP counter logic, not filter behavior.

## What It Verifies

- MMAP write-clear behavior for the packet-loss counter
- MMAP readback behavior for the packet-loss counter
- `bpf_packet_loss` increments the counter once per asserted cycle
- the BPF engine can still run normally afterward

## Expected Result

- counter reads `0` after clear
- counter reads `3` after `bpf_packet_loss` is held high for 3 cycles
- the program still returns and accepts

## Notes About FSM

This is not controlled by a dedicated packet-loss FSM.

The counter is implemented as simple sequential logic in `bpf_npu.v`, separate from the BPF instruction FSM:

- the BPF execution FSM is in `bpf_control.v`
- the packet-loss counter increment is in `bpf_npu.v`
