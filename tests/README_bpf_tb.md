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
- tests/integration/test_bpf_env_smoke.py
- tests/integration/test_bpf_env_tcp_placeholder.py

Notes:
- DUT target is `bpf_env`
- `BPF_START_ADDR` still needs the real constant from your RTL package/include files
- the TCP test is intentionally skipped until you provide real compiled instructions
