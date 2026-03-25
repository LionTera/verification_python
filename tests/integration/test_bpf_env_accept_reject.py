from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import BpfPythonTB, RET_K_OPCODE, encode_bpf_instruction
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available
from tests.bpf_env.packets import make_tcp_packet


def _run_ret_k_program(ret_value: int):
    dut = build_bpf_env()
    tb = BpfPythonTB(dut, trace_path=Path("reports") / f"bpf_ret_{ret_value}.csv")
    tb.init_signals()
    tb.load_packet(make_tcp_packet(payload=b"\x01\x02\x03\x04"))
    tb.load_program([encode_bpf_instruction(RET_K_OPCODE, k=ret_value)])
    tb.configure_start_address(0)
    tb.pulse_start()
    return tb.run_until_return(max_cycles=64)


@pytest.mark.integration
def test_bpf_env_ret_k_accepts_nonzero():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    result = _run_ret_k_program(1)

    assert result.returned
    assert result.accepted
    assert result.ret_value == 1
    assert result.trace_path.exists()


@pytest.mark.integration
def test_bpf_env_ret_k_rejects_zero():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    result = _run_ret_k_program(0)

    assert result.returned
    assert not result.accepted
    assert result.ret_value == 0
    assert result.trace_path.exists()
