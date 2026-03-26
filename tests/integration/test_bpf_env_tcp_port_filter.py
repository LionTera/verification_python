from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import (
    BpfPythonTB,
    bpf_jeq_k,
    bpf_ldb_abs,
    bpf_ldh_abs,
    bpf_ret_k,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available
from tests.bpf_env.packets import make_tcp_packet, make_udp_packet


def make_tcp_port_80_filter() -> list[int]:
    return [
        bpf_ldb_abs(23),
        bpf_jeq_k(6, jt=0, jf=2),
        bpf_ldh_abs(36),
        bpf_jeq_k(80, jt=1, jf=0),
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def run_filter(packet: bytes, trace_name: str):
    dut = build_bpf_env()
    tb = BpfPythonTB(dut, trace_path=Path("reports") / trace_name)
    program = make_tcp_port_80_filter()
    tb.init_signals()
    print("Testing TCP dst-port-80 filter")
    tb.print_packet_summary(packet)
    tb.load_packet(packet)
    tb.load_program(program)
    tb.print_program()
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=128)
    tb.print_run_result(result)
    return result


@pytest.mark.integration
def test_bpf_env_tcp_port_filter_accepts_tcp_port_80():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    result = run_filter(make_tcp_packet(dst_port=80), "bpf_tcp80_accept.csv")

    assert result.returned
    assert result.accepted
    assert result.ret_value == 1


@pytest.mark.integration
def test_bpf_env_tcp_port_filter_rejects_tcp_port_443():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    result = run_filter(make_tcp_packet(dst_port=443), "bpf_tcp443_reject.csv")

    assert result.returned
    assert not result.accepted
    assert result.ret_value == 0


@pytest.mark.integration
def test_bpf_env_tcp_port_filter_rejects_udp_port_80():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    result = run_filter(make_udp_packet(dst_port=80), "bpf_udp80_reject.csv")

    assert result.returned
    assert not result.accepted
    assert result.ret_value == 0
