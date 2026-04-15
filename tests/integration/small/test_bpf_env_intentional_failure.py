"""Intentional failure test used to validate failure-time artifacts."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import BpfPythonTB, RET_K_OPCODE, encode_bpf_instruction, reports_enabled
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test


@pytest.mark.integration
def test_bpf_env_intentional_failure():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_intentional_failure"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_intentional_failure.csv")
    packet = bytes.fromhex("00112233445566778899aabb0800")
    program = [encode_bpf_instruction(RET_K_OPCODE, k=1)]

    tb.init_signals()
    print("Intentional failure test")
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
    if reports_enabled():
        assert result.trace_path.exists()
        assert result.report_path.exists()

    # Intentionally wrong expected value so users can validate failure flow and artifacts.
    assert result.ret_value == 0, "Intentional failure: DUT returns 1 but this test expects 0"
