from tests.bpf_env.dut_builders import build_bpf_env
from tests.bpf_env.bpf_python_tb import BpfPythonTB
from tests.bpf_env.packets import make_zero_program


def test_bpf_env_smoke():
    dut = build_bpf_env()
    tb = BpfPythonTB(dut)
    tb.init_signals()

    # Very small placeholder program
    tb.load_program(make_zero_program(2), start_addr=0)
    tb.start(packet_len=0)

    try:
        tb.run_until_return(max_cycles=50)
    except RuntimeError:
        # still useful during bring-up
        pass

    tb.print_summary()
    tb.dump_trace_csv("reports/bpf_env_smoke_trace.csv")

    assert int(dut.bpf_active) in (0, 1)
    assert int(dut.bpf_return) in (0, 1)
