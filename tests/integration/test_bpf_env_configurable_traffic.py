"""Parameterized configurable-traffic test driven by CLI or environment settings."""

from __future__ import annotations

import os
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
from tests.bpf_env.network_ingress import drive_ingress_frame, read_counters
from tests.bpf_env.packet_generator import (
    EXPECTED_DST_MAC,
    TrafficConfig,
    describe_generated_item,
    generate_configurable_packet_stream,
)
from tests.bpf_env.packets import make_tcp_packet, make_udp_packet


UNIQUE_PACKETS_ENV_VAR = "BPF_UNIQUE_PACKETS"
PROTOCOL_MODE_ENV_VAR = "BPF_PROTOCOL_MODE"
ERROR_LEVEL_ENV_VAR = "BPF_ERROR_LEVEL"
RNG_SEED_ENV_VAR = "BPF_PACKET_RNG_SEED"

DEFAULT_UNIQUE_PACKETS = 32
DEFAULT_PROTOCOL_MODE = 3
DEFAULT_ERROR_LEVEL = 1
DEFAULT_RNG_SEED = 0x5EED5EED


def _get_positive_int_env(name: str, default: int) -> int:
    """Read a positive integer override from the environment."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    value = int(raw, 0)
    if value <= 0:
        raise ValueError(f"{name} must be > 0, got {value}")
    return value


def load_config() -> TrafficConfig:
    """Load configurable-traffic settings from the environment."""
    return TrafficConfig(
        unique_packets=_get_positive_int_env(UNIQUE_PACKETS_ENV_VAR, DEFAULT_UNIQUE_PACKETS),
        protocol_mode=_get_positive_int_env(PROTOCOL_MODE_ENV_VAR, DEFAULT_PROTOCOL_MODE),
        error_level=_get_positive_int_env(ERROR_LEVEL_ENV_VAR, DEFAULT_ERROR_LEVEL),
        seed=_get_positive_int_env(RNG_SEED_ENV_VAR, DEFAULT_RNG_SEED),
    )


def _probe_program(packet: bytes, program: list[int], trace_name: str, *, label: str):
    """Run a short probe program on one packet to discover field offsets."""
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
    """Search for the packet byte offset that yields the expected field values."""
    print(f"Probing {name} offsets")
    for offset in candidate_offsets:
        program = [bpf_ldb_abs(offset), bpf_ret_a()]
        result_a = _probe_program(
            packet_a,
            program,
            f"bpf_probe_configurable_{name}_a_off_{offset}.csv",
            label=f"Probe configurable {name} offset {offset} packet A",
        )
        result_b = _probe_program(
            packet_b,
            program,
            f"bpf_probe_configurable_{name}_b_off_{offset}.csv",
            label=f"Probe configurable {name} offset {offset} packet B",
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
    """Build the filter used by the configurable-traffic test."""
    return [
        bpf_ldb_abs(protocol_offset),
        bpf_jeq_k(0x06, jt=0, jf=2),
        bpf_ldb_abs(dst_port_low_offset),
        bpf_jeq_k(accepted_low_byte, jt=1, jf=0),
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def append_configurable_report(
    report_path: Path,
    *,
    config: TrafficConfig,
    traffic_history: list[dict[str, object]],
    protocol_offset: int,
    dst_port_low_offset: int,
    program: list[int],
) -> None:
    """Append configurable-traffic summary sections to the main report."""
    lines = [
        "",
        "## Configurable Traffic Run",
        "",
        f"- Unique packets: `{config.unique_packets}`",
        f"- Protocol mode: `{config.protocol_mode}`",
        f"- Error level: `{config.error_level}`",
        f"- RNG seed: `0x{config.seed:08x}`",
        f"- Protocol offset used by filter: `{protocol_offset}`",
        f"- Destination-port low-byte offset used by filter: `{dst_port_low_offset}`",
        "",
        "## Filter Program",
        "",
        program_report_markdown(program),
        "## Traffic Summary",
        "",
        "| Index | Name | Protocol | Ingress Error | Packet Loss Injected | Entered BPF | Expected Accept | Actual Accept | Accept Counter | Reject Counter | Loss Counter |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in traffic_history:
        lines.append(
            f"| `{item['index']}` | `{item['name']}` | `{item['protocol']}` | `{item['ingress_error']}` | "
            f"`{item['packet_loss_injected']}` | `{item['entered_bpf']}` | `{item['expected_accept']}` | "
            f"`{item['actual_accept']}` | `{item['accept_count']}` | `{item['reject_count']}` | `{item['loss_count']}` |"
        )
    with report_path.open("a", encoding="utf-8") as report_file:
        report_file.write("\n".join(lines))


@pytest.mark.integration
@pytest.mark.slow
def test_bpf_env_configurable_traffic():
    """Run the configurable traffic scenario and check its expected behavior."""
    if not verilator_available():
        pytest.skip("verilator is not installed")

    config = load_config()
    traffic = generate_configurable_packet_stream(config)

    tcp_accept_probe = make_tcp_packet(dst_mac=EXPECTED_DST_MAC, dst_port=0x5678, payload=bytes.fromhex("deadbeef"))
    tcp_reject_probe = make_tcp_packet(dst_mac=EXPECTED_DST_MAC, dst_port=0x56BB, payload=bytes.fromhex("deadbeef"))
    udp_probe = make_udp_packet(dst_mac=EXPECTED_DST_MAC, dst_port=0x5678, payload=bytes.fromhex("deadbeef"))

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

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_configurable_traffic"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_configurable_traffic.csv")
    tb.init_signals()
    print("Configurable traffic test")
    print(
        f"unique_packets={config.unique_packets} protocol_mode={config.protocol_mode} "
        f"error_level={config.error_level} seed=0x{config.seed:08x}"
    )
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

    for item in traffic:
        metadata = dict(item["metadata"])
        print(describe_generated_item(item))
        decision = drive_ingress_frame(tb, item["frame"], expected_dst_mac=EXPECTED_DST_MAC, packet_loss_cycles=1)
        actual_accept = None

        if decision.accepted:
            if metadata["packet_loss_injected"]:
                tb.set_packet_loss(1)
                tb.step(1)
                tb.set_packet_loss(0)
                tb.step(1)
                loss_expected += 1
            tb.configure_start_address(0)
            tb.pulse_start()
            result = tb.run_until_return(max_cycles=128)
            tb.print_run_result(result)
            actual_accept = result.accepted
            assert actual_accept is bool(metadata["expected_accept"])
            tb.step(1)
            if actual_accept:
                accept_expected += 1
            else:
                reject_expected += 1
        else:
            assert metadata["ingress_error"] != "none"
            loss_expected += 1

        accept_now, reject_now, loss_now = read_counters(tb)
        assert accept_now == accept_expected
        assert reject_now == reject_expected
        assert loss_now == loss_expected

        traffic_history.append(
            {
                "index": item["index"],
                "name": item["name"],
                "protocol": metadata["protocol"],
                "ingress_error": metadata["ingress_error"],
                "packet_loss_injected": metadata["packet_loss_injected"],
                "entered_bpf": decision.accepted,
                "expected_accept": metadata["expected_accept"],
                "actual_accept": actual_accept,
                "accept_count": accept_now,
                "reject_count": reject_now,
                "loss_count": loss_now,
            }
        )

        for _ in range(8):
            if not int(tb.dut.bpf_return) and not int(tb.dut.bpf_active):
                break
            tb.step(1)

    if reports_enabled():
        assert tb.trace_path.exists()
        assert tb.report_path.exists()
        append_configurable_report(
            tb.report_path,
            config=config,
            traffic_history=traffic_history,
            protocol_offset=protocol_offset,
            dst_port_low_offset=dst_port_low_offset,
            program=program,
        )
