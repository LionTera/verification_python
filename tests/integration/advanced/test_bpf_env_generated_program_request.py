"""Request-driven generated BPF program test with randomized traffic and a golden model."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import (
    BpfPythonTB,
    bpf_ldb_abs,
    bpf_ret_a,
    program_report_markdown,
    reports_enabled,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.golden_model import (
    GoldenModelTracker,
    append_markdown_sections,
    event_cycles_comparison_markdown,
    golden_events_markdown,
)
from tests.bpf_env.packet_generator import TrafficConfig, generate_configurable_packet_stream
from tests.bpf_env.program_generator import (
    FieldProbe,
    GeneratedProgramProfile,
    ProgramRequest,
    RandomnessLevel,
    build_profile_program,
    build_profile_probes,
    evaluate_profile_accept,
    finalize_profile_offsets,
    generate_program,
)


UNIQUE_PACKETS_ENV_VAR = "BPF_UNIQUE_PACKETS"
PROTOCOL_MODE_ENV_VAR = "BPF_PROTOCOL_MODE"
RNG_SEED_ENV_VAR = "BPF_PACKET_RNG_SEED"
RANDOMIZE_FIELDS_ENV_VAR = "BPF_RANDOMIZE_FIELDS"
PAYLOAD_LEN_MIN_ENV_VAR = "BPF_PAYLOAD_LEN_MIN"
PAYLOAD_LEN_MAX_ENV_VAR = "BPF_PAYLOAD_LEN_MAX"
PROGRAM_RANDOMNESS_ENV_VAR = "BPF_PROGRAM_RANDOMNESS"
PROGRAM_TTL_MIN_ENV_VAR = "BPF_PROGRAM_TTL_MIN"
PROGRAM_TCP_FLAGS_MASK_ENV_VAR = "BPF_PROGRAM_TCP_FLAGS_MASK"
PROGRAM_MIN_PACKET_LEN_ENV_VAR = "BPF_PROGRAM_MIN_PACKET_LEN"

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


def _get_nonnegative_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    value = int(raw, 0)
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")
    return value


def _get_randomize_fields_env() -> tuple[str, ...]:
    return tuple(field.strip() for field in os.environ.get(RANDOMIZE_FIELDS_ENV_VAR, "").split(",") if field.strip())


def load_traffic_config() -> TrafficConfig:
    """Load request-driven traffic settings from the environment."""
    return TrafficConfig(
        unique_packets=_get_positive_int_env(UNIQUE_PACKETS_ENV_VAR, DEFAULT_UNIQUE_PACKETS),
        protocol_mode=_get_positive_int_env(PROTOCOL_MODE_ENV_VAR, DEFAULT_PROTOCOL_MODE),
        error_level=1,
        seed=_get_positive_int_env(RNG_SEED_ENV_VAR, DEFAULT_RNG_SEED),
        randomize_fields=_get_randomize_fields_env(),
        payload_len_min=_get_nonnegative_int_env(PAYLOAD_LEN_MIN_ENV_VAR, 0),
        payload_len_max=_get_nonnegative_int_env(PAYLOAD_LEN_MAX_ENV_VAR, 32),
    )


def load_program_request() -> ProgramRequest:
    """Load one request-driven BPF program definition from the environment."""
    randomness = os.environ.get(PROGRAM_RANDOMNESS_ENV_VAR, "low").strip().lower() or "low"
    return ProgramRequest(
        target_ops=12,
        tolerance=4,
        randomness=RandomnessLevel(randomness),
        seed=None,
        require_tcp=True,
        use_ttl=True,
        ttl_mode="ge",
        ttl_min=_get_positive_int_env(PROGRAM_TTL_MIN_ENV_VAR, 33),
        use_tcp_flags=True,
        tcp_flags_mask=int(os.environ.get(PROGRAM_TCP_FLAGS_MASK_ENV_VAR, "0x02"), 0),
        use_packet_len=True,
        min_packet_len=_get_positive_int_env(PROGRAM_MIN_PACKET_LEN_ENV_VAR, 251),
    )


def _probe_program(packet: bytes, program: list[int], trace_name: str, *, label: str):
    dut = build_bpf_env(waveform=waveform_path_for_test(Path(trace_name).stem, probe=True))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / trace_name)
    tb.init_signals()
    print(label)
    tb.load_packet(packet)
    tb.load_program(program)
    tb.print_program()
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=128)
    tb.print_run_result(result)
    return result


def discover_offset(probe: FieldProbe, *, profile_name: str) -> int:
    """Search for one DUT-visible offset using a probe definition."""
    print(f"Probing {profile_name} field {probe.name}")
    for offset in probe.candidate_offsets:
        program = [bpf_ldb_abs(offset), bpf_ret_a()]
        result_a = _probe_program(
            probe.packet_a,
            program,
            f"bpf_probe_generated_request_{profile_name}_{probe.name}_a_off_{offset}.csv",
            label=f"Probe generated request {profile_name} {probe.name} offset {offset} packet A",
        )
        result_b = _probe_program(
            probe.packet_b,
            program,
            f"bpf_probe_generated_request_{profile_name}_{probe.name}_b_off_{offset}.csv",
            label=f"Probe generated request {profile_name} {probe.name} offset {offset} packet B",
        )
        if result_a.ret_value == probe.expected_a and result_b.ret_value == probe.expected_b:
            print(f"Selected {profile_name} {probe.name} offset: {offset}")
            return offset
    raise AssertionError(f"Could not discover {probe.name} offset for request-driven profile {profile_name}")


def _collect_return_cycles(trace_rows: list[dict[str, int | str]], *, accepted: bool) -> list[int]:
    target_accept = 1 if accepted else 0
    cycles: list[int] = []
    prev_return = 0
    for row in trace_rows:
        current_return = int(row["bpf_return"])
        if current_return == 1 and prev_return == 0 and int(row["bpf_accept"]) == target_accept:
            cycles.append(int(row["cycle"]))
        prev_return = current_return
    return cycles


def append_request_report(
    report_path: Path,
    *,
    request: ProgramRequest,
    config: TrafficConfig,
    offsets: dict[str, int],
    generated_program,
    golden_model: GoldenModelTracker,
    actual_accept_cycles: list[int],
    actual_reject_cycles: list[int],
    history: list[dict[str, object]],
) -> None:
    sections = [
        "",
        "## Generated Program Request",
        "",
        f"- Traffic seed: `0x{config.seed:08x}`",
        f"- Unique packets: `{config.unique_packets}`",
        f"- Protocol mode: `{config.protocol_mode}`",
        f"- Randomized fields: `{', '.join(config.randomize_fields) or 'none'}`",
        f"- Payload length range: `[{config.payload_len_min}, {config.payload_len_max}]`",
        f"- Program target ops: `{request.target_ops}`",
        f"- Program actual ops: `{generated_program.actual_ops}`",
        "",
        "### Offsets",
        "",
    ]
    for key, value in offsets.items():
        sections.append(f"- {key}: `{value}`")
    sections.extend(
        [
            "",
            "### Program",
            "",
            program_report_markdown(generated_program.program),
            event_cycles_comparison_markdown(
                title="Accept Cycle Comparison",
                expected_cycles=golden_model.cycles("accept"),
                actual_cycles=actual_accept_cycles,
            ),
            event_cycles_comparison_markdown(
                title="Reject Cycle Comparison",
                expected_cycles=golden_model.cycles("reject"),
                actual_cycles=actual_reject_cycles,
            ),
            golden_events_markdown(title="Golden Accept/Reject Events", events=golden_model.events),
            "## Packet Results",
            "",
            "| Index | Name | Protocol | Packet Length | Expected Accept | Actual Accept | Return Value | ACC | X | PC |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in history:
        sections.append(
            f"| `{item['index']}` | `{item['name']}` | `{item['protocol']}` | `{item['packet_length']}` | "
            f"`{item['expected_accept']}` | `{item['actual_accept']}` | `0x{item['ret_value']:08x}` | "
            f"`0x{item['acc']:08x}` | `0x{item['x_reg']:08x}` | `0x{item['pc']:08x}` |"
        )
    append_markdown_sections(report_path, sections)


@pytest.mark.integration
@pytest.mark.slow
def test_bpf_env_generated_program_request():
    """Run a custom generated BPF request against randomized traffic and a golden model."""
    if not verilator_available():
        pytest.skip("verilator is not installed")

    request = load_program_request()
    config = load_traffic_config()
    traffic = generate_configurable_packet_stream(config)

    request_profile = GeneratedProgramProfile(
        name="request_driven",
        level="custom",
        description="Request-driven generated program run.",
        recommended_randomize_fields=config.randomize_fields,
        request=request,
    )

    discovered_offsets = {
        probe.name: discover_offset(probe, profile_name=request_profile.name)
        for probe in build_profile_probes(request_profile)
    }
    final_offsets = finalize_profile_offsets(request_profile, discovered_offsets)
    generated_program = generate_program(request, final_offsets)
    program = build_profile_program(request_profile, final_offsets)

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_generated_program_request"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_generated_program_request.csv")
    tb.init_signals()
    tb.load_program(program)
    tb.print_program()

    golden_model = GoldenModelTracker()
    history: list[dict[str, object]] = []

    for item in traffic:
        spec = item["spec"]
        packet = item["packet"]
        expected_accept = evaluate_profile_accept(request_profile, spec)

        print(f"Generated request packet={item['name']} expected_accept={expected_accept}")
        tb.load_packet(packet)
        tb.configure_start_address(0)
        tb.pulse_start()
        result = tb.run_until_return(max_cycles=256)
        tb.print_run_result(result)
        tb.print_register_snapshot()

        assert result.returned
        assert result.accepted == expected_accept

        golden_model.record(
            event_type="accept" if expected_accept else "reject",
            cycle=result.cycles,
            reason="request_driven",
            item_index=int(item["index"]),
            entered_bpf=True,
            name=str(item["name"]),
            protocol=str(spec.l4),
            start_cycle=None,
            end_cycle=result.cycles,
        )
        history.append(
            {
                "index": int(item["index"]),
                "name": str(item["name"]),
                "protocol": spec.l4,
                "packet_length": len(packet),
                "expected_accept": expected_accept,
                "actual_accept": result.accepted,
                "ret_value": result.ret_value,
                "acc": int(tb.dut.bpf_acc),
                "x_reg": int(tb.dut.bpf_x),
                "pc": int(tb.dut.bpf_pc),
            }
        )

    actual_accept_cycles = _collect_return_cycles(tb.trace_rows, accepted=True)
    actual_reject_cycles = _collect_return_cycles(tb.trace_rows, accepted=False)
    golden_model.compare_cycles(actual_accept_cycles, "accept")
    golden_model.compare_cycles(actual_reject_cycles, "reject")

    if reports_enabled():
        append_request_report(
            tb.report_path,
            request=request,
            config=config,
            offsets=final_offsets,
            generated_program=generated_program,
            golden_model=golden_model,
            actual_accept_cycles=actual_accept_cycles,
            actual_reject_cycles=actual_reject_cycles,
            history=history,
        )
        assert tb.trace_path.exists()
        assert tb.report_path.exists()
