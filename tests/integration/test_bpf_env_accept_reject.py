from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import BpfPythonTB, RET_K_OPCODE, encode_bpf_instruction, reports_enabled
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.packets import make_tcp_packet


def _run_ret_k_program(ret_value: int):
    dut = build_bpf_env(waveform=waveform_path_for_test(f"test_bpf_env_ret_k_{ret_value}"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / f"bpf_ret_{ret_value}.csv")
    packet = make_tcp_packet()
    program = [encode_bpf_instruction(RET_K_OPCODE, k=ret_value)]
    tb.init_signals()
    print(f"Testing RET_K path with k={ret_value}")
    tb.print_packet_summary(packet)
    tb.load_packet(packet)
    tb.load_program(program)
    tb.print_program()
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=64)
    tb.print_run_result(result)
    return result


@pytest.mark.integration
def test_bpf_env_ret_k_accepts_nonzero():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    result = _run_ret_k_program(1)

    assert result.returned
    assert result.accepted
    assert result.ret_value == 1
    if reports_enabled():
        assert result.trace_path.exists()
        assert result.report_path.exists()


@pytest.mark.integration
def test_bpf_env_ret_k_rejects_zero():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    result = _run_ret_k_program(0)

    assert result.returned
    assert not result.accepted
    assert result.ret_value == 0
    if reports_enabled():
        assert result.trace_path.exists()
        assert result.report_path.exists()
