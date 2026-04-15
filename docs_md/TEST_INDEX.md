# Test Index

This document is the high-level index of the Python-based BPF verification tests.

It is intended to answer three questions quickly:

1. Which tests exist?
2. What does each one verify?
3. How are packets built for these tests?

## Test Groups

The integration tests are now organized into three groups:

- `tests/integration/small/`
- `tests/integration/stress/`
- `tests/integration/advanced/`

Use this mental model:

- `small` = focused sanity and feature checks
- `stress` = large traffic or long-run counter tests
- `advanced` = richer programs, richer packet scenarios, deeper debug

## Small Tests

### `test_bpf_env_smoke.py`

Purpose:

- minimal bring-up test for the Python TB + imported DUT flow
- verifies one simple packet and one trivial BPF program can run end to end

Checks:

- DUT starts
- DUT returns
- trivial accept path works

### `test_bpf_env_tcp.py`

Purpose:

- verifies that a normal TCP packet can be loaded and processed

Checks:

- packet builder works for a realistic Ethernet/IPv4/TCP frame
- packet RAM loading works for a normal packet

### `test_bpf_env_accept_reject.py`

Purpose:

- verifies the simplest return semantics of the DUT

Checks:

- `ret #1` is treated as accept
- `ret #0` is treated as reject

### `test_bpf_env_packet_header_probe.py`

Purpose:

- verifies that packet bytes can be read back through small BPF probe programs

Checks:

- byte-load behavior for packet header probing
- basic packet field observability through BPF

### `test_bpf_env_packet_memory_map.py`

Purpose:

- verifies packet memory mapping and reporting

Checks:

- packet word layout in PRAM
- packet field map and memory map reporting path

### `test_bpf_env_packet_loss_counter.py`

Purpose:

- focused test for the packet-loss counter path

Checks:

- `bpf_packet_loss` input increments the expected DUT counter

### `test_bpf_env_intentional_failure.py`

Purpose:

- deliberately fails after a valid DUT run

Checks:

- failure-time artifact generation
- report/waveform generation still works when pytest fails

## Stress Tests

### `test_bpf_env_random_traffic_5000_loss.py`

Purpose:

- long deterministic traffic run with packet-loss injection

Checks:

- mixed TCP/UDP traffic over many packets
- accept/reject counts
- packet-loss counter behavior
- seeded repeatability

Notes:

- this is one of the main large-stream tests
- good for long waveform/report/debug sessions

### `test_bpf_env_packet_loss_long_run.py`

Purpose:

- long-run packet-loss counter stress

Checks:

- packet-loss counter behavior over repeated long runs

### `test_bpf_env_mixed_traffic_counters.py`

Purpose:

- mixed traffic with counter validation

Checks:

- accept counter
- reject counter
- packet-loss counter
- mixed traffic behavior under a more sustained run

### `test_bpf_env_configurable_traffic.py`

Purpose:

- parameterized traffic run controlled by CLI/environment settings

Checks:

- generated traffic across selected protocol modes
- configurable error injection
- expected accept/reject behavior

Good when you want:

- one reusable test entry point
- different packet mixes without writing a new test each time

## Advanced Tests

### `test_bpf_env_tcp_port_filter.py`

Purpose:

- real multi-instruction filter based on protocol and TCP destination port

Checks:

- packet-field probing
- conditional branching
- real filter behavior on TCP vs UDP and accepted vs rejected port

### `test_bpf_env_packet_header_walk.py`

Purpose:

- multi-step header-reading program

Checks:

- packet reads across several header fields
- more realistic control/data flow than a trivial probe

### `test_bpf_env_long_program_with_packet_loss.py`

Purpose:

- longer learning/debug program with multiple field checks and packet loss

Checks:

- longer instruction flow
- multiple probes/branches
- packet-loss interaction during execution

### `test_bpf_env_ingress_drop_model.py`

Purpose:

- software-modeled ingress drop behavior before BPF execution

Checks:

- CRC-based drop
- wrong destination MAC drop
- unsupported ethertype drop
- too-short frame drop
- accepted packets still run through BPF

### `test_bpf_env_packet_loss_golden_model.py`

Purpose:

- packet-loss verification using an explicit golden model

Checks:

- expected vs actual loss cycles
- expected vs actual loss count
- reason-tagged loss events

### `test_bpf_env_opcode_execution_suite.py`

Purpose:

- broad opcode-family regression

Checks representative execution for:

- loads
- scratch memory ops
- ALU ops
- jumps
- `TAX` / `TXA`
- return instructions

Use this test when you want:

- opcode-family coverage
- localized failures by case name

### `test_bpf_env_complex_mixed_program.py`

Purpose:

- richer filter test using a longer mixed-type BPF program and richer packets

Checks:

- protocol, TTL, DSCP, TCP flags, destination port, and payload signature checks
- indirect loads through `ldxb`
- mixed branch behavior
- register snapshots (`A`, `X`, `PC`) after runs

This is the current best example of:

- richer packet generation
- richer filtering logic
- execution/debug-oriented reporting

### `test_bpf_env_generated_program_profiles.py`

Purpose:

- generated short/medium/long BPF programs with deterministic randomized packets and a Python golden model

Checks:

- generated BPF programs from short to long complexity
- includes a dedicated 30-op TTL-value profile
- offset discovery before program generation
- golden-model accept/reject comparison
- final register snapshots (`A`, `X`, `PC`) per packet

Use this test when you want:

- a path from simple to complex generated programs
- randomized packet fields checked by real filters
- a reusable place to extend future BPF program profiles

## How We Build Packets

Packet construction is handled mainly by:

- [tests/bpf_env/packets.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/packets.py)
- [tests/bpf_env/packet_generator.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/packet_generator.py)
- [PACKET_RANDOMIZATION_GUIDE.md](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/docs_md/PACKET_RANDOMIZATION_GUIDE.md)

## Packet Construction Layers

### Low-Level Builders

In `packets.py`, we build raw packet bytes directly:

- `make_tcp_packet(...)`
- `make_udp_packet(...)`

These functions construct:

- Ethernet header
- IPv4 header
- TCP or UDP header
- payload
- checksums

Supported fields now include:

- source/destination MAC
- source/destination IP
- DSCP/ECN
- identification
- flags/fragment field
- TTL
- IPv4 options
- source/destination port
- TCP sequence/ack
- TCP flags
- TCP window
- payload

### Packet Specification Layer

In `packet_generator.py`, we use `PacketSpec` as a declarative packet template.

`PacketSpec` lets us define a packet in Python with fields such as:

- protocol (`tcp`, `udp`, `ip`)
- L2/L3/L4 fields
- payload
- metadata

Then `build_packet(spec)` converts that specification into raw bytes.

### Traffic Stream Layer

Higher-level helpers then create streams of packet items:

- `packet_stream(...)`
- `random_packet_stream(...)`
- `generate_configurable_packet_stream(...)`

Those functions return dictionaries containing:

- packet index
- packet name
- raw packet bytes
- frame with FCS when relevant
- metadata such as expected accept/reject or ingress error

## Deterministic Random Generation

The packet generator supports seeded deterministic generation.

That means:

- same seed + same parameters = same traffic
- different seed = different traffic

This is how we get repeatable “random” runs for debugging and golden-model comparisons.

## Can We Generate Random Packets In Terms Of Length, Data, Etc.?

For the exact supported randomization fields, valid ranges, and recommended BPF filtering styles for each field, see:

- [PACKET_RANDOMIZATION_GUIDE.md](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/docs_md/PACKET_RANDOMIZATION_GUIDE.md)

Yes.

The short answer is:

- yes, logically the current infrastructure supports it
- some of it already exists today
- some of it can be expanded further very easily

### What is already randomized or varied today

Depending on the test or generator flow, we already vary things like:

- protocol type
- source IP
- source port
- sequence number
- acknowledgment number
- payload contents
- destination port
- ingress error injection
- protocol mode
- packet-loss scheduling

### What can be randomized further

With the current `PacketSpec` model, we can also generate random variation in:

- payload length
- total packet length
- DSCP/ECN
- TTL
- IPv4 options length
- identification
- flags/fragment field
- TCP flags combinations
- TCP window
- source/destination address classes
- payload signatures and offsets

So yes, we can absolutely make the packets more random in:

- length
- data
- header fields
- option fields
- protocol combinations

### Recommended approach

Do not make packets “fully random” without control.

The better approach is:

- deterministic randomness with a seed
- bounded ranges
- metadata describing what each packet is supposed to test

That gives you:

- reproducibility
- better debug
- meaningful expected behavior

## Which Test To Run For What

Use this simple selection guide:

- want a bring-up sanity check:
  - `small/test_bpf_env_smoke.py`
- want basic accept/reject behavior:
  - `small/test_bpf_env_accept_reject.py`
- want packet loading / reporting:
  - `small/test_bpf_env_tcp.py`
  - `small/test_bpf_env_packet_memory_map.py`
- want long traffic and counters:
  - `stress/test_bpf_env_random_traffic_5000_loss.py`
  - `stress/test_bpf_env_mixed_traffic_counters.py`
- want one configurable entry point:
  - `stress/test_bpf_env_configurable_traffic.py`
- want real multi-op filter logic:
  - `advanced/test_bpf_env_tcp_port_filter.py`
  - `advanced/test_bpf_env_complex_mixed_program.py`
- want opcode-family coverage:
  - `advanced/test_bpf_env_opcode_execution_suite.py`
- want golden-model packet-loss validation:
  - `advanced/test_bpf_env_packet_loss_golden_model.py`
- want ingress realism:
  - `advanced/test_bpf_env_ingress_drop_model.py`

## Suggested Reading Order

If you want to understand the project progressively:

1. [docs_md/PROJECT_STRUCTURE_GUIDE.md](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/docs_md/PROJECT_STRUCTURE_GUIDE.md)
2. [docs_md/PYTEST_BPF_EXECUTION_FLOW.md](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/docs_md/PYTEST_BPF_EXECUTION_FLOW.md)
3. [docs_md/bpf_python_tb_explained.md](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/docs_md/bpf_python_tb_explained.md)
4. this file
5. one stress test and one advanced test
