# BPF Program Generator Guide

This document explains how the generated BPF-program flow is built, how packets are created, how the golden model is computed, how register snapshots are captured, and how the profiles progress from short programs to longer mixed-op programs.

## Purpose

The generated-program flow exists to solve a specific problem:

- short one-off tests are useful, but they do not scale well
- long hand-written programs are useful, but they are harder to maintain

So this flow introduces a reusable middle layer:

- packet generator
- program-profile generator
- Python golden model
- one integration test that runs those profiles

Main files:

- [packet_generator.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/packet_generator.py)
- [program_generator.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/program_generator.py)
- [golden_model.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/golden_model.py)
- [test_bpf_env_generated_program_profiles.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/integration/advanced/test_bpf_env_generated_program_profiles.py)

The generator now has two layers:

- request-driven CLI generation through `ProgramRequest`
- named profile presets used by the integration test flow

## High-Level Flow

When you run the generated-program test, the flow is:

1. load one program profile
2. build probe packets for the fields used by that profile
3. discover the DUT-visible offsets for those fields
4. build the final BPF program from those offsets
5. generate deterministic randomized packets
6. evaluate the expected accept/reject result in Python
7. run the DUT on each packet
8. compare DUT results against the golden model
9. record final A/X/PC snapshots
10. write report and waveform artifacts

So the important point is:

- the BPF program is generated after offset discovery
- the golden model is generated before DUT execution

## Packet Creation

Packet creation starts with `PacketSpec`.

`PacketSpec` describes one packet declaratively:

- protocol
- MAC addresses
- IP addresses
- DSCP/ECN
- TTL
- ports
- sequence/ack values
- TCP flags
- payload

`build_packet(spec)` then converts that spec into raw Ethernet + IPv4 + TCP/UDP bytes.

Higher-level traffic generation is handled by:

- `generate_configurable_packet_stream(config)`

That function creates a repeatable packet stream from:

- `unique_packets`
- `protocol_mode`
- `seed`
- `randomize_fields`

## How Randomization Works

Randomization uses a local seeded Python RNG:

```python
rng = random.Random(seed)
```

Only the selected fields are randomized.

Examples:

- `ttl`
- `dscp_ecn`
- `payload_len`
- `payload_bytes`
- `tcp_flags`
- `src_port`
- `seq`
- `ack`

Important rule:

- same seed + same config + same selected field list = same packets

For detailed field descriptions and valid ranges, see:

- [PACKET_RANDOMIZATION_GUIDE.md](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/docs_md/PACKET_RANDOMIZATION_GUIDE.md)

## Program Profiles

Program profiles are defined in:

- [program_generator.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/program_generator.py)

Each profile defines:

- `name`
- `level`
- `description`
- `recommended_randomize_fields`

Under the hood, each preset is implemented as a `ProgramRequest`.

The current progression is:

### `short_tcp_port`

Purpose:

- short filter
- good starting point for bring-up

Checks:

- IPv4 protocol == TCP
- TCP destination-port low byte == `0x78`

Program style:

- absolute byte loads
- `jeq`
- short control flow

### `ttl_value_chain_30`

Purpose:

- fixed-size 30-instruction TTL filter

Checks:

- loads the IPv4 TTL field
- preserves that value through a longer execution path
- accepts only these TTL values:
  - `32`
  - `48`
  - `64`
  - `96`
  - `128`
  - `200`

Program style:

- absolute TTL load
- scratch-memory store/load round trips
- `TAX` / `TXA`
- harmless ALU normalization operations
- long `jeq` chain

Why it is useful:

- gives you a true 30-op program
- still easy to reason about in waveform
- good for verifying long instruction flow with one simple filtering rule

### `medium_ttl_dscp_flags`

Purpose:

- medium filter with more realistic header checks

Checks:

- protocol == TCP
- TTL >= 64
- DSCP class matches `0x28`
- SYN bit set
- destination-port low byte == `0x78`

Program style:

- absolute loads
- ALU `and`
- `jeq`
- `jge`
- `jset`

### `long_edge_mix`

Purpose:

- longer filter with packet-length and indirect-load behavior

Checks:

- protocol == TCP
- packet length >= 62 bytes
- TTL >= 64
- DSCP class matches `0x28`
- dynamic TCP header access through `ldxb msh`
- SYN bit set
- destination-port low byte == `0x78`
- payload marker bit set

Program style:

- `ld len`
- ALU `and`
- `ldxb msh`
- indirect `ldb ind`
- `jeq`
- `jge`
- `jset`

This is the current best profile for:

- longer program execution
- short/long packet filtering
- payload-dependent filtering
- waveform walkthroughs

## Offset Discovery

The DUT does not always expose packet fields at the canonical software byte offsets.

So each profile first runs a probe phase.

The probe phase:

1. builds two packets where one field differs
2. runs a tiny BPF probe program:
   - `ldb [offset]`
   - `ret a`
3. compares the returned byte against the expected field value
4. picks the offset that matches both packets

That is how the generated program becomes DUT-specific without hardcoding assumptions.

## How The Golden Model Is Built

The golden model is event-based and packet-spec-based.

For each generated packet:

1. Python evaluates the packet spec against the same logical rule as the BPF profile
2. Python decides:
   - expected accept
   - expected reject
3. After the DUT run, the test records the actual result
4. Expected and actual return cycles are compared

The software rule lives in:

- `evaluate_profile_accept(profile, spec)`

That function is the golden model for the profile.

So the golden model is not reading the DUT.
It is reading the input packet specification and applying the intended filter rule in pure Python.

## Why This Is Useful

This gives you two independent views:

- generated BPF program running in RTL
- software reference model in Python

If they disagree, the test fails.

## Register Snapshots

Final register snapshots are available through the Python TB and wrapper signals:

- `A / ACC`
- `X`
- `PC`

These are:

- recorded into the trace
- written into the Markdown report
- printed to the console in the generated-program test

Console helper:

- `tb.print_register_snapshot()`

The test calls that after each packet run, so you can see the final state of:

- `A`
- `X`
- `PC`

without needing to open the waveform first.

## Where To See The Final Snapshot

There are three places:

1. console output
   - printed after each packet run
2. shared Markdown report
   - top-level register snapshot section
3. generated-program profile summary
   - per-packet table with final `ACC`, `X`, and `PC`

## How To Run The Test

Run the full profile set:

```bash
python -m pytest tests/integration/advanced/test_bpf_env_generated_program_profiles.py -s \
  --bpf-reports \
  --bpf-waveform \
  --bpf-unique-packets 24 \
  --bpf-protocol-mode 3 \
  --bpf-packet-rng-seed 0x1234 \
  --bpf-randomize-fields ttl,dscp_ecn,payload_len,payload_bytes,tcp_flags,src_port,seq,ack
```

Standalone request-driven preview:

```bash
python .\tests\bpf_env\program_generator.py --use-ttl --ttl-mode ge --ttl-min 64 --use-dscp --dscp-value 0x28
```

Standalone preset preview:

```bash
python .\tests\bpf_env\program_generator.py --preset ttl_value_chain_30
```

Run one profile only:

```bash
python -m pytest tests/integration/advanced/test_bpf_env_generated_program_profiles.py -s \
  --bpf-reports \
  --bpf-waveform \
  -k long_edge_mix
```

Run only the 30-op TTL program:

```bash
python -m pytest tests/integration/advanced/test_bpf_env_generated_program_profiles.py -s \
  --bpf-reports \
  --bpf-waveform \
  --bpf-unique-packets 24 \
  --bpf-protocol-mode 3 \
  --bpf-packet-rng-seed 0x1234 \
  --bpf-randomize-fields ttl,payload_len,payload_bytes \
  -k ttl_value_chain_30
```

Run a custom request-driven program for:

- `TTL > 32`
- `SYN bit set`
- `packet length > 250`
- randomized packet flow with a large payload range

```bash
python -m pytest tests/integration/advanced/test_bpf_env_generated_program_request.py -s \
  --bpf-reports \
  --bpf-waveform \
  --bpf-unique-packets 24 \
  --bpf-protocol-mode 3 \
  --bpf-packet-rng-seed 0x1234 \
  --bpf-randomize-fields ttl,tcp_flags,payload_len,payload_bytes,src_ip,dst_ip \
  --bpf-payload-len-min 220 \
  --bpf-payload-len-max 320 \
  --bpf-program-randomness medium \
  --bpf-program-ttl-min 33 \
  --bpf-program-tcp-flags-mask 0x02 \
  --bpf-program-min-packet-len 251
```

This test:

- builds the BPF program from a `ProgramRequest`
- generates randomized packets
- discovers DUT-visible offsets
- builds a Python golden model
- compares DUT accept/reject cycles against the golden model
- prints final `A`, `X`, and `PC` after each packet

## How To Extend The Generator

To add a new profile:

1. add a new `GeneratedProgramProfile`
2. add its probe packets in `build_profile_probes(...)`
3. add the program builder in `build_profile_program(...)`
4. add the software rule in `evaluate_profile_accept(...)`

That gives you:

- probes
- final program
- golden model
- report support

all in one place

## Recommended Reading Order

If you want to understand the full flow in code, read in this order:

1. [packet_generator.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/packet_generator.py)
2. [program_generator.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/program_generator.py)
3. [golden_model.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/golden_model.py)
4. [test_bpf_env_generated_program_profiles.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/integration/advanced/test_bpf_env_generated_program_profiles.py)
5. [bpf_python_tb.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/bpf_python_tb.py)
