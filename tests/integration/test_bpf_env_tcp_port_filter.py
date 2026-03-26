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
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available
from tests.bpf_env.packets import make_tcp_packet, make_udp_packet


def run_program(packet: bytes, program: list[int], trace_name: str, *, label: str):
    dut = build_bpf_env()
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


def make_tcp_port_80_filter(dst_port_low_byte_offset: int) -> list[int]:
    return [
        bpf_ldb_abs(23),
        bpf_jeq_k(6, jt=0, jf=2),
        bpf_ldb_abs(dst_port_low_byte_offset),
        bpf_jeq_k(80, jt=1, jf=0),
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def run_filter(packet: bytes, trace_name: str, *, dst_port_low_byte_offset: int):
    return run_program(
        packet,
        make_tcp_port_80_filter(dst_port_low_byte_offset),
        trace_name,
        label=f"Testing TCP dst-port-80 filter with offset {dst_port_low_byte_offset}",
    )


@pytest.mark.integration
def test_bpf_env_tcp_port_filter_accepts_tcp_port_80():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    offset = discover_tcp_dst_port_low_byte_offset()
    result = run_filter(make_tcp_packet(dst_port=80), "bpf_tcp80_accept.csv", dst_port_low_byte_offset=offset)

    assert result.returned
    assert result.accepted
    assert result.ret_value == 1


@pytest.mark.integration
def test_bpf_env_tcp_port_filter_rejects_tcp_port_443():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    offset = discover_tcp_dst_port_low_byte_offset()
    result = run_filter(make_tcp_packet(dst_port=443), "bpf_tcp443_reject.csv", dst_port_low_byte_offset=offset)

    assert result.returned
    assert not result.accepted
    assert result.ret_value == 0


@pytest.mark.integration
def test_bpf_env_tcp_port_filter_rejects_udp_port_80():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    offset = discover_tcp_dst_port_low_byte_offset()
    result = run_filter(make_udp_packet(dst_port=80), "bpf_udp80_reject.csv", dst_port_low_byte_offset=offset)

    assert result.returned
    assert not result.accepted
    assert result.ret_value == 0
