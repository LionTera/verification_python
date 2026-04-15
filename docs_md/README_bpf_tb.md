# Python BPF TB Bootstrap

This scaffold was generated from the flow seen in `tb_bpf.v`.

It mirrors these steps:

1. initialize DUT signals
2. load packet into PRAM
3. load instructions into IRAM through MMAP
4. pulse `bpf_start`
5. run until `bpf_return`

Generated files:
- tests/bpf_env/dut_builders.py
- tests/bpf_env/packets.py
- tests/bpf_env/bpf_python_tb.py
- tests/integration/test_bpf_env_accept_reject.py
- tests/integration/test_bpf_env_smoke.py
- tests/integration/test_bpf_env_tcp_placeholder.py
- tools/check_bpf_env_linux.py
- tools/run_bpf_integration_linux.sh
- tools/run_bpf_env_smoke_linux.sh

Notes:
- DUT target is `bpf_env`
- `BPF_START_ADDR` is set to `0x1000` in `tests/bpf_env/bpf_python_tb.py`
- the TCP test is intentionally skipped until you provide real compiled instructions
- On Linux, run `python tools/check_bpf_env_linux.py` before `./tools/run_bpf_env_smoke_linux.sh` to confirm the RTL and wrapper files are present
- Use `./tools/run_bpf_integration_linux.sh` to run the current BPF integration set on Linux
