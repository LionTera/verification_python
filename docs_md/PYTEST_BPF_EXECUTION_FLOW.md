# Pytest BPF Execution Flow

This document explains what happens when you run a BPF verification test with `pytest`, for example:

```bash
python -m pytest tests/integration/test_bpf_env_random_traffic_5000_loss.py -s
```

## High-Level Flow

The execution chain is:

```text
pytest
  -> Python test file
  -> DUT builder
  -> shared Python testbench
  -> imported Verilog DUT
  -> trace / report / waveform artifacts
  -> Python assertions decide pass/fail
```

Or in shorter form:

```text
pytest -> test_*.py -> BpfPythonTB -> Verilated bpf_env -> report/waveform/assertions
```

## Step By Step

### 1. `pytest` starts

When you run:

```bash
python -m pytest tests/integration/test_bpf_env_random_traffic_5000_loss.py -s
```

`pytest`:

- loads the selected Python test module
- discovers test functions such as `test_bpf_env_random_traffic_5000_loss()`
- loads [conftest.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/conftest.py)

## 2. `conftest.py` configures the run

[conftest.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/conftest.py) adds the BPF-specific CLI options and mirrors them into environment variables.

Examples:

- `--bpf-reports` -> `BPF_REPORTS`
- `--bpf-waveform` -> `BPF_WAVEFORM`
- `--bpf-packet-count` -> `BPF_PACKET_COUNT`
- `--bpf-run-id` -> `BPF_RUN_ID`

This is how the rest of the Python flow sees one consistent configuration.

## 3. The Python test file runs

The selected integration test file contains the scenario logic.

For example, in [test_bpf_env_random_traffic_5000_loss.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/integration/test_bpf_env_random_traffic_5000_loss.py), the test does things like:

- load config
- generate packets in Python
- generate or probe BPF instructions in Python
- decide expected results in Python
- create the DUT
- use the shared Python TB to drive the DUT
- assert expected behavior

The test file is where the verification intent lives.

## 4. The DUT is built from Python

The test calls:

- `build_bpf_env(...)`

from [dut_builders.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/dut_builders.py).

This layer:

- prepares Verilator / PyMTL
- imports the Verilog design into Python
- returns a Python object wrapping the real RTL DUT

So the actual hardware model being simulated is still the Verilog `bpf_env` design.

## 5. The shared Python testbench is created

The test then creates:

- [BpfPythonTB](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/bpf_python_tb.py)

This is not the old Verilog testbench from `tb_bpf.v`.

It is a Python driver around the DUT interface. It knows how to:

- initialize DUT-facing signals
- write packet RAM
- write instruction memory through MMAP
- pulse start
- advance simulation
- collect CSV trace rows
- write Markdown reports

## 6. The Python testbench drives the DUT

Typical sequence inside a test:

1. `tb.init_signals()`
2. `tb.load_packet(packet)`
3. `tb.load_program(program)`
4. `tb.configure_start_address(0)`
5. `tb.pulse_start()`
6. `result = tb.run_until_return(...)`

What those do:

- `load_packet(...)` writes into `bpf_pram_*`
- `load_program(...)` writes into `bpf_mmap_*`
- `pulse_start()` drives `bpf_start`
- `run_until_return()` repeatedly calls `dut.sim_tick()`

So Python is the outer control loop for the simulation.

## 7. The Verilog DUT executes

While Python calls `sim_tick()`, the imported Verilog `bpf_env` runs.

Inside the DUT:

- control logic advances
- datapath executes BPF instructions
- IRAM / PRAM / scratch RAM are accessed
- outputs such as `bpf_return`, `bpf_accept`, and `bpf_ret_value` change

This is the real RTL execution phase.

## 8. Python collects trace and report data

The shared Python TB records information on each cycle.

Examples:

- cycle number
- `bpf_start`
- `bpf_return`
- `bpf_accept`
- `bpf_ret_value`
- PRAM write/read addresses
- packet-derived decode fields

If reports are enabled, it writes:

- a CSV trace
- a Markdown report

If waveform dumping is enabled, Verilator also writes a VCD waveform.

## 9. The Python test decides pass or fail

The DUT itself does not decide whether the test passed.

The Python test file checks the result with assertions such as:

- did the DUT return?
- was the packet accepted or rejected as expected?
- was the return value correct?
- did counters match the expected model?
- did loss events match the golden model?

So final pass/fail always comes from Python assertions in the test file.

## What Each Layer Is Responsible For

### `pytest`

- test discovery
- test execution
- console pass/fail reporting

### `test_*.py`

- scenario logic
- packet generation
- expected-result / golden-model logic
- assertions

### `BpfPythonTB`

- DUT signal driving
- packet/program loading
- cycle stepping
- CSV/Markdown reporting

### `bpf_env` RTL

- actual hardware behavior
- instruction execution
- counters, return value, accept/reject behavior

## Important Distinction

Do not confuse:

- the Python shared TB in [bpf_python_tb.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/bpf_python_tb.py)

with:

- the legacy Verilog TB in [tb_bpf.v](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/bpf_test/u2u_v401/tf_bpf/tb/tb_bpf.v)

In the current pytest flow:

- the Verilog DUT is used
- the Python TB is the active driver
- the Verilog TB is not what runs the test

## Practical Mental Model

Use this short model:

- the test file decides what to test
- the Python TB decides how to drive the DUT
- the Verilog DUT does the actual hardware work
- the test file checks whether the results are correct

Or even shorter:

```text
Python defines the scenario.
Python drives the DUT.
Verilog executes the logic.
Python checks the result.
```

## Related Files

- [conftest.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/conftest.py)
- [bpf_python_tb.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/bpf_python_tb.py)
- [dut_builders.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/dut_builders.py)
- [test_bpf_env_random_traffic_5000_loss.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/integration/test_bpf_env_random_traffic_5000_loss.py)
- [tb_bpf.v](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/bpf_test/u2u_v401/tf_bpf/tb/tb_bpf.v)
