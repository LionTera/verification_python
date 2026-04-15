from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import sys

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

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
    BPF_LEN,
    BPF_MSH,
    bpf_jeq_k,
    bpf_ldb_abs,
    bpf_ret_k,
    encode_bpf_instruction,
    format_bpf_program,
)
from tests.bpf_env.packet_generator import PacketSpec, build_packet, derive_packet


class RandomnessLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ProgramRequest:
    target_ops: int = 12
    tolerance: int = 2
    randomness: RandomnessLevel = RandomnessLevel.LOW
    seed: int | None = None

    require_tcp: bool = True

    use_ttl: bool = False
    ttl_mode: str = "ge"  # "ge" or "eq_any"
    ttl_min: int | None = None
    ttl_values: tuple[int, ...] = ()

    use_dscp: bool = False
    dscp_value: int | None = None
    dscp_mask: int = 0xFC

    use_dst_port_low: bool = False
    dst_port_low: int | None = None

    use_tcp_flags: bool = False
    tcp_flags_mask: int | None = None

    use_packet_len: bool = False
    min_packet_len: int | None = None

    use_payload_len: bool = False
    min_payload_len: int | None = None

    use_payload_bit: bool = False
    payload_byte_index: int = 4
    payload_bit_mask: int | None = None

    @property
    def min_ops(self) -> int:
        return max(1, self.target_ops - self.tolerance)

    @property
    def max_ops(self) -> int:
        return self.target_ops + self.tolerance


@dataclass
class GeneratedProgram:
    seed: int | None
    request: ProgramRequest
    resolved_offsets: dict[str, int]
    resolved_constants: dict[str, int | tuple[int, ...] | str]
    actual_ops: int
    program: list[int]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FieldProbe:
    """One probe definition used for DUT-visible offset discovery."""

    name: str
    packet_a: bytes
    expected_a: int
    packet_b: bytes
    expected_b: int
    candidate_offsets: range


@dataclass(frozen=True)
class GeneratedProgramProfile:
    """Named generated-program preset used by integration tests."""

    name: str
    level: str
    description: str
    recommended_randomize_fields: tuple[str, ...]
    request: ProgramRequest


def _stmt(code: int, k: int = 0) -> int:
    return encode_bpf_instruction(code, k=k)


def _jump(code: int, k: int, jt: int, jf: int) -> int:
    return encode_bpf_instruction(code, k=k, jt=jt, jf=jf)


def _alu_and_k(value: int) -> int:
    return _stmt(BPF_ALU | BPF_AND | BPF_K, value)


def _ld_len() -> int:
    return _stmt(BPF_LD | BPF_LEN, 0)


def _ldxb_msh(offset: int) -> int:
    return _stmt(BPF_LDX | BPF_B | BPF_MSH, offset)


def _ldb_ind(offset: int) -> int:
    return _stmt(BPF_LD | BPF_B | 0x40, offset)


def _jge_k(value: int, *, jt: int, jf: int) -> int:
    return _jump(BPF_JMP | BPF_JGE | BPF_K, value, jt, jf)


def _jset_k(value: int, *, jt: int, jf: int) -> int:
    return _jump(BPF_JMP | BPF_JSET | BPF_K, value, jt, jf)


def preview_offsets() -> dict[str, int]:
    offsets = {
        "version_ihl": 14,
        "dscp": 15,
        "ttl": 22,
        "protocol": 23,
        "dst_port_low": 37,
        "tcp_flags": 47,
        "payload_marker": 58,
    }
    ipv4_base_header_len = 20
    offsets["flags_rel"] = offsets["tcp_flags"] - ipv4_base_header_len
    offsets["dst_port_rel"] = offsets["dst_port_low"] - ipv4_base_header_len
    offsets["payload_marker_rel"] = offsets["payload_marker"] - ipv4_base_header_len
    return offsets


def make_base_program_spec() -> PacketSpec:
    """Return the shared base packet used for probe generation."""
    return PacketSpec(
        l4="tcp",
        src_mac=bytes.fromhex("112233445566"),
        dst_mac=bytes.fromhex("aabbccddeeff"),
        src_ip="10.10.1.1",
        dst_ip="192.0.2.99",
        dscp_ecn=0x28,
        ttl=64,
        src_port=0x1234,
        dst_port=0x5678,
        seq=0x01020304,
        ack=0xA1B2C3D4,
        flags=0x12,
        payload=bytes.fromhex("00112233d8adbeef"),
        name="base_profile_packet",
    )


PROGRAM_PROFILES = (
    GeneratedProgramProfile(
        name="short_tcp_port",
        level="short",
        description="Short filter: TCP protocol plus destination-port low-byte match.",
        recommended_randomize_fields=("src_ip", "src_port", "seq", "ack", "payload_len"),
        request=ProgramRequest(
            target_ops=6,
            tolerance=1,
            randomness=RandomnessLevel.LOW,
            require_tcp=True,
            use_dst_port_low=True,
            dst_port_low=0x78,
        ),
    ),
    GeneratedProgramProfile(
        name="ttl_value_chain_30",
        level="medium",
        description="Thirty-instruction TTL filter that accepts only selected TTL values through a long equality chain.",
        recommended_randomize_fields=("ttl", "payload_len", "payload_bytes", "src_ip", "dst_ip"),
        request=ProgramRequest(
            target_ops=30,
            tolerance=0,
            randomness=RandomnessLevel.LOW,
            require_tcp=False,
            use_ttl=True,
            ttl_mode="eq_any",
            ttl_values=(32, 48, 64, 96, 128, 200),
        ),
    ),
    GeneratedProgramProfile(
        name="medium_ttl_dscp_flags",
        level="medium",
        description="Medium filter: TCP, TTL threshold, DSCP class, SYN bit, destination port.",
        recommended_randomize_fields=("ttl", "dscp_ecn", "tcp_flags", "src_port", "seq", "ack"),
        request=ProgramRequest(
            target_ops=12,
            tolerance=2,
            randomness=RandomnessLevel.LOW,
            require_tcp=True,
            use_ttl=True,
            ttl_mode="ge",
            ttl_min=64,
            use_dscp=True,
            dscp_value=0x28,
            dscp_mask=0xFC,
            use_dst_port_low=True,
            dst_port_low=0x78,
            use_tcp_flags=True,
            tcp_flags_mask=0x02,
        ),
    ),
    GeneratedProgramProfile(
        name="long_edge_mix",
        level="long",
        description="Long mixed-op filter: packet length, TTL, DSCP, indirect TCP loads, payload marker bit.",
        recommended_randomize_fields=("ttl", "dscp_ecn", "payload_len", "payload_bytes", "tcp_flags", "src_port", "seq", "ack"),
        request=ProgramRequest(
            target_ops=18,
            tolerance=3,
            randomness=RandomnessLevel.LOW,
            require_tcp=True,
            use_packet_len=True,
            min_packet_len=62,
            use_ttl=True,
            ttl_mode="ge",
            ttl_min=64,
            use_dscp=True,
            dscp_value=0x28,
            dscp_mask=0xFC,
            use_dst_port_low=True,
            dst_port_low=0x78,
            use_tcp_flags=True,
            tcp_flags_mask=0x02,
            use_payload_bit=True,
            payload_byte_index=4,
            payload_bit_mask=0x08,
        ),
    ),
)


def get_program_profile(name: str) -> GeneratedProgramProfile:
    """Return one named generated-program preset."""
    for profile in PROGRAM_PROFILES:
        if profile.name == name:
            return profile
    raise ValueError(f"Unknown generated program profile: {name}")


def _make_rng(seed: int | None) -> random.Random:
    return random.Random(seed)


def _random_ttl_values(rng: random.Random, level: RandomnessLevel) -> tuple[int, ...]:
    pool = [16, 24, 32, 40, 48, 56, 64, 96, 112, 128, 160, 192, 200, 224, 255]
    count = 3 if level == RandomnessLevel.LOW else 4 if level == RandomnessLevel.MEDIUM else 6
    return tuple(sorted(rng.sample(pool, count)))


def _canonical_header_len(payload_byte_index: int) -> int:
    return 54 + payload_byte_index + 1


def _resolve_request(
    request: ProgramRequest,
) -> tuple[ProgramRequest, dict[str, int | tuple[int, ...] | str]]:
    rng = _make_rng(request.seed)
    constants: dict[str, int | tuple[int, ...] | str] = {}

    ttl_min = request.ttl_min
    ttl_values = request.ttl_values
    dscp_value = request.dscp_value
    dst_port_low = request.dst_port_low
    tcp_flags_mask = request.tcp_flags_mask
    min_packet_len = request.min_packet_len
    min_payload_len = request.min_payload_len
    payload_bit_mask = request.payload_bit_mask

    if request.use_ttl:
        if request.ttl_mode == "ge":
            if ttl_min is None:
                ttl_min = 64 if request.randomness == RandomnessLevel.LOW else rng.choice([32, 48, 64, 96, 128])
            constants["ttl_mode"] = "ge"
            constants["ttl_min"] = ttl_min
        elif request.ttl_mode == "eq_any":
            if not ttl_values:
                ttl_values = _random_ttl_values(rng, request.randomness)
            constants["ttl_mode"] = "eq_any"
            constants["ttl_values"] = ttl_values
        else:
            raise ValueError(f"Unsupported ttl_mode: {request.ttl_mode}")

    if request.use_dscp:
        if dscp_value is None:
            dscp_value = 0x28 if request.randomness == RandomnessLevel.LOW else rng.choice(
                [0x00, 0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38]
            )
        constants["dscp_value"] = dscp_value
        constants["dscp_mask"] = request.dscp_mask

    if request.use_dst_port_low:
        if dst_port_low is None:
            dst_port_low = 0x78 if request.randomness == RandomnessLevel.LOW else rng.choice(
                [0x16, 0x22, 0x44, 0x78, 0xA5, 0xD3]
            )
        constants["dst_port_low"] = dst_port_low

    if request.use_tcp_flags:
        if tcp_flags_mask is None:
            tcp_flags_mask = 0x02 if request.randomness == RandomnessLevel.LOW else rng.choice(
                [0x02, 0x10, 0x04, 0x12]
            )
        constants["tcp_flags_mask"] = tcp_flags_mask

    if request.use_packet_len:
        if min_packet_len is None:
            min_packet_len = 62 if request.randomness == RandomnessLevel.LOW else rng.choice(
                [54, 58, 62, 70, 78]
            )
        constants["min_packet_len"] = min_packet_len

    if request.use_payload_len:
        if min_payload_len is None:
            min_payload_len = 8 if request.randomness == RandomnessLevel.LOW else rng.choice(
                [4, 8, 12, 16, 24]
            )
        constants["min_payload_len"] = min_payload_len

    if request.use_payload_bit:
        if payload_bit_mask is None:
            payload_bit_mask = 0x08 if request.randomness == RandomnessLevel.LOW else rng.choice(
                [0x01, 0x02, 0x04, 0x08, 0x10]
            )
        constants["payload_byte_index"] = request.payload_byte_index
        constants["payload_bit_mask"] = payload_bit_mask

    resolved = ProgramRequest(
        target_ops=request.target_ops,
        tolerance=request.tolerance,
        randomness=request.randomness,
        seed=request.seed,
        require_tcp=request.require_tcp,
        use_ttl=request.use_ttl,
        ttl_mode=request.ttl_mode,
        ttl_min=ttl_min,
        ttl_values=ttl_values,
        use_dscp=request.use_dscp,
        dscp_value=dscp_value,
        dscp_mask=request.dscp_mask,
        use_dst_port_low=request.use_dst_port_low,
        dst_port_low=dst_port_low,
        use_tcp_flags=request.use_tcp_flags,
        tcp_flags_mask=tcp_flags_mask,
        use_packet_len=request.use_packet_len,
        min_packet_len=min_packet_len,
        use_payload_len=request.use_payload_len,
        min_payload_len=min_payload_len,
        use_payload_bit=request.use_payload_bit,
        payload_byte_index=request.payload_byte_index,
        payload_bit_mask=payload_bit_mask,
    )
    return resolved, constants


def _build_ttl_eq_any_clause(offsets: dict[str, int], values: tuple[int, ...]) -> list[int]:
    program = [bpf_ldb_abs(offsets["ttl"])]
    for i, value in enumerate(values):
        remaining = len(values) - i
        program.append(bpf_jeq_k(value, jt=remaining, jf=0))
    program.append(bpf_ret_k(0))
    program.append(bpf_ret_k(1))
    return program


def _build_program(request: ProgramRequest, offsets: dict[str, int]) -> list[int]:
    checks: list[list[int]] = []

    if request.require_tcp:
        checks.append([
            bpf_ldb_abs(offsets["protocol"]),
            bpf_jeq_k(0x06, jt=1, jf=0),
            bpf_ret_k(0),
        ])

    if request.use_packet_len:
        assert request.min_packet_len is not None
        checks.append([
            _ld_len(),
            _jge_k(request.min_packet_len, jt=1, jf=0),
            bpf_ret_k(0),
        ])

    if request.use_payload_len:
        assert request.min_payload_len is not None
        derived_min_len = 54 + request.min_payload_len
        checks.append([
            _ld_len(),
            _jge_k(derived_min_len, jt=1, jf=0),
            bpf_ret_k(0),
        ])

    if request.use_ttl:
        if request.ttl_mode == "ge":
            assert request.ttl_min is not None
            checks.append([
                bpf_ldb_abs(offsets["ttl"]),
                _jge_k(request.ttl_min, jt=1, jf=0),
                bpf_ret_k(0),
            ])
        elif request.ttl_mode == "eq_any":
            assert request.ttl_values
            return _finalize_program(checks + [_build_ttl_eq_any_clause(offsets, request.ttl_values)])
        else:
            raise ValueError(f"Unsupported ttl_mode: {request.ttl_mode}")

    if request.use_dscp:
        assert request.dscp_value is not None
        checks.append([
            bpf_ldb_abs(offsets["dscp"]),
            _alu_and_k(request.dscp_mask),
            bpf_jeq_k(request.dscp_value, jt=1, jf=0),
            bpf_ret_k(0),
        ])

    if request.use_tcp_flags:
        assert request.tcp_flags_mask is not None
        checks.append([
            bpf_ldb_abs(offsets["tcp_flags"]),
            _jset_k(request.tcp_flags_mask, jt=1, jf=0),
            bpf_ret_k(0),
        ])

    if request.use_dst_port_low:
        assert request.dst_port_low is not None
        checks.append([
            bpf_ldb_abs(offsets["dst_port_low"]),
            bpf_jeq_k(request.dst_port_low, jt=1, jf=0),
            bpf_ret_k(0),
        ])

    if request.use_payload_bit:
        assert request.payload_bit_mask is not None
        required_len = _canonical_header_len(request.payload_byte_index)
        checks.append([
            _ld_len(),
            _jge_k(required_len, jt=1, jf=0),
            bpf_ret_k(0),
            _ldxb_msh(offsets["version_ihl"]),
            _ldb_ind(offsets["payload_marker_rel"]),
            _jset_k(request.payload_bit_mask, jt=1, jf=0),
            bpf_ret_k(0),
        ])

    if not checks:
        raise ValueError("At least one filter condition must be enabled.")

    return _finalize_program(checks)


def _finalize_program(checks: list[list[int]]) -> list[int]:
    program: list[int] = []
    for clause in checks:
        program.extend(clause)

    if not program or program[-1] != bpf_ret_k(1):
        program.append(bpf_ret_k(1))

    return program


def build_profile_program(profile: GeneratedProgramProfile, offsets: dict[str, int]) -> list[int]:
    """Compatibility wrapper for profile-based callers."""
    return generate_program(profile.request, offsets).program


def _evaluate_request_accept(request: ProgramRequest, spec: PacketSpec) -> bool:
    """Evaluate one packet spec against a generated-program request."""
    if request.require_tcp and spec.l4 != "tcp":
        return False
    if request.use_ttl:
        if request.ttl_mode == "ge":
            assert request.ttl_min is not None
            if spec.ttl < request.ttl_min:
                return False
        elif request.ttl_mode == "eq_any":
            if spec.ttl not in set(request.ttl_values):
                return False
    if request.use_dscp:
        assert request.dscp_value is not None
        if (spec.dscp_ecn & request.dscp_mask) != request.dscp_value:
            return False
    if request.use_dst_port_low:
        assert request.dst_port_low is not None
        if (spec.dst_port & 0xFF) != request.dst_port_low:
            return False
    if request.use_tcp_flags:
        assert request.tcp_flags_mask is not None
        if spec.l4 != "tcp" or not (spec.flags & request.tcp_flags_mask):
            return False
    if request.use_packet_len:
        assert request.min_packet_len is not None
        if len(build_packet(spec)) < request.min_packet_len:
            return False
    if request.use_payload_len:
        assert request.min_payload_len is not None
        if len(spec.payload) < request.min_payload_len:
            return False
    if request.use_payload_bit:
        assert request.payload_bit_mask is not None
        if len(spec.payload) <= request.payload_byte_index:
            return False
        if not (spec.payload[request.payload_byte_index] & request.payload_bit_mask):
            return False
    return True


def evaluate_profile_accept(profile: GeneratedProgramProfile, spec: PacketSpec) -> bool:
    """Compatibility wrapper for profile-based golden-model checks."""
    return _evaluate_request_accept(profile.request, spec)


def build_profile_probes(profile: GeneratedProgramProfile) -> list[FieldProbe]:
    """Build probe packets for the fields used by one generated profile."""
    request = profile.request
    base = make_base_program_spec()
    udp = derive_packet(base, l4="udp")
    low_ttl = derive_packet(base, ttl=32)
    wrong_dscp = derive_packet(base, dscp_ecn=0x00)
    wrong_flags = derive_packet(base, flags=0x10)
    wrong_port = derive_packet(base, dst_port=0x56BB)
    marker_clear = derive_packet(base, payload=bytes.fromhex("00112233d0adbeef"))

    probes: list[FieldProbe] = []
    if request.require_tcp:
        probes.append(FieldProbe("protocol", build_packet(base), 0x06, build_packet(udp), 0x11, range(16, 28)))
    if request.use_ttl:
        probes.append(FieldProbe("ttl", build_packet(base), 64, build_packet(low_ttl), 32, range(16, 28)))
    if request.use_dscp:
        probes.append(FieldProbe("dscp", build_packet(base), 0x28, build_packet(wrong_dscp), 0x00, range(12, 20)))
    if request.use_tcp_flags:
        probes.append(FieldProbe("tcp_flags", build_packet(base), 0x12, build_packet(wrong_flags), 0x10, range(40, 56)))
    if request.use_dst_port_low:
        probes.append(FieldProbe("dst_port_low", build_packet(base), 0x78, build_packet(wrong_port), 0xBB, range(34, 50)))
    if request.use_payload_bit:
        pass_options = derive_packet(base, ip_options=bytes.fromhex("01010101"))
        probes.extend(
            [
                FieldProbe("version_ihl", build_packet(base), 0x45, build_packet(pass_options), 0x46, range(12, 20)),
                FieldProbe("payload_marker", build_packet(base), 0xD8, build_packet(marker_clear), 0xD0, range(46, 68)),
            ]
        )
    return probes


def finalize_profile_offsets(profile: GeneratedProgramProfile, discovered_offsets: dict[str, int]) -> dict[str, int]:
    """Convert absolute discovered offsets into the final offsets used by a profile."""
    offsets = dict(discovered_offsets)
    if profile.request.use_payload_bit:
        base_packet = build_packet(make_base_program_spec())
        ipv4_base_header_len = (base_packet[14] & 0x0F) * 4
        if "tcp_flags" in offsets:
            offsets["flags_rel"] = offsets["tcp_flags"] - ipv4_base_header_len
        if "dst_port_low" in offsets:
            offsets["dst_port_rel"] = offsets["dst_port_low"] - ipv4_base_header_len
        if "payload_marker" in offsets:
            offsets["payload_marker_rel"] = offsets["payload_marker"] - ipv4_base_header_len
    return offsets


def generate_program(request: ProgramRequest, offsets: dict[str, int] | None = None) -> GeneratedProgram:
    resolved_request, constants = _resolve_request(request)
    actual_offsets = offsets or preview_offsets()
    program = _build_program(resolved_request, actual_offsets)

    notes = [
        "Preview offsets used." if offsets is None else "Caller-provided offsets used.",
        "No filler padding is added. Program ends when logical checks end.",
    ]

    if not (resolved_request.min_ops <= len(program) <= resolved_request.max_ops):
        notes.append(
            f"Actual ops {len(program)} are outside requested target window "
            f"[{resolved_request.min_ops}, {resolved_request.max_ops}] because padding is disabled."
        )

    return GeneratedProgram(
        seed=resolved_request.seed,
        request=resolved_request,
        resolved_offsets=actual_offsets,
        resolved_constants=constants,
        actual_ops=len(program),
        program=program,
        notes=notes,
    )


def describe_generated_program(result: GeneratedProgram) -> str:
    lines = [
        f"Seed: {result.seed}",
        f"Randomness: {result.request.randomness.value}",
        f"Target ops: {result.request.target_ops}",
        f"Tolerance: ±{result.request.tolerance}",
        f"Actual ops: {result.actual_ops}",
        "Resolved constants:",
    ]

    if result.resolved_constants:
        for key, value in result.resolved_constants.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")

    lines.append("Offsets:")
    for key, value in result.resolved_offsets.items():
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("Generated BPF program:")
    lines.append(format_bpf_program(result.program))

    if result.notes:
        lines.append("")
        lines.append("Notes:")
        for note in result.notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Request-driven BPF program generator.")

    parser.add_argument(
        "--preset",
        choices=[profile.name for profile in PROGRAM_PROFILES],
        default=None,
        help="Optional named preset used by the generated-program integration test flow.",
    )

    parser.add_argument("--target-ops", type=int, default=12, help="Target instruction count.")
    parser.add_argument("--tolerance", type=int, default=2, help="Allowed deviation from target ops.")
    parser.add_argument(
        "--randomness",
        choices=[lvl.value for lvl in RandomnessLevel],
        default="low",
        help="Randomness level for auto-selected constants.",
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible generation.")

    parser.add_argument("--no-require-tcp", action="store_true", help="Do not automatically require protocol == TCP.")

    parser.add_argument("--use-ttl", action="store_true", help="Enable TTL-based filtering.")
    parser.add_argument("--ttl-mode", choices=["ge", "eq_any"], default="ge", help="TTL filter mode.")
    parser.add_argument("--ttl-min", type=int, default=None, help="TTL threshold for ge mode.")
    parser.add_argument("--ttl-values", type=int, nargs="*", default=None, help="TTL values for eq_any mode.")

    parser.add_argument("--use-dscp", action="store_true", help="Enable DSCP masked compare.")
    parser.add_argument("--dscp-value", type=lambda x: int(x, 0), default=None, help="DSCP value, e.g. 0x28.")
    parser.add_argument("--dscp-mask", type=lambda x: int(x, 0), default=0xFC, help="DSCP mask, default 0xFC.")

    parser.add_argument("--use-dst-port-low", action="store_true", help="Enable low-byte destination port compare.")
    parser.add_argument("--dst-port-low", type=lambda x: int(x, 0), default=None, help="Port low byte, e.g. 0x78.")

    parser.add_argument("--use-tcp-flags", action="store_true", help="Enable TCP flags bitmask check.")
    parser.add_argument("--tcp-flags-mask", type=lambda x: int(x, 0), default=None, help="Flags mask, e.g. 0x02.")

    parser.add_argument("--use-packet-len", action="store_true", help="Enable total packet length check.")
    parser.add_argument("--min-packet-len", type=int, default=None, help="Minimum total packet length.")

    parser.add_argument("--use-payload-len", action="store_true", help="Enable derived payload-length check.")
    parser.add_argument("--min-payload-len", type=int, default=None, help="Minimum payload length.")

    parser.add_argument("--use-payload-bit", action="store_true", help="Enable payload bit check.")
    parser.add_argument("--payload-byte-index", type=int, default=4, help="Payload byte index to inspect.")
    parser.add_argument("--payload-bit-mask", type=lambda x: int(x, 0), default=None, help="Payload bit mask.")

    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.preset:
        preset_request = get_program_profile(args.preset).request
        request = ProgramRequest(
            target_ops=args.target_ops if args.target_ops != 12 else preset_request.target_ops,
            tolerance=args.tolerance if args.tolerance != 2 else preset_request.tolerance,
            randomness=RandomnessLevel(args.randomness) if args.randomness != "low" else preset_request.randomness,
            seed=args.seed if args.seed is not None else preset_request.seed,
            require_tcp=preset_request.require_tcp if not args.no_require_tcp else False,
            use_ttl=preset_request.use_ttl,
            ttl_mode=preset_request.ttl_mode,
            ttl_min=args.ttl_min if args.ttl_min is not None else preset_request.ttl_min,
            ttl_values=tuple(args.ttl_values or preset_request.ttl_values),
            use_dscp=preset_request.use_dscp,
            dscp_value=args.dscp_value if args.dscp_value is not None else preset_request.dscp_value,
            dscp_mask=args.dscp_mask if args.dscp_mask != 0xFC else preset_request.dscp_mask,
            use_dst_port_low=preset_request.use_dst_port_low,
            dst_port_low=args.dst_port_low if args.dst_port_low is not None else preset_request.dst_port_low,
            use_tcp_flags=preset_request.use_tcp_flags,
            tcp_flags_mask=args.tcp_flags_mask if args.tcp_flags_mask is not None else preset_request.tcp_flags_mask,
            use_packet_len=preset_request.use_packet_len,
            min_packet_len=args.min_packet_len if args.min_packet_len is not None else preset_request.min_packet_len,
            use_payload_len=preset_request.use_payload_len,
            min_payload_len=args.min_payload_len if args.min_payload_len is not None else preset_request.min_payload_len,
            use_payload_bit=preset_request.use_payload_bit,
            payload_byte_index=args.payload_byte_index if args.payload_byte_index != 4 else preset_request.payload_byte_index,
            payload_bit_mask=args.payload_bit_mask if args.payload_bit_mask is not None else preset_request.payload_bit_mask,
        )
    else:
        request = ProgramRequest(
            target_ops=args.target_ops,
            tolerance=args.tolerance,
            randomness=RandomnessLevel(args.randomness),
            seed=args.seed,
            require_tcp=not args.no_require_tcp,
            use_ttl=args.use_ttl,
            ttl_mode=args.ttl_mode,
            ttl_min=args.ttl_min,
            ttl_values=tuple(args.ttl_values or ()),
            use_dscp=args.use_dscp,
            dscp_value=args.dscp_value,
            dscp_mask=args.dscp_mask,
            use_dst_port_low=args.use_dst_port_low,
            dst_port_low=args.dst_port_low,
            use_tcp_flags=args.use_tcp_flags,
            tcp_flags_mask=args.tcp_flags_mask,
            use_packet_len=args.use_packet_len,
            min_packet_len=args.min_packet_len,
            use_payload_len=args.use_payload_len,
            min_payload_len=args.min_payload_len,
            use_payload_bit=args.use_payload_bit,
            payload_byte_index=args.payload_byte_index,
            payload_bit_mask=args.payload_bit_mask,
        )

    result = generate_program(request)
    print(describe_generated_program(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
