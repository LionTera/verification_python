# BPF Verification Developer Summary

## Purpose

This document is a developer-oriented summary of the Python-based hardware verification environment around the BPF RTL.

It is intended for a hardware engineer who wants to understand:

- which software packages and tools are used
- how Python connects to the Verilog RTL
- how packets are generated and injected
- how the Python testbench is structured
- how each class of test is executed
- how packet loss is modeled
- how reports and waveforms are produced

## Technology Stack

### External Tools

- `Python`
  - test orchestration, packet generation, reporting, golden models
- `pytest`
  - test runner and CLI parameterization
- `Verilator`
  - compiles and simulates the Verilog RTL
- `PyMTL3`
  - wraps the Verilog DUT and exposes it as a Python-accessible component
- `GTKWave`
  - waveform inspection

### Python Packages Used

Core verification/runtime packages:

- `pymtl3`
  - component model and Verilog import flow
- `pytest`
  - test execution

Standard-library packages used across the environment:

- `pathlib`
  - artifact and repo path handling
- `dataclasses`
  - structured config and packet descriptors
- `csv`
  - trace generation
- `random`
  - deterministic randomized traffic
- `ipaddress`
  - IPv4 field construction and decode
- `logging`
  - trace/debug logging
- `os`
  - environment and runtime configuration
- `re`
  - path rewriting and generated-wrapper patching
- `tempfile`
  - temporary probe waveform storage
- `importlib`
  - reload of imported DUT after waveform patching
- `subprocess`
  - platform-specific helper setup
- `shutil`
  - file cleanup and dependency checks

### Optional Pytest Plugins

The test environment may also load plugins such as:

- `hypothesis`

That plugin is not central to the BPF bring-up flow, but it may appear in the pytest environment.

## Repository Areas

### Python Verification Side

- `pymtl/wrappers/`
  - PyMTL wrappers for imported Verilog modules
- `tests/bpf_env/`
  - reusable verification utilities
- `tests/integration/`
  - scenario-based end-to-end tests
- `reports/`
  - generated CSV traces, Markdown reports, and waveforms

### RTL Side

- `bpf_test/u2u_v401/tf_bpf/rtl/`
  - Verilog/SystemVerilog source files for the DUT and related modules

## High-Level Python To RTL Connection

The practical connection chain is:

1. `pytest` runs an integration test in `tests/integration/`.
2. The test calls `build_bpf_env(...)` from `tests/bpf_env/dut_builders.py`.
3. `build_bpf_env(...)` elaborates the PyMTL wrapper `BpfEnv`.
4. `BpfEnv` points PyMTL to the top wrapper Verilog file and RTL library files.
5. PyMTL + Verilator import the RTL into a Python simulation object.
6. `BpfPythonTB` drives that imported DUT object cycle by cycle.

This is the central bridge between Python and Verilog.

## Main Python Files And Their Roles

### `pymtl/wrappers/bpf_env_wrapper.py`

Role:

- defines the PyMTL component interface exposed to Python
- declares the top-level DUT-visible ports
- points PyMTL to the Verilog top wrapper
- registers RTL library files and include directories

Key points:

- the wrapper component is `BpfEnv`
- it exposes ports such as:
  - `bpf_start`
  - `bpf_packet_len`
  - `bpf_packet_loss`
  - `bpf_mmap_*`
  - `bpf_pram_*`
  - `tb_cycle_counter`
- it uses:
  - `pymtl/wrappers/bpf_env_tb_wrapper.v` as the Verilog top module
- it includes the BPF RTL libraries, including:
  - `bpf_package.sv`
  - `bpf_control.v`
  - `bpf_dp.v`
  - `bpf_npu.v`
  - `bpf_iram.v`
  - `bpf_sram.v`
  - `bpf_pram.v`

### `tests/bpf_env/dut_builders.py`

Role:

- builds and imports the Verilog DUT into the Python simulation
- handles Linux/Windows path differences
- enables optional waveform dumping
- patches generated/imported wrapper behavior when needed

Main responsibilities:

- check that `verilator` is available
- clean old generated PyMTL/Verilator artifacts
- elaborate the wrapper
- run PyMTL translation/import passes
- set Verilator warning options
- enable waveform tracing when requested
- reload the imported DUT after patching the wrapper VCD path

Important functions:

- `build_bpf_env(...)`
  - main DUT factory
- `waveform_path_for_test(...)`
  - computes main/probe waveform path policy
- `verilator_available()`
  - runtime dependency check

### `tests/bpf_env/bpf_python_tb.py`

Role:

- reusable Python testbench API for the BPF DUT
- owns cycle stepping, packet loading, program loading, MMAP access, and trace/report generation

This is the core software-side testbench.

Main responsibilities:

- BPF instruction encoding helpers
- packet decode utilities
- packet-to-PRAM mapping helpers
- CSV trace capture
- report generation
- cycle-accurate DUT driving

Important methods in `BpfPythonTB`:

- `init_signals()`
  - initializes all DUT-visible control ports
- `load_packet(packet)`
  - writes the packet into PRAM through `bpf_pram_waddr`, `bpf_pram_wdata`, `bpf_pram_wr`
- `load_program(instructions)`
  - writes the BPF program to IRAM through MMAP space
- `configure_start_address(...)`
  - configures the BPF start register
- `pulse_start()`
  - starts execution
- `run_until_return(...)`
  - ticks until `bpf_return`
- `write_mmap(...)` / `read_mmap(...)`
  - register and memory-mapped access
- `set_packet_loss(...)`
  - direct drive of the loss input

The same file also defines:

- BPF opcode helpers such as `bpf_ldb_abs`, `bpf_jeq_k`, `bpf_ret_k`, `bpf_ret_a`
- packet analysis helpers
- packet memory maps
- Markdown report formatting helpers

### `tests/bpf_env/packets.py`

Role:

- low-level packet construction helpers

It currently provides direct builders for:

- TCP packets
- UDP packets

This file handles:

- Ethernet header assembly
- IPv4 header assembly
- protocol checksum generation

### `tests/bpf_env/packet_generator.py`

Role:

- higher-level configurable packet generation layer

It provides:

- declarative packet specs
- deterministic configurable traffic streams
- standalone CLI generation mode

This is the main file for:

- variable protocol mix
- deterministic traffic generation by seed
- packet inspection without running the DUT

### `tests/bpf_env/network_ingress.py`

Role:

- ingress/drop policy model before BPF execution

This file separates:

- a frame being dropped before BPF
- a frame entering BPF and then being accepted/rejected by the BPF program

Current ingress checks include:

- too short
- bad CRC/FCS
- wrong destination MAC
- unsupported EtherType

If ingress rejects the frame:

- Python pulses `bpf_packet_loss`
- the frame is not loaded into BPF

If ingress accepts the frame:

- the frame payload is loaded into PRAM
- the DUT is allowed to execute on it

### `tests/integration/*.py`

Role:

- end-to-end scenarios using the common testbench and generators

These files compose:

- DUT builder
- packet/program generation
- runtime scenario
- expected behavior
- assertions
- report extension logic

## Main RTL Files And Their Roles

### `bpf_npu.v`

Role:

- top-level BPF processing subsystem for the verification environment

It integrates:

- control
- datapath
- instruction RAM
- scratch SRAM
- packet RAM banks
- MMAP registers and counters

Key functions:

- memory-map decode
- program start register
- accept/reject/loss counters
- routing of packet RAM banks
- instantiation of `bpf_control` and `bpf_dp`

Important registers/counters:

- `bpf_start_addr`
- `accept_counter`
- `reject_counter`
- `packet_loss_counter`

Important note:

- `packet_loss_counter` increments whenever `bpf_packet_loss` is asserted
- RTL does not know why the packet was lost

### `bpf_control.v`

Role:

- fetch/decode/execute/write-back control pipeline

Pipeline stages:

- `s0` = fetch
- `s1` = decode
- `s2` = execute
- `s3` = write-back

Main responsibilities:

- program counter update
- instruction decode
- generation of datapath control signals
- branch decisions
- return detection
- pipeline active/idle control

Useful debug signals:

- `pc`
- `bpf_pc`
- `s1_inst`
- `s2_inst`
- `s3_inst`
- `s1_opcode`
- `s1_opcode_str`

### `bpf_dp.v`

Role:

- datapath execution engine

Main responsibilities:

- packet memory address generation
- unaligned packet-read alignment
- scratch-pad access
- accumulator and X register updates
- ALU operations
- return-value generation
- out-of-packet and divide-by-zero indication

Internal registers:

- `acc`
  - accumulator, register A
- `x_reg`
  - index register X

Exported datapath views:

- `bpf_acc`
- `bpf_pc`

Useful internal debug signals:

- `acc`
- `x_reg`
- `pram_d`
- `alu_q`

### Memory Modules

- `bpf_iram.v`
  - instruction storage
- `bpf_sram.v`
  - scratch memory
- `bpf_pram.v`
  - packet RAM bank

These are instantiated by `bpf_npu.v`.

## Python/Verilog Signal Ownership

### Signals Driven By Python

Through the PyMTL wrapper and `BpfPythonTB`, Python directly drives:

- `bpf_start`
- `bpf_packet_len`
- `bpf_packet_loss`
- `bpf_mmap_addr`
- `bpf_mmap_wdata`
- `bpf_mmap_wr`
- `bpf_mmap_rd`
- `bpf_pram_waddr`
- `bpf_pram_wdata`
- `bpf_pram_wr`
- `bpf_pram_raddr`
- `bpf_pram_bank_rx`
- `bpf_pram_bank_bpf`
- `bpf_pram_bank_tx`

### Signals Observed By Python

Python reads:

- `bpf_return`
- `bpf_accept`
- `bpf_reject`
- `bpf_ret_value`
- `bpf_active`
- `bpf_mmap_rdata`
- `bpf_mmap_ack`
- `bpf_pram_rdata`
- `tb_cycle_counter`

### Internal Signals Used For Waveform Debug

These are not usually top-level Python control ports, but they are important in VCD debug:

- `acc`
- `x_reg`
- `pc`
- `bpf_acc`
- `bpf_pc`
- `s1_inst`
- `s2_inst`
- `s3_inst`
- `bpf_pram_a`
- `bpf_pram_b`
- `bpf_pram_rdata_a`
- `bpf_pram_rdata_b`

## Packet Generation Logic

### Low-Level Packet Builders

At the lowest level:

- `make_tcp_packet(...)`
- `make_udp_packet(...)`

construct complete Ethernet + IPv4 + TCP/UDP packets.

These builders are useful when:

- a test needs only one or two specific packets
- exact fields are easier to express inline

### Higher-Level Packet Generator

`packet_generator.py` adds a reusable abstraction layer.

Main structures:

- `PacketSpec`
  - declarative packet description
- `TrafficConfig`
  - configurable traffic generation parameters

Main concepts:

- deterministic generation from a seed
- protocol modes
- per-packet metadata such as expected accept/reject
- standalone generation for offline inspection

Supported protocol modes in the configurable flow:

- `1` = TCP
- `2` = UDP
- `3` = TCP + UDP
- `4` = TCP + UDP + IP

Packet uniqueness is typically created by varying:

- source/destination IP
- source/destination ports
- sequence/ack values
- payload content
- protocol selection

## Packet Injection Logic

Packet injection into the DUT is not a direct “send frame” operation.

The logical flow is:

1. Python constructs packet bytes.
2. `load_packet(packet)` stores the packet bytes into PRAM as 32-bit words.
3. `bpf_packet_len` is updated.
4. The BPF program is already loaded or is loaded through MMAP.
5. Python pulses `bpf_start`.
6. The DUT fetches instructions and reads PRAM during execution.

Important detail:

- `load_packet(packet)` writes PRAM in 32-bit chunks
- this is what you later see as `bpf_pram_wr`, `bpf_pram_waddr`, `bpf_pram_wdata` activity in the waveform

## Program Loading Logic

Program load flow:

1. A test constructs BPF instructions with helper functions.
2. Each instruction is encoded into a 64-bit value.
3. `load_program(...)` writes each instruction into IRAM through MMAP space.
4. The DUT fetches those instructions during execution.

Instruction helpers are defined in `bpf_python_tb.py`, for example:

- `bpf_ldb_abs(offset)`
- `bpf_ldh_abs(offset)`
- `bpf_jeq_k(value, jt, jf)`
- `bpf_ret_k(value)`
- `bpf_ret_a()`

## Packet Loss Logic

There are two distinct software-side models.

### 1. Direct Packet-Loss Injection

Python directly asserts:

- `bpf_packet_loss`

This verifies:

- packet-loss counter incrementing
- exact cycle timing of loss pulses

This is the simplest model and is useful for focused counter tests.

### 2. Ingress-Style Loss Modeling

Python evaluates the frame before BPF execution.

Possible software-modeled reasons include:

- too short
- bad CRC/FCS
- wrong destination MAC
- unsupported EtherType

If ingress rejects:

- Python pulses `bpf_packet_loss`
- BPF does not start for that packet

If ingress accepts:

- packet is loaded into PRAM
- execution continues

### Golden-Model Loss Verification

In the strongest loss tests, Python first creates a golden event list:

- expected packet index
- expected reason
- expected loss assert cycle
- expected loss counter value after the event

Then the test:

- runs the DUT
- extracts actual loss cycles from the trace
- compares actual versus expected

That turns the test from “read and inspect” into a structured compare against a software model.

## Testbench Structure

The common testbench structure is:

1. Build DUT.
2. Initialize DUT-visible signals.
3. Build/load packet data.
4. Build/load BPF program.
5. Optionally clear MMAP counters.
6. Start execution.
7. Wait for `bpf_return`.
8. Read counters and/or outputs.
9. Assert expected behavior.
10. Write CSV/Markdown/VCD artifacts if enabled.

This pattern is repeated with different scenario logic in the integration tests.

## Typical Flow Of A Simple Test

Example pattern:

1. call `build_bpf_env(...)`
2. create `BpfPythonTB(...)`
3. call `init_signals()`
4. build a packet
5. build a simple program like `RET_K 1`
6. call `load_packet(...)`
7. call `load_program(...)`
8. call `configure_start_address(0)`
9. call `pulse_start()`
10. call `run_until_return(...)`
11. assert `returned`, `accepted`, and `ret_value`

## Typical Flow Of A Packet-Header Filter Test

Pattern:

1. build reference packets with distinguishable field values
2. probe DUT-visible offsets using tiny temporary programs
3. identify which byte offsets the DUT actually sees
4. build the real multi-instruction filter using those offsets
5. run accept/reject packets
6. compare DUT accept/reject against expected behavior

This probing step avoids hardcoding byte offsets when the exact DUT-visible layout should be measured first.

## Typical Flow Of A Loss-Golden-Model Test

Pattern:

1. generate a deterministic traffic list
2. assign software-side loss reasons
3. build a golden list of expected loss cycles and counter progression
4. run ingress/drop and direct-loss scenarios
5. collect actual `bpf_packet_loss` cycles from the trace
6. compare actual cycle list with expected cycle list
7. append the comparison to the report

This is the most verification-rich test shape currently in the environment.

## Reporting And Artifacts

### CSV Trace

Generated by:

- `BpfPythonTB._flush_trace()`

Contains per-cycle fields such as:

- `cycle`
- `bpf_start`
- `bpf_packet_loss`
- `bpf_return`
- `bpf_accept`
- `bpf_active`
- `bpf_ret_value`
- `bpf_pram_waddr`
- `bpf_pram_wr`
- `bpf_pram_raddr`
- `tb_cycle_counter`

It also includes packet decode fields for the currently loaded packet.

### Markdown Report

Generated by:

- `BpfPythonTB._write_report()`
- plus test-specific append functions in scenario tests

Usually contains:

- result summary
- packet decode
- packet field map
- packet memory map
- BPF program listing
- scenario-specific tables such as loss events or traffic summaries

### VCD Waveform

Enabled through:

- `--bpf-waveform`

Path policy is handled in `waveform_path_for_test(...)`.

Main waveform goes to:

- `reports/<test_name>.verilator1.vcd`

Probe waveforms:

- go to a temporary location unless full artifacts are explicitly enabled

## Recommended Debug Signals

### Packet-Level Debug

- `bpf_packet_len`
- `bpf_pram_wr`
- `bpf_pram_waddr`
- `bpf_pram_wdata`
- `bpf_pram_raddr`
- `bpf_pram_rdata`
- `bpf_pram_a`
- `bpf_pram_b`
- `bpf_pram_rdata_a`
- `bpf_pram_rdata_b`

### Execution-Level Debug

- `bpf_start`
- `bpf_active`
- `bpf_return`
- `bpf_accept`
- `bpf_ret_value`
- `pc`
- `bpf_pc`
- `s1_inst`
- `s2_inst`
- `s3_inst`
- `s1_opcode`
- `s1_opcode_str`
- `acc`
- `x_reg`

### Counter-Level Debug

- `bpf_packet_loss`
- `packet_loss_counter`
- `accept_counter`
- `reject_counter`
- `bpf_mmap_addr`
- `bpf_mmap_wdata`
- `bpf_mmap_rdata`
- `bpf_mmap_wr`
- `bpf_mmap_rd`
- `bpf_mmap_ack`

## Recommended Entry Points For A New HW Engineer

Read in this order:

1. `tests/bpf_env/bpf_python_tb.py`
   - understand the reusable testbench API
2. `pymtl/wrappers/bpf_env_wrapper.py`
   - understand the exposed DUT interface
3. `tests/bpf_env/dut_builders.py`
   - understand how the RTL is imported and traced
4. `bpf_test/u2u_v401/tf_bpf/rtl/bpf_npu.v`
   - understand top-level integration and counters
5. `bpf_test/u2u_v401/tf_bpf/rtl/bpf_control.v`
   - understand instruction/control flow
6. `bpf_test/u2u_v401/tf_bpf/rtl/bpf_dp.v`
   - understand accumulator/X, packet reads, ALU flow
7. `tests/integration/test_bpf_env_smoke.py`
   - simplest runnable scenario
8. `tests/integration/test_bpf_env_tcp_port_filter.py`
   - real protocol/filter logic
9. `tests/integration/test_bpf_env_packet_loss_golden_model.py`
   - strongest end-to-end loss-model comparison

## Summary

The environment is organized around a clean split:

- RTL remains the implementation under test
- Python provides stimulus, modeling, checking, and reporting

The important engineering value is that the environment is not only executing tests.

It is also:

- parameterizing test scenarios
- generating realistic traffic
- building reproducible golden models
- collecting structured debug artifacts
- linking high-level scenarios back to low-level waveforms

For a hardware engineer, the most important files are:

- wrapper: `pymtl/wrappers/bpf_env_wrapper.py`
- builder: `tests/bpf_env/dut_builders.py`
- testbench: `tests/bpf_env/bpf_python_tb.py`
- packet generation: `tests/bpf_env/packets.py`, `tests/bpf_env/packet_generator.py`
- ingress model: `tests/bpf_env/network_ingress.py`
- RTL top: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_npu.v`
- control: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_control.v`
- datapath: `bpf_test/u2u_v401/tf_bpf/rtl/bpf_dp.v`
