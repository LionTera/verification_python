"""Packet memory map test for verifying PRAM word layout reporting."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import (
    BpfPythonTB,
    RET_K_OPCODE,
    encode_bpf_instruction,
    packet_field_map_entries,
    reports_enabled,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.packets import make_tcp_packet


@pytest.mark.integration
def test_bpf_env_packet_memory_map():
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

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_packet_memory_map"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_packet_memory_map.csv")
    tb.init_signals()
    print("Learning test: packet memory map")
    tb.print_packet_summary(packet)
    tb.print_packet_field_map(packet)
    tb.print_packet_memory_map(packet)
    tb.load_packet(packet)
    tb.load_program(program)
    tb.print_program()
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=96)
    tb.print_run_result(result)

    field_map = {entry["field"]: entry for entry in packet_field_map_entries(packet)}
    assert field_map["eth.dst_mac"]["raw"] == "aabbccddeeff"
    assert field_map["eth.src_mac"]["raw"] == "112233445566"
    assert field_map["eth.eth_type"]["raw"] == "0800"
    assert field_map["ipv4.protocol"]["raw"] == "06"
    assert field_map["ipv4.src_ip"]["raw"] == bytes.fromhex("0a010203").hex()
    assert field_map["ipv4.dst_ip"]["raw"] == bytes.fromhex("c0000263").hex()
    assert field_map["tcp.src_port"]["raw"] == bytes.fromhex("1234").hex()
    assert field_map["tcp.dst_port"]["raw"] == bytes.fromhex("5678").hex()
    assert field_map["tcp.seq_num"]["raw"] == bytes.fromhex("01020304").hex()
    assert field_map["tcp.ack_num"]["raw"] == bytes.fromhex("a1b2c3d4").hex()
    assert field_map["tcp.payload"]["raw"] == bytes.fromhex("deadbeef").hex()
    assert result.returned
    assert result.accepted
    assert result.ret_value == 1
    if reports_enabled():
        assert result.trace_path.exists()
        assert result.report_path.exists()
