from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import (
    BPF_ACCEPT_COUNTER_ADDR,
    BPF_PACKET_LOSS_COUNTER_ADDR,
    BPF_REJECT_COUNTER_ADDR,
    BpfPythonTB,
    bpf_jeq_k,
    bpf_ldb_abs,
    bpf_ret_a,
    bpf_ret_k,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.packets import make_tcp_packet, make_udp_packet


def _probe_program(packet: bytes, program: list[int], trace_name: str, *, label: str):
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
        program = [bpf_ldb_abs(offset), bpf_ret_a()]
        result_a = _probe_program(
            packet_a,
            program,
            f"bpf_probe_mixed_{name}_a_off_{offset}.csv",
            label=f"Probe mixed {name} offset {offset} packet A",
        )
        result_b = _probe_program(
            packet_b,
            program,
            f"bpf_probe_mixed_{name}_b_off_{offset}.csv",
            label=f"Probe mixed {name} offset {offset} packet B",
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


def make_tcp_dst_filter(protocol_offset: int, dst_port_low_offset: int, *, accepted_low_byte: int) -> list[int]:
    return [
        bpf_ldb_abs(protocol_offset),
        bpf_jeq_k(0x06, jt=0, jf=2),
        bpf_ldb_abs(dst_port_low_offset),
        bpf_jeq_k(accepted_low_byte, jt=1, jf=0),
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


@pytest.mark.integration
@pytest.mark.slow
def test_bpf_env_mixed_traffic_counters():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    tcp_accept = make_tcp_packet(
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
    tcp_reject = make_tcp_packet(
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
    udp_reject = make_udp_packet(
        dst_mac=bytes.fromhex("aabbccddeeff"),
        src_mac=bytes.fromhex("112233445566"),
        src_ip="10.1.2.3",
        dst_ip="192.0.2.99",
        src_port=0x1234,
        dst_port=0x5678,
        payload=bytes.fromhex("deadbeef"),
    )

    protocol_offset = discover_offset(tcp_accept, 0x06, udp_reject, 0x11, range(20, 28), name="protocol")
    dst_port_low_offset = discover_offset(tcp_accept, 0x78, tcp_reject, 0xBB, range(34, 42), name="dst_port_low")
    program = make_tcp_dst_filter(protocol_offset, dst_port_low_offset, accepted_low_byte=0x78)

    traffic = [
        ("tcp_accept_0", tcp_accept, 0, True),
        ("tcp_reject_0", tcp_reject, 0, False),
        ("udp_reject_0", udp_reject, 0, False),
        ("tcp_accept_loss2", tcp_accept, 2, True),
        ("tcp_reject_loss1", tcp_reject, 1, False),
        ("tcp_accept_loss3", tcp_accept, 3, True),
    ]

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_mixed_traffic_counters"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_mixed_traffic_counters.csv")
    tb.init_signals()
    print("Mixed traffic counters test")
    print(f"Using protocol offset={protocol_offset}, dst_port_low_offset={dst_port_low_offset}")
    tb.load_program(program)
    tb.print_program()
    tb.write_mmap(BPF_ACCEPT_COUNTER_ADDR, 0)
    tb.write_mmap(BPF_REJECT_COUNTER_ADDR, 0)
    tb.write_mmap(BPF_PACKET_LOSS_COUNTER_ADDR, 0)

    accept_expected = 0
    reject_expected = 0
    loss_expected = 0

    for index, (name, packet, loss_cycles, expected_accept) in enumerate(traffic):
        print(f"Traffic item {index}: {name} loss_cycles={loss_cycles} expected_accept={expected_accept}")
        tb.print_packet_summary(packet)
        tb.print_packet_field_map(packet)
        tb.print_packet_memory_map(packet)
        tb.load_packet(packet)

        if loss_cycles:
            tb.set_packet_loss(1)
            tb.step(loss_cycles)
            tb.set_packet_loss(0)
            tb.step(1)
            loss_expected += loss_cycles

        tb.configure_start_address(0)
        tb.pulse_start()
        result = tb.run_until_return(max_cycles=128)
        tb.print_run_result(result)

        assert result.returned
        assert result.accepted is expected_accept
        tb.step(1)

        if expected_accept:
            accept_expected += 1
        else:
            reject_expected += 1

        accept_now = tb.read_mmap(BPF_ACCEPT_COUNTER_ADDR)
        reject_now = tb.read_mmap(BPF_REJECT_COUNTER_ADDR)
        loss_now = tb.read_mmap(BPF_PACKET_LOSS_COUNTER_ADDR)
        print(
            f"Counters after {name}: "
            f"accept=0x{accept_now:08x} reject=0x{reject_now:08x} loss=0x{loss_now:08x}"
        )
        assert accept_now == accept_expected
        assert reject_now == reject_expected
        assert loss_now == loss_expected

        for _ in range(8):
            if not int(tb.dut.bpf_return) and not int(tb.dut.bpf_active):
                break
            tb.step(1)

    assert tb.trace_path.exists()
    assert tb.report_path.exists()
