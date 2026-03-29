from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import BpfPythonTB, RET_K_OPCODE, encode_bpf_instruction, reports_enabled
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.packets import make_tcp_packet


@pytest.mark.integration
def test_bpf_env_packet_header_probe():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    packet = make_tcp_packet(
        dst_mac=bytes.fromhex("aabbccddeeff"),
        src_mac=bytes.fromhex("112233445566"),
        src_ip="10.1.2.3",
        dst_ip="192.0.2.99",
        src_port=0x1234,
        dst_port=0x5678,
        seq=0x01020304,
        ack=0xA1B2C3D4,
        flags=0x12,
        payload=bytes.fromhex("deadbeef"),
    )
    program = [encode_bpf_instruction(RET_K_OPCODE, k=1)]

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_packet_header_probe"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_packet_header_probe.csv")
    tb.init_signals()
    print("Learning test: packet header probe")
    tb.print_packet_summary(packet)
    tb.print_packet_memory_map(packet)
    tb.load_packet(packet)
    tb.load_program(program)
    tb.print_program()
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=96)
    tb.print_run_result(result)

    assert result.returned
    assert result.accepted
    assert result.ret_value == 1
    if reports_enabled():
        assert result.trace_path.exists()
        assert result.report_path.exists()
