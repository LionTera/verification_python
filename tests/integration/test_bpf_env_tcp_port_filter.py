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
    tb.load_packet(packet)
    tb.load_program(program)
    tb.print_program()
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=128)
    tb.print_run_result(result)
    return result


def discover_tcp_dst_port_low_byte_offset() -> int:
    tcp_80 = make_tcp_packet(dst_port=80)
    tcp_443 = make_tcp_packet(dst_port=443)
    candidate_offsets = range(34, 42)

    print("Probing TCP destination-port byte offsets")
    for offset in candidate_offsets:
        probe_program = [bpf_ldb_abs(offset), bpf_ret_a()]
        result_80 = run_program(
            tcp_80,
            probe_program,
            f"bpf_probe_tcp80_off_{offset}.csv",
            label=f"Probe TCP/80 offset {offset}",
        )
        result_443 = run_program(
            tcp_443,
            probe_program,
            f"bpf_probe_tcp443_off_{offset}.csv",
            label=f"Probe TCP/443 offset {offset}",
        )
        print(
            f"Offset {offset}: tcp80=0x{result_80.ret_value:02x} "
            f"tcp443=0x{result_443.ret_value:02x}"
        )
        if result_80.ret_value == 0x50 and result_443.ret_value == 0xBB:
            print(f"Selected TCP destination-port low-byte offset: {offset}")
            return offset

    raise AssertionError("Could not discover TCP destination-port low-byte offset for this RTL")


def discover_ipv4_protocol_offset() -> int:
    tcp_packet = make_tcp_packet(dst_port=80)
    udp_packet = make_udp_packet(dst_port=80)
    candidate_offsets = range(20, 28)

    print("Probing IPv4 protocol byte offsets")
    for offset in candidate_offsets:
        probe_program = [bpf_ldb_abs(offset), bpf_ret_a()]
        result_tcp = run_program(
            tcp_packet,
            probe_program,
            f"bpf_probe_proto_tcp_off_{offset}.csv",
            label=f"Probe TCP protocol offset {offset}",
        )
        result_udp = run_program(
            udp_packet,
            probe_program,
            f"bpf_probe_proto_udp_off_{offset}.csv",
            label=f"Probe UDP protocol offset {offset}",
        )
        print(
            f"Offset {offset}: tcp=0x{result_tcp.ret_value:02x} "
            f"udp=0x{result_udp.ret_value:02x}"
        )
        if result_tcp.ret_value == 0x06 and result_udp.ret_value == 0x11:
            print(f"Selected IPv4 protocol offset: {offset}")
            return offset

    raise AssertionError("Could not discover IPv4 protocol byte offset for this RTL")


def make_tcp_port_80_filter(protocol_offset: int, dst_port_low_byte_offset: int) -> list[int]:
    return [
        bpf_ldb_abs(protocol_offset),
        bpf_jeq_k(6, jt=0, jf=2),
        bpf_ldb_abs(dst_port_low_byte_offset),
        bpf_jeq_k(80, jt=1, jf=0),
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def run_filter(packet: bytes, trace_name: str, *, protocol_offset: int, dst_port_low_byte_offset: int):
    return run_program(
        packet,
        make_tcp_port_80_filter(protocol_offset, dst_port_low_byte_offset),
        trace_name,
        label=(
            "Testing TCP dst-port-80 filter "
            f"with protocol offset {protocol_offset} and dst-port offset {dst_port_low_byte_offset}"
        ),
    )


@pytest.mark.integration
def test_bpf_env_tcp_port_filter_accepts_tcp_port_80():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    protocol_offset = discover_ipv4_protocol_offset()
    dst_port_offset = discover_tcp_dst_port_low_byte_offset()
    result = run_filter(
        make_tcp_packet(dst_port=80),
        "bpf_tcp80_accept.csv",
        protocol_offset=protocol_offset,
        dst_port_low_byte_offset=dst_port_offset,
    )

    assert result.returned
    assert result.accepted
    assert result.ret_value == 1
    assert result.report_path.exists()


@pytest.mark.integration
def test_bpf_env_tcp_port_filter_rejects_tcp_port_443():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    protocol_offset = discover_ipv4_protocol_offset()
    dst_port_offset = discover_tcp_dst_port_low_byte_offset()
    result = run_filter(
        make_tcp_packet(dst_port=443),
        "bpf_tcp443_reject.csv",
        protocol_offset=protocol_offset,
        dst_port_low_byte_offset=dst_port_offset,
    )

    assert result.returned
    assert not result.accepted
    assert result.ret_value == 0
    assert result.report_path.exists()


@pytest.mark.integration
def test_bpf_env_tcp_port_filter_rejects_udp_port_80():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    protocol_offset = discover_ipv4_protocol_offset()
    dst_port_offset = discover_tcp_dst_port_low_byte_offset()
    result = run_filter(
        make_udp_packet(dst_port=80),
        "bpf_udp80_reject.csv",
        protocol_offset=protocol_offset,
        dst_port_low_byte_offset=dst_port_offset,
    )

    assert result.returned
    assert not result.accepted
    assert result.ret_value == 0
    assert result.report_path.exists()
