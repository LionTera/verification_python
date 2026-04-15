"""Ingress-model test for CRC, MAC, ethertype, and length-based drops."""

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
    packet_field_map_markdown,
    packet_memory_map_markdown,
    packet_report_markdown,
    program_report_markdown,
    reports_enabled,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.network_ingress import (
    drive_ingress_frame,
    mutate_ethertype,
    read_counters,
    with_ethernet_fcs,
)
from tests.bpf_env.packets import make_tcp_packet, make_udp_packet


EXPECTED_DST_MAC = bytes.fromhex("020000000002")


def _probe_program(packet: bytes, program: list[int], trace_name: str, *, label: str):
    """Run a short probe program on one packet to discover field offsets."""
    dut = build_bpf_env(waveform=waveform_path_for_test(Path(trace_name).stem, probe=True))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / trace_name, emit_reports=False)
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
    """Search for the packet byte offset that yields the expected field values."""
    print(f"Probing {name} offsets")
    for offset in candidate_offsets:
        program = [bpf_ldb_abs(offset), bpf_ret_a()]
        result_a = _probe_program(
            packet_a,
            program,
            f"bpf_probe_ingress_{name}_a_off_{offset}.csv",
            label=f"Probe ingress {name} offset {offset} packet A",
        )
        result_b = _probe_program(
            packet_b,
            program,
            f"bpf_probe_ingress_{name}_b_off_{offset}.csv",
            label=f"Probe ingress {name} offset {offset} packet B",
        )
        if result_a.ret_value == expected_a and result_b.ret_value == expected_b:
            print(f"Selected {name} offset: {offset}")
            return offset
    raise AssertionError(f"Could not discover {name} offset for this RTL")


def make_tcp_dst_filter(protocol_offset: int, dst_port_low_offset: int, *, accepted_low_byte: int) -> list[int]:
    """Build the TCP destination-port filter used after ingress checks."""
    return [
        bpf_ldb_abs(protocol_offset),
        bpf_jeq_k(0x06, jt=0, jf=2),
        bpf_ldb_abs(dst_port_low_offset),
        bpf_jeq_k(accepted_low_byte, jt=1, jf=0),
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def append_ingress_report(
    report_path: Path,
    *,
    traffic_history: list[dict[str, object]],
    program: list[int],
    protocol_offset: int,
    dst_port_low_offset: int,
) -> None:
    """Append ingress-model summary sections to the main report."""
    lines = [
        "",
        "## Ingress Drop Model",
        "",
        "- This test uses a modeled ingress policy before BPF load/start.",
        "- Accepted frames are loaded into PRAM and run through BPF.",
        "- Dropped frames assert `bpf_packet_loss` and do not enter BPF execution.",
        "",
        "### Drop Reasons",
        "",
        "- `bad_crc`: Ethernet FCS mismatch",
        "- `wrong_dst_mac`: destination MAC does not match ingress MAC",
        "- `unsupported_ethertype`: Ethernet type is not IPv4",
        "- `too_short`: frame shorter than Ethernet header plus FCS",
        "",
        f"- Protocol offset used by filter: `{protocol_offset}`",
        f"- Destination-port low-byte offset used by filter: `{dst_port_low_offset}`",
        "",
        "### Sequence Summary",
        "",
        "| Item | Name | Ingress Reason | Entered BPF | Expected Accept | Actual Accept | Accept Counter | Reject Counter | Loss Counter |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, item in enumerate(traffic_history):
        lines.append(
            f"| `{index}` | `{item['name']}` | `{item['ingress_reason']}` | `{item['entered_bpf']}` | "
            f"`{item['expected_accept']}` | `{item['actual_accept']}` | `{item['accept_count']}` | "
            f"`{item['reject_count']}` | `{item['loss_count']}` |"
        )

    lines.extend(["", "## Filter Program", "", program_report_markdown(program)])

    for index, item in enumerate(traffic_history):
        frame = item["frame"]
        packet = item["packet_for_bpf"]
        lines.extend(
            [
                f"## Traffic Item {index}: {item['name']}",
                "",
                f"- Ingress Reason: `{item['ingress_reason']}`",
                f"- Entered BPF: `{item['entered_bpf']}`",
                f"- Expected Accept: `{item['expected_accept']}`",
                f"- Actual Accept: `{item['actual_accept']}`",
                f"- Counters After Item: accept=`{item['accept_count']}` reject=`{item['reject_count']}` loss=`{item['loss_count']}`",
                f"- Ethernet Frame With FCS: `{frame.hex()}`",
                "",
            ]
        )
        if packet is not None:
            lines.extend(
                [
                    packet_report_markdown(packet),
                    packet_field_map_markdown(packet),
                    packet_memory_map_markdown(packet),
                ]
            )

    with report_path.open("a", encoding="utf-8") as report_file:
        report_file.write("\n".join(lines))


@pytest.mark.integration
@pytest.mark.slow
def test_bpf_env_ingress_drop_model():
    """Verify ingress drops and BPF decisions across a mixed packet set."""
    if not verilator_available():
        pytest.skip("verilator is not installed")

    tcp_accept = make_tcp_packet(dst_mac=EXPECTED_DST_MAC, dst_port=0x5678, payload=bytes.fromhex("deadbeef"))
    tcp_reject = make_tcp_packet(dst_mac=EXPECTED_DST_MAC, dst_port=0x56BB, payload=bytes.fromhex("deadbeef"))
    udp_reject = make_udp_packet(dst_mac=EXPECTED_DST_MAC, dst_port=0x5678, payload=bytes.fromhex("deadbeef"))

    protocol_offset = discover_offset(tcp_accept, 0x06, udp_reject, 0x11, range(20, 28), name="protocol")
    dst_port_low_offset = discover_offset(tcp_accept, 0x78, tcp_reject, 0xBB, range(34, 42), name="dst_port_low")
    program = make_tcp_dst_filter(protocol_offset, dst_port_low_offset, accepted_low_byte=0x78)

    good_accept = with_ethernet_fcs(tcp_accept)
    bad_crc = good_accept[:-4] + b"\x00\x00\x00\x00"
    wrong_dst = with_ethernet_fcs(make_tcp_packet(dst_mac=bytes.fromhex("001122334455"), dst_port=0x5678, payload=bytes.fromhex("deadbeef")))
    wrong_ethertype = with_ethernet_fcs(mutate_ethertype(tcp_accept, 0x86DD))
    too_short = b"\x01\x02\x03\x04\x05"
    good_tcp_reject = with_ethernet_fcs(tcp_reject)
    good_udp_reject = with_ethernet_fcs(udp_reject)

    traffic = [
        ("good_tcp_accept", good_accept, True, True),
        ("bad_crc_drop", bad_crc, False, None),
        ("wrong_dst_drop", wrong_dst, False, None),
        ("wrong_ethertype_drop", wrong_ethertype, False, None),
        ("too_short_drop", too_short, False, None),
        ("good_tcp_reject", good_tcp_reject, True, False),
        ("good_udp_reject", good_udp_reject, True, False),
    ]

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_ingress_drop_model"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_ingress_drop_model.csv")
    tb.init_signals()
    print("Ingress drop-model test")
    print(f"Using protocol offset={protocol_offset}, dst_port_low_offset={dst_port_low_offset}")
    tb.load_program(program)
    tb.print_program()
    tb.write_mmap(BPF_ACCEPT_COUNTER_ADDR, 0)
    tb.write_mmap(BPF_REJECT_COUNTER_ADDR, 0)
    tb.write_mmap(BPF_PACKET_LOSS_COUNTER_ADDR, 0)

    accept_expected = 0
    reject_expected = 0
    loss_expected = 0
    traffic_history: list[dict[str, object]] = []

    for index, (name, frame, should_enter_bpf, expected_accept) in enumerate(traffic):
        print(f"Traffic item {index}: {name}")
        decision = drive_ingress_frame(tb, frame, expected_dst_mac=EXPECTED_DST_MAC, packet_loss_cycles=1)
        actual_accept = None
        packet_for_bpf = decision.packet_for_bpf

        if decision.accepted:
            assert should_enter_bpf
            assert packet_for_bpf is not None
            tb.print_packet_summary(packet_for_bpf)
            tb.print_packet_field_map(packet_for_bpf)
            tb.print_packet_memory_map(packet_for_bpf)
            tb.configure_start_address(0)
            tb.pulse_start()
            result = tb.run_until_return(max_cycles=128)
            tb.print_run_result(result)
            actual_accept = result.accepted
            assert actual_accept is expected_accept
            tb.step(1)
            if expected_accept:
                accept_expected += 1
            else:
                reject_expected += 1
        else:
            assert not should_enter_bpf
            loss_expected += 1

        accept_now, reject_now, loss_now = read_counters(tb)
        assert accept_now == accept_expected
        assert reject_now == reject_expected
        assert loss_now == loss_expected
        traffic_history.append(
            {
                "name": name,
                "frame": frame,
                "ingress_reason": decision.reason,
                "entered_bpf": decision.accepted,
                "expected_accept": expected_accept,
                "actual_accept": actual_accept,
                "accept_count": accept_now,
                "reject_count": reject_now,
                "loss_count": loss_now,
                "packet_for_bpf": packet_for_bpf,
            }
        )

        for _ in range(8):
            if not int(tb.dut.bpf_return) and not int(tb.dut.bpf_active):
                break
            tb.step(1)

    if reports_enabled():
        assert tb.trace_path.exists()
        assert tb.report_path.exists()
        append_ingress_report(
            tb.report_path,
            traffic_history=traffic_history,
            program=program,
            protocol_offset=protocol_offset,
            dst_port_low_offset=dst_port_low_offset,
        )
