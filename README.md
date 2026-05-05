# BPF Verification Environment

Python-based verification environment for a Berkeley Packet Filter (BPF) RTL implementation. It uses [PyMTL3](https://github.com/pymtl/pymtl3) to wrap and simulate Verilog RTL via Verilator, and [pytest](https://docs.pytest.org/) to run integration tests.

---

## Prerequisites

| Tool | Notes |
|---|---|
| Python 3.10+ | Tested on CPython 3.10 |
| [Verilator](https://verilator.org/) | Must be on `PATH`; see Windows note below |
| PyMTL3 | Installed via `requirements.txt` |
| **Windows only** | MSYS2/UCRT64 — provides `gcc` and runtime DLLs for Verilator |

### Windows setup

1. Install [MSYS2](https://www.msys2.org/) to `C:\msys64` (default).
2. In an MSYS2 UCRT64 shell: `pacman -S mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-verilator`
3. Make sure `C:\msys64\ucrt64\bin` is reachable (the test harness adds it automatically).

Override default paths with environment variables if your setup differs:

```
VP_PUBLIC_ROOT   — junction staging area (default: C:/Users/Public)
VP_MSYS2_UCRT_BIN — MSYS2 UCRT bin directory (default: C:/msys64/ucrt64/bin)
```

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Running tests

```bash
# All tests (requires Verilator)
pytest

# Fast smoke tests only
pytest tests/integration/small/

# With waveform dumps
BPF_WAVEFORM=1 pytest tests/integration/small/

# With full probe artifacts retained
BPF_FULL_ARTIFACTS=1 pytest

# Tag a run for unique artifact names
BPF_RUN_ID=my_run pytest
```

---

## Directory structure

```
verification_python/
├── bootstrap_bpf_env.py     # One-shot environment bootstrapper (regenerates wrappers + tools)
├── requirements.txt
├── pytest.ini
│
├── pymtl/
│   └── wrappers/            # Auto-generated PyMTL3 wrappers for each RTL module
│
├── tests/
│   ├── bpf_env/             # Shared test infrastructure (TB, golden model, generators)
│   │   ├── bpf_python_tb.py
│   │   ├── dut_builders.py
│   │   ├── golden_model.py
│   │   ├── packet_generator.py
│   │   ├── program_generator.py
│   │   └── artifacts.py
│   └── integration/
│       ├── small/           # Quick single-feature tests
│       ├── advanced/        # Multi-feature and mixed-program tests
│       └── stress/          # Long-running randomized tests
│
├── tools/
│   ├── verilog_parser.py    # Shared Verilog parsing utilities
│   ├── gen_pymtl_wrapper.py # Generate wrappers for a given RTL directory
│   ├── analyze_bpf_design.py
│   ├── bpf_flow_report.py
│   └── ...
│
└── reports/                 # Generated reports and waveforms (not committed)
```

---

## Regenerating wrappers

When the RTL changes, regenerate the PyMTL3 wrappers:

```bash
python bootstrap_bpf_env.py --rtl bpf_test/u2u_v401 --force
```

Or use the standalone wrapper generator:

```bash
python tools/gen_pymtl_wrapper.py --rtl bpf_test/u2u_v401 --outdir pymtl/wrappers
```

---

## Environment variables reference

| Variable | Default | Description |
|---|---|---|
| `BPF_WAVEFORM` | off | Set to `1` to enable VCD waveform dumps |
| `BPF_FULL_ARTIFACTS` | off | Set to `1` to retain probe waveforms alongside test artifacts |
| `BPF_RUN_ID` | _(empty)_ | Suffix appended to artifact file names for uniqueness |
| `VP_PUBLIC_ROOT` | `C:/Users/Public` | Windows junction staging root |
| `VP_MSYS2_UCRT_BIN` | `C:/msys64/ucrt64/bin` | MSYS2 UCRT64 bin directory |
