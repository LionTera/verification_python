# Project Structure Guide

This document explains the main parts of the `verification_python` project so it is easier to understand where the RTL, Python verification code, reports, and generated artifacts live.

## Top-Level View

At the top level, this project is organized into a few main areas:

- `bpf_test/`
- `pymtl/`
- `tests/`
- `tools/`
- `reports/`
- `docs_md/`
- `docs_pdf/`
- `tb/`
- `rtl/`
- `sim/`
- generated/imported build artifacts in the root

The practical split is:

- RTL source and legacy collateral
- Python-based verification infrastructure
- pytest scenario tests
- generated reports and waveforms
- documentation and helper tools

## `bpf_test/`

This is the main legacy BPF design area.

In this repo it currently contains:

- `bpf_test/u2u_v401/...`

This tree is important because it holds the real Verilog/SystemVerilog design and legacy collateral, including:

- RTL files such as `bpf_control.v`, `bpf_dp.v`, and related package/include files
- the legacy Verilog testbench such as `tb_bpf.v`
- assembly/program collateral used by the older flow

When the Python verification flow builds the DUT, this RTL is the hardware being simulated.

So:

- `bpf_test/` = source of the actual BPF RTL design and old-style collateral

## `pymtl/`

This area contains the Python/PyMTL wrapper side that exposes the Verilog design to the Python test flow.

Typical contents include:

- wrapper modules such as the `bpf_env_wrapper`
- generated or maintained PyMTL placeholder/import definitions

This is part of the bridge between:

- Python test code
- Verilator-imported RTL

So:

- `pymtl/` = the Python-side wrapper layer around the RTL

## `tests/`

This is the main Python verification area.

It is split into subdirectories with different roles.

### `tests/bpf_env/`

This contains shared verification infrastructure used by many tests.

Important files here include:

- [bpf_python_tb.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/bpf_python_tb.py)
  - the shared Python testbench/driver
- `dut_builders.py`
  - builds/imports the Verilated DUT
- `packets.py`
  - raw TCP/UDP packet builders
- `packet_generator.py`
  - deterministic traffic generation
- `network_ingress.py`
  - software ingress/drop model
- `golden_model.py`
  - helpers for expected event tracking and report comparison
- `artifacts.py`
  - unique artifact naming helpers

So:

- `tests/bpf_env/` = reusable building blocks for the Python verification environment

### `tests/integration/`

This contains the real scenario tests run by `pytest`.

Examples:

- `test_bpf_env_smoke.py`
- `test_bpf_env_tcp.py`
- `test_bpf_env_tcp_port_filter.py`
- `test_bpf_env_random_traffic_5000_loss.py`
- `test_bpf_env_ingress_drop_model.py`
- `test_bpf_env_packet_loss_golden_model.py`
- `test_bpf_env_opcode_execution_suite.py`

These files define:

- the verification scenario
- packet/program generation
- expected results
- assertions
- optional golden-model logic

So:

- `tests/integration/` = end-to-end DUT verification scenarios

### `tests/unit/`

This area is for smaller focused tests, usually around narrower Python-side or wrapper-side behavior.

In many projects, this is where you would place:

- wrapper smoke tests
- helper-level tests
- narrow logic tests not requiring a full traffic scenario

### `tests/regression/`

This area is for larger grouped regressions or future broader regression organization.

### `tests/*.md`

The `tests/` tree also contains many documentation files that explain:

- run flow
- architecture
- packet generation
- specific tests
- developer onboarding

Examples already present in the repo include:

- `BPF_TEST_RUN_GUIDE.md`
- `BPF_HW_ENGINEER_DEVELOPER_SUMMARY.md`
- `PYTEST_BPF_EXECUTION_FLOW.md`

## `tools/`

This folder contains helper scripts for generating wrappers, organizing reports, checking environments, and launching UI/tools.

Important examples:

- [bpf_verification_ui.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tools/bpf_verification_ui.py)
  - GUI for launching verification runs
- `check_bpf_env_linux.py`
  - Linux environment sanity check
- `organize_bpf_reports.py`
  - organize generated artifacts
- `prune_bpf_reports.py`
  - remove old generated artifacts
- `verify_bpf_loss_schedule.py`
  - compare expected loss schedule against trace CSV
- `gen_pymtl_wrapper.py` / `gen_pymtl_wrappers_v2.py`
  - wrapper generation helpers
- `analyze_bpf_design.py`
  - basic RTL structure analysis

So:

- `tools/` = project utilities, generators, analysis helpers, and UI

## `reports/`

This folder contains generated outputs from verification runs and helper tools.

Typical contents:

- per-test CSV traces
- per-test Markdown reports
- VCD waveform files
- implementation/wrapper reports
- generated architecture summaries

Examples:

- `bpf_random_traffic_5000_loss__<run_id>.csv`
- `bpf_random_traffic_5000_loss__<run_id>.md`
- `test_bpf_env_random_traffic_5000_loss__<run_id>.verilator1.vcd`

Important detail:

- this folder is mostly generated output
- many files here are not source code
- generated CSV/MD files are ignored by git according to the project rules already added

So:

- `reports/` = generated artifacts from test execution and helper tooling

## `docs_md/`

This folder contains the Markdown documentation set for the project.

Examples:

- test run guide
- execution flow explanations
- presentation-oriented summaries
- hardware/developer summaries
- packet-generator documentation
- TB comparison notes

This is the best place for human-readable project documentation.

So:

- `docs_md/` = Markdown documentation library for the project

## `docs_pdf/`

This folder is intended for PDF versions of project documentation.

Use this area when you want exportable/shareable versions for:

- presentations
- management reviews
- formal handoff documents

So:

- `docs_pdf/` = PDF documentation/export area

## `tb/`

This is a generic top-level testbench area.

Its current README says:

- put original Verilog/SystemVerilog testbench files here if needed

In the current BPF flow, the main legacy BPF TB of interest is actually under:

- `bpf_test/.../tb/tb_bpf.v`

So this top-level `tb/` is more of a general placeholder/project-area folder.

## `rtl/`

This is a generic top-level RTL area.

In the current BPF flow, the primary BPF RTL of interest is under:

- `bpf_test/u2u_v401/.../rtl`

So like `tb/`, this top-level `rtl/` behaves more like a project workspace area than the main BPF RTL source of record.

## `sim/`

This is a generic simulation/project area.

It can be used for simulation-related collateral or future organization, but for the current Python BPF flow the key simulation artifacts are primarily driven through:

- `tests/`
- `tools/`
- `reports/`
- Verilator/PyMTL build outputs

## Generated Build Artifacts In The Root

You also have generated files directly in the project root, for example:

- `BpfEnv_noparam_v.py`
- `BpfEnv_noparam_v.cpp`
- `BpfEnv_noparam_v__ALL_pickled.cpp`
- `BpfEnv_noparam__pickled.v`
- `libBpfEnv_noparam_v.so`
- `obj_dir_BpfEnv_noparam/`

These are not the source design.

They are generated/imported build artifacts produced by the PyMTL/Verilator flow when the DUT is translated/imported.

So:

- source RTL is in `bpf_test/.../rtl`
- generated imported simulation artifacts may appear in the repo root

## Root Python Configuration Files

A few root-level files are especially important:

- [conftest.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/conftest.py)
  - pytest CLI options and BPF run configuration export
- `pytest.ini`
  - pytest configuration
- `requirements.txt`
  - Python dependency list
- `pymtl.ini`
  - PyMTL configuration
- `bootstrap_bpf_env.py`
  - environment/bootstrap helper

## How The Parts Work Together

The practical verification flow is:

1. `pytest` starts from `tests/integration/...`
2. tests use helpers from `tests/bpf_env/...`
3. DUT build/import happens through `tests/bpf_env/dut_builders.py`
4. the Verilog DUT comes from `bpf_test/.../rtl`
5. simulation is driven by `BpfPythonTB`
6. helper tools from `tools/` support analysis, UI, and artifact handling
7. outputs go into `reports/`
8. project explanations live in `docs_md/`

## Practical Mental Model

Use this short map:

- `bpf_test/` = hardware design and legacy collateral
- `pymtl/` = Python wrapper bridge to the RTL
- `tests/bpf_env/` = reusable Python verification infrastructure
- `tests/integration/` = real verification scenarios
- `tools/` = utilities and UI
- `reports/` = generated outputs
- `docs_md/` = Markdown documentation
- `docs_pdf/` = PDF documentation/export area

## Suggested Reading Order For A New Engineer

If someone is new to the project, the best order is:

1. [docs_md/PROJECT_STRUCTURE_GUIDE.md](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/docs_md/PROJECT_STRUCTURE_GUIDE.md)
2. [docs_md/PYTEST_BPF_EXECUTION_FLOW.md](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/docs_md/PYTEST_BPF_EXECUTION_FLOW.md)
3. [docs_md/bpf_python_tb_explained.md](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/docs_md/bpf_python_tb_explained.md)
4. one representative test such as [test_bpf_env_random_traffic_5000_loss.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/integration/test_bpf_env_random_traffic_5000_loss.py)
5. the RTL starting from:
   - [tb_bpf.v](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/bpf_test/u2u_v401/tf_bpf/tb/tb_bpf.v)
   - `bpf_control.v`
   - `bpf_dp.v`
