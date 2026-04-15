# BPF Hardware Verification With Python

## Purpose Of This Document

This document is written as a presentation-ready overview of our verification work.

It is intended for:

- explaining the project to management
- summarizing what has already been built
- showing why Python-based verification is useful for hardware
- serving as input for a later slide deck or AI-generated presentation

## Executive Summary

We built a Python-based verification environment around a hardware BPF engine.

The key idea is:

- Python generates realistic packets, programs, and error scenarios
- Python drives the DUT through PyMTL/Verilator
- Python collects traces, reports, and waveforms
- the tests compare DUT behavior against a software-side golden model

This gives us a verification flow that is:

- faster to iterate than writing everything in pure HDL testbenches
- easier to parameterize and automate
- easier to document and explain
- strong enough to validate both data-path behavior and control/counter behavior

## What We Are Verifying

The DUT is a BPF processing block with:

- packet memory access
- instruction/program loading
- execution control
- accept/reject result generation
- a packet-loss counter

At a high level, verification covers:

- packet loading into packet RAM
- instruction loading into instruction RAM
- BPF execution
- accept/reject behavior
- packet-loss counting
- ingress-style drop scenarios before packets enter BPF
- waveform correlation between generated traffic and DUT activity

## Why Python For Hardware Verification

Python gives us several advantages in this project:

- packet generation is much easier than in raw Verilog testbenches
- traffic patterns can be randomized but still deterministic through seeds
- reports can be generated automatically in Markdown and CSV
- golden models are easier to express and maintain
- tests are easy to parameterize from the command line
- one environment can cover smoke tests, protocol tests, counter tests, and stress tests

In practice, Python is used here as:

- the stimulus generator
- the scenario/orchestration layer
- the golden-model layer
- the reporting layer

## Verification Architecture

The flow is:

1. Python builds packets and BPF programs.
2. Python loads packets and instructions into the DUT.
3. PyMTL/Verilator runs the RTL.
4. Python reads counters and outputs from the DUT.
5. Python writes:
   - console logs
   - CSV traces
   - Markdown reports
   - VCD waveforms
6. The test compares actual DUT behavior against the expected software model.

Main components:

- `tests/bpf_env/bpf_python_tb.py`
  - reusable Python testbench API
- `tests/bpf_env/packet_generator.py`
  - configurable packet generation
- `tests/bpf_env/network_ingress.py`
  - ingress/drop decision model
- `tests/integration/*.py`
  - scenario-based integration tests
- `reports/`
  - generated CSV/MD/VCD artifacts

## How We Run The Tests

General Linux command:

```bash
python -m pytest <test_file> -s
```

Useful test flags:

- `--bpf-reports`
  - generate CSV and Markdown reports
- `--bpf-waveform`
  - generate the main VCD waveform
- `--bpf-full-artifacts`
  - keep probe artifacts for deeper debug
- `--bpf-unique-packets`
  - control packet count in configurable tests
- `--bpf-protocol-mode`
  - select traffic mix
- `--bpf-error-level`
  - select error scenario type
- `--bpf-packet-rng-seed`
  - make runs deterministic and reproducible

## Main Test Categories

### 1. Bring-Up / Smoke

Goal:

- prove the DUT builds and runs

Examples:

- `test_bpf_env_smoke.py`
- `test_bpf_env_accept_reject.py`

These tests answer:

- can the environment compile and run
- can the DUT return
- does accept/reject work at a basic level

### 2. Packet Visibility / Packet Mapping

Goal:

- prove that generated packet bytes are loaded exactly as expected into packet memory

Examples:

- `test_bpf_env_tcp.py`
- `test_bpf_env_packet_memory_map.py`
- `test_bpf_env_packet_header_probe.py`

These tests answer:

- what bytes were generated
- where they appear in packet RAM
- what to look for in the waveform

### 3. Protocol And Filter Logic

Goal:

- verify real BPF behavior, not just trivial return values

Examples:

- `test_bpf_env_packet_header_walk.py`
- `test_bpf_env_tcp_port_filter.py`
- `test_bpf_env_configurable_traffic.py`

These tests answer:

- can the DUT read real packet fields
- can it distinguish TCP and UDP
- can it accept/reject based on header content
- can we vary traffic mix without writing a new test each time

### 4. Packet-Loss And Counter Verification

Goal:

- verify the packet-loss counter and realistic drop scenarios

Examples:

- `test_bpf_env_packet_loss_counter.py`
- `test_bpf_env_packet_loss_long_run.py`
- `test_bpf_env_ingress_drop_model.py`
- `test_bpf_env_packet_loss_golden_model.py`

These tests answer:

- does the loss counter increment correctly
- do loss pulses occur on the cycles we expect
- can we model realistic drop reasons in software
- can we compare DUT activity against a golden loss schedule

## How Packets Are Generated

Packet generation is not hardcoded inside every test.

We use reusable Python helpers to generate:

- TCP packets
- UDP packets
- configurable packet streams
- deterministic randomized traffic

The generator can run by itself without the DUT.

Example:

```bash
python -m tests.bpf_env.packet_generator \
  --unique-packets 10 \
  --protocol-mode 4 \
  --error-level 2 \
  --seed 0x1234 \
  --show-limit 10
```

This is useful because it lets us:

- inspect the exact packets before a simulation run
- verify protocol fields and payloads
- confirm that the generated test data makes sense

## Protocol Modes In The Configurable Flow

The configurable test flow supports protocol mixes such as:

- `1` = TCP
- `2` = UDP
- `3` = TCP + UDP
- `4` = TCP + UDP + IP

This lets one test file cover many traffic scenarios.

## How Packet Loss Works

Packet loss is currently modeled in software, then reflected into the DUT through `bpf_packet_loss`.

There are two main styles:

### A. Direct Packet-Loss Injection

This is the simplest model.

Python drives:

```python
tb.set_packet_loss(1)
tb.step(n)
tb.set_packet_loss(0)
tb.step(1)
```

Meaning:

- the loss flag is asserted directly by the testbench
- the DUT packet-loss counter increments once per asserted cycle

This is best for:

- exact counter testing
- cycle-accurate loss-pulse verification

### B. Ingress-Style Drop Modeling

This is the more realistic system model.

Before loading a packet into BPF, the software checks:

- is the frame too short
- is the CRC/FCS wrong
- is the destination MAC wrong
- is the EtherType unsupported

If the frame fails ingress:

- the packet is not loaded into BPF
- the testbench asserts `bpf_packet_loss`
- the DUT loss counter increments

If the frame passes ingress:

- the packet enters BPF
- BPF processing continues normally

This gives us realistic software-side reasons for loss even though the RTL only sees a loss pulse.

## Important Clarification

The RTL itself does not know the semantic reason for the loss.

Inside the RTL, packet loss is still just:

- `bpf_packet_loss = 1` for a cycle or more

The reason:

- bad CRC
- wrong MAC
- random loss
- too short

is modeled in the Python testbench and recorded in the report.

That is useful because it lets us validate system-like behavior without changing the RTL interface.

## Golden Model Approach

One of the strongest parts of the flow is the golden-model comparison.

Instead of only reading the DUT result after the fact, the test can:

1. build an expected sequence of events in software
2. assign expected loss reasons
3. assign expected loss cycles
4. assign expected counter values after each event
5. run the DUT
6. compare the actual DUT trace against the expected model

This is exactly the goal of the packet-loss golden-model test.

That gives us:

- better confidence than manual waveform reading alone
- repeatability
- structured debug when something mismatches

## Reports And Debug Artifacts

For each run, we can generate:

- console output
- CSV trace
- Markdown report
- VCD waveform

These artifacts serve different roles:

- console output
  - quick feedback during development
- CSV trace
  - structured cycle-by-cycle machine-readable data
- Markdown report
  - human-readable summary for review and documentation
- waveform
  - low-level signal debug

## How The Report Helps Waveform Debug

The report is not only a summary.

It also acts as a bridge back to the waveform by recording:

- packet index
- packet type
- expected accept/reject
- loss reason
- loss assert cycle
- loss release cycle
- expected loss counter after each event
- actual loss counter after each event
- start cycle
- return cycle

This means a debug flow can be:

1. open the report
2. find the packet or loss event of interest
3. note the cycle numbers
4. open the waveform
5. jump directly to those cycles

## What Signals Matter In The Waveform

Recommended top-level signals:

- `clk`
- `reset`
- `bpf_start`
- `bpf_active`
- `bpf_return`
- `bpf_accept`
- `bpf_ret_value`
- `bpf_packet_len`
- `bpf_pram_wr`
- `bpf_pram_waddr`
- `bpf_pram_wdata`
- `bpf_pram_raddr`
- `bpf_pram_rdata`
- `bpf_packet_loss`
- `packet_loss_counter`
- `accept_counter`
- `reject_counter`
- `tb_cycle_counter`

Recommended internal debug signals:

- register A: `acc`
- register X: `x_reg`
- control PC: `pc`
- exported PC view: `bpf_pc`
- exported A view: `bpf_acc`
- instruction pipeline signals:
  - `s1_inst`
  - `s2_inst`
  - `s3_inst`
  - `s1_opcode`
  - `s1_opcode_str`

## Example Demo Flow For A Presentation

If you want to demo the environment live, the best order is:

### Demo 1: Smoke

Show:

- the test runs
- the DUT returns
- reports are generated

Command:

```bash
python -m pytest tests/integration/test_bpf_env_smoke.py -s --bpf-reports
```

### Demo 2: Packet Generation

Show:

- generated packet bytes
- protocol fields
- deterministic generation by seed

Command:

```bash
python -m tests.bpf_env.packet_generator \
  --unique-packets 5 \
  --protocol-mode 3 \
  --error-level 2 \
  --seed 0x1234 \
  --show-limit 5
```

### Demo 3: Ingress Drop Model

Show:

- wrong CRC
- wrong MAC
- accepted vs dropped frames

Command:

```bash
python -m pytest tests/integration/test_bpf_env_ingress_drop_model.py -s --bpf-reports
```

### Demo 4: Golden-Model Loss Verification

Show:

- many loss events
- documented software-side reasons
- expected vs actual loss cycles
- correlation back to waveform

Command:

```bash
python -m pytest tests/integration/test_bpf_env_packet_loss_golden_model.py -s \
  --bpf-reports \
  --bpf-waveform \
  --bpf-unique-packets 40 \
  --bpf-protocol-mode 3 \
  --bpf-packet-rng-seed 0x1234
```

## Suggested Slide Structure

If this document is later converted into slides, a good structure is:

1. Problem
   - need a scalable and explainable HW verification flow
2. Solution
   - Python-driven verification around PyMTL/Verilator
3. Architecture
   - packet generator, testbench, DUT, reports, waveforms
4. Why Python
   - speed, flexibility, golden models, reporting
5. Test Coverage
   - smoke, packet mapping, protocol logic, packet loss, stress
6. Packet Generation
   - deterministic configurable traffic
7. Packet Loss Modeling
   - direct loss vs ingress-style loss
8. Golden Model
   - expected cycle/reason model compared to DUT trace
9. Debug Flow
   - report to waveform correlation
10. Value To The Team
   - faster debug, better confidence, easier maintenance

## Message To Emphasize To Management

The strongest message is not only that the tests run.

The strongest message is that we built a verification environment that:

- creates realistic and configurable traffic
- documents what it is doing
- generates repeatable artifacts
- supports waveform-level debug
- can compare the RTL against a golden software model

That is a scalable verification asset, not just a collection of one-off tests.

## Related Documents

- `tests/BPF_TEST_RUN_GUIDE.md`
  - how to run each test
- `tests/PACKET_LOSS_MODEL.md`
  - packet-loss modeling explanation
- `tests/bpf_env/PACKET_GENERATOR.md`
  - packet generator overview
