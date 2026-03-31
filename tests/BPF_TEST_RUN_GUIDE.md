# BPF Test Run Guide

This file explains how to run the current BPF integration tests on Linux and what each test is intended to validate.

## Prerequisites

- Run from the repo root.
- `verilator` must be installed and visible in `PATH`.
- Use `-s` with `pytest` if you want to see packet prints, program prints, and run summaries.

Basic form:

```bash
python -m pytest <test_file> -s
```

Useful flags:

- `--bpf-reports`
  - write CSV and Markdown reports in `reports/`
- `--bpf-waveform`
  - write the main VCD waveform in `reports/`
- `--bpf-full-artifacts`
  - also keep probe waveforms and probe reports for tests that do offset discovery

Example:

```bash
python -m pytest tests/integration/test_bpf_env_tcp.py -s --bpf-reports --bpf-waveform
```

## Quick Start

Smoke test:

```bash
python -m pytest tests/integration/test_bpf_env_smoke.py -s
```

Simple packet test:

```bash
python -m pytest tests/integration/test_bpf_env_tcp.py -s --bpf-reports
```

Ingress/drop model:

```bash
python -m pytest tests/integration/test_bpf_env_ingress_drop_model.py -s --bpf-reports
```

Configurable traffic test:

```bash
python -m pytest tests/integration/test_bpf_env_configurable_traffic.py -s \
  --bpf-reports \
  --bpf-unique-packets 20 \
  --bpf-protocol-mode 4 \
  --bpf-error-level 2 \
  --bpf-packet-rng-seed 0x1234
```

## Test List

### `test_bpf_env_smoke.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_smoke.py -s
```

What it does:

- builds the DUT
- loads a trivial `RET_K 1` program
- checks that the DUT returns and accepts

### `test_bpf_env_accept_reject.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_accept_reject.py -s --bpf-reports
```

What it does:

- checks simple accept vs reject behavior
- verifies `RET_K 1` accepts
- verifies `RET_K 0` rejects

### `test_bpf_env_tcp.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_tcp.py -s --bpf-reports
```

What it does:

- loads one structured Ethernet/IPv4/TCP packet
- verifies the packet can be written into PRAM and executed

### `test_bpf_env_packet_memory_map.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_packet_memory_map.py -s --bpf-reports
```

What it does:

- prints and reports the packet memory word layout
- helps correlate packet bytes to PRAM writes

### `test_bpf_env_packet_header_probe.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_packet_header_probe.py -s --bpf-reports --bpf-waveform
```

What it does:

- loads a distinctive packet
- helps inspect header bytes in PRAM and waveform

### `test_bpf_env_packet_header_walk.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_packet_header_walk.py -s --bpf-reports
```

What it does:

- uses a real multi-instruction BPF program
- probes DUT-visible offsets before building the final filter
- checks header-based filtering behavior

### `test_bpf_env_tcp_port_filter.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_tcp_port_filter.py -s --bpf-reports
```

What it does:

- dynamically probes packet offsets
- builds a TCP destination-port filter
- checks TCP accept/reject and UDP reject behavior

### `test_bpf_env_packet_loss_counter.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_packet_loss_counter.py -s --bpf-reports
```

What it does:

- checks MMAP clear/read behavior of the packet-loss counter
- checks per-cycle increment when `bpf_packet_loss=1`

### `test_bpf_env_packet_loss_long_run.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_packet_loss_long_run.py -s --bpf-reports
```

What it does:

- runs repeated packets
- injects packet loss across multiple iterations
- checks final counter totals

### `test_bpf_env_packet_loss_golden_model.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_packet_loss_golden_model.py -s \
  --bpf-reports \
  --bpf-waveform \
  --bpf-unique-packets 40 \
  --bpf-protocol-mode 3 \
  --bpf-packet-rng-seed 0x1234
```

What it does:

- creates a deterministic golden model of packet-loss events before running the DUT
- mixes realistic loss reasons:
  - bad CRC
  - wrong destination MAC
  - random injected loss pulse
- records the expected loss cycles and expected counter progression
- runs the DUT and extracts the actual `bpf_packet_loss` cycles from the trace
- compares expected loss cycles against actual waveform-visible loss cycles
- appends a report table you can use to cross-check the waveform

### `test_bpf_env_long_program_with_packet_loss.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_long_program_with_packet_loss.py -s --bpf-reports
```

What it does:

- runs a longer BPF program
- injects packet loss while the DUT is active
- checks the final loss counter result

### `test_bpf_env_ingress_drop_model.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_ingress_drop_model.py -s --bpf-reports
```

What it does:

- models ingress policy before BPF execution
- only accepted frames enter BPF
- dropped frames increment `bpf_packet_loss`
- covers bad CRC, wrong destination MAC, wrong EtherType, too-short frame, TCP reject, and UDP reject

### `test_bpf_env_mixed_traffic_counters.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_mixed_traffic_counters.py -s --bpf-reports
```

What it does:

- runs mixed traffic
- checks accept/reject/loss counters across a sequence

### `test_bpf_env_random_traffic_5000_loss.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_random_traffic_5000_loss.py -s \
  --bpf-reports \
  --bpf-packet-count 1000 \
  --bpf-packet-loss-percent 5 \
  --bpf-packet-rng-seed 0x5eed5eed
```

What it does:

- generates a deterministic random traffic stream
- injects packet-loss events
- verifies counter totals over a long run

Supported knobs:

- `--bpf-packet-count`
- `--bpf-packet-loss-percent`
- `--bpf-packet-rng-seed`
- `--bpf-progress-interval`

### `test_bpf_env_configurable_traffic.py`

Run:

```bash
python -m pytest tests/integration/test_bpf_env_configurable_traffic.py -s \
  --bpf-reports \
  --bpf-unique-packets 20 \
  --bpf-protocol-mode 4 \
  --bpf-error-level 2 \
  --bpf-packet-rng-seed 0x1234
```

What it does:

- generates a configurable packet set from one test file
- probes DUT-visible offsets before building the final filter
- supports multiple traffic mixes and error modes
- drives ingress behavior and BPF execution from the generated packets

Supported knobs:

- `--bpf-unique-packets`
  - number of unique packets to generate
- `--bpf-protocol-mode`
  - `1` = TCP
  - `2` = UDP
  - `3` = TCP + UDP
  - `4` = TCP + UDP + IP
- `--bpf-error-level`
  - `1` = packet loss injection
  - `2` = CRC errors plus packet loss
- `--bpf-packet-rng-seed`
  - deterministic generation seed

## Packet Generator Only

You can run the packet generator without the DUT to inspect exactly what traffic will be produced.

Run:

```bash
python -m tests.bpf_env.packet_generator \
  --unique-packets 10 \
  --protocol-mode 4 \
  --error-level 2 \
  --seed 0x1234 \
  --show-limit 10
```

What it prints:

- packet name
- protocol
- expected accept/reject
- whether packet loss will be injected
- ingress error type
- decoded packet summary
- raw frame bytes with FCS

Generator arguments:

- `--unique-packets`
- `--protocol-mode`
- `--error-level`
- `--seed`
- `--show-limit`

## Waveform Notes

If you enable `--bpf-waveform`, the main waveform is written to `reports/`.

Recommended signals:

- `bpf_packet_len`
- `bpf_pram_wr`
- `bpf_pram_waddr`
- `bpf_pram_wdata`
- `bpf_pram_raddr`
- `bpf_pram_rdata`
- `bpf_start`
- `bpf_active`
- `bpf_return`
- `bpf_accept`
- `bpf_ret_value`

Useful packet field locations:

- IPv4 protocol byte: packet byte `23`
- TCP/UDP destination port: packet bytes `36:37`

Common write addresses:

- `0x0014`
  - contains the word with IPv4 protocol
- `0x0024`
  - contains the word with TCP/UDP destination port

## Artifact Locations

Main outputs go under `reports/`:

- `*.csv`
  - cycle-by-cycle trace
- `*.md`
  - run summary and packet/program decode
- `*.verilator1.vcd`
  - waveform if enabled

Probe artifacts are only intended when `--bpf-full-artifacts` is enabled.
