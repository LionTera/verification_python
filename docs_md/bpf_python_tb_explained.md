# `bpf_python_tb.py` Explained

This note explains the structure and purpose of:

- `tests/bpf_env/bpf_python_tb.py`

This file is the shared Python-side testbench layer used by many of the BPF integration tests.

It is one of the most important files in the environment because it provides:

- DUT control helpers
- BPF instruction encoding helpers
- packet loading helpers
- MMAP read/write helpers
- report generation
- per-cycle CSV trace generation

## Big Picture

The role of `bpf_python_tb.py` is to give tests a reusable interface to the imported DUT.

Instead of every test manually driving:

- `bpf_start`
- `bpf_packet_len`
- `bpf_mmap_*`
- `bpf_pram_*`
- `bpf_packet_loss`

the tests use a higher-level Python API:

- `load_packet(...)`
- `load_program(...)`
- `configure_start_address(...)`
- `pulse_start()`
- `run_until_return(...)`
- `read_mmap(...)`
- `write_mmap(...)`

So this file is effectively the software testbench framework for the BPF RTL.

## Main Responsibilities

This file has four major jobs:

1. encode and format BPF instructions
2. decode and describe packet contents
3. control the DUT cycle by cycle
4. generate traces and reports

## Section 1: Constants And BPF Encoding

At the top of the file, the code defines:

- MMAP addresses
- BPF instruction-class constants
- BPF ALU constants
- BPF jump constants
- operand-source constants

Examples:

- `BPF_START_ADDR = 0x1000`
- `BPF_ACCEPT_COUNTER_ADDR = 0x1010`
- `BPF_REJECT_COUNTER_ADDR = 0x1011`
- `BPF_PACKET_LOSS_COUNTER_ADDR = 0x1012`
- `BPF_IRAM_ADDR = 0x2000`

These values are the software-side addresses used to access the DUT’s MMAP interface.

### Instruction Encoding Helpers

Main helper:

- `encode_bpf_instruction(code, jt=0, jf=0, k=0)`

This packs a classic-BPF instruction into a 64-bit integer in the format expected by the DUT.

The file also provides convenience wrappers:

- `bpf_stmt(code, k=0)`
- `bpf_jump(code, k, jt, jf)`
- `bpf_ldb_abs(offset)`
- `bpf_ldh_abs(offset)`
- `bpf_jeq_k(value, jt, jf)`
- `bpf_ret_k(value)`
- `bpf_ret_a()`

These are what tests use to build short and readable BPF programs.

## Section 2: BPF Instruction Decode And Formatting

The file also contains helpers for turning encoded instructions back into readable text.

Main helpers:

- `decode_bpf_instruction(instruction)`
- `format_bpf_instruction(instruction)`
- `format_bpf_instruction_asm(instruction)`
- `format_bpf_program(instructions)`

These are mainly for:

- console printing
- Markdown reports
- debugging

Example output:

```text
[00] 0x0006000000000001  ret #1    ; RET_K (code=0x06, jt=0, jf=0, k=0x00000001)
```

This makes the generated reports much easier to understand.

## Section 3: Packet Decode Helpers

This file includes many helpers for decoding the packet currently loaded into the testbench.

Why this is here:

- tests often need to print or report the packet being sent
- engineers need to correlate packet bytes with PRAM writes and waveforms

Main helpers:

- `analyze_packet(packet)`
  - short text summary
- `packet_csv_fields(packet)`
  - structured fields for CSV trace rows
- `packet_report_markdown(packet)`
  - Markdown packet summary
- `packet_memory_map_text(packet)`
  - human-readable packet-to-PRAM word mapping
- `packet_memory_map_markdown(packet)`
  - Markdown version of the above
- `packet_field_map_entries(packet)`
  - structured byte-range mapping for packet fields
- `packet_field_map_text(packet)`
- `packet_field_map_markdown(packet)`

These helpers are purely software-side analysis.

They do not affect DUT behavior.

They are there so tests and engineers can understand:

- which packet was loaded
- where important fields live
- how fields map into packet RAM words

## Section 4: Reports And Artifact Control

Two helpers determine whether reports and full artifacts are enabled:

- `reports_enabled()`
- `full_artifacts_enabled()`

These are controlled through environment/pytest option wiring.

The shared testbench uses them to decide whether to:

- write CSV traces
- write Markdown reports
- keep probe artifacts

## Section 5: `BpfRunResult`

`BpfRunResult` is a small dataclass that captures the outcome of one DUT execution run.

Fields:

- `cycles`
- `returned`
- `accepted`
- `ret_value`
- `trace_path`
- `report_path`

This is returned by:

- `run_until_return(...)`

Tests then use it for assertions and report printing.

## Section 6: The `BpfPythonTB` Class

This is the heart of the file.

`BpfPythonTB` is the reusable software testbench wrapper around the DUT.

### Constructor

The constructor takes:

- `dut`
- optional `trace_path`
- optional `emit_reports`

It sets up:

- output paths
- report path
- internal cycle counter
- trace row list
- currently loaded program
- currently loaded packet

Important internal members:

- `self._cycle`
- `self._trace_rows`
- `self._loaded_program`
- `self._loaded_packet`

### `current_cycle`

This property exposes the current testbench cycle count.

Tests use it when they want to record:

- loss assert cycle
- start cycle
- return cycle

### `trace_rows`

This property returns the currently accumulated trace rows.

This is especially useful for:

- golden-model tests
- extracting actual signal-assert cycles after a run

## Section 7: DUT Initialization

### `init_signals()`

Purpose:

- put all DUT-visible control signals into a known starting state

It drives initial values for:

- `bpf_start`
- `bpf_packet_len`
- `bpf_packet_loss`
- `bpf_mmap_*`
- `bpf_pram_*`
- bank-select signals

Then it performs one tick with `_tick()`.

This is the standard first step in most tests.

## Section 8: Trace Recording

### `_record_trace()`

Purpose:

- capture one trace row for the current cycle

Each row includes:

- cycle number
- control state (`bpf_start`, `bpf_packet_loss`)
- result state (`bpf_return`, `bpf_accept`, `bpf_active`, `bpf_ret_value`)
- MMAP activity (`bpf_mmap_addr`, `bpf_mmap_ack`)
- PRAM activity (`bpf_pram_waddr`, `bpf_pram_wr`, `bpf_pram_raddr`)
- `tb_cycle_counter`

It also appends packet-level CSV fields for the current packet.

That means the trace combines:

- cycle-level DUT signals
- packet metadata

### `_flush_trace()`

Purpose:

- write the accumulated trace rows to the CSV file

### `_tick(cycles=1)`

Purpose:

- advance the DUT by one or more cycles

What it does per cycle:

1. call `dut.sim_tick()`
2. record trace row
3. increment `self._cycle`

This is the basic time-advance primitive used everywhere.

## Section 9: MMAP Access Helpers

### `write_mmap(addr, data, timeout=20)`

Purpose:

- perform a memory-mapped write through the DUT MMAP interface

How:

- drive address/data/write control
- tick until `bpf_mmap_ack`
- deassert write
- tick once more

If no acknowledge arrives before timeout, it raises `TimeoutError`.

### `read_mmap(addr, timeout=20)`

Purpose:

- perform a memory-mapped read through the DUT MMAP interface

How:

- drive address/read control
- tick until `bpf_mmap_ack`
- capture `bpf_mmap_rdata`
- deassert read
- tick once more

Again, timeout protection is included.

These helpers are how tests read:

- accept counter
- reject counter
- packet-loss counter
- start-address register
- IRAM/SRAM MMAP space if needed

## Section 10: Packet-Loss Control

### `set_packet_loss(value)`

Purpose:

- directly drive the DUT’s `bpf_packet_loss` input

This is the low-level helper used by:

- direct packet-loss tests
- random-traffic loss injection
- golden-model loss tests

This does not itself tick the DUT.

The caller decides how many cycles the signal stays asserted.

## Section 11: Packet Loading

### `load_packet(packet, base_addr=0)`

Purpose:

- load raw packet bytes into packet RAM through the DUT-visible PRAM write interface

What it does:

1. store the packet as `self._loaded_packet`
2. print a packet-load summary
3. print a decoded packet summary
4. drive `bpf_packet_len`
5. write the packet into PRAM in 32-bit chunks

For each 4-byte chunk:

- pad to 4 bytes if needed
- convert to a 32-bit word
- drive `bpf_pram_waddr`
- drive `bpf_pram_wdata`
- assert `bpf_pram_wr`
- tick
- deassert `bpf_pram_wr`
- tick again

This is why packet loading is visible in the waveform as a sequence of PRAM writes.

## Section 12: Program Loading

### `load_program(instructions, base_addr=BPF_IRAM_ADDR)`

Purpose:

- load a BPF program into IRAM through the MMAP interface

How:

- store the instruction list as `self._loaded_program`
- for each 64-bit instruction:
  - split into low 32-bit word
  - split into high 32-bit word
  - write both through MMAP

This is the standard way tests program the DUT.

## Section 13: Starting Execution

### `configure_start_address(start_addr=0, enable=True)`

Purpose:

- program the DUT start register

It writes the MMAP start register in the format expected by the DUT:

- enable bit in bit 31
- start address shifted into the proper position

### `pulse_start(cycles=1)`

Purpose:

- pulse the `bpf_start` input

It:

- asserts `bpf_start`
- ticks for the requested number of cycles
- deasserts `bpf_start`
- ticks once more

This is the standard run trigger.

## Section 14: Run-To-Completion Helper

### `run_until_return(max_cycles=200)`

Purpose:

- keep ticking until the DUT asserts `bpf_return` or the timeout is reached

What it does:

- loop up to `max_cycles`
- stop when `bpf_return` is high
- build a `BpfRunResult`
- if report generation is enabled:
  - flush CSV trace
  - write Markdown report

This is the main execution helper used by most tests.

## Section 15: Markdown Report Generation

### `_write_report(result)`

Purpose:

- write the common Markdown report for the current run

It currently includes:

- title
- final DUT run snapshot
- packet summary
- packet field map
- packet memory map
- BPF program table

Important note:

- for multi-packet tests, this top report section describes the final packet/program state seen by the shared testbench
- test-level summaries are appended later by the individual test files

That is why some reports look like:

- a final packet snapshot at the top
- whole-test summary sections further down

## Section 16: Convenience Print Helpers

These helpers just print already-generated information:

- `print_packet_summary(packet)`
- `print_packet_memory_map(packet)`
- `print_packet_field_map(packet)`
- `print_program()`
- `print_run_result(result)`

They are useful during interactive or verbose test runs.

## Typical Usage Pattern In A Test

Most tests use the shared testbench like this:

1. build DUT with `build_bpf_env(...)`
2. create `BpfPythonTB(...)`
3. call `init_signals()`
4. build/load packet
5. build/load program
6. configure start address
7. pulse start
8. run until return
9. assert expected result
10. optionally read MMAP counters
11. let the test append scenario-specific report content

Example mental model:

```python
dut = build_bpf_env(...)
tb = BpfPythonTB(dut, trace_path=...)
tb.init_signals()
tb.load_packet(packet)
tb.load_program(program)
tb.configure_start_address(0)
tb.pulse_start()
result = tb.run_until_return(max_cycles=...)
assert result.returned
assert result.accepted
```

## Why This File Matters

This file is important because it centralizes:

- how packets are written
- how programs are written
- how cycles advance
- how traces are recorded
- how reports are created

Without it, every integration test would need to reimplement:

- PRAM writes
- MMAP writes
- start pulses
- return loops
- packet formatting
- report generation

That would create duplicated logic and inconsistent behavior.

## Short Summary

`bpf_python_tb.py` is the reusable Python testbench framework for the BPF RTL.

It provides:

- BPF instruction construction
- packet decode/report helpers
- DUT initialization and cycle stepping
- packet/program loading
- MMAP access
- run-to-completion execution
- CSV and Markdown artifact generation

If you want to understand how the tests really drive the DUT, this is one of the first files to read.
