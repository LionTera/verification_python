"""Generated BPF program profiles with randomized packets and a golden model.

This test family is meant to scale from short filters to longer mixed-op
programs. Each profile uses:

- deterministic packet generation with selected randomized fields
- offset discovery against the DUT-visible packet layout
- a generated BPF program
- a Python-side golden model based on the packet specification
- final A/X/PC snapshots per packet
"""

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
    PROGRAM_PROFILES,
    FieldProbe,
    build_profile_program,
    build_profile_probes,
    evaluate_profile_accept,
    finalize_profile_offsets,
)


UNIQUE_PACKETS_ENV_VAR = "BPF_UNIQUE_PACKETS"
PROTOCOL_MODE_ENV_VAR = "BPF_PROTOCOL_MODE"
RNG_SEED_ENV_VAR = "BPF_PACKET_RNG_SEED"
RANDOMIZE_FIELDS_ENV_VAR = "BPF_RANDOMIZE_FIELDS"

DEFAULT_UNIQUE_PACKETS = 24
DEFAULT_PROTOCOL_MODE = 3
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


def _get_randomize_fields_env() -> tuple[str, ...]:
    """Read the selected randomization field list from the environment."""
    return tuple(field.strip() for field in os.environ.get(RANDOMIZE_FIELDS_ENV_VAR, "").split(",") if field.strip())


def _merge_randomize_fields(*groups: tuple[str, ...]) -> tuple[str, ...]:
    """Merge randomization field lists while preserving order."""
    ordered: list[str] = []
    for group in groups:
        for field in group:
            if field not in ordered:
                ordered.append(field)
    return tuple(ordered)


def load_config_for_profile(profile_name: str, *, recommended_randomize_fields: tuple[str, ...]) -> TrafficConfig:
    """Load one profile-specific traffic configuration from the environment."""
    return TrafficConfig(
        unique_packets=_get_positive_int_env(UNIQUE_PACKETS_ENV_VAR, DEFAULT_UNIQUE_PACKETS),
        protocol_mode=_get_positive_int_env(PROTOCOL_MODE_ENV_VAR, DEFAULT_PROTOCOL_MODE),
        error_level=1,
        seed=_get_positive_int_env(RNG_SEED_ENV_VAR, DEFAULT_RNG_SEED) ^ (sum(ord(ch) for ch in profile_name) << 4),
        randomize_fields=_merge_randomize_fields(_get_randomize_fields_env(), recommended_randomize_fields),
    )


def _probe_program(packet: bytes, program: list[int], trace_name: str, *, label: str):
    """Run a short probe program on one packet to discover one field offset."""
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
            f"bpf_probe_generated_{profile_name}_{probe.name}_a_off_{offset}.csv",
            label=f"Probe {profile_name} {probe.name} offset {offset} packet A",
        )
        result_b = _probe_program(
            probe.packet_b,
            program,
            f"bpf_probe_generated_{profile_name}_{probe.name}_b_off_{offset}.csv",
            label=f"Probe {profile_name} {probe.name} offset {offset} packet B",
        )
        if result_a.ret_value == probe.expected_a and result_b.ret_value == probe.expected_b:
            print(f"Selected {profile_name} {probe.name} offset: {offset}")
            return offset
    raise AssertionError(f"Could not discover {probe.name} offset for profile {profile_name}")


def _collect_return_cycles(trace_rows: list[dict[str, int | str]], *, accepted: bool) -> list[int]:
    """Collect cycles where the DUT returned with the requested accept bit."""
    target_accept = 1 if accepted else 0
    cycles: list[int] = []
    prev_return = 0
    for row in trace_rows:
        current_return = int(row["bpf_return"])
        if current_return == 1 and prev_return == 0 and int(row["bpf_accept"]) == target_accept:
            cycles.append(int(row["cycle"]))
        prev_return = current_return
    return cycles


def append_profile_report(
    report_path: Path,
    *,
    profile_name: str,
    profile_description: str,
    config: TrafficConfig,
    offsets: dict[str, int],
    program: list[int],
    golden_model: GoldenModelTracker,
    actual_accept_cycles: list[int],
    actual_reject_cycles: list[int],
    history: list[dict[str, object]],
) -> None:
    """Append test-level profile summary to the shared Markdown report."""
    sections = [
        "",
        f"## Generated Program Profile: {profile_name}",
        "",
        profile_description,
        "",
        f"- Unique packets: `{config.unique_packets}`",
        f"- Protocol mode: `{config.protocol_mode}`",
        f"- RNG seed: `0x{config.seed:08x}`",
        f"- Randomized fields: `{', '.join(config.randomize_fields) or 'none'}`",
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
            program_report_markdown(program),
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
            "| Index | Name | Protocol | Expected Accept | Actual Accept | Return Value | ACC | X | PC | Packet Length |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in history:
        sections.append(
            f"| `{item['index']}` | `{item['name']}` | `{item['protocol']}` | `{item['expected_accept']}` | "
            f"`{item['actual_accept']}` | `0x{item['ret_value']:08x}` | `0x{item['acc']:08x}` | "
            f"`0x{item['x_reg']:08x}` | `0x{item['pc']:08x}` | `{item['packet_length']}` |"
        )
    append_markdown_sections(report_path, sections)


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.parametrize("profile", PROGRAM_PROFILES, ids=[profile.name for profile in PROGRAM_PROFILES])
def test_bpf_env_generated_program_profiles(profile):
    """Run generated short/medium/long BPF programs against randomized packet streams."""
    if not verilator_available():
        pytest.skip("verilator is not installed")

    config = load_config_for_profile(profile.name, recommended_randomize_fields=profile.recommended_randomize_fields)
    traffic = generate_configurable_packet_stream(config)

    discovered_offsets = {
        probe.name: discover_offset(probe, profile_name=profile.name)
        for probe in build_profile_probes(profile)
    }
    final_offsets = finalize_profile_offsets(profile, discovered_offsets)
    program = build_profile_program(profile, final_offsets)

    dut = build_bpf_env(waveform=waveform_path_for_test(f"test_bpf_env_generated_program_profiles_{profile.name}"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / f"bpf_generated_program_{profile.name}.csv")
    tb.init_signals()
    tb.load_program(program)
    tb.print_program()

    golden_model = GoldenModelTracker()
    history: list[dict[str, object]] = []

    for item in traffic:
        spec = item["spec"]
        packet = item["packet"]
        expected_accept = evaluate_profile_accept(profile, spec)

        print(f"Generated program profile={profile.name} packet={item['name']} expected_accept={expected_accept}")
        tb.load_packet(packet)
        tb.configure_start_address(0)
        tb.pulse_start()
        result = tb.run_until_return(max_cycles=256)
        tb.print_run_result(result)
        tb.print_register_snapshot()

        assert result.returned
        assert result.accepted == expected_accept
        return_cycle = result.cycles - 1

        golden_model.record(
            event_type="accept" if expected_accept else "reject",
            cycle=return_cycle,
            reason=profile.name,
            item_index=int(item["index"]),
            entered_bpf=True,
            name=str(item["name"]),
            protocol=str(spec.l4),
            start_cycle=None,
            end_cycle=return_cycle,
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
                "return_cycle": return_cycle,
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
        append_profile_report(
            tb.report_path,
            profile_name=profile.name,
            profile_description=profile.description,
            config=config,
            offsets=final_offsets,
            program=program,
            golden_model=golden_model,
            actual_accept_cycles=actual_accept_cycles,
            actual_reject_cycles=actual_reject_cycles,
            history=history,
        )
        assert tb.trace_path.exists()
        assert tb.report_path.exists()
