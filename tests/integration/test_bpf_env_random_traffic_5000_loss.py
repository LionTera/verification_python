from __future__ import annotations

import random
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
    full_artifacts_enabled,
    program_report_markdown,
    reports_enabled,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.packets import make_tcp_packet, make_udp_packet


PACKET_COUNT = 5000
LOSS_PERCENT = 5
LOSS_COUNT = PACKET_COUNT * LOSS_PERCENT // 100
RNG_SEED = 0x5EED5EED
PROGRESS_INTERVAL = 250


def _probe_program(packet: bytes, program: list[int], trace_name: str, *, label: str):
    dut = build_bpf_env(waveform=waveform_path_for_test(Path(trace_name).stem, probe=True))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / trace_name, emit_reports=full_artifacts_enabled())
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
            f"bpf_probe_random5000_{name}_a_off_{offset}.csv",
            label=f"Probe random5000 {name} offset {offset} packet A",
        )
        result_b = _probe_program(
            packet_b,
            program,
            f"bpf_probe_random5000_{name}_b_off_{offset}.csv",
            label=f"Probe random5000 {name} offset {offset} packet B",
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


def generate_packet_stream(count: int, *, seed: int) -> list[dict[str, object]]:
    rng = random.Random(seed)
    items: list[dict[str, object]] = []
    for index in range(count):
        selector = rng.random()
        seq = 0x01000000 + index
        ack = 0xA1000000 + index
        src_port = 0x1200 + (index % 200)
        payload = index.to_bytes(4, "big")
        common_kwargs = {
            "dst_mac": bytes.fromhex("aabbccddeeff"),
            "src_mac": bytes.fromhex("112233445566"),
            "src_ip": f"10.1.{(index // 256) % 256}.{index % 256}",
            "dst_ip": "192.0.2.99",
            "src_port": src_port,
            "payload": payload,
        }
        if selector < 0.45:
            packet = make_tcp_packet(
                dst_port=0x5678,
                seq=seq,
                ack=ack,
                flags=0x12,
                **common_kwargs,
            )
            kind = "tcp_accept"
            expected_accept = True
        elif selector < 0.85:
            packet = make_tcp_packet(
                dst_port=0x56BB,
                seq=seq,
                ack=ack,
                flags=0x12,
                **common_kwargs,
            )
            kind = "tcp_reject"
            expected_accept = False
        else:
            packet = make_udp_packet(
                dst_port=0x5678,
                **common_kwargs,
            )
            kind = "udp_reject"
            expected_accept = False
        items.append(
            {
                "index": index,
                "kind": kind,
                "expected_accept": expected_accept,
                "packet": packet,
            }
        )
    return items


def append_random_traffic_report(
    report_path: Path,
    *,
    traffic_history: list[dict[str, object]],
    loss_events: list[dict[str, int]],
    program: list[int],
    protocol_offset: int,
    dst_port_low_offset: int,
) -> None:
    accept_total = sum(1 for item in traffic_history if item["expected_accept"])
    reject_total = len(traffic_history) - accept_total
    lines = [
        "",
        "## Random Traffic Stress Summary",
        "",
        f"- Packet count: `{PACKET_COUNT}`",
        f"- Loss percent target: `{LOSS_PERCENT}%`",
        f"- Loss event count: `{LOSS_COUNT}`",
        f"- RNG seed: `0x{RNG_SEED:08x}`",
        f"- Protocol offset used by filter: `{protocol_offset}`",
        f"- Destination-port low-byte offset used by filter: `{dst_port_low_offset}`",
        f"- Expected accepted packets: `{accept_total}`",
        f"- Expected rejected packets: `{reject_total}`",
        "",
        "## Filter Program Used For Random Traffic",
        "",
        program_report_markdown(program),
        "## Golden Loss Events",
        "",
        "| Loss Event | Packet Index | Assert Cycle | Release Cycle | Expected Loss Counter After Pulse |",
        "| --- | --- | --- | --- | --- |",
    ]
    for event_index, event in enumerate(loss_events):
        lines.append(
            f"| `{event_index}` | `{event['packet_index']}` | `{event['assert_cycle']}` | "
            f"`{event['release_cycle']}` | `{event['expected_loss_count']}` |"
        )

    lines.extend(
        [
            "",
            "## Packet Stream Golden Model",
            "",
            "| Index | Kind | Expected Accept | Loss Injected | Loss Assert Cycle | Start Pulse Cycle | Return Cycle | Expected Accept Count | Expected Reject Count | Expected Loss Count | Raw Bytes |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in traffic_history:
        loss_assert_cycle = item["loss_assert_cycle"]
        lines.append(
            f"| `{item['index']}` | `{item['kind']}` | `{item['expected_accept']}` | `{item['loss_injected']}` | "
            f"`{loss_assert_cycle if loss_assert_cycle is not None else '-'}` | `{item['start_cycle']}` | "
            f"`{item['return_cycle']}` | `{item['expected_accept_count']}` | `{item['expected_reject_count']}` | "
            f"`{item['expected_loss_count']}` | `{item['packet'].hex()}` |"
        )

    with report_path.open("a", encoding="utf-8") as report_file:
        report_file.write("\n".join(lines))


@pytest.mark.integration
@pytest.mark.slow
def test_bpf_env_random_traffic_5000_loss():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    tcp_accept_probe = make_tcp_packet(
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
    tcp_reject_probe = make_tcp_packet(
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
    udp_probe = make_udp_packet(
        dst_mac=bytes.fromhex("aabbccddeeff"),
        src_mac=bytes.fromhex("112233445566"),
        src_ip="10.1.2.3",
        dst_ip="192.0.2.99",
        src_port=0x1234,
        dst_port=0x5678,
        payload=bytes.fromhex("deadbeef"),
    )

    protocol_offset = discover_offset(tcp_accept_probe, 0x06, udp_probe, 0x11, range(20, 28), name="protocol")
    dst_port_low_offset = discover_offset(
        tcp_accept_probe,
        0x78,
        tcp_reject_probe,
        0xBB,
        range(34, 42),
        name="dst_port_low",
    )
    program = make_tcp_dst_filter(protocol_offset, dst_port_low_offset, accepted_low_byte=0x78)

    traffic = generate_packet_stream(PACKET_COUNT, seed=RNG_SEED)
    loss_indices = set(random.Random(RNG_SEED ^ 0xA5A5A5A5).sample(range(PACKET_COUNT), LOSS_COUNT))

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_random_traffic_5000_loss"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_random_traffic_5000_loss.csv")
    tb.init_signals()
    print("Random traffic 5000-packet packet-loss stress test")
    print(f"RNG seed=0x{RNG_SEED:08x} packet_count={PACKET_COUNT} loss_count={LOSS_COUNT}")
    print(f"Using protocol offset={protocol_offset}, dst_port_low_offset={dst_port_low_offset}")
    tb.load_program(program)
    tb.print_program()
    tb.write_mmap(BPF_ACCEPT_COUNTER_ADDR, 0)
    tb.write_mmap(BPF_REJECT_COUNTER_ADDR, 0)
    tb.write_mmap(BPF_PACKET_LOSS_COUNTER_ADDR, 0)

    accept_expected = 0
    reject_expected = 0
    loss_expected = 0
    loss_events: list[dict[str, int]] = []
    traffic_history: list[dict[str, object]] = []

    for item in traffic:
        index = int(item["index"])
        packet = item["packet"]
        expected_accept = bool(item["expected_accept"])
        tb.load_packet(packet)

        loss_assert_cycle: int | None = None
        if index in loss_indices:
            loss_assert_cycle = tb.current_cycle
            tb.set_packet_loss(1)
            tb.step(1)
            tb.set_packet_loss(0)
            tb.step(1)
            loss_expected += 1
            loss_events.append(
                {
                    "packet_index": index,
                    "assert_cycle": loss_assert_cycle,
                    "release_cycle": tb.current_cycle,
                    "expected_loss_count": loss_expected,
                }
            )

        start_cycle = tb.current_cycle
        tb.configure_start_address(0)
        tb.pulse_start()
        result = tb.run_until_return(max_cycles=128)

        assert result.returned
        assert result.accepted is expected_accept
        tb.step(1)

        if expected_accept:
            accept_expected += 1
        else:
            reject_expected += 1

        traffic_history.append(
            {
                "index": index,
                "kind": item["kind"],
                "packet": packet,
                "expected_accept": expected_accept,
                "loss_injected": index in loss_indices,
                "loss_assert_cycle": loss_assert_cycle,
                "start_cycle": start_cycle,
                "return_cycle": result.cycles,
                "expected_accept_count": accept_expected,
                "expected_reject_count": reject_expected,
                "expected_loss_count": loss_expected,
            }
        )

        should_check = index in loss_indices or index == PACKET_COUNT - 1 or ((index + 1) % PROGRESS_INTERVAL == 0)
        if should_check:
            accept_now = tb.read_mmap(BPF_ACCEPT_COUNTER_ADDR)
            reject_now = tb.read_mmap(BPF_REJECT_COUNTER_ADDR)
            loss_now = tb.read_mmap(BPF_PACKET_LOSS_COUNTER_ADDR)
            assert accept_now == accept_expected
            assert reject_now == reject_expected
            assert loss_now == loss_expected
            print(
                f"Progress packet {index + 1}/{PACKET_COUNT}: "
                f"accept={accept_now} reject={reject_now} loss={loss_now}"
            )

        for _ in range(8):
            if not int(tb.dut.bpf_return) and not int(tb.dut.bpf_active):
                break
            tb.step(1)

    accept_count = tb.read_mmap(BPF_ACCEPT_COUNTER_ADDR)
    reject_count = tb.read_mmap(BPF_REJECT_COUNTER_ADDR)
    packet_loss_count = tb.read_mmap(BPF_PACKET_LOSS_COUNTER_ADDR)

    assert accept_count == accept_expected
    assert reject_count == reject_expected
    assert packet_loss_count == LOSS_COUNT

    if reports_enabled():
        assert tb.trace_path.exists()
        assert tb.report_path.exists()
        append_random_traffic_report(
            tb.report_path,
            traffic_history=traffic_history,
            loss_events=loss_events,
            program=program,
            protocol_offset=protocol_offset,
            dst_port_low_offset=dst_port_low_offset,
        )
