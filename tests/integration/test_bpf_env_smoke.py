from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import BpfPythonTB, RET_K_OPCODE, encode_bpf_instruction
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available


@pytest.mark.integration
def test_bpf_env_smoke():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    dut = build_bpf_env()
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_trace.csv")
    tb.init_signals()
    tb.load_packet(bytes.fromhex("00112233445566778899aabb0800"))
    tb.load_program([encode_bpf_instruction(RET_K_OPCODE, k=1)])
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=64)

    assert result.returned
    assert result.accepted
    assert result.ret_value == 1
    assert result.trace_path.exists()
