from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import BpfPythonTB, RET_K_OPCODE, encode_bpf_instruction
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available
from tests.bpf_env.packets import make_tcp_packet


@pytest.mark.integration
def test_bpf_env_tcp():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    packet = make_tcp_packet()
    dut = build_bpf_env()
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_trace.csv")
    program = [encode_bpf_instruction(RET_K_OPCODE, k=1)]
    tb.init_signals()
    tb.print_packet_summary(packet)
    tb.load_packet(packet)
    tb.load_program(program)
    tb.print_program()
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=64)
    tb.print_run_result(result)

    assert result.returned
    assert result.accepted
    assert len(packet) >= 54
