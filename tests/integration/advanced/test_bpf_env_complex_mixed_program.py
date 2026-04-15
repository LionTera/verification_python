"""Advanced mixed-program test with richer packets and register snapshots.

This test builds a longer BPF filter that combines:

- absolute loads
- indirect loads via `ldxb 4*([k] & 0xf)`
- an ALU mask
- `jeq`, `jge`, and `jset` branches

It also uses richer packet generation than the simple TCP/UDP tests by varying:

- DSCP/ECN
- TTL
- TCP flags
- destination port
- IPv4 option length
- payload signature

The goal is to exercise a more realistic filter path and capture A/X/PC
snapshots after each packet run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import (
    BPF_ALU,
    BPF_AND,
    BPF_B,
    BPF_JEQ,
    BPF_JGE,
    BPF_JMP,
    BPF_JSET,
    BPF_K,
    BPF_LD,
    BPF_LDX,
    BPF_MSH,
    BpfPythonTB,
    bpf_ldb_abs,
    bpf_ret_a,
    bpf_ret_k,
    encode_bpf_instruction,
    full_artifacts_enabled,
    program_report_markdown,
    reports_enabled,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.packet_generator import PacketSpec, build_packet, derive_packet


def _stmt(code: int, k: int = 0) -> int:
    """Encode a non-branch instruction."""
    return encode_bpf_instruction(code, k=k)


def _jump(code: int, k: int, jt: int, jf: int) -> int:
    """Encode a branch instruction."""
    return encode_bpf_instruction(code, k=k, jt=jt, jf=jf)


def _probe_program(packet: bytes, program: list[int], trace_name: str, *, label: str):
    """Run a small probe program on one packet to discover field offsets."""
    dut = build_bpf_env(waveform=waveform_path_for_test(Path(trace_name).stem, probe=True))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / trace_name, emit_reports=full_artifacts_enabled())
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


def discover_offset(
    packet_a: bytes,
    expected_a: int,
    packet_b: bytes,
    expected_b: int,
    candidate_offsets: range,
    *,
    name: str,
) -> int:
    """Search for the DUT-visible byte offset that yields the expected values."""
    print(f"Probing {name} offsets")
    for offset in candidate_offsets:
        program = [bpf_ldb_abs(offset), bpf_ret_a()]
        result_a = _probe_program(
            packet_a,
            program,
            f"bpf_probe_complex_{name}_a_off_{offset}.csv",
            label=f"Probe complex {name} offset {offset} packet A",
        )
        result_b = _probe_program(
            packet_b,
            program,
            f"bpf_probe_complex_{name}_b_off_{offset}.csv",
            label=f"Probe complex {name} offset {offset} packet B",
        )
        if result_a.ret_value == expected_a and result_b.ret_value == expected_b:
            print(f"Selected {name} offset: {offset}")
            return offset
    raise AssertionError(f"Could not discover {name} offset for this RTL")


def _alu_and_k(value: int) -> int:
    return _stmt(BPF_ALU | BPF_AND | BPF_K, value)


def _ldxb_msh(offset: int) -> int:
    return _stmt(BPF_LDX | BPF_B | BPF_MSH, offset)


def _ldb_ind(offset: int) -> int:
    return _stmt(BPF_LD | BPF_B | 0x40, offset)


def _jeq_k(value: int, *, jt: int, jf: int) -> int:
    return _jump(BPF_JMP | BPF_JEQ | BPF_K, value, jt, jf)


def _jge_k(value: int, *, jt: int, jf: int) -> int:
    return _jump(BPF_JMP | BPF_JGE | BPF_K, value, jt, jf)


def _jset_k(value: int, *, jt: int, jf: int) -> int:
    return _jump(BPF_JMP | BPF_JSET | BPF_K, value, jt, jf)


def make_complex_filter(
    *,
    protocol_offset: int,
    ttl_offset: int,
    dscp_offset: int,
    version_ihl_offset: int,
    flags_rel_offset: int,
    dst_port_rel_offset: int,
    payload_rel_offset: int,
) -> list[int]:
    """Build a mixed-type filter program for richer packet validation."""
    return [
        bpf_ldb_abs(protocol_offset),
        _jeq_k(0x06, jt=0, jf=12),
        bpf_ldb_abs(ttl_offset),
        _jge_k(64, jt=0, jf=10),
        bpf_ldb_abs(dscp_offset),
        _alu_and_k(0xFC),
        _jeq_k(0x28, jt=0, jf=7),
        _ldxb_msh(version_ihl_offset),
        _ldb_ind(flags_rel_offset),
        _jset_k(0x02, jt=0, jf=4),
        _ldb_ind(dst_port_rel_offset),
        _jeq_k(0x78, jt=0, jf=2),
        _ldb_ind(payload_rel_offset),
        _jeq_k(0xD1, jt=1, jf=0),
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def append_complex_report(
    report_path: Path,
    *,
    offsets: dict[str, int],
    program: list[int],
    history: list[dict[str, object]],
) -> None:
    """Append complex-program run details to the shared report."""
    lines = [
        "",
        "## Complex Mixed Program",
        "",
        "### Discovered Offsets",
        "",
        f"- Protocol offset: `{offsets['protocol']}`",
        f"- TTL offset: `{offsets['ttl']}`",
        f"- DSCP/ECN offset: `{offsets['dscp']}`",
        f"- Version/IHL offset: `{offsets['version_ihl']}`",
        f"- TCP flags relative offset: `{offsets['flags_rel']}`",
        f"- TCP dst-port-low relative offset: `{offsets['dst_port_rel']}`",
        f"- Payload-first-byte relative offset: `{offsets['payload_rel']}`",
        "",
        "### Program",
        "",
        program_report_markdown(program),
        "### Packet Results",
        "",
        "| Name | Expected Accept | Actual Accept | Return Value | ACC | X | PC | Packet Bytes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in history:
        lines.append(
            f"| `{item['name']}` | `{item['expected_accept']}` | `{item['actual_accept']}` | "
            f"`0x{item['ret_value']:08x}` | `0x{item['acc']:08x}` | `0x{item['x_reg']:08x}` | "
            f"`0x{item['pc']:08x}` | `{item['packet'].hex()}` |"
        )
    with report_path.open("a", encoding="utf-8") as report_file:
        report_file.write("\n".join(lines))


@pytest.mark.integration
@pytest.mark.slow
def test_bpf_env_complex_mixed_program():
    """Run a richer filter against several complex packet variants."""
    if not verilator_available():
        pytest.skip("verilator is not installed")

    base_spec = PacketSpec(
        l4="tcp",
        src_mac=bytes.fromhex("112233445566"),
        dst_mac=bytes.fromhex("aabbccddeeff"),
        src_ip="10.10.1.1",
        dst_ip="192.0.2.99",
        dscp_ecn=0x28,
        ttl=64,
        src_port=0x1200,
        dst_port=0x5678,
        seq=0x01020304,
        ack=0xA1B2C3D4,
        flags=0x12,
        payload=bytes.fromhex("d1adbeef"),
        name="tcp_pass",
        metadata={"expected_accept": True},
    )

    pass_packet = build_packet(base_spec)
    pass_options_packet = build_packet(
        derive_packet(
            base_spec,
            ip_options=bytes.fromhex("01010101"),
            name="tcp_pass_options",
            payload=bytes.fromhex("d1adbeef"),
        )
    )
    udp_packet = build_packet(derive_packet(base_spec, l4="udp", name="udp_reject", metadata={"expected_accept": False}))
    low_ttl_packet = build_packet(derive_packet(base_spec, ttl=32, name="tcp_low_ttl", metadata={"expected_accept": False}))
    wrong_dscp_packet = build_packet(derive_packet(base_spec, dscp_ecn=0x00, name="tcp_wrong_dscp", metadata={"expected_accept": False}))
    wrong_flags_packet = build_packet(derive_packet(base_spec, flags=0x10, name="tcp_wrong_flags", metadata={"expected_accept": False}))
    wrong_port_packet = build_packet(derive_packet(base_spec, dst_port=0x56BB, name="tcp_wrong_port", metadata={"expected_accept": False}))
    wrong_payload_packet = build_packet(derive_packet(base_spec, payload=bytes.fromhex("aaadbeef"), name="tcp_wrong_payload", metadata={"expected_accept": False}))

    protocol_offset = discover_offset(pass_packet, 0x06, udp_packet, 0x11, range(16, 28), name="protocol")
    ttl_offset = discover_offset(pass_packet, 64, low_ttl_packet, 32, range(16, 28), name="ttl")
    dscp_offset = discover_offset(pass_packet, 0x28, wrong_dscp_packet, 0x00, range(12, 20), name="dscp")
    version_ihl_offset = discover_offset(pass_packet, 0x45, pass_options_packet, 0x46, range(12, 20), name="version_ihl")
    flags_abs_offset = discover_offset(pass_packet, 0x12, wrong_flags_packet, 0x10, range(40, 56), name="tcp_flags")
    dst_port_low_abs_offset = discover_offset(pass_packet, 0x78, wrong_port_packet, 0xBB, range(34, 50), name="dst_port_low")
    payload_first_abs_offset = discover_offset(pass_packet, 0xD1, wrong_payload_packet, 0xAA, range(46, 64), name="payload_first")

    base_ihl = (pass_packet[14] & 0x0F) * 4
    offsets = {
        "protocol": protocol_offset,
        "ttl": ttl_offset,
        "dscp": dscp_offset,
        "version_ihl": version_ihl_offset,
        "flags_rel": flags_abs_offset - base_ihl,
        "dst_port_rel": dst_port_low_abs_offset - base_ihl,
        "payload_rel": payload_first_abs_offset - base_ihl,
    }

    program = make_complex_filter(
        protocol_offset=offsets["protocol"],
        ttl_offset=offsets["ttl"],
        dscp_offset=offsets["dscp"],
        version_ihl_offset=offsets["version_ihl"],
        flags_rel_offset=offsets["flags_rel"],
        dst_port_rel_offset=offsets["dst_port_rel"],
        payload_rel_offset=offsets["payload_rel"],
    )

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_complex_mixed_program"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_complex_mixed_program.csv")
    tb.init_signals()
    tb.load_program(program)
    tb.print_program()

    cases = [
        ("tcp_pass", pass_packet, True),
        ("tcp_pass_options", pass_options_packet, True),
        ("udp_reject", udp_packet, False),
        ("tcp_low_ttl", low_ttl_packet, False),
        ("tcp_wrong_dscp", wrong_dscp_packet, False),
        ("tcp_wrong_flags", wrong_flags_packet, False),
        ("tcp_wrong_port", wrong_port_packet, False),
        ("tcp_wrong_payload", wrong_payload_packet, False),
    ]

    history: list[dict[str, object]] = []
    for name, packet, expected_accept in cases:
        print(f"Complex mixed-program case: {name}")
        tb.load_packet(packet)
        tb.configure_start_address(0)
        tb.pulse_start()
        result = tb.run_until_return(max_cycles=256)
        tb.print_run_result(result)
        history.append(
            {
                "name": name,
                "packet": packet,
                "expected_accept": expected_accept,
                "actual_accept": result.accepted,
                "ret_value": result.ret_value,
                "acc": int(tb.dut.bpf_acc),
                "x_reg": int(tb.dut.bpf_x),
                "pc": int(tb.dut.bpf_pc),
            }
        )
        assert result.returned
        assert result.accepted == expected_accept

    if reports_enabled():
        append_complex_report(tb.report_path, offsets=offsets, program=program, history=history)
        assert tb.trace_path.exists()
        assert tb.report_path.exists()
