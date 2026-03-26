# BPF Integration Status

This note summarizes the BPF integration bring-up work completed so far, the fixes that were required, and what the current tests actually validate.

## Goal

Bring the `bpf_env` PyMTL/Verilator integration flow up on Linux, make the smoke and basic integration tests pass, and make the tests print enough information to understand:

- which packet is being loaded
- which BPF instructions are being executed
- what result the DUT produced

## Problems We Hit

### 1. Windows-only builder logic on Linux

The original builder path tried to run:

- `cmd /c mklink /J ...`

That works only on Windows. On Linux it failed immediately because `cmd` does not exist.

### 2. Missing RTL files on the Linux VM

The Linux checkout initially did not contain the RTL under:

- `bpf_test/u2u_v401/tf_bpf/rtl`

Without those files, the placeholder source metadata pointed at paths that did not exist.

### 3. Out-of-sync wrapper/test helper files on Linux

The Linux VM had older versions of:

- `pymtl/wrappers/bpf_env_wrapper.py`
- `tests/bpf_env/bpf_python_tb.py`
- `tests/bpf_env/dut_builders.py`
- `tests/integration/test_bpf_env_smoke.py`

This caused failures such as:

- missing width constants in the wrapper
- missing exported helper symbols in the testbench
- stale test behavior

### 4. Missing SystemVerilog package file in wrapper metadata

Verilator failed because `bpf_package.sv` was not passed in through the wrapper's library file metadata. The RTL imports:

- `import bpf_package::*;`

so the package must be included in `v_libs`.

### 5. Pytest marker warning

The Linux environment was using a `pytest.ini` that did not yet include the custom `integration` marker, which produced:

- `PytestUnknownMarkWarning`

### 6. New test depending on newer packet helper signature

The `accept/reject` test originally used `make_tcp_packet(payload=...)`, but the Linux side still had an older helper signature. The test was simplified so it does not depend on that argument.

## Repo Changes Made

### Core BPF integration files

- `pymtl/wrappers/bpf_env_wrapper.py`
  - includes `bpf_package.sv` in `VerilogPlaceholderPass.v_libs`
- `tests/bpf_env/dut_builders.py`
  - supports Linux path handling
  - keeps Windows-specific junction logic only on Windows
  - normalizes placeholder paths back into the active repo
- `tests/bpf_env/bpf_python_tb.py`
  - provides reusable DUT programming helpers
  - now prints packet analysis
  - now prints BPF program listings
  - now prints final run summaries
- `tests/integration/test_bpf_env_smoke.py`
  - minimal bring-up test
- `tests/integration/test_bpf_env_accept_reject.py`
  - verifies `RET_K 1` accepts
  - verifies `RET_K 0` rejects
- `tests/integration/test_bpf_env_tcp.py`
  - verifies a structured TCP packet can be loaded and processed

### Linux support scripts

- `tools/check_bpf_env_linux.py`
  - verifies the required RTL and Python files exist
- `tools/run_bpf_env_smoke_linux.sh`
  - runs the smoke test only
- `tools/run_bpf_integration_linux.sh`
  - runs the current BPF integration set

### Generator update

- `tools/gen_pymtl_wrappers_v2.py`
  - now preserves `.sv` support files like package files when wrappers are regenerated

## Current Test Coverage

### Smoke test

File:

- `tests/integration/test_bpf_env_smoke.py`
- `tests/integration/test_bpf_env_smoke.md`

What it checks:

- DUT builds on Linux
- Verilator import succeeds
- a trivial `RET_K 1` program runs to completion
- the DUT returns and accepts
- a trace file is generated

### Accept/reject logic test

File:

- `tests/integration/test_bpf_env_accept_reject.py`
- `tests/integration/test_bpf_env_accept_reject.md`

What it checks:

- `RET_K 1` produces `accepted=True`
- `RET_K 0` produces `accepted=False`
- both programs return successfully

### TCP packet test

File:

- `tests/integration/test_bpf_env_tcp.py`
- `tests/integration/test_bpf_env_tcp.md`

What it checks:

- a structured Ethernet + IPv4 + TCP packet can be loaded
- the DUT handles the packet under the current trivial return program

### TCP port filter test

File:

- `tests/integration/test_bpf_env_tcp_port_filter.py`
- `tests/integration/test_bpf_env_tcp_port_filter.md`

What it checks:

- classic-BPF absolute packet loads work
- conditional jumps work
- multi-instruction control flow works
- TCP dst port `80` is accepted
- TCP dst port `443` is rejected
- UDP dst port `80` is rejected

## Test Output Improvements

The current test output printed with `pytest -s` now includes:

- packet length
- raw packet bytes
- decoded Ethernet fields
- decoded IPv4 fields
- decoded TCP fields
- BPF program listing
- assembly-style BPF instruction lines
- final run summary with:
  - cycle count
  - returned flag
  - accepted flag
  - return value
  - trace file path

Example instruction output:

```text
BPF program:
  [00] 0x0600000000000001  ret #1    ; RET_K (code=0x06, jt=0, jf=0, k=0x00000001)
```

## What Is Still Missing

The current tests prove the infrastructure works, but they do not yet prove much real BPF decision logic.

Still missing:

- malformed packet behavior
- out-of-bounds load behavior
- MMAP readback and register-level checks
- additional multi-step BPF programs beyond protocol/port filtering
- memory/scratch-register flows (`st`, `stx`, `ld M[]`, `ldx M[]`)
- ALU-heavy programs and accumulator/X-register interaction

## Recommended Next Step

Add the first real logic test using multiple instructions.

Best candidate:

- accept only TCP destination port `80`
- reject a different destination port

That test would exercise:

- absolute packet loads
- conditional jump behavior
- nontrivial accept/reject logic

## How To Run On Linux

Check environment:

```bash
python tools/check_bpf_env_linux.py
```

Run smoke only:

```bash
./tools/run_bpf_env_smoke_linux.sh
```

Run the current BPF integration set:

```bash
./tools/run_bpf_integration_linux.sh
```

## Waveforms

The DUT builder supports optional Verilator waveform output:

```python
dut = build_bpf_env(waveform="reports/my_waveform")
```

This enables `vl_trace` on the imported Verilator model and writes a VCD using the requested base filename.
