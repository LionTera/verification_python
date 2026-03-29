from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import (
    BpfPythonTB,
    bpf_jeq_k,
    bpf_ldb_abs,
    bpf_ret_a,
    bpf_ret_k,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.packets import make_tcp_packet, make_udp_packet


def run_program(packet: bytes, program: list[int], trace_name: str, *, label: str):
    dut = build_bpf_env(waveform=waveform_path_for_test(Path(trace_name).stem))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / trace_name)
    tb.init_signals()
    print(label)
    tb.print_packet_summary(packet)
    tb.print_packet_memory_map(packet)
    tb.load_packet(packet)
    tb.load_program(program)
    tb.print_program()
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=160)
    tb.print_run_result(result)
    return result


def discover_offset(
    packet_a: bytes,
    expected_a: int,
    packet_b: bytes,
    expected_b: int,
    candidate_offsets: range,
    *,
    name: str,
) -> int:
    print(f"Probing {name} offsets")
    for offset in candidate_offsets:
        probe_program = [bpf_ldb_abs(offset), bpf_ret_a()]
        result_a = run_program(
            packet_a,
            probe_program,
            f"bpf_probe_{name}_a_off_{offset}.csv",
            label=f"Probe {name} offset {offset} packet A",
        )
        result_b = run_program(
            packet_b,
            probe_program,
            f"bpf_probe_{name}_b_off_{offset}.csv",
            label=f"Probe {name} offset {offset} packet B",
        )
        print(
            f"Offset {offset}: "
            f"A=0x{result_a.ret_value:02x} expected=0x{expected_a:02x} "
            f"B=0x{result_b.ret_value:02x} expected=0x{expected_b:02x}"
        )
        if result_a.ret_value == expected_a and result_b.ret_value == expected_b:
            print(f"Selected {name} offset: {offset}")
            return offset
    raise AssertionError(f"Could not discover {name} offset for this RTL")


def make_header_walk_program(
    *,
    protocol_offset: int,
    dst_port_low_offset: int,
    seq_low_offset: int,
    ack_low_offset: int,
    payload_first_offset: int,
) -> list[int]:
    return [
        bpf_ldb_abs(protocol_offset),
        bpf_jeq_k(0x06, jt=0, jf=8),
        bpf_ldb_abs(dst_port_low_offset),
        bpf_jeq_k(0x78, jt=0, jf=6),
        bpf_ldb_abs(seq_low_offset),
        bpf_jeq_k(0x04, jt=0, jf=4),
        bpf_ldb_abs(ack_low_offset),
        bpf_jeq_k(0xD4, jt=0, jf=2),
        bpf_ldb_abs(payload_first_offset),
        bpf_jeq_k(0xDE, jt=1, jf=0),
        bpf_ret_k(0),
        bpf_ret_k(0xA5),
    ]


@pytest.mark.integration
@pytest.mark.slow
def test_bpf_env_packet_header_walk():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    learning_packet = make_tcp_packet(
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
    alt_protocol_packet = make_udp_packet(
        dst_mac=bytes.fromhex("aabbccddeeff"),
        src_mac=bytes.fromhex("112233445566"),
        src_ip="10.1.2.3",
        dst_ip="192.0.2.99",
        src_port=0x1234,
        dst_port=0x5678,
        payload=bytes.fromhex("deadbeef"),
    )
    alt_dst_port_packet = make_tcp_packet(
        dst_mac=bytes.fromhex("aabbccddeeff"),
        src_mac=bytes.fromhex("112233445566"),
        src_ip="10.1.2.3",
        dst_ip="192.0.2.99",
        src_port=0x1234,
        dst_port=0x56BB,
        seq=0x01020304,
        ack=0xA1B2C3D4,
        flags=0x12,
        payload=bytes.fromhex("deadbeef"),
    )
    alt_ack_packet = make_tcp_packet(
        dst_mac=bytes.fromhex("aabbccddeeff"),
        src_mac=bytes.fromhex("112233445566"),
        src_ip="10.1.2.3",
        dst_ip="192.0.2.99",
        src_port=0x1234,
        dst_port=0x5678,
        seq=0x01020304,
        ack=0xA1B2C355,
        flags=0x12,
        payload=bytes.fromhex("deadbeef"),
    )
    alt_payload_packet = make_tcp_packet(
        dst_mac=bytes.fromhex("aabbccddeeff"),
        src_mac=bytes.fromhex("112233445566"),
        src_ip="10.1.2.3",
        dst_ip="192.0.2.99",
        src_port=0x1234,
        dst_port=0x5678,
        seq=0x01020304,
        ack=0xA1B2C3D4,
        flags=0x12,
        payload=bytes.fromhex("aaadbeef"),
    )
    alt_seq_packet = make_tcp_packet(
        dst_mac=bytes.fromhex("aabbccddeeff"),
        src_mac=bytes.fromhex("112233445566"),
        src_ip="10.1.2.3",
        dst_ip="192.0.2.99",
        src_port=0x1234,
        dst_port=0x5678,
        seq=0x010203AA,
        ack=0xA1B2C3D4,
        flags=0x12,
        payload=bytes.fromhex("deadbeef"),
    )

    protocol_offset = discover_offset(
        learning_packet,
        0x06,
        alt_protocol_packet,
        0x11,
        range(20, 28),
        name="protocol",
    )
    dst_port_low_offset = discover_offset(
        learning_packet,
        0x78,
        alt_dst_port_packet,
        0xBB,
        range(34, 50),
        name="dst_port_low",
    )
    seq_low_offset = discover_offset(
        learning_packet,
        0x04,
        alt_seq_packet,
        0xAA,
        range(38, 54),
        name="seq_low",
    )
    ack_low_offset = discover_offset(
        learning_packet,
        0xD4,
        alt_ack_packet,
        0x55,
        range(42, 58),
        name="ack_low",
    )
    payload_first_offset = discover_offset(
        learning_packet,
        0xDE,
        alt_payload_packet,
        0xAA,
        range(46, 62),
        name="payload_first",
    )

    program = make_header_walk_program(
        protocol_offset=protocol_offset,
        dst_port_low_offset=dst_port_low_offset,
        seq_low_offset=seq_low_offset,
        ack_low_offset=ack_low_offset,
        payload_first_offset=payload_first_offset,
    )
    result = run_program(
        learning_packet,
        program,
        "bpf_packet_header_walk.csv",
        label=(
            "Learning test: packet header walk "
            f"(protocol={protocol_offset}, dst_low={dst_port_low_offset}, "
            f"seq_low={seq_low_offset}, ack_low={ack_low_offset}, "
            f"payload_first={payload_first_offset})"
        ),
    )

    assert result.returned
    assert result.accepted
    assert result.ret_value == 0xA5
    assert result.trace_path.exists()
    assert result.report_path.exists()
