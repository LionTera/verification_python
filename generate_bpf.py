"""Standalone BPF program generator — no project dependencies required.

Usage examples:
  python generate_bpf.py --preset short_tcp_port
  python generate_bpf.py --preset medium_ttl_dscp_flags
  python generate_bpf.py --use-ttl --ttl-mode ge --ttl-min 64 --use-dscp --dscp-value 0x28
  python generate_bpf.py --use-ttl --ttl-mode eq_any --ttl-values 32 64 128 --no-require-tcp
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# BPF constants (from bpf_python_tb.py)
# ---------------------------------------------------------------------------

BPF_LD   = 0x00
BPF_LDX  = 0x01
BPF_ST   = 0x02
BPF_STX  = 0x03
BPF_ALU  = 0x04
BPF_JMP  = 0x05
BPF_RET  = 0x06
BPF_MISC = 0x07

BPF_W    = 0x00
BPF_H    = 0x08
BPF_B    = 0x10

BPF_IMM  = 0x00
BPF_ABS  = 0x20
BPF_IND  = 0x40
BPF_MEM  = 0x60
BPF_LEN  = 0x80
BPF_MSH  = 0xA0
BPF_INDM = 0xC0

# ALU ops
BPF_ADD  = 0x00
BPF_SUB  = 0x10
BPF_MUL  = 0x20
BPF_DIV  = 0x30
BPF_OR   = 0x40
BPF_AND  = 0x50
BPF_LSH  = 0x60
BPF_RSH  = 0x70
BPF_NEG  = 0x80
BPF_MOD  = 0x90
BPF_XOR  = 0xA0

# JMP ops
BPF_JA   = 0x00
BPF_JEQ  = 0x10
BPF_JGT  = 0x20
BPF_JGE  = 0x30
BPF_JSET = 0x40
BPF_JAL  = 0x50  # custom: jump-and-link (saves PC+1 to A)
BPF_JRA  = 0x60  # custom: jump to return address (jumps to A)

# Source / return value selectors
BPF_K    = 0x00
BPF_X    = 0x08
BPF_A    = 0x10

# MISC ops
BPF_TAX  = 0x00  # A -> X
BPF_TXA  = 0x80  # X -> A

BPF_CLASS_MASK = 0x07
BPF_SIZE_MASK  = 0x18
BPF_MODE_MASK  = 0xE0
BPF_OP_MASK    = 0xF0
BPF_SRC_MASK   = 0x08

RET_K_OPCODE = 0x06
RET_A_OPCODE = 0x16

# ---------------------------------------------------------------------------
# Instruction encoding / formatting (from bpf_python_tb.py)
# ---------------------------------------------------------------------------

def encode_bpf_instruction(code: int, *, jt: int = 0, jf: int = 0, k: int = 0) -> int:
    return ((code & 0xFF) << 48) | ((jt & 0xFF) << 40) | ((jf & 0xFF) << 32) | (k & 0xFFFFFFFF)


def bpf_stmt(code: int, k: int = 0) -> int:
    return encode_bpf_instruction(code, k=k)


def bpf_jump(code: int, k: int, jt: int, jf: int) -> int:
    return encode_bpf_instruction(code, jt=jt, jf=jf, k=k)


def bpf_ldb_abs(offset: int) -> int:
    return bpf_stmt(BPF_LD | BPF_B | BPF_ABS, offset)


def bpf_jeq_k(value: int, *, jt: int, jf: int) -> int:
    return bpf_jump(BPF_JMP | BPF_JEQ | BPF_K, value, jt, jf)


def bpf_ret_k(value: int) -> int:
    return bpf_stmt(BPF_RET | BPF_K, value)


def decode_bpf_instruction(instruction: int) -> dict[str, int]:
    return {
        "code": (instruction >> 48) & 0xFF,
        "jt":   (instruction >> 40) & 0xFF,
        "jf":   (instruction >> 32) & 0xFF,
        "k":     instruction & 0xFFFFFFFF,
    }


def format_bpf_instruction(instruction: int) -> str:
    decoded = decode_bpf_instruction(instruction)
    mnemonic = {
        RET_K_OPCODE: "RET_K",
        RET_A_OPCODE: "RET_A",
    }.get(decoded["code"], f"OP_0x{decoded['code']:02x}")
    return (
        f"{mnemonic} "
        f"(code=0x{decoded['code']:02x}, jt={decoded['jt']}, jf={decoded['jf']}, k=0x{decoded['k']:08x})"
    )


def format_bpf_instruction_asm(instruction: int) -> str:
    decoded = decode_bpf_instruction(instruction)
    code = decoded["code"]
    klass = code & BPF_CLASS_MASK
    size  = code & BPF_SIZE_MASK
    mode  = code & BPF_MODE_MASK
    op    = code & BPF_OP_MASK
    src   = code & BPF_SRC_MASK

    if code == RET_K_OPCODE:
        return f"ret #{decoded['k']}"
    if code == RET_A_OPCODE:
        return "ret a"
    if klass == BPF_LD:
        size_name = {BPF_W: "ld", BPF_H: "ldh", BPF_B: "ldb"}.get(size, f"ld?0x{size:02x}")
        if mode == BPF_ABS:
            return f"{size_name} [{decoded['k']}]"
        if mode == BPF_IND:
            return f"{size_name} [x + {decoded['k']}]"
        if mode == BPF_IMM:
            return f"ld #{decoded['k']}"
        if mode == BPF_LEN:
            return "ld #pktlen"
        if mode == BPF_MEM:
            return f"ld M[{decoded['k']}]"
    if klass == BPF_LDX:
        if mode == BPF_MSH:
            return f"ldxb 4*([{decoded['k']}] & 0xf)"
        if mode == BPF_IMM:
            return f"ldx #{decoded['k']}"
        if mode == BPF_LEN:
            return "ldx #pktlen"
        if mode == BPF_MEM:
            return f"ldx M[{decoded['k']}]"
    if klass == BPF_ALU:
        if op == BPF_NEG:
            return "neg"
        rhs = "x" if src == BPF_X else f"#{decoded['k']}"
        op_name = {
            BPF_ADD: "add", BPF_SUB: "sub", BPF_MUL: "mul", BPF_DIV: "div",
            BPF_OR:  "or",  BPF_AND: "and", BPF_LSH: "lsh", BPF_RSH: "rsh",
            BPF_MOD: "mod", BPF_XOR: "xor",
        }.get(op)
        if op_name is not None:
            return f"{op_name} {rhs}"
    if klass == BPF_ST:
        if mode == BPF_IMM:
            return f"st M[{decoded['k']}]"
        if mode == BPF_INDM:
            return f"st M[x + {decoded['k']}]"
    if klass == BPF_STX:
        if mode == BPF_IMM:
            return f"stx M[{decoded['k']}]"
        if mode == BPF_INDM:
            return f"stx M[x + {decoded['k']}]"
    if klass == BPF_MISC:
        if code == (BPF_MISC | BPF_TAX):
            return "tax"
        if code == (BPF_MISC | BPF_TXA):
            return "txa"
    if klass == BPF_JMP:
        if op == BPF_JA:
            k = decoded['k']
            signed_k = k if k < 0x80000000 else k - 0x100000000
            return f"ja {signed_k:+d}"
        rhs = "x" if src == BPF_X else f"#{decoded['k']}"
        op_name = {
            BPF_JEQ: "jeq", BPF_JGT: "jgt", BPF_JGE: "jge", BPF_JSET: "jset",
        }.get(op)
        if op_name is not None:
            return f"{op_name} {rhs}, jt {decoded['jt']}, jf {decoded['jf']}"
        if op == BPF_JAL:
            k = decoded['k']
            signed_k = k if k < 0x80000000 else k - 0x100000000
            return f"jal {signed_k:+d}"
        if op == BPF_JRA:
            return "jra"
    return f".word 0x{instruction:016x}"


def format_bpf_program(instructions: list[int]) -> str:
    lines = ["BPF program:"]
    for idx, instr in enumerate(instructions):
        lines.append(
            f"  [{idx:02d}] 0x{instr:016x}  {format_bpf_instruction_asm(instr)}"
            f"    ; {format_bpf_instruction(instr)}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Program generator (from program_generator.py)
# ---------------------------------------------------------------------------

class RandomnessLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


@dataclass(frozen=True)
class ProgramRequest:
    target_ops: int = 12
    tolerance:  int = 2
    randomness: RandomnessLevel = RandomnessLevel.LOW
    seed:       int | None = None

    require_tcp: bool = True

    use_ttl:    bool = False
    ttl_mode:   str  = "ge"
    ttl_min:    int | None = None
    ttl_values: tuple[int, ...] = ()

    use_dscp:   bool = False
    dscp_value: int | None = None
    dscp_mask:  int = 0xFC

    use_dst_port_low: bool = False
    dst_port_low:     int | None = None

    use_tcp_flags:   bool = False
    tcp_flags_mask:  int | None = None

    use_packet_len:  bool = False
    min_packet_len:  int | None = None

    use_payload_len: bool = False
    min_payload_len: int | None = None

    use_payload_bit:    bool = False
    payload_byte_index: int  = 4
    payload_bit_mask:   int | None = None

    @property
    def min_ops(self) -> int:
        return max(1, self.target_ops - self.tolerance)

    @property
    def max_ops(self) -> int:
        return self.target_ops + self.tolerance


@dataclass
class GeneratedProgram:
    seed:              int | None
    request:           ProgramRequest
    resolved_offsets:  dict[str, int]
    resolved_constants: dict[str, int | tuple[int, ...] | str]
    actual_ops:        int
    program:           list[int]
    notes:             list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GeneratedProgramProfile:
    name:                        str
    level:                       str
    description:                 str
    recommended_randomize_fields: tuple[str, ...]
    request:                     ProgramRequest


# ---------------------------------------------------------------------------
# Instruction builder helpers
# ---------------------------------------------------------------------------

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
    return _stmt(BPF_LD | BPF_B | BPF_IND, offset)


def _jge_k(value: int, *, jt: int, jf: int) -> int:
    return _jump(BPF_JMP | BPF_JGE | BPF_K, value, jt, jf)


def _jset_k(value: int, *, jt: int, jf: int) -> int:
    return _jump(BPF_JMP | BPF_JSET | BPF_K, value, jt, jf)


# ---------------------------------------------------------------------------
# Additional instruction encoders for coverage mode
# ---------------------------------------------------------------------------

def bpf_ldh_abs(offset: int) -> int:
    return bpf_stmt(BPF_LD | BPF_H | BPF_ABS, offset)


def bpf_ldw_abs(offset: int) -> int:
    return bpf_stmt(BPF_LD | BPF_W | BPF_ABS, offset)


def bpf_ld_imm(value: int) -> int:
    return bpf_stmt(BPF_LD | BPF_W | BPF_IMM, value)


def bpf_ldx_imm(value: int) -> int:
    return bpf_stmt(BPF_LDX | BPF_W | BPF_IMM, value)


def bpf_ld_mem(idx: int) -> int:
    return bpf_stmt(BPF_LD | BPF_W | BPF_MEM, idx)


def bpf_ldx_mem(idx: int) -> int:
    return bpf_stmt(BPF_LDX | BPF_W | BPF_MEM, idx)


def bpf_st_mem(idx: int) -> int:
    return bpf_stmt(BPF_ST | BPF_W | BPF_IMM, idx)


def bpf_stx_mem(idx: int) -> int:
    return bpf_stmt(BPF_STX | BPF_W | BPF_IMM, idx)


def bpf_alu_k(op: int, value: int) -> int:
    return bpf_stmt(BPF_ALU | op | BPF_K, value)


def bpf_alu_x(op: int) -> int:
    return bpf_stmt(BPF_ALU | op | BPF_X, 0)


def bpf_neg() -> int:
    return bpf_stmt(BPF_ALU | BPF_NEG | BPF_K, 0)


def bpf_tax() -> int:
    return bpf_stmt(BPF_MISC | BPF_TAX, 0)


def bpf_txa() -> int:
    return bpf_stmt(BPF_MISC | BPF_TXA, 0)


def bpf_ja(offset: int) -> int:
    """Unconditional jump. Negative offset = backwards jump."""
    return bpf_stmt(BPF_JMP | BPF_JA | BPF_K, offset & 0xFFFFFFFF)


def bpf_jgt_k(value: int, *, jt: int, jf: int) -> int:
    return bpf_jump(BPF_JMP | BPF_JGT | BPF_K, value, jt, jf)


def bpf_jeq_x(*, jt: int, jf: int) -> int:
    return bpf_jump(BPF_JMP | BPF_JEQ | BPF_X, 0, jt, jf)


def bpf_jgt_x(*, jt: int, jf: int) -> int:
    return bpf_jump(BPF_JMP | BPF_JGT | BPF_X, 0, jt, jf)


def bpf_jge_x(*, jt: int, jf: int) -> int:
    return bpf_jump(BPF_JMP | BPF_JGE | BPF_X, 0, jt, jf)


def bpf_jset_x(*, jt: int, jf: int) -> int:
    return bpf_jump(BPF_JMP | BPF_JSET | BPF_X, 0, jt, jf)


def bpf_jal(offset: int) -> int:
    """Jump-and-link: saves PC+1 into A, then jumps by signed offset."""
    return bpf_stmt(BPF_JMP | BPF_JAL | BPF_K, offset & 0xFFFFFFFF)


def bpf_jra() -> int:
    """Jump to return address: jumps to address stored in A."""
    return bpf_stmt(BPF_JMP | BPF_JRA | BPF_K, 0)


def bpf_ret_a() -> int:
    return bpf_stmt(BPF_RET | BPF_A, 0)


# ---------------------------------------------------------------------------
# Preset profiles
# ---------------------------------------------------------------------------

PROGRAM_PROFILES = (
    GeneratedProgramProfile(
        name="short_tcp_port",
        level="short",
        description="Short filter: TCP protocol plus destination-port low-byte match.",
        recommended_randomize_fields=("src_ip", "src_port", "seq", "ack", "payload_len"),
        request=ProgramRequest(
            target_ops=6, tolerance=1, randomness=RandomnessLevel.LOW,
            require_tcp=True, use_dst_port_low=True, dst_port_low=0x78,
        ),
    ),
    GeneratedProgramProfile(
        name="ttl_value_chain_30",
        level="medium",
        description="Thirty-instruction TTL filter that accepts only selected TTL values through a long equality chain.",
        recommended_randomize_fields=("ttl", "payload_len", "payload_bytes", "src_ip", "dst_ip"),
        request=ProgramRequest(
            target_ops=30, tolerance=0, randomness=RandomnessLevel.LOW,
            require_tcp=False, use_ttl=True, ttl_mode="eq_any",
            ttl_values=(32, 48, 64, 96, 128, 200),
        ),
    ),
    GeneratedProgramProfile(
        name="medium_ttl_dscp_flags",
        level="medium",
        description="Medium filter: TCP, TTL threshold, DSCP class, SYN bit, destination port.",
        recommended_randomize_fields=("ttl", "dscp_ecn", "tcp_flags", "src_port", "seq", "ack"),
        request=ProgramRequest(
            target_ops=12, tolerance=2, randomness=RandomnessLevel.LOW,
            require_tcp=True, use_ttl=True, ttl_mode="ge", ttl_min=64,
            use_dscp=True, dscp_value=0x28, dscp_mask=0xFC,
            use_dst_port_low=True, dst_port_low=0x78,
            use_tcp_flags=True, tcp_flags_mask=0x02,
        ),
    ),
    GeneratedProgramProfile(
        name="long_edge_mix",
        level="long",
        description="Long mixed-op filter: packet length, TTL, DSCP, indirect TCP loads, payload marker bit.",
        recommended_randomize_fields=("ttl", "dscp_ecn", "payload_len", "payload_bytes", "tcp_flags", "src_port", "seq", "ack"),
        request=ProgramRequest(
            target_ops=18, tolerance=3, randomness=RandomnessLevel.LOW,
            require_tcp=True, use_packet_len=True, min_packet_len=62,
            use_ttl=True, ttl_mode="ge", ttl_min=64,
            use_dscp=True, dscp_value=0x28, dscp_mask=0xFC,
            use_dst_port_low=True, dst_port_low=0x78,
            use_tcp_flags=True, tcp_flags_mask=0x02,
            use_payload_bit=True, payload_byte_index=4, payload_bit_mask=0x08,
        ),
    ),
)


def get_program_profile(name: str) -> GeneratedProgramProfile:
    for profile in PROGRAM_PROFILES:
        if profile.name == name:
            return profile
    raise ValueError(f"Unknown generated program profile: {name}")


# ---------------------------------------------------------------------------
# Default packet offsets (Ethernet + IPv4 + TCP, no IP options)
# ---------------------------------------------------------------------------

def preview_offsets() -> dict[str, int]:
    offsets = {
        "version_ihl":    14,
        "dscp":           15,
        "ttl":            22,
        "protocol":       23,
        "dst_port_low":   37,
        "tcp_flags":      47,
        "payload_marker": 58,
    }
    ipv4_base = 20
    offsets["flags_rel"]          = offsets["tcp_flags"]      - ipv4_base
    offsets["dst_port_rel"]       = offsets["dst_port_low"]   - ipv4_base
    offsets["payload_marker_rel"] = offsets["payload_marker"] - ipv4_base
    return offsets


# ---------------------------------------------------------------------------
# Request resolution
# ---------------------------------------------------------------------------

def _make_rng(seed: int | None) -> random.Random:
    return random.Random(seed)


def _random_ttl_values(rng: random.Random, level: RandomnessLevel) -> tuple[int, ...]:
    pool  = [16, 24, 32, 40, 48, 56, 64, 96, 112, 128, 160, 192, 200, 224, 255]
    count = 3 if level == RandomnessLevel.LOW else 4 if level == RandomnessLevel.MEDIUM else 6
    return tuple(sorted(rng.sample(pool, count)))


def _resolve_request(
    request: ProgramRequest,
) -> tuple[ProgramRequest, dict[str, int | tuple[int, ...] | str]]:
    rng       = _make_rng(request.seed)
    constants: dict[str, int | tuple[int, ...] | str] = {}

    ttl_min        = request.ttl_min
    ttl_values     = request.ttl_values
    dscp_value     = request.dscp_value
    dst_port_low   = request.dst_port_low
    tcp_flags_mask = request.tcp_flags_mask
    min_packet_len = request.min_packet_len
    min_payload_len = request.min_payload_len
    payload_bit_mask = request.payload_bit_mask

    if request.use_ttl:
        if request.ttl_mode == "ge":
            if ttl_min is None:
                ttl_min = 64 if request.randomness == RandomnessLevel.LOW else rng.choice([32, 48, 64, 96, 128])
            constants["ttl_mode"] = "ge"
            constants["ttl_min"]  = ttl_min
        elif request.ttl_mode == "eq_any":
            if not ttl_values:
                ttl_values = _random_ttl_values(rng, request.randomness)
            constants["ttl_mode"]   = "eq_any"
            constants["ttl_values"] = ttl_values
        else:
            raise ValueError(f"Unsupported ttl_mode: {request.ttl_mode}")

    if request.use_dscp:
        if dscp_value is None:
            dscp_value = (
                0x28 if request.randomness == RandomnessLevel.LOW
                else rng.choice([0x00, 0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38])
            )
        constants["dscp_value"] = dscp_value
        constants["dscp_mask"]  = request.dscp_mask

    if request.use_dst_port_low:
        if dst_port_low is None:
            dst_port_low = (
                0x78 if request.randomness == RandomnessLevel.LOW
                else rng.choice([0x16, 0x22, 0x44, 0x78, 0xA5, 0xD3])
            )
        constants["dst_port_low"] = dst_port_low

    if request.use_tcp_flags:
        if tcp_flags_mask is None:
            tcp_flags_mask = (
                0x02 if request.randomness == RandomnessLevel.LOW
                else rng.choice([0x02, 0x10, 0x04, 0x12])
            )
        constants["tcp_flags_mask"] = tcp_flags_mask

    if request.use_packet_len:
        if min_packet_len is None:
            min_packet_len = (
                62 if request.randomness == RandomnessLevel.LOW
                else rng.choice([54, 58, 62, 70, 78])
            )
        constants["min_packet_len"] = min_packet_len

    if request.use_payload_len:
        if min_payload_len is None:
            min_payload_len = (
                8 if request.randomness == RandomnessLevel.LOW
                else rng.choice([4, 8, 12, 16, 24])
            )
        constants["min_payload_len"] = min_payload_len

    if request.use_payload_bit:
        if payload_bit_mask is None:
            payload_bit_mask = (
                0x08 if request.randomness == RandomnessLevel.LOW
                else rng.choice([0x01, 0x02, 0x04, 0x08, 0x10])
            )
        constants["payload_byte_index"] = request.payload_byte_index
        constants["payload_bit_mask"]   = payload_bit_mask

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


# ---------------------------------------------------------------------------
# Program builder
# ---------------------------------------------------------------------------

def _canonical_header_len(payload_byte_index: int) -> int:
    return 54 + payload_byte_index + 1


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
        f"Tolerance: \xb1{result.request.tolerance}",
        f"Actual ops: {result.actual_ops}",
        "Resolved constants:",
    ]
    if result.resolved_constants:
        for key, value in result.resolved_constants.items():
            lines.append(f"  {key}: {value}")
    else:
        lines.append("  none")

    lines.append("Offsets:")
    for key, value in result.resolved_offsets.items():
        lines.append(f"  {key}: {value}")

    lines.append("")
    lines.append(format_bpf_program(result.program))

    if result.notes:
        lines.append("")
        lines.append("Notes:")
        for note in result.notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Coverage programs — one per untested instruction class
# ---------------------------------------------------------------------------

def _cov_backwards_jump() -> list[int]:
    """Countdown loop: ld #3; loop: sub #1; if !=0 ja back; ret #1."""
    # PC  instruction       A after
    # [00] ld #3            3
    # [01] sub #1           2 / 1 / 0
    # [02] jeq #0,jt=1,jf=0 exit when A==0
    # [03] ja -3            back to [01]  (k = 1 - 3 - 1 = -3)
    # [04] ret #1
    return [
        bpf_ld_imm(3),
        bpf_alu_k(BPF_SUB, 1),
        bpf_jeq_k(0, jt=1, jf=0),
        bpf_ja(-3),
        bpf_ret_k(1),
    ]


def _cov_jal_jra() -> list[int]:
    """Subroutine call/return: jal jumps forward, jra returns."""
    # [00] jal +1  -> A=1, jump to [02]
    # [01] ret #1  <- return point (accept)
    # [02] jra     -> jump to A=1
    return [
        bpf_jal(1),
        bpf_ret_k(1),
        bpf_jra(),
    ]


def _cov_alu_k() -> list[int]:
    """All ALU ops with immediate K: add sub mul div or and xor lsh rsh mod neg."""
    # Computes a chain with a known result:
    # ld #16 -> add 20 -> sub 4 -> mul 3 -> div 6 ->
    # or 0x21 -> and 0x3F -> xor 1 -> lsh 2 -> rsh 3 -> mod 7 ->
    # neg -> and 0xFF  => expect A = 0xFD
    return [
        bpf_ld_imm(0x10),           # A = 16
        bpf_alu_k(BPF_ADD, 0x14),  # A = 36
        bpf_alu_k(BPF_SUB, 0x04),  # A = 32
        bpf_alu_k(BPF_MUL, 0x03),  # A = 96
        bpf_alu_k(BPF_DIV, 0x06),  # A = 16
        bpf_alu_k(BPF_OR,  0x21),  # A = 49  (0x10|0x21=0x31)
        bpf_alu_k(BPF_AND, 0x3F),  # A = 49
        bpf_alu_k(BPF_XOR, 0x01),  # A = 48  (0x31^0x01=0x30)
        bpf_alu_k(BPF_LSH, 2),     # A = 192 (0xC0)
        bpf_alu_k(BPF_RSH, 3),     # A = 24  (0x18)
        bpf_alu_k(BPF_MOD, 0x07),  # A = 3
        bpf_neg(),                  # A = 0xFFFFFFFD
        bpf_alu_k(BPF_AND, 0xFF),  # A = 0xFD
        bpf_jeq_k(0xFD, jt=1, jf=0),
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def _cov_alu_x() -> list[int]:
    """ALU ops with X register, plus tax/txa."""
    # ldx #3; ld #0x0F; add/sub/mul/div/mod x -> clears A
    # ldx #6; ld #3; or/and/xor x
    # tax; ldx #2; txa; lsh/rsh x  => expect A=2
    return [
        bpf_ldx_imm(3),             # X = 3
        bpf_ld_imm(0x0F),           # A = 15
        bpf_alu_x(BPF_ADD),         # A = 18
        bpf_alu_x(BPF_SUB),         # A = 15
        bpf_alu_x(BPF_MUL),         # A = 45
        bpf_alu_x(BPF_DIV),         # A = 15
        bpf_alu_x(BPF_MOD),         # A = 0  (15 % 3)
        bpf_ldx_imm(6),             # X = 6
        bpf_ld_imm(3),              # A = 3
        bpf_alu_x(BPF_OR),          # A = 7  (3|6)
        bpf_alu_x(BPF_AND),         # A = 6  (7&6)
        bpf_alu_x(BPF_XOR),         # A = 0  (6^6)
        bpf_tax(),                   # X = 0  (tax: A->X)
        bpf_ldx_imm(2),             # X = 2
        bpf_txa(),                   # A = 2  (txa: X->A)
        bpf_alu_x(BPF_LSH),         # A = 8  (2<<2)
        bpf_alu_x(BPF_RSH),         # A = 2  (8>>2)
        bpf_jeq_k(2, jt=1, jf=0),
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def _cov_memory() -> list[int]:
    """Scratch pad: st M[], stx M[], ld M[], ldx M[]."""
    # st 0xAB at M[0]; stx 0x55 at M[1]; load both back; add; xor => 0
    return [
        bpf_ld_imm(0xAB),           # A = 0xAB
        bpf_st_mem(0),              # M[0] = 0xAB
        bpf_ldx_imm(0x55),         # X = 0x55
        bpf_stx_mem(1),             # M[1] = 0x55
        bpf_ld_mem(1),              # A = M[1] = 0x55
        bpf_ldx_mem(0),             # X = M[0] = 0xAB
        bpf_alu_x(BPF_ADD),         # A = 0x55 + 0xAB = 0x100
        bpf_alu_k(BPF_XOR, 0x100), # A = 0
        bpf_jeq_k(0, jt=1, jf=0),
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def _cov_loads() -> list[int]:
    """ldh (halfword) and ld (word) absolute packet loads."""
    # ldh [22] => TTL<<8 | protocol; mask low byte; check TCP
    # ld  [26] => src IP word; check 10.10.1.1 = 0x0A0A0101
    return [
        bpf_ldh_abs(22),                        # A = halfword(TTL, proto)
        bpf_alu_k(BPF_AND, 0x00FF),             # A = protocol byte
        bpf_jeq_k(0x06, jt=1, jf=0),           # check TCP
        bpf_ret_k(0),
        bpf_ldw_abs(26),                        # A = src IP word
        bpf_jeq_k(0x0A0A0101, jt=1, jf=0),     # check 10.10.1.1
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def _cov_jgt() -> list[int]:
    """jgt (strictly greater than) with K and X."""
    # ld #7; jgt #6 -> pass; jgt #7 -> fail; jgt #8 -> fail path
    # then ldx #5; jgt x (7>5) -> pass
    return [
        bpf_ld_imm(7),
        bpf_jgt_k(6, jt=1, jf=0),      # 7 > 6 -> jt
        bpf_ret_k(0),                   # not reached
        bpf_jgt_k(7, jt=0, jf=1),      # 7 > 7 false -> jf skip
        bpf_ret_k(0),                   # not reached
        bpf_ldx_imm(5),
        bpf_jgt_x(jt=1, jf=0),         # 7 > 5 -> jt
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def _cov_jumps_x() -> list[int]:
    """Conditional jumps with X register: jeq x, jge x, jset x."""
    # ld #6; ldx #6; jeq x -> pass
    # ldx #5; jge x (6>=5) -> pass
    # ldx #4; jset x (6 & 4 = 4 != 0) -> pass
    return [
        bpf_ld_imm(6),
        bpf_ldx_imm(6),
        bpf_jeq_x(jt=1, jf=0),         # 6==6 -> jt
        bpf_ret_k(0),
        bpf_ldx_imm(5),
        bpf_jge_x(jt=1, jf=0),         # 6>=5 -> jt
        bpf_ret_k(0),
        bpf_ldx_imm(4),
        bpf_jset_x(jt=1, jf=0),        # 6&4=4 != 0 -> jt
        bpf_ret_k(0),
        bpf_ret_k(1),
    ]


def _cov_ret_a() -> list[int]:
    """ret a: return the accumulator value."""
    return [
        bpf_ldb_abs(23),    # A = protocol byte (6 for TCP)
        bpf_ret_a(),        # return A
    ]


COVERAGE_PROGRAMS: dict[str, tuple[str, list[int]]] = {}


def _cov_unified() -> list[int]:
    """Single program that visits every implemented instruction type.

    Expected packet: Ethernet + IPv4/TCP, IHL=5 (no options), src_ip=10.10.1.1.
    Expected result: ret a with A=1 (accept).

    Sections
    --------
    1  Packet loads:  ldb abs, ldh abs, ld word abs, ldb ind (ldxb MSH + ldb IND)
    2  Scratch:       st M[], stx M[], ld M[], ldx M[]
    3  ALU with X:    add/sub/mul/div/mod/or/and/xor/lsh/rsh x  +  tax / txa
    4  ALU with K:    add/sub/mul/div/or/and/xor/lsh/rsh/mod #k  +  neg
    5  JAL / JRA:     subroutine call + return (custom extensions)
    6  Jumps K:       jeq, jge, jgt, jset  with immediate
    7  Jumps X:       jeq x, jgt x, jge x, jset x
    8  Backwards ja:  countdown loop using negative k
    9  ret a:         return accumulator value
    """
    prog: list[int] = []

    # ── SECTION 1: Packet loads ───────────────────────────────────────────
    # ldb abs
    prog += [bpf_ldb_abs(23)]           # A = protocol (6 = TCP)
    prog += [bpf_st_mem(0)]             # M[0] = protocol
    # ldh abs
    prog += [bpf_ldh_abs(22)]           # A = halfword (TTL<<8 | proto)
    prog += [bpf_alu_k(BPF_AND, 0xFF)] # A = proto (low byte)
    prog += [bpf_st_mem(1)]             # M[1] = proto (same value, different load path)
    # ld word abs
    prog += [bpf_ldw_abs(26)]           # A = src IP word (10.10.1.1 = 0x0A0A0101)
    prog += [bpf_st_mem(2)]             # M[2] = src IP
    # ldb indirect (ldxb MSH sets X = IHL*4 = 20; ldb [x+3] = packet[23] = proto)
    prog += [_ldxb_msh(14)]             # X = 4*(packet[14]&0xF) = 20
    prog += [_ldb_ind(3)]               # A = packet[X+3] = packet[23] = proto
    prog += [bpf_st_mem(3)]             # M[3] = proto

    # ── SECTION 2: Scratch memory (stx + ldx M[]) ────────────────────────
    prog += [bpf_ldx_imm(3)]            # X = 3
    prog += [bpf_stx_mem(4)]            # M[4] = 3
    # Consistency check: M[0] == M[1] (both should be protocol=6)
    prog += [bpf_ld_mem(0)]             # A = M[0] = 6
    prog += [bpf_ldx_mem(1)]            # X = M[1] = 6
    prog += [bpf_jeq_x(jt=1, jf=0)]    # jeq x: 6==6 → skip ret #0
    prog += [bpf_ret_k(0)]              # not reached

    # ── SECTION 3: ALU with X register + tax + txa ───────────────────────
    prog += [bpf_ldx_imm(3)]            # X = 3
    prog += [bpf_ld_imm(15)]            # A = 15
    prog += [bpf_alu_x(BPF_ADD)]        # A = 18
    prog += [bpf_alu_x(BPF_SUB)]        # A = 15
    prog += [bpf_alu_x(BPF_MUL)]        # A = 45
    prog += [bpf_alu_x(BPF_DIV)]        # A = 15
    prog += [bpf_alu_x(BPF_MOD)]        # A = 0  (15 % 3)
    prog += [bpf_ldx_imm(6)]            # X = 6
    prog += [bpf_ld_imm(3)]             # A = 3
    prog += [bpf_alu_x(BPF_OR)]         # A = 7  (3 | 6)
    prog += [bpf_alu_x(BPF_AND)]        # A = 6  (7 & 6)
    prog += [bpf_alu_x(BPF_XOR)]        # A = 0  (6 ^ 6)
    prog += [bpf_tax()]                  # X = 0  (tax: A→X)
    prog += [bpf_ldx_imm(2)]            # X = 2
    prog += [bpf_txa()]                  # A = 2  (txa: X→A)
    prog += [bpf_alu_x(BPF_LSH)]        # A = 8  (2 << 2)
    prog += [bpf_alu_x(BPF_RSH)]        # A = 2  (8 >> 2)

    # ── SECTION 4: ALU with K immediate ──────────────────────────────────
    prog += [bpf_alu_k(BPF_ADD, 0x0E)]  # A = 16
    prog += [bpf_alu_k(BPF_MUL, 3)]     # A = 48
    prog += [bpf_alu_k(BPF_DIV, 6)]     # A = 8
    prog += [bpf_alu_k(BPF_OR,  0x07)]  # A = 15  (8 | 7)
    prog += [bpf_alu_k(BPF_AND, 0x0F)]  # A = 15
    prog += [bpf_alu_k(BPF_XOR, 0x05)]  # A = 10  (15 ^ 5)
    prog += [bpf_alu_k(BPF_LSH, 1)]     # A = 20
    prog += [bpf_alu_k(BPF_RSH, 2)]     # A = 5
    prog += [bpf_alu_k(BPF_MOD, 3)]     # A = 2
    prog += [bpf_neg()]                  # A = 0xFFFFFFFE
    prog += [bpf_alu_k(BPF_AND, 0xFF)]  # A = 0xFE

    # ── SECTION 5: JAL / JRA subroutine ──────────────────────────────────
    # Save A before jal overwrites it with the return address.
    # Layout:  jal → subroutine(jra) → return-point(ld M[]) → ja-skip → ...
    prog += [bpf_st_mem(5)]             # M[5] = 0xFE  (save)
    jal_idx = len(prog)
    prog += [bpf_jal(2)]                # jal +2: A=ret_pc, jump to subroutine (+2 ahead)
    prog += [bpf_ld_mem(5)]             # return landing: A = 0xFE
    prog += [bpf_ja(1)]                 # ja +1: skip over subroutine body
    prog += [bpf_jra()]                 # subroutine body: jra → return to A=ret_pc
    # Execution: jal→jra→ld M[5]→ja→ (continues)
    # A = 0xFE after this section

    # ── SECTION 6: Conditional jumps with K immediate ────────────────────
    # A = 0xFE throughout this section
    prog += [bpf_jeq_k(0xFE, jt=1, jf=0)]   # 0xFE == 0xFE → skip
    prog += [bpf_ret_k(0)]
    prog += [_jge_k(0xFE, jt=1, jf=0)]       # 0xFE >= 0xFE → skip
    prog += [bpf_ret_k(0)]
    prog += [bpf_jgt_k(0xFD, jt=1, jf=0)]   # 0xFE >  0xFD → skip
    prog += [bpf_ret_k(0)]
    prog += [_jset_k(0x08, jt=1, jf=0)]      # 0xFE & 0x08 = 8 ≠ 0 → skip
    prog += [bpf_ret_k(0)]

    # ── SECTION 7: Conditional jumps with X register ─────────────────────
    prog += [bpf_ldx_imm(0xFE)]
    prog += [bpf_jeq_x(jt=1, jf=0)]          # 0xFE == X=0xFE → skip
    prog += [bpf_ret_k(0)]
    prog += [bpf_ldx_imm(0xFD)]
    prog += [bpf_jgt_x(jt=1, jf=0)]          # 0xFE >  X=0xFD → skip
    prog += [bpf_ret_k(0)]
    prog += [bpf_ldx_imm(0xFE)]
    prog += [bpf_jge_x(jt=1, jf=0)]          # 0xFE >= X=0xFE → skip
    prog += [bpf_ret_k(0)]
    prog += [bpf_ldx_imm(0x08)]
    prog += [bpf_jset_x(jt=1, jf=0)]         # 0xFE & X=0x08 = 8 ≠ 0 → skip
    prog += [bpf_ret_k(0)]

    # ── SECTION 8: Backwards jump (countdown loop) ───────────────────────
    # ja with negative k: loop 3 times, A counts down to 0
    loop_top = len(prog) + 1             # PC of the sub instruction
    prog += [bpf_ld_imm(3)]              # A = 3
    prog += [bpf_alu_k(BPF_SUB, 1)]     # A -= 1     ← loop top
    prog += [bpf_jeq_k(0, jt=1, jf=0)]  # if A==0 exit loop
    back = loop_top - (len(prog) + 1)   # signed offset back to sub
    prog += [bpf_ja(back)]              # ja back to sub
    # A = 0 after loop

    # ── SECTION 9: ret a ─────────────────────────────────────────────────
    prog += [bpf_ld_imm(1)]              # A = 1 (non-zero = accept)
    prog += [bpf_ret_a()]                # ret a

    return prog


def _build_coverage_programs() -> dict[str, tuple[str, list[int]]]:
    return {
        "backwards-jump": ("Countdown loop using ja with negative k (backwards jump)",
                           _cov_backwards_jump()),
        "jal-jra":        ("Subroutine call/return via custom JAL+JRA extensions",
                           _cov_jal_jra()),
        "alu":            ("All ALU ops with K immediate: add sub mul div or and xor lsh rsh mod neg",
                           _cov_alu_k()),
        "alu-x":          ("ALU ops with X register source, plus tax/txa",
                           _cov_alu_x()),
        "memory":         ("Scratch pad: st M[], stx M[], ld M[], ldx M[]",
                           _cov_memory()),
        "loads":          ("Half-word (ldh) and word (ld) absolute packet loads",
                           _cov_loads()),
        "jgt":            ("jgt (strictly greater than) with K and X",
                           _cov_jgt()),
        "jumps-x":        ("Conditional jumps with X register: jeq x, jge x, jset x",
                           _cov_jumps_x()),
        "ret-a":          ("ret a — return accumulator value",
                           _cov_ret_a()),
        "unified":        ("Single program exercising every instruction type end-to-end",
                           _cov_unified()),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone BPF program generator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join([
            "Presets:  " + ", ".join(p.name for p in PROGRAM_PROFILES),
            "",
            "Examples:",
            "  python generate_bpf.py --preset short_tcp_port",
            "  python generate_bpf.py --preset medium_ttl_dscp_flags",
            "  python generate_bpf.py --use-ttl --ttl-mode eq_any --ttl-values 32 64 128 --no-require-tcp",
        ]),
    )

    _cov_names = list(_build_coverage_programs().keys()) + ["all"]
    parser.add_argument(
        "--coverage",
        choices=_cov_names,
        default=None,
        metavar="{" + ",".join(_cov_names) + "}",
        help="Generate an opcode-coverage program instead of a packet filter.",
    )

    parser.add_argument("--preset", choices=[p.name for p in PROGRAM_PROFILES], default=None,
                        help="Load a named preset (overridable with other flags).")

    parser.add_argument("--target-ops",  type=int, default=12,  help="Target instruction count (default: 12).")
    parser.add_argument("--tolerance",   type=int, default=2,   help="Allowed deviation from target ops (default: 2).")
    parser.add_argument("--randomness",  choices=[l.value for l in RandomnessLevel], default="low",
                        help="Randomness level for auto-selected constants (default: low).")
    parser.add_argument("--seed",        type=int, default=None, help="Random seed for reproducible generation.")

    parser.add_argument("--no-require-tcp", action="store_true", help="Do not require protocol == TCP.")

    parser.add_argument("--use-ttl",    action="store_true", help="Enable TTL-based filtering.")
    parser.add_argument("--ttl-mode",   choices=["ge", "eq_any"], default="ge", help="TTL filter mode (default: ge).")
    parser.add_argument("--ttl-min",    type=int, default=None, help="TTL threshold for ge mode.")
    parser.add_argument("--ttl-values", type=int, nargs="*",   default=None, help="TTL values for eq_any mode.")

    parser.add_argument("--use-dscp",   action="store_true", help="Enable DSCP masked compare.")
    parser.add_argument("--dscp-value", type=lambda x: int(x, 0), default=None, help="DSCP value (e.g. 0x28).")
    parser.add_argument("--dscp-mask",  type=lambda x: int(x, 0), default=0xFC, help="DSCP mask (default: 0xFC).")

    parser.add_argument("--use-dst-port-low", action="store_true", help="Enable destination port low-byte compare.")
    parser.add_argument("--dst-port-low",     type=lambda x: int(x, 0), default=None, help="Port low byte (e.g. 0x78).")

    parser.add_argument("--use-tcp-flags",  action="store_true", help="Enable TCP flags bitmask check.")
    parser.add_argument("--tcp-flags-mask", type=lambda x: int(x, 0), default=None, help="Flags mask (e.g. 0x02).")

    parser.add_argument("--use-packet-len", action="store_true", help="Enable total packet length check.")
    parser.add_argument("--min-packet-len", type=int, default=None, help="Minimum total packet length.")

    parser.add_argument("--use-payload-len", action="store_true", help="Enable derived payload-length check.")
    parser.add_argument("--min-payload-len", type=int, default=None, help="Minimum payload length.")

    parser.add_argument("--use-payload-bit",    action="store_true", help="Enable payload byte bit check.")
    parser.add_argument("--payload-byte-index", type=int, default=4, help="Payload byte index to inspect (default: 4).")
    parser.add_argument("--payload-bit-mask",   type=lambda x: int(x, 0), default=None, help="Payload bit mask.")

    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.coverage:
        programs = _build_coverage_programs()
        to_run = list(programs.items()) if args.coverage == "all" else [(args.coverage, programs[args.coverage])]
        for name, (description, instructions) in to_run:
            sep = "=" * 60
            print(f"\n{sep}")
            print(f"Coverage: {name}")
            print(f"  {description}")
            print(f"  Instruction count: {len(instructions)}")
            print(sep)
            print(format_bpf_program(instructions))
        return 0

    if args.preset:
        base = get_program_profile(args.preset).request
        request = ProgramRequest(
            target_ops  = args.target_ops  if args.target_ops  != 12  else base.target_ops,
            tolerance   = args.tolerance   if args.tolerance   != 2   else base.tolerance,
            randomness  = RandomnessLevel(args.randomness) if args.randomness != "low" else base.randomness,
            seed        = args.seed if args.seed is not None else base.seed,
            require_tcp = base.require_tcp if not args.no_require_tcp else False,
            use_ttl     = base.use_ttl,
            ttl_mode    = base.ttl_mode,
            ttl_min     = args.ttl_min    if args.ttl_min    is not None else base.ttl_min,
            ttl_values  = tuple(args.ttl_values or base.ttl_values),
            use_dscp    = base.use_dscp,
            dscp_value  = args.dscp_value  if args.dscp_value  is not None else base.dscp_value,
            dscp_mask   = args.dscp_mask   if args.dscp_mask   != 0xFC     else base.dscp_mask,
            use_dst_port_low = base.use_dst_port_low,
            dst_port_low     = args.dst_port_low   if args.dst_port_low   is not None else base.dst_port_low,
            use_tcp_flags    = base.use_tcp_flags,
            tcp_flags_mask   = args.tcp_flags_mask if args.tcp_flags_mask is not None else base.tcp_flags_mask,
            use_packet_len   = base.use_packet_len,
            min_packet_len   = args.min_packet_len if args.min_packet_len is not None else base.min_packet_len,
            use_payload_len  = base.use_payload_len,
            min_payload_len  = args.min_payload_len if args.min_payload_len is not None else base.min_payload_len,
            use_payload_bit      = base.use_payload_bit,
            payload_byte_index   = args.payload_byte_index if args.payload_byte_index != 4 else base.payload_byte_index,
            payload_bit_mask     = args.payload_bit_mask  if args.payload_bit_mask  is not None else base.payload_bit_mask,
        )
    else:
        request = ProgramRequest(
            target_ops  = args.target_ops,
            tolerance   = args.tolerance,
            randomness  = RandomnessLevel(args.randomness),
            seed        = args.seed,
            require_tcp = not args.no_require_tcp,
            use_ttl     = args.use_ttl,
            ttl_mode    = args.ttl_mode,
            ttl_min     = args.ttl_min,
            ttl_values  = tuple(args.ttl_values or ()),
            use_dscp    = args.use_dscp,
            dscp_value  = args.dscp_value,
            dscp_mask   = args.dscp_mask,
            use_dst_port_low = args.use_dst_port_low,
            dst_port_low     = args.dst_port_low,
            use_tcp_flags    = args.use_tcp_flags,
            tcp_flags_mask   = args.tcp_flags_mask,
            use_packet_len   = args.use_packet_len,
            min_packet_len   = args.min_packet_len,
            use_payload_len  = args.use_payload_len,
            min_payload_len  = args.min_payload_len,
            use_payload_bit      = args.use_payload_bit,
            payload_byte_index   = args.payload_byte_index,
            payload_bit_mask     = args.payload_bit_mask,
        )

    result = generate_program(request)
    print(describe_generated_program(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
