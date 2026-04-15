# Python TB vs Verilog TB

This document compares the shared Python testbench in [bpf_python_tb.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/bpf_python_tb.py) with the legacy Verilog testbench in [tb_bpf.v](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/bpf_test/u2u_v401/tf_bpf/tb/tb_bpf.v).

The short version:

- [tb_bpf.v](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/bpf_test/u2u_v401/tf_bpf/tb/tb_bpf.v) is a self-contained RTL testbench written in Verilog.
- [bpf_python_tb.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/bpf_python_tb.py) is a reusable Python-side driver/reporting layer used by many pytest scenarios.
- Both drive the same DUT-facing interface conceptually:
  - packet RAM writes
  - MMAP instruction/program writes
  - start pulse
  - packet length
  - return/accept/ret-value observation

## Main Difference

The Verilog TB is a monolithic testbench that:

- compiles BPF assembly
- loads packet/program files
- starts the DUT
- waits for completion
- prints results directly with `$display`

The Python TB is an infrastructure layer that:

- expects the test to generate packet bytes and program words
- provides reusable methods to drive the DUT
- records a cycle-by-cycle CSV trace
- writes Markdown reports
- lets each pytest test add its own golden model and scenario logic

So the Verilog TB is a complete standalone runner, while the Python TB is a reusable verification API.

## High-Level Mapping

| Verilog TB | Python TB | Role |
| --- | --- | --- |
| `init_dut_signals` | `init_signals()` | Reset all DUT input-side interface signals to known values |
| `init_packet_mem(...)` | `load_packet(...)` | Write packet bytes into PRAM |
| `init_instruction_mem(...)` | `load_program(...)` + `configure_start_address(...)` | Load BPF instructions into IRAM through MMAP |
| `run_test(...)` | test code calling `load_packet()`, `pulse_start()`, `run_until_return()` | Execute one packet/program run |
| `print_test_results(...)` | `_write_report(...)`, `print_run_result()`, packet/program formatting helpers | Present results |
| Verilog local mirrors `tb_pram`, `tb_iram` | Python-side `_loaded_packet`, `_loaded_program`, `_trace_rows` | Keep testbench-visible state for reporting/debug |

## DUT Instantiation Style

In [tb_bpf.v](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/bpf_test/u2u_v401/tf_bpf/tb/tb_bpf.v), the testbench directly instantiates `bpf_env` and drives the interface from Verilog regs.

In [bpf_python_tb.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/bpf_python_tb.py), the DUT is already constructed by Python builder code, and `BpfPythonTB` receives that DUT object and drives it with PyMTL-style `@=` assignments plus `sim_tick()`.

Implication:

- Verilog TB owns DUT creation.
- Python TB assumes DUT creation is done elsewhere and focuses on control/observation.

## Clocking And Time

### Verilog TB

The Verilog TB manages time with:

- `always`/`initial` blocks
- `@(posedge clk)`
- local counters like `tb_n_clock`

Execution is event-driven in RTL style.

### Python TB

The Python TB manages time explicitly:

- `self.dut.sim_tick()`
- `_tick()`
- `step(cycles)`
- `run_until_return(max_cycles)`

Execution is procedural from Python.

Implication:

- Verilog TB feels natural for classic RTL simulation.
- Python TB makes it easier to build deterministic scenario logic and custom checking in software.

## Program Loading

### Verilog TB

In [tb_bpf.v](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/bpf_test/u2u_v401/tf_bpf/tb/tb_bpf.v), `init_instruction_mem(...)` does two things:

1. runs the BPF assembler through `$system(...)`
2. parses the generated text file and writes each instruction into IRAM using MMAP writes

It also writes the start address register at the end.

This means the Verilog TB starts from assembly source files such as `.s`.

### Python TB

In [bpf_python_tb.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/bpf_python_tb.py), `load_program(...)` expects already-encoded 64-bit BPF instructions.

It splits each instruction into:

- low 32-bit word
- high 32-bit word

and writes both through `write_mmap(...)`.

Then `configure_start_address(...)` writes the start-address register separately.

Implication:

- Verilog TB includes assembly compilation in the TB.
- Python TB usually builds instructions in Python with helpers like `bpf_ldb_abs(...)`, `bpf_jeq_k(...)`, and `bpf_ret_k(...)`.

## Packet Loading

### Verilog TB

`init_packet_mem(...)` reads a packet memory file from disk.

The packet file format is:

- first line: packet length
- following lines: `address : data`

The task then:

- writes the packet into PRAM with `bpf_pram_wr`
- byte-swaps to the DUT-visible word order
- stores a local byte mirror in `tb_pram`

### Python TB

`load_packet(...)` takes packet bytes directly.

It then:

- sets `bpf_packet_len`
- walks the packet in 4-byte chunks
- converts each chunk into a 32-bit word with `int.from_bytes(..., "big")`
- writes each word into PRAM
- stores the original packet in `_loaded_packet`
- prints a packet summary

Implication:

- Verilog TB is file-driven.
- Python TB is packet-bytes-driven.

This is one of the biggest practical differences. The Python TB is much better for generated traffic because the test can construct packets directly in memory instead of generating intermediate `.mem` files.

## Starting Execution

### Verilog TB

`run_test(...)`:

- randomly chooses a start address
- loads packet memory and instruction memory in parallel with `fork/join`
- sets `bpf_start`
- sets `bpf_packet_len`
- waits until `bpf_return`

### Python TB

The Python tests typically do this sequence:

1. `tb.load_packet(...)`
2. `tb.load_program(...)`
3. `tb.configure_start_address(...)`
4. `tb.pulse_start()`
5. `result = tb.run_until_return(...)`

The Python TB itself is lower-level and does not force one monolithic `run_test(...)` wrapper.

Implication:

- Verilog TB is more rigid and standalone.
- Python TB is more composable, which is why it supports many custom pytest scenarios.

## Result Observation

### Verilog TB

The Verilog TB reports:

- return value
- clock count
- `acc`
- `x_reg`
- `pc`
- scratch RAM contents
- packet dump
- program disassembly

This is printed directly with `$display`.

### Python TB

The Python TB captures:

- `bpf_return`
- `bpf_accept`
- `bpf_ret_value`
- cycle count
- MMAP and PRAM activity
- packet-derived CSV fields

It then generates:

- a CSV trace
- a Markdown report
- optional additional per-test report sections

It also prints:

- packet decode summary
- formatted program
- concise run result line

Implication:

- Verilog TB is console-oriented.
- Python TB is report-oriented and easier to automate.

## Internal State Visibility

The Verilog TB directly reaches into DUT hierarchy during reporting, for example:

- `bpf_env.bpf_npu.bpf_dp.acc`
- `bpf_env.bpf_npu.bpf_dp.x_reg`
- `bpf_env.bpf_npu.bpf_control.pc`
- `bpf_env.bpf_npu.bpf_sram.mem[...]`

This gives a classic RTL-debug view.

The Python TB mostly stays at the interface level and only records signals that are visible from the simulation wrapper, plus software-side decoded packet/program state.

Implication:

- Verilog TB is stronger for direct hierarchical RTL introspection.
- Python TB is stronger for reusable black-box or near-black-box scenario validation.

## Reporting Philosophy

### Verilog TB

One run produces one console-centric result dump.

The TB itself decides what to print.

### Python TB

The shared TB writes a generic "final DUT run snapshot", and each individual pytest test can append higher-level sections such as:

- traffic summaries
- golden-model comparisons
- packet-loss tables
- configurable scenario descriptions

This is why multi-packet tests in Python can express much richer verification intent than the legacy Verilog TB.

## Randomization And Test Intent

### Verilog TB

Randomization mainly appears in:

- `tb_rnd`
- randomized start address selection

The overall test list is still a fixed set of `run_test(...)` calls using predefined assembly and packet files.

### Python TB

Randomization is often test-specific and seed-controlled in Python, for example:

- packet stream generation
- loss schedule generation
- protocol selection
- per-packet field variation

This makes the Python TB much better suited for:

- long traffic runs
- deterministic replay
- golden-model generation
- scenario sweeps from CLI/UI parameters

## Reuse Model

### Verilog TB

Reuse style:

- one TB file
- many `run_test(...)` calls
- many packet/program files on disk

### Python TB

Reuse style:

- one shared TB class
- many pytest scenario files
- packet/program generation in Python
- shared helpers for artifacts, golden models, packet generation, DUT builders

This is the core architectural shift from the old flow to the new flow.

## Strengths Of Each Approach

### Verilog TB Strengths

- close to classic RTL methodology
- direct hierarchical access to internal DUT registers and memories
- self-contained for assembly-file based regression
- simple mental model for one packet + one program runs

### Python TB Strengths

- reusable across many tests
- easy packet/program generation without intermediate files
- deterministic random traffic from seeds
- better golden-model integration
- CSV/Markdown artifact generation
- easier parameterization from pytest or a UI

## Weaknesses Of Each Approach

### Verilog TB Weaknesses

- harder to scale for high-level traffic scenarios
- more file-oriented and less flexible
- less convenient for rich software-side checking
- harder to integrate with modern reporting/UI flows

### Python TB Weaknesses

- less direct by default for internal RTL introspection
- depends on external builder/infrastructure layers
- top shared report can be misunderstood if the test appends multi-packet summary later
- requires more Python helper structure around the DUT

## Practical Mental Model

Use this mapping:

- Verilog TB = legacy standalone runner for assembly-file + packet-file DUT execution
- Python TB = modern reusable driver and reporting layer for scenario-based verification

Or even shorter:

- Verilog TB asks: "Can I run this packet/program case in RTL and print the result?"
- Python TB asks: "Can I build many verification scenarios on top of one reusable DUT driver?"

## Suggested Reading Order

To understand both together:

1. Read [tb_bpf.v](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/bpf_test/u2u_v401/tf_bpf/tb/tb_bpf.v) for the legacy standalone execution flow.
2. Read [bpf_python_tb.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/bpf_python_tb.py) for the reusable Python driver layer.
3. Read [bpf_python_tb_explained.md](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/bpf_python_tb_explained.md) for the Python TB breakdown.
4. Read one scenario test such as [test_bpf_env_random_traffic_5000_loss.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/integration/test_bpf_env_random_traffic_5000_loss.py) to see how the Python TB is used in practice.
