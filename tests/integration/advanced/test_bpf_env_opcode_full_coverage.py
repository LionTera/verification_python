"""Extended opcode coverage for the BPF DUT.

Fills the gaps left by test_bpf_env_opcode_execution_suite:

- False-branch (jf > 0) paths for all conditional jump types (K and X variants)
- jgt/jge boundary conditions (A == K, A == X)
- Indirect loads with non-zero k offset: X=0+k, and X+k both non-zero
- MSH + indirect combinations (the canonical indirect-addressing pattern)
- Long forward ja jumps (ja with offset > 1)
- ALU edge cases: 32-bit overflow/underflow, zero operands, identity ops, self-XOR
- Multiple scratch memory slot isolation (M[0]..M[3], STX path)
- Combined multi-instruction programs (ALU chain, scratch accumulate, TAX/TXA chain)
- Combined filter programs (protocol + flag check, accept and reject paths)
- jf multi-skip (jf > 1)

Note on backward jumps: classic BPF `ja` uses a forward offset only.
Negative (backward) jumps are not part of the architecture and are not tested here.

Packet layout used (58 bytes total):
  [0:6]   = dst_mac  aa:bb:cc:dd:ee:ff
  [6:12]  = src_mac  11:22:33:44:55:66
  [12:14] = ethertype 0x0800
  [14]    = 0x45  version/IHL -> ldxb_msh(14) yields X = 20
  [22]    = 0x40  TTL (64)
  [23]    = 0x06  protocol (TCP)
  [34:36] = 0x1234 src_port
  [36:38] = 0x5678 dst_port
  [38:42] = 0x01020304 seq
  [42:46] = 0xA1B2C3D4 ack
  [46]    = 0x50  data offset
  [47]    = 0x12  TCP flags (SYN|ACK)
  [54:58] = 0xdeadbeef payload
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.bpf_env.artifacts import unique_artifact_path
from tests.bpf_env.bpf_python_tb import (
    BPF_ADD,
    BPF_ALU,
    BPF_AND,
    BPF_B,
    BPF_DIV,
    BPF_H,
    BPF_IMM,
    BPF_IND,
    BPF_JA,
    BPF_JEQ,
    BPF_JGE,
    BPF_JGT,
    BPF_JMP,
    BPF_JSET,
    BPF_K,
    BPF_LD,
    BPF_LDX,
    BPF_LEN,
    BPF_LSH,
    BPF_MEM,
    BPF_MISC,
    BPF_MOD,
    BPF_MSH,
    BPF_MUL,
    BPF_NEG,
    BPF_OR,
    BPF_RET,
    BPF_RSH,
    BPF_ST,
    BPF_STX,
    BPF_SUB,
    BPF_W,
    BPF_X,
    BPF_XOR,
    BpfPythonTB,
    encode_bpf_instruction,
    reports_enabled,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.packets import make_tcp_packet


BPF_TAX = 0x00
BPF_TXA = 0x80


# ---------------------------------------------------------------------------
# Instruction encoding helpers
# ---------------------------------------------------------------------------

def _stmt(code: int, k: int = 0) -> int:
    return encode_bpf_instruction(code, k=k)


def _jump(code: int, k: int, jt: int, jf: int) -> int:
    return encode_bpf_instruction(code, k=k, jt=jt, jf=jf)


def _ld_imm(v: int) -> int:
    return _stmt(BPF_LD | BPF_W | BPF_IMM, v)


def _ldx_imm(v: int) -> int:
    return _stmt(BPF_LDX | BPF_W | BPF_IMM, v)


def _ld_mem(idx: int) -> int:
    return _stmt(BPF_LD | BPF_W | BPF_MEM, idx)


def _ldx_mem(idx: int) -> int:
    return _stmt(BPF_LDX | BPF_W | BPF_MEM, idx)


def _st(idx: int) -> int:
    return _stmt(BPF_ST, idx)


def _stx(idx: int) -> int:
    return _stmt(BPF_STX, idx)


def _ldb_abs(offset: int) -> int:
    return _stmt(BPF_LD | BPF_B | 0x20, offset)


def _ldh_abs(offset: int) -> int:
    return _stmt(BPF_LD | BPF_H | 0x20, offset)


def _ldb_ind(offset: int) -> int:
    return _stmt(BPF_LD | BPF_B | BPF_IND, offset)


def _ldh_ind(offset: int) -> int:
    return _stmt(BPF_LD | BPF_H | BPF_IND, offset)


def _ldw_ind(offset: int) -> int:
    return _stmt(BPF_LD | BPF_W | BPF_IND, offset)


def _ldxb_msh(offset: int) -> int:
    return _stmt(BPF_LDX | BPF_B | BPF_MSH, offset)


def _alu_k(op: int, v: int) -> int:
    return _stmt(BPF_ALU | op | BPF_K, v)


def _alu_x(op: int) -> int:
    return _stmt(BPF_ALU | op | BPF_X, 0)


def _ja(offset: int) -> int:
    return _jump(BPF_JMP | BPF_JA, offset, 0, 0)


def _jmp_k(op: int, v: int, *, jt: int, jf: int) -> int:
    return _jump(BPF_JMP | op | BPF_K, v, jt, jf)


def _jmp_x(op: int, *, jt: int, jf: int) -> int:
    return _jump(BPF_JMP | op | BPF_X, 0, jt, jf)


def _ret_k(v: int) -> int:
    return _stmt(BPF_RET | BPF_K, v)


def _ret_a() -> int:
    return _stmt(BPF_RET | 0x10, 0)


def _tax() -> int:
    return _stmt(BPF_MISC | BPF_TAX, 0)


def _txa() -> int:
    return _stmt(BPF_MISC | BPF_TXA, 0)


# ---------------------------------------------------------------------------
# Test case definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OpcodeCase:
    name: str
    program: list[int]
    expected_ret: int


@dataclass(frozen=True)
class OpcodeCaseOutcome:
    name: str
    expected_ret: int
    actual_ret: int
    returned: bool
    accepted: bool
    expected_accept: bool
    passed: bool
    trace_path: Path
    report_path: Path


PACKET = make_tcp_packet(
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
# len(PACKET) == 58,  packet[23] == 0x06,  packet[47] == 0x12,
# ldxb_msh(14) -> X == 20


CASES = [

    # -----------------------------------------------------------------------
    # Group 1: False-branch (jf > 0) — all conditional jump types, K variant
    # Condition is false so jf path is taken; jf=1 skips one instruction.
    # -----------------------------------------------------------------------
    OpcodeCase("jeq_k_jf_taken",
               [_ld_imm(4), _jmp_k(BPF_JEQ, 5, jt=0, jf=1), _ret_k(0), _ret_k(0x42)],
               0x42),
    OpcodeCase("jgt_k_jf_taken",
               [_ld_imm(3), _jmp_k(BPF_JGT, 5, jt=0, jf=1), _ret_k(0), _ret_k(0x42)],
               0x42),
    OpcodeCase("jge_k_jf_taken",
               [_ld_imm(4), _jmp_k(BPF_JGE, 5, jt=0, jf=1), _ret_k(0), _ret_k(0x42)],
               0x42),
    OpcodeCase("jset_k_jf_taken",
               [_ld_imm(0x40), _jmp_k(BPF_JSET, 0x80, jt=0, jf=1), _ret_k(0), _ret_k(0x42)],
               0x42),

    # -----------------------------------------------------------------------
    # Group 2: False-branch (jf > 0) — X variant
    # -----------------------------------------------------------------------
    OpcodeCase("jeq_x_jf_taken",
               [_ld_imm(4), _ldx_imm(5), _jmp_x(BPF_JEQ, jt=0, jf=1), _ret_k(0), _ret_k(0x42)],
               0x42),
    OpcodeCase("jgt_x_jf_taken",
               [_ld_imm(3), _ldx_imm(5), _jmp_x(BPF_JGT, jt=0, jf=1), _ret_k(0), _ret_k(0x42)],
               0x42),
    OpcodeCase("jge_x_jf_taken",
               [_ld_imm(4), _ldx_imm(5), _jmp_x(BPF_JGE, jt=0, jf=1), _ret_k(0), _ret_k(0x42)],
               0x42),
    OpcodeCase("jset_x_jf_taken",
               [_ld_imm(0x40), _ldx_imm(0x80), _jmp_x(BPF_JSET, jt=0, jf=1), _ret_k(0), _ret_k(0x42)],
               0x42),

    # -----------------------------------------------------------------------
    # Group 3: Boundary conditions — A == K / A == X
    # jgt: strictly greater, so A==K is FALSE → jf path
    # jge: greater-or-equal, so A==K is TRUE → jt path
    # -----------------------------------------------------------------------
    OpcodeCase("jgt_k_boundary_eq_not_taken",
               [_ld_imm(5), _jmp_k(BPF_JGT, 5, jt=1, jf=0), _ret_k(99), _ret_k(0)],
               99),  # A==K → not strictly greater → jf=0 → ret_k(99)
    OpcodeCase("jgt_x_boundary_eq_not_taken",
               [_ld_imm(5), _ldx_imm(5), _jmp_x(BPF_JGT, jt=1, jf=0), _ret_k(99), _ret_k(0)],
               99),
    OpcodeCase("jge_x_boundary_eq_taken",
               [_ld_imm(5), _ldx_imm(5), _jmp_x(BPF_JGE, jt=1, jf=0), _ret_k(0), _ret_k(99)],
               99),  # A==X → taken → skip ret_k(0) → ret_k(99)

    # -----------------------------------------------------------------------
    # Group 4: Indirect loads with non-zero k, X = 0
    # Verifies the k offset field is used even when X holds 0.
    # packet[0+23]=0x06  packet[0+36:38]=0x5678  packet[0+38:42]=0x01020304
    # -----------------------------------------------------------------------
    OpcodeCase("ldb_ind_k_only",
               [_ldx_imm(0), _ldb_ind(23), _ret_a()],
               0x06),
    OpcodeCase("ldh_ind_k_only",
               [_ldx_imm(0), _ldh_ind(36), _ret_a()],
               0x5678),
    OpcodeCase("ldw_ind_k_only",
               [_ldx_imm(0), _ldw_ind(38), _ret_a()],
               0x01020304),

    # -----------------------------------------------------------------------
    # Group 5: Indirect loads with both X and k non-zero
    # X=14 (eth header size), k=offset-within-ipv4-onwards
    # packet[14+9=23]=0x06  packet[14+22=36:38]=0x5678  packet[14+24=38:42]=0x01020304
    # -----------------------------------------------------------------------
    OpcodeCase("ldb_ind_x_plus_k",
               [_ldx_imm(14), _ldb_ind(9), _ret_a()],
               0x06),
    OpcodeCase("ldh_ind_x_plus_k",
               [_ldx_imm(14), _ldh_ind(22), _ret_a()],
               0x5678),
    OpcodeCase("ldw_ind_x_plus_k",
               [_ldx_imm(14), _ldw_ind(24), _ret_a()],
               0x01020304),

    # -----------------------------------------------------------------------
    # Group 6: MSH + indirect — the canonical dynamic-header-length pattern
    # ldxb_msh(14) sets X = (packet[14] & 0xF) * 4 = 5*4 = 20 (IPv4 IHL)
    # Then ldb/ldh/ldw ind with offset relative to X locate TCP fields.
    # packet[20+3=23]=0x06  packet[20+16=36:38]=0x5678  packet[20+18=38:42]=0x01020304
    # -----------------------------------------------------------------------
    OpcodeCase("msh_ldb_ind_protocol",
               [_ldxb_msh(14), _ldb_ind(3), _ret_a()],
               0x06),
    OpcodeCase("msh_ldh_ind_dst_port",
               [_ldxb_msh(14), _ldh_ind(16), _ret_a()],
               0x5678),
    OpcodeCase("msh_ldw_ind_seq",
               [_ldxb_msh(14), _ldw_ind(18), _ret_a()],
               0x01020304),

    # -----------------------------------------------------------------------
    # Group 7: Long forward ja jumps (offset > 1)
    # -----------------------------------------------------------------------
    OpcodeCase("ja_skip_two",
               [_ja(2), _ret_k(0), _ret_k(0), _ret_k(0x55)],
               0x55),
    OpcodeCase("ja_skip_three",
               [_ja(3), _ret_k(0), _ret_k(0), _ret_k(0), _ret_k(0x66)],
               0x66),

    # -----------------------------------------------------------------------
    # Group 8: jf multi-skip (jf > 1)
    # jeq false with jf=2: skips two instructions after the jump.
    # -----------------------------------------------------------------------
    OpcodeCase("jeq_jf_skip_two",
               [_ld_imm(4), _jmp_k(BPF_JEQ, 5, jt=0, jf=2), _ret_k(0), _ret_k(0), _ret_k(0x55)],
               0x55),

    # -----------------------------------------------------------------------
    # Group 9: ALU edge cases
    # -----------------------------------------------------------------------
    # 32-bit wraparound
    OpcodeCase("alu_add_overflow",
               [_ld_imm(0xFFFFFFFF), _alu_k(BPF_ADD, 1), _ret_a()],
               0),
    OpcodeCase("alu_sub_underflow",
               [_ld_imm(0), _alu_k(BPF_SUB, 1), _ret_a()],
               0xFFFFFFFF),
    # Zero operands
    OpcodeCase("alu_mul_zero",
               [_ld_imm(0xFF), _alu_k(BPF_MUL, 0), _ret_a()],
               0),
    OpcodeCase("alu_and_zero",
               [_ld_imm(0xFF), _alu_k(BPF_AND, 0), _ret_a()],
               0),
    OpcodeCase("alu_or_zero",
               [_ld_imm(0), _alu_k(BPF_OR, 0x42), _ret_a()],
               0x42),
    # Identity shifts (shift by 0)
    OpcodeCase("alu_lsh_zero",
               [_ld_imm(0x55), _alu_k(BPF_LSH, 0), _ret_a()],
               0x55),
    OpcodeCase("alu_rsh_zero",
               [_ld_imm(0x55), _alu_k(BPF_RSH, 0), _ret_a()],
               0x55),
    # Identity multiply/divide
    OpcodeCase("alu_mul_one",
               [_ld_imm(0x1234), _alu_k(BPF_MUL, 1), _ret_a()],
               0x1234),
    OpcodeCase("alu_div_one",
               [_ld_imm(0x1234), _alu_k(BPF_DIV, 1), _ret_a()],
               0x1234),
    # NEG of zero — this DUT implements NEG as bitwise NOT (~), confirmed by
    # the existing suite: ~1 = 0xFFFFFFFE.  Therefore ~0 = 0xFFFFFFFF.
    OpcodeCase("alu_neg_zero",
               [_ld_imm(0), _alu_k(BPF_NEG, 0), _ret_a()],
               0xFFFFFFFF),
    # XOR a value with itself via TAX: A ^ A = 0
    OpcodeCase("alu_xor_self",
               [_ld_imm(0xAA), _tax(), _alu_x(BPF_XOR), _ret_a()],
               0),

    # -----------------------------------------------------------------------
    # Group 10: Multiple scratch memory slot isolation
    # Write four distinct power-of-two values to M[0..3] then XOR them all.
    # Result: 0x11 ^ 0x22 ^ 0x44 ^ 0x88 = 0xFF.
    # Any slot aliasing would corrupt the XOR chain.
    # -----------------------------------------------------------------------
    OpcodeCase("scratch_slots_isolation",
               [
                   _ld_imm(0x11), _st(0),
                   _ld_imm(0x22), _st(1),
                   _ld_imm(0x44), _st(2),
                   _ld_imm(0x88), _st(3),
                   _ld_mem(0), _tax(),
                   _ld_mem(1), _alu_x(BPF_XOR), _tax(),
                   _ld_mem(2), _alu_x(BPF_XOR), _tax(),
                   _ld_mem(3), _alu_x(BPF_XOR),
                   _ret_a(),
               ],
               0xFF),
    # STX path: store X register into slot 5, reload it, verify via TXA
    OpcodeCase("scratch_stx_slot5",
               [_ldx_imm(0x77), _stx(5), _ldx_imm(0), _ldx_mem(5), _txa(), _ret_a()],
               0x77),

    # -----------------------------------------------------------------------
    # Group 11: Combined multi-instruction programs
    # -----------------------------------------------------------------------
    # ALU chain: 10 +5=15, *2=30, -6=24, /4=6
    OpcodeCase("combined_alu_chain",
               [
                   _ld_imm(10),
                   _alu_k(BPF_ADD, 5),
                   _alu_k(BPF_MUL, 2),
                   _alu_k(BPF_SUB, 6),
                   _alu_k(BPF_DIV, 4),
                   _ret_a(),
               ],
               6),
    # Scratch accumulate: M[0]=100, M[1]=50 → sum = 150
    OpcodeCase("combined_scratch_accumulate",
               [
                   _ld_imm(100), _st(0),
                   _ld_imm(50), _st(1),
                   _ld_mem(0), _tax(),
                   _ld_mem(1), _alu_x(BPF_ADD),
                   _ret_a(),
               ],
               150),
    # TAX/TXA chain: load 0xAA into X, overwrite A with 0x55, overwrite X
    # with 0x55, then TXA restores 0x55, OR with 0xAA → 0xFF
    OpcodeCase("combined_tax_txa_chain",
               [
                   _ld_imm(0xAA), _tax(),
                   _ld_imm(0x55), _tax(),
                   _ld_imm(0), _txa(),
                   _alu_k(BPF_OR, 0xAA),
                   _ret_a(),
               ],
               0xFF),

    # -----------------------------------------------------------------------
    # Group 12: Combined filter programs (realistic multi-check sequences)
    # -----------------------------------------------------------------------
    # Accept path: packet is TCP (protocol==6) AND has SYN bit (flags & 0x02)
    OpcodeCase("combined_filter_tcp_syn_accept",
               [
                   _ldb_abs(23),
                   _jmp_k(BPF_JEQ, 0x06, jt=1, jf=0),
                   _ret_k(0),
                   _ldb_abs(47),
                   _jmp_k(BPF_JSET, 0x02, jt=1, jf=0),
                   _ret_k(0),
                   _ret_k(1),
               ],
               1),
    # Reject path: filter expects UDP (0x11) but packet is TCP (0x06) → ret 0
    OpcodeCase("combined_filter_udp_reject",
               [
                   _ldb_abs(23),
                   _jmp_k(BPF_JEQ, 0x11, jt=1, jf=0),
                   _ret_k(0),
                   _ret_k(1),
               ],
               0),
    # MSH-based filter: use dynamic IHL to locate TCP flags, then check SYN
    # ldxb_msh(14) → X=20 (IHL); packet[20+27=47]=0x12 (SYN|ACK); 0x12 & 0x02 ≠ 0 → accept
    OpcodeCase("combined_msh_ind_filter_syn",
               [
                   _ldxb_msh(14),               # X = IPv4 IHL in bytes = 20
                   _ldb_ind(27),                # A = packet[20+27=47] = 0x12 (TCP flags)
                   _jmp_k(BPF_JSET, 0x02, jt=1, jf=0),
                   _ret_k(0),
                   _ret_k(1),
               ],
               1),
]


# ---------------------------------------------------------------------------
# Suite report
# ---------------------------------------------------------------------------

SUITE_RESULTS: list[OpcodeCaseOutcome] = []
SUITE_REPORT_PATH = unique_artifact_path(Path("reports") / "bpf_opcode_full_coverage.md")


def _write_suite_report() -> None:
    if not SUITE_RESULTS:
        return

    passed = sum(1 for r in SUITE_RESULTS if r.passed)
    failed = len(SUITE_RESULTS) - passed
    failed_rows = [r for r in SUITE_RESULTS if not r.passed]

    lines = [
        "# BPF Opcode Full Coverage Suite",
        "",
        "## Summary",
        "",
        f"- Total cases: `{len(SUITE_RESULTS)}`",
        f"- Passed cases: `{passed}`",
        f"- Failed cases: `{failed}`",
        "",
        "## Case Results",
        "",
        "| Case | Returned | Expected Ret | Actual Ret | Expected Accept | Actual Accept | Passed |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in SUITE_RESULTS:
        lines.append(
            f"| `{r.name}` | `{r.returned}` | `0x{r.expected_ret:08x}` | `0x{r.actual_ret:08x}` | "
            f"`{r.expected_accept}` | `{r.accepted}` | `{r.passed}` |"
        )

    lines.extend(["", "## Failed Cases", ""])
    if not failed_rows:
        lines.append("All cases passed.")
    else:
        lines.extend(["| Case | Failure Detail |", "| --- | --- |"])
        for r in failed_rows:
            lines.append(
                f"| `{r.name}` | expected ret=`0x{r.expected_ret:08x}` actual ret=`0x{r.actual_ret:08x}` "
                f"expected accept=`{r.expected_accept}` actual accept=`{r.accepted}` returned=`{r.returned}` |"
            )

    SUITE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUITE_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(scope="module", autouse=True)
def _full_coverage_report_fixture():
    SUITE_RESULTS.clear()
    yield
    _write_suite_report()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run_case(case: OpcodeCase):
    dut = build_bpf_env(waveform=waveform_path_for_test(f"test_bpf_opcode_full_{case.name}"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / f"bpf_opcode_full_{case.name}.csv")
    tb.init_signals()
    print(f"\nOpcode full-coverage case: {case.name}")
    tb.load_packet(PACKET)
    tb.load_program(case.program)
    tb.print_program()
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=128)
    tb.print_run_result(result)
    tb.print_register_snapshot()
    return result


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_bpf_env_opcode_full_coverage(case: OpcodeCase):
    """Verify extended BPF opcode coverage: jf paths, indirect addressing, edge cases, combined programs."""
    if not verilator_available():
        pytest.skip("verilator is not installed")

    result = _run_case(case)
    expected_accept = case.expected_ret != 0
    passed = (
        result.returned
        and result.ret_value == case.expected_ret
        and result.accepted == expected_accept
    )
    SUITE_RESULTS.append(
        OpcodeCaseOutcome(
            name=case.name,
            expected_ret=case.expected_ret,
            actual_ret=result.ret_value,
            returned=result.returned,
            accepted=result.accepted,
            expected_accept=expected_accept,
            passed=passed,
            trace_path=result.trace_path,
            report_path=result.report_path,
        )
    )

    assert result.returned, f"{case.name}: DUT did not return within cycle budget"
    assert result.ret_value == case.expected_ret, (
        f"{case.name}: ret_value=0x{result.ret_value:08x} expected=0x{case.expected_ret:08x}"
    )
    assert result.accepted == expected_accept, (
        f"{case.name}: accepted={result.accepted} expected={expected_accept}"
    )
    if reports_enabled():
        assert result.trace_path.exists()
        assert result.report_path.exists()
