import pytest

from tests.bpf_env.dut_builders import build_bpf_env
from tests.bpf_env.bpf_python_tb import BpfPythonTB
from tests.bpf_env.packets import make_tcp_packet, make_zero_program


@pytest.mark.skip(reason="Replace placeholder program with real compiled BPF instructions first")
def test_bpf_env_tcp_placeholder():
    dut = build_bpf_env()
    tb = BpfPythonTB(dut)
    tb.init_signals()

    packet = make_tcp_packet()

    # Replace with real 64-bit instructions compiled from your BPF assembly.
    program = make_zero_program(4)

    tb.load_packet(packet)
    tb.load_program(program, start_addr=0)
    tb.start(packet_len=len(packet))
    tb.run_until_return(max_cycles=300)

    tb.print_summary()
    tb.dump_trace_csv("reports/bpf_env_tcp_trace.csv")

    # Replace these with real expectations once the program is known
    assert int(dut.bpf_return) == 1
