# `test_bpf_env_random_traffic_5000_loss.py` Explained

This note explains the structure and flow of:

- `tests/integration/test_bpf_env_random_traffic_5000_loss.py`

It is intended as a code-reading guide.

## Big Picture

This test is a long BPF stress test.

It does four main things:

1. discovers the real packet byte offsets the DUT sees
2. builds a small BPF filter program from those offsets
3. generates a large deterministic traffic stream
4. injects deterministic packet-loss events and checks counters/results against a software-side expected model

Important clarification:

- this is not an ingress-drop test
- here, packet loss means the testbench pulses `bpf_packet_loss`
- the packet still gets loaded and still runs through the BPF program

## Imports And Constants

At the top of the file, the test imports:

- MMAP counter addresses and the shared Python TB from `bpf_python_tb.py`
- DUT build helpers from `dut_builders.py`
- packet builders from `packets.py`

Main constants:

- default packet count: `5000`
- default loss percent: `5`
- default RNG seed: `0x5EED5EED`

These are overridable through the existing pytest/environment config wiring.

## Function By Function

### `_get_positive_int_env(name, default)`

Purpose:

- read a numeric config value from the environment
- fall back to a default if it is missing
- reject non-positive values

So this is a safe config parser.

### `load_stress_config()`

Purpose:

- build one config dictionary for the whole test

It calculates:

- `packet_count`
- `loss_percent`
- `loss_count`
- `rng_seed`
- `progress_interval`

Important detail:

- `loss_count = packet_count * loss_percent // 100`

So if you run 1000 packets with 10% loss, the test schedules exactly 100 loss events.

### `_probe_program(packet, program, trace_name, label=...)`

Purpose:

- run a tiny temporary BPF program on one packet and return the DUT result

What it does:

- builds a fresh DUT
- creates a temporary/shared TB
- loads one packet
- loads the temporary probe program
- starts execution
- runs until return
- returns the result

This helper is used only during offset discovery.

### `discover_offset(packet_a, expected_a, packet_b, expected_b, candidate_offsets, name=...)`

Purpose:

- find the actual packet byte offset the DUT should use for a field

How:

- for each candidate offset, build a 2-instruction probe:
  - `ldb [offset]`
  - `ret a`
- run that probe on packet A and packet B
- compare returned byte values against expected values
- if both match, that offset is selected

Examples:

- for IPv4 protocol, packet A should return `0x06` and packet B should return `0x11`
- for TCP dst-port low byte, packet A should return `0x78` and packet B should return `0xBB`

Why this exists:

- the test avoids hardcoding offsets until it proves what the RTL actually sees

### `make_tcp_dst_filter(protocol_offset, dst_port_low_offset, accepted_low_byte=...)`

Purpose:

- build the actual BPF program used in the stress test

Program logic:

1. load IPv4 protocol byte
2. compare to `0x06` (TCP)
3. if not TCP, reject
4. load TCP destination-port low byte
5. compare to the accepted low byte, `0x78`
6. if match, accept
7. else reject

So this filter accepts:

- TCP packets with destination port low byte `0x78`

And rejects:

- TCP packets with destination port low byte `0xBB`
- UDP packets

### `generate_packet_stream(count, seed=...)`

Purpose:

- create the actual packet list for the run

How it works:

- create `rng = random.Random(seed)`
- loop over `count`
- for each packet, choose a random class with `selector = rng.random()`

Traffic distribution:

- `< 0.45`: TCP accept packet
- `< 0.85`: TCP reject packet
- otherwise: UDP reject packet

So the approximate mix is:

- 45% TCP packets that should pass
- 40% TCP packets that should fail
- 15% UDP packets that should fail

Each packet is made unique by varying:

- source IP
- sequence number
- ack number
- source port
- payload

Returned per-item fields:

- `index`
- `kind`
- `expected_accept`
- `packet`

### `append_random_traffic_report(...)`

Purpose:

- append the test-level summary into the Markdown report

What it writes:

- packet count / loss percent / seed
- discovered offsets
- filter program
- golden loss-event table
- packet stream golden model table

This is where the report becomes a whole-test summary, not just the final packet snapshot.

## Main Test Flow

### `test_bpf_env_random_traffic_5000_loss()`

Here is the flow in plain English.

### 1. Check Verilator

The test skips if Verilator is unavailable.

### 2. Load config

The test reads packet count, loss count, seed, and progress interval.

### 3. Build three probe packets

It creates:

- TCP packet that should be accepted
- TCP packet that should be rejected
- UDP packet

These are only for offset discovery.

### 4. Discover protocol offset

The test probes candidate offsets `20..27` until it finds the one returning:

- `0x06` for TCP
- `0x11` for UDP

### 5. Discover destination-port low-byte offset

The test probes candidate offsets `34..41` until it finds the one returning:

- `0x78` for accept TCP
- `0xBB` for reject TCP

### 6. Build the actual filter program

Now the test has a real BPF program tailored to the observed RTL-visible offsets.

### 7. Generate the traffic stream

It creates `packet_count` packets deterministically from the seed.

### 8. Generate deterministic loss indices

It chooses exactly `loss_count` packet indices to receive a loss pulse.

Important detail:

- it uses a second deterministic RNG:
  - `random.Random(seed ^ 0xA5A5A5A5)`

So packet generation and loss scheduling are both deterministic, but separated.

### 9. Build DUT and TB

The test creates the DUT and TB and prints run information.

### 10. Load the program once

The filter program is loaded into IRAM once before the packet loop.

### 11. Clear counters

The test clears:

- accept counter
- reject counter
- packet-loss counter

### 12. Initialize expected-model variables

The test initializes:

- `accept_expected`
- `reject_expected`
- `loss_expected`
- `loss_events`
- `traffic_history`

This is the software-side running model.

### 13. Main packet loop

For each packet:

- get packet index, bytes, expected accept
- load packet into PRAM with `tb.load_packet(packet)`

If that packet index is in `loss_indices`:

- record current cycle as `loss_assert_cycle`
- pulse `bpf_packet_loss` for one cycle
- increment expected loss count
- add a loss event to the golden list

Then:

- record `start_cycle`
- configure start address
- pulse `bpf_start`
- run until return

Then assert:

- DUT returned
- DUT accept/reject matches `expected_accept`

Then update expected counters:

- if packet should pass, increment `accept_expected`
- else increment `reject_expected`

Then store a history entry for the report.

### 14. Periodic counter check and progress print

The test does not read counters every packet.

It checks when:

- the current packet had a loss event
- or this is the final packet
- or the progress interval is reached

When it checks:

- read accept/reject/loss counters from MMAP
- compare against expected software-side counts
- print progress line

That is why progress lines appear only occasionally.

### 15. Drain a few extra cycles if needed

The test gives the DUT a few cleanup cycles until return/active settle.

### 16. Final counter check

At the end, it reads final counters and compares them to:

- expected accept total
- expected reject total
- configured loss count

### 17. Append test-level report

If report generation is enabled, it appends the random-traffic summary and golden-model tables.

## What This Test Verifies

This test verifies several things at once:

- the DUT can process a long packet stream
- the BPF program behaves correctly on TCP accept / TCP reject / UDP reject
- the packet-loss counter increments exactly for the chosen loss events
- MMAP readback matches the software-side expected model
- the whole run is deterministic given the same seed and parameters

## What “Loss” Means In This Test

This is important.

In this test, “loss” does not mean:

- packet dropped before BPF because of CRC/MAC/etc.

Instead it means:

- the testbench pulses `bpf_packet_loss` for selected packet indices

The packet still gets loaded and still runs through the BPF program.

So this test is:

- a long stress test for filter behavior and counter behavior

not:

- a pure ingress-drop realism test

For ingress-style loss reasoning, the closer test is:

- `test_bpf_env_ingress_drop_model.py`

## Why The Code Is Structured This Way

The structure is deliberate:

- offset probe first
  - avoids hardcoding assumptions about RTL-visible byte offsets
- deterministic generator
  - allows repeatable debugging
- separate loss schedule
  - gives independent control of traffic content and loss injection
- periodic counter reads
  - reduces overhead while still checking correctness
- report append step
  - keeps the main TB generic and lets each scenario add its own summary

## Mental Model For Reading The File

The easiest mental model is:

- config layer:
  - `load_stress_config`
- offset-discovery layer:
  - `_probe_program`, `discover_offset`
- program-construction layer:
  - `make_tcp_dst_filter`
- traffic-generation layer:
  - `generate_packet_stream`
- golden-model/report layer:
  - `loss_indices`, `loss_events`, `traffic_history`, `append_random_traffic_report`
- execution loop:
  - load packet, maybe inject loss, run DUT, update expected counters, compare

## Short Summary

This file is a deterministic long-run BPF stress test.

It:

- discovers packet offsets
- builds a real filter
- generates many packets
- injects deterministic loss pulses
- checks accept/reject/loss counters against a software-side expected model
- writes a detailed report for later debug
