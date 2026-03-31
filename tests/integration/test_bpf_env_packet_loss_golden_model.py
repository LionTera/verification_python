from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import (
    BPF_ACCEPT_COUNTER_ADDR,
    BPF_PACKET_LOSS_COUNTER_ADDR,
    BPF_REJECT_COUNTER_ADDR,
    BpfPythonTB,
    RET_K_OPCODE,
    encode_bpf_instruction,
    reports_enabled,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.network_ingress import drive_ingress_frame, read_counters, with_ethernet_fcs
from tests.bpf_env.packet_generator import EXPECTED_DST_MAC, TrafficConfig, generate_configurable_packet_stream


UNIQUE_PACKETS_ENV_VAR = "BPF_UNIQUE_PACKETS"
PROTOCOL_MODE_ENV_VAR = "BPF_PROTOCOL_MODE"
RNG_SEED_ENV_VAR = "BPF_PACKET_RNG_SEED"

DEFAULT_UNIQUE_PACKETS = 24
DEFAULT_PROTOCOL_MODE = 3
DEFAULT_RNG_SEED = 0x5EED5EED


def _get_positive_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    value = int(raw, 0)
    if value <= 0:
        raise ValueError(f"{name} must be > 0, got {value}")
    return value


def load_config() -> TrafficConfig:
    return TrafficConfig(
        unique_packets=_get_positive_int_env(UNIQUE_PACKETS_ENV_VAR, DEFAULT_UNIQUE_PACKETS),
        protocol_mode=_get_positive_int_env(PROTOCOL_MODE_ENV_VAR, DEFAULT_PROTOCOL_MODE),
        error_level=1,
        seed=_get_positive_int_env(RNG_SEED_ENV_VAR, DEFAULT_RNG_SEED),
    )


def _with_wrong_dst_mac(packet: bytes) -> bytes:
    updated = bytearray(packet)
    updated[0:6] = bytes.fromhex("001122334455")
    return with_ethernet_fcs(bytes(updated))


def build_loss_reason_schedule(config: TrafficConfig) -> list[dict[str, object]]:
    base_items = generate_configurable_packet_stream(config)
    scheduled: list[dict[str, object]] = []
    for item in base_items:
        index = int(item["index"])
        frame = with_ethernet_fcs(item["packet"])
        reason = "none"
        enters_bpf = True
        inject_random_loss = False

        selector = index % 4
        if selector == 1:
            frame = frame[:-4] + b"\x00\x00\x00\x00"
            reason = "bad_crc"
            enters_bpf = False
        elif selector == 2:
            frame = _with_wrong_dst_mac(item["packet"])
            reason = "wrong_dst_mac"
            enters_bpf = False
        elif selector == 3:
            reason = "random_loss"
            inject_random_loss = True

        scheduled.append(
            {
                **item,
                "frame": frame,
                "loss_reason": reason,
                "enters_bpf": enters_bpf,
                "inject_random_loss": inject_random_loss,
            }
        )
    return scheduled


def collect_loss_cycles(tb: BpfPythonTB) -> list[int]:
    return [int(row["cycle"]) for row in tb.trace_rows if int(row["bpf_packet_loss"]) == 1]


def append_loss_golden_report(
    report_path: Path,
    *,
    config: TrafficConfig,
    traffic_history: list[dict[str, object]],
    expected_loss_cycles: list[int],
    actual_loss_cycles: list[int],
) -> None:
    lines = [
        "",
        "## Packet Loss Golden Model",
        "",
        f"- Unique packets: `{config.unique_packets}`",
        f"- Protocol mode: `{config.protocol_mode}`",
        f"- RNG seed: `0x{config.seed:08x}`",
        f"- Expected loss count: `{len(expected_loss_cycles)}`",
        f"- Actual loss count: `{len(actual_loss_cycles)}`",
        f"- Loss cycle match: `{expected_loss_cycles == actual_loss_cycles}`",
        "",
        "## Loss Cycle Comparison",
        "",
        "| Event | Expected Cycle | Actual Cycle | Match |",
        "| --- | --- | --- | --- |",
    ]

    max_len = max(len(expected_loss_cycles), len(actual_loss_cycles))
    for index in range(max_len):
        expected_cycle = expected_loss_cycles[index] if index < len(expected_loss_cycles) else "-"
        actual_cycle = actual_loss_cycles[index] if index < len(actual_loss_cycles) else "-"
        lines.append(
            f"| `{index}` | `{expected_cycle}` | `{actual_cycle}` | `{expected_cycle == actual_cycle}` |"
        )

    lines.extend(
        [
            "",
            "## Golden Loss Events",
            "",
            "| Packet Index | Name | Protocol | Loss Reason | Entered BPF | Loss Assert Cycle | Loss Release Cycle | Expected Loss Counter | Actual Loss Counter | Start Cycle | Return Cycle |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in traffic_history:
        if item["loss_reason"] == "none":
            continue
        lines.append(
            f"| `{item['index']}` | `{item['name']}` | `{item['protocol']}` | `{item['loss_reason']}` | "
            f"`{item['entered_bpf']}` | `{item['loss_assert_cycle']}` | `{item['loss_release_cycle']}` | "
            f"`{item['expected_loss_count']}` | `{item['actual_loss_count']}` | `{item['start_cycle']}` | `{item['return_cycle']}` |"
        )

    lines.extend(
        [
            "",
            "## Traffic Summary",
            "",
            "| Index | Name | Protocol | Loss Reason | Entered BPF | Expected Accept | Actual Accept | Accept Counter | Reject Counter | Loss Counter |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in traffic_history:
        lines.append(
            f"| `{item['index']}` | `{item['name']}` | `{item['protocol']}` | `{item['loss_reason']}` | "
            f"`{item['entered_bpf']}` | `{item['expected_accept']}` | `{item['actual_accept']}` | "
            f"`{item['accept_count']}` | `{item['reject_count']}` | `{item['actual_loss_count']}` |"
        )

    with report_path.open("a", encoding="utf-8") as report_file:
        report_file.write("\n".join(lines))


@pytest.mark.integration
@pytest.mark.slow
def test_bpf_env_packet_loss_golden_model():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    config = load_config()
    traffic = build_loss_reason_schedule(config)
    program = [encode_bpf_instruction(RET_K_OPCODE, k=1)]

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_packet_loss_golden_model"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_packet_loss_golden_model.csv")
    tb.init_signals()
    print("Packet-loss golden-model test")
    print(
        f"unique_packets={config.unique_packets} protocol_mode={config.protocol_mode} "
        f"seed=0x{config.seed:08x}"
    )
    tb.load_program(program)
    tb.print_program()
    tb.write_mmap(BPF_ACCEPT_COUNTER_ADDR, 0)
    tb.write_mmap(BPF_REJECT_COUNTER_ADDR, 0)
    tb.write_mmap(BPF_PACKET_LOSS_COUNTER_ADDR, 0)

    accept_expected = 0
    reject_expected = 0
    loss_expected = 0
    traffic_history: list[dict[str, object]] = []
    expected_loss_cycles: list[int] = []

    for item in traffic:
        metadata = dict(item["metadata"])
        loss_reason = str(item["loss_reason"])
        loss_assert_cycle: int | None = None
        loss_release_cycle: int | None = None
        start_cycle: int | None = None
        return_cycle: int | None = None
        actual_accept: bool | None = None

        print(
            f"Traffic item {item['index']}: name={item['name']} protocol={metadata['protocol']} "
            f"loss_reason={loss_reason}"
        )
        decision = drive_ingress_frame(tb, item["frame"], expected_dst_mac=EXPECTED_DST_MAC, packet_loss_cycles=1)

        if not decision.accepted:
            loss_assert_cycle = tb.current_cycle - 2
            loss_release_cycle = tb.current_cycle
            expected_loss_cycles.append(loss_assert_cycle)
            loss_expected += 1
        else:
            if bool(item["inject_random_loss"]):
                loss_assert_cycle = tb.current_cycle
                expected_loss_cycles.append(loss_assert_cycle)
                tb.set_packet_loss(1)
                tb.step(1)
                tb.set_packet_loss(0)
                tb.step(1)
                loss_release_cycle = tb.current_cycle
                loss_expected += 1
            start_cycle = tb.current_cycle
            tb.configure_start_address(0)
            tb.pulse_start()
            result = tb.run_until_return(max_cycles=128)
            tb.print_run_result(result)
            return_cycle = result.cycles
            actual_accept = result.accepted
            assert result.returned
            assert actual_accept
            assert bool(metadata["expected_accept"]) in {True, False}
            tb.step(1)
            accept_expected += 1

        accept_now, reject_now, loss_now = read_counters(tb)
        assert accept_now == accept_expected
        assert reject_now == reject_expected
        assert loss_now == loss_expected

        traffic_history.append(
            {
                "index": item["index"],
                "name": item["name"],
                "protocol": metadata["protocol"],
                "loss_reason": loss_reason,
                "entered_bpf": decision.accepted,
                "loss_assert_cycle": loss_assert_cycle,
                "loss_release_cycle": loss_release_cycle,
                "expected_loss_count": loss_expected,
                "actual_loss_count": loss_now,
                "expected_accept": decision.accepted,
                "actual_accept": actual_accept,
                "accept_count": accept_now,
                "reject_count": reject_now,
                "start_cycle": start_cycle,
                "return_cycle": return_cycle,
            }
        )

        for _ in range(8):
            if not int(tb.dut.bpf_return) and not int(tb.dut.bpf_active):
                break
            tb.step(1)

    actual_loss_cycles = collect_loss_cycles(tb)
    assert actual_loss_cycles == expected_loss_cycles

    accept_count = tb.read_mmap(BPF_ACCEPT_COUNTER_ADDR)
    reject_count = tb.read_mmap(BPF_REJECT_COUNTER_ADDR)
    packet_loss_count = tb.read_mmap(BPF_PACKET_LOSS_COUNTER_ADDR)
    assert accept_count == accept_expected
    assert reject_count == reject_expected
    assert packet_loss_count == len(expected_loss_cycles)

    if reports_enabled():
        assert tb.trace_path.exists()
        assert tb.report_path.exists()
        append_loss_golden_report(
            tb.report_path,
            config=config,
            traffic_history=traffic_history,
            expected_loss_cycles=expected_loss_cycles,
            actual_loss_cycles=actual_loss_cycles,
        )
