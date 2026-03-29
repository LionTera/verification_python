from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import (
    BPF_PACKET_LOSS_COUNTER_ADDR,
    BpfPythonTB,
    RET_K_OPCODE,
    encode_bpf_instruction,
    reports_enabled,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.packets import make_tcp_packet


@pytest.mark.integration
def test_bpf_env_packet_loss_counter():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    packet = make_tcp_packet()
    program = [encode_bpf_instruction(RET_K_OPCODE, k=1)]
    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_packet_loss_counter"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_packet_loss_counter.csv")
    tb.init_signals()
    print("Testing packet-loss counter at MMAP address 0x1012")
    tb.print_packet_summary(packet)
    tb.load_packet(packet)
    tb.load_program(program)
    tb.print_program()

    tb.write_mmap(BPF_PACKET_LOSS_COUNTER_ADDR, 0)
    cleared_value = tb.read_mmap(BPF_PACKET_LOSS_COUNTER_ADDR)
    print(f"Counter after clear: 0x{cleared_value:08x}")

    tb.set_packet_loss(1)
    tb.step(3)
    tb.set_packet_loss(0)
    tb.step(1)

    counted_value = tb.read_mmap(BPF_PACKET_LOSS_COUNTER_ADDR)
    print(f"Counter after 3 asserted cycles: 0x{counted_value:08x}")

    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=96)
    tb.print_run_result(result)

    assert cleared_value == 0
    assert counted_value == 3
    assert result.returned
    assert result.accepted
    assert result.ret_value == 1
    if reports_enabled():
        assert result.report_path.exists()
