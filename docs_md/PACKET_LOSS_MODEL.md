# Packet Loss Model

## Purpose

This note explains how packet loss is currently generated in the BPF verification environment.

There are now two levels of packet-loss modeling:

1. direct packet-loss injection
2. ingress-style frame drop modeling

They serve different verification goals.

## 1. Direct Packet-Loss Injection

This is the original and simplest model.

The testbench drives the DUT input:

- `bpf_packet_loss`

In Python, this is done through:

```python
tb.set_packet_loss(1)
tb.step(n)
tb.set_packet_loss(0)
tb.step(1)
```

Meaning:

- for `n` clock cycles, the DUT sees `bpf_packet_loss = 1`
- the RTL packet-loss counter increments once per asserted cycle

This model is useful when you want to verify:

- the packet-loss counter increments correctly
- MMAP clear/readback works
- packet-loss pulses line up with waveform cycles

What it does **not** model:

- why the packet was lost
- Ethernet validity checking
- MAC filtering
- CRC/FCS checking
- ingress admission policy

So this is a pure accounting/input-stimulus model.

## 2. Ingress Drop Model

This is the newer, more realistic model.

It is implemented in:

- [`network_ingress.py`](C:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/network_ingress.py)

Instead of directly deciding to pulse `bpf_packet_loss` with no reason, the testbench first evaluates an Ethernet frame and decides whether it should enter BPF at all.

Current ingress checks:

- frame too short
- bad Ethernet CRC/FCS
- wrong destination MAC
- unsupported EtherType

If the frame passes ingress:

- the frame payload without FCS is loaded into PRAM
- the BPF engine is started

If the frame fails ingress:

- `bpf_packet_loss` is asserted for one cycle
- the packet-loss counter increments
- BPF is **not** started for that frame

So this model separates:

- dropped before BPF
- processed and rejected by BPF
- processed and accepted by BPF

## Current RTL Meaning

The packet-loss counter is still implemented in RTL as a simple counter on the `bpf_packet_loss` input.

In [`bpf_npu.v`](C:/Users/Lionn%20Bruckstein/Documents/verification_python/bpf_test/u2u_v401/tf_bpf/rtl/bpf_npu.v):

- MMAP write to `0x1012` clears the counter
- each cycle with `bpf_packet_loss = 1` increments the counter by `1`

So the RTL itself does not know *why* a packet was lost.

The reason is currently modeled in the testbench.

## When To Use Each Model

Use direct packet-loss injection when:

- you want a small focused counter test
- you want exact cycle-by-cycle control
- you do not care about ingress realism

Use the ingress drop model when:

- you want more system-like behavior
- you want drop reasons such as bad CRC or wrong destination MAC
- you want to distinguish ingress drops from BPF rejects

## Tests That Use These Models

Direct packet-loss injection:

- [`test_bpf_env_packet_loss_counter.py`](C:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/integration/test_bpf_env_packet_loss_counter.py)
- [`test_bpf_env_packet_loss_long_run.py`](C:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/integration/test_bpf_env_packet_loss_long_run.py)
- [`test_bpf_env_long_program_with_packet_loss.py`](C:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/integration/test_bpf_env_long_program_with_packet_loss.py)
- [`test_bpf_env_random_traffic_5000_loss.py`](C:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/integration/test_bpf_env_random_traffic_5000_loss.py)

Ingress drop model:

- [`test_bpf_env_ingress_drop_model.py`](C:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/integration/test_bpf_env_ingress_drop_model.py)

## Waveform Guidance

To inspect packet loss in GTKWave, start with:

- `tb_cycle_counter`
- `clk`
- `bpf_packet_loss`
- `packet_loss_counter`
- `bpf_start`
- `bpf_return`
- `bpf_accept`
- `accept_counter`
- `reject_counter`

Interpretation:

- `bpf_packet_loss` high with no `bpf_start` nearby usually means ingress-style drop
- `bpf_start` followed by `bpf_return` means the packet entered BPF
- `bpf_accept` shows whether BPF accepted or rejected that packet

## Summary

The system now has:

- a low-level packet-loss pulse model for counter verification
- a higher-level ingress-drop model for more realistic system behavior

The counter behavior in RTL is unchanged.

What changed is that the testbench can now generate packet loss either:

- directly
- or as a consequence of a modeled ingress decision
