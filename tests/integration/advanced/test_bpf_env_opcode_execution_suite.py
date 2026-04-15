"""Broad opcode execution suite for the Python-driven BPF environment.

This test exercises representative instructions across the main classic BPF
categories used by the DUT:

- loads and load variants
- scratch-memory store/load
- ALU operations with immediate and X operands
- jumps with immediate and X operands
- return instructions
- TAX/TXA transfers

The intent is not to prove every microarchitectural corner case in one test.
Instead, it provides a compact regression that catches decode/execution
breakage across the major instruction families.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.bpf_env.artifacts import unique_artifact_path
from tests.bpf_env.bpf_python_tb import (
    BPF_A,
    BPF_ABS,
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


def _stmt(code: int, k: int = 0) -> int:
    """Encode a non-branch instruction."""
    return encode_bpf_instruction(code, k=k)


def _jump(code: int, k: int, jt: int, jf: int) -> int:
    """Encode a jump instruction."""
    return encode_bpf_instruction(code, k=k, jt=jt, jf=jf)


def _ld_imm(value: int) -> int:
    return _stmt(BPF_LD | BPF_W | BPF_IMM, value)


def _ldx_imm(value: int) -> int:
    return _stmt(BPF_LDX | BPF_W | BPF_IMM, value)


def _ld_mem(index: int) -> int:
    return _stmt(BPF_LD | BPF_W | BPF_MEM, index)


def _ldx_mem(index: int) -> int:
    return _stmt(BPF_LDX | BPF_W | BPF_MEM, index)


def _st(index: int) -> int:
    return _stmt(BPF_ST, index)


def _stx(index: int) -> int:
    return _stmt(BPF_STX, index)


def _ld_len() -> int:
    return _stmt(BPF_LD | BPF_W | BPF_LEN, 0)


def _ldx_len() -> int:
    return _stmt(BPF_LDX | BPF_W | BPF_LEN, 0)


def _ldb_abs(offset: int) -> int:
    return _stmt(BPF_LD | BPF_B | BPF_ABS, offset)


def _ldh_abs(offset: int) -> int:
    return _stmt(BPF_LD | BPF_H | BPF_ABS, offset)


def _ldw_abs(offset: int) -> int:
    return _stmt(BPF_LD | BPF_W | BPF_ABS, offset)


def _ldb_ind(offset: int) -> int:
    return _stmt(BPF_LD | BPF_B | BPF_IND, offset)


def _ldh_ind(offset: int) -> int:
    return _stmt(BPF_LD | BPF_H | BPF_IND, offset)


def _ldw_ind(offset: int) -> int:
    return _stmt(BPF_LD | BPF_W | BPF_IND, offset)


def _ldxb_msh(offset: int) -> int:
    return _stmt(BPF_LDX | BPF_B | BPF_MSH, offset)


def _alu_k(op: int, value: int) -> int:
    return _stmt(BPF_ALU | op | BPF_K, value)


def _alu_x(op: int) -> int:
    return _stmt(BPF_ALU | op | BPF_X, 0)


def _ja(offset: int) -> int:
    return _jump(BPF_JMP | BPF_JA, offset, 0, 0)


def _jmp_k(op: int, value: int, *, jt: int, jf: int) -> int:
    return _jump(BPF_JMP | op | BPF_K, value, jt, jf)


def _jmp_x(op: int, *, jt: int, jf: int) -> int:
    return _jump(BPF_JMP | op | BPF_X, 0, jt, jf)


def _ret_k(value: int) -> int:
    return _stmt(BPF_RET | BPF_K, value)


def _ret_a() -> int:
    return _stmt(BPF_RET | BPF_A, 0)


def _tax() -> int:
    return _stmt(BPF_MISC | BPF_TAX, 0)


def _txa() -> int:
    return _stmt(BPF_MISC | BPF_TXA, 0)


@dataclass(frozen=True)
class OpcodeCase:
    """One opcode-execution test case."""

    name: str
    program: list[int]
    expected_ret: int


@dataclass(frozen=True)
class OpcodeCaseOutcome:
    """Recorded outcome for one opcode-suite case."""

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


CASES = [
    OpcodeCase("ret_k", [_ret_k(0x11)], 0x11),
    OpcodeCase("ld_imm_ret_a", [_ld_imm(0x12345678), _ret_a()], 0x12345678),
    OpcodeCase("ldx_imm_txa_ret", [_ldx_imm(0x11223344), _txa(), _ret_a()], 0x11223344),
    OpcodeCase("ld_len", [_ld_len(), _ret_a()], len(PACKET)),
    OpcodeCase("ldx_len_txa", [_ldx_len(), _txa(), _ret_a()], len(PACKET)),
    OpcodeCase("ldb_abs_protocol", [_ldb_abs(23), _ret_a()], 0x06),
    OpcodeCase("ldh_abs_dst_port", [_ldh_abs(36), _ret_a()], 0x5678),
    OpcodeCase("ldw_abs_seq", [_ldw_abs(38), _ret_a()], 0x01020304),
    OpcodeCase("ldb_ind_protocol", [_ldx_imm(23), _ldb_ind(0), _ret_a()], 0x06),
    OpcodeCase("ldh_ind_dst_port", [_ldx_imm(36), _ldh_ind(0), _ret_a()], 0x5678),
    OpcodeCase("ldw_ind_seq", [_ldx_imm(38), _ldw_ind(0), _ret_a()], 0x01020304),
    OpcodeCase("ldxb_msh", [_ldxb_msh(14), _txa(), _ret_a()], 20),
    OpcodeCase("st_ld_mem", [_ld_imm(0x55), _st(3), _ld_imm(0), _ld_mem(3), _ret_a()], 0x55),
    OpcodeCase("stx_ldx_mem_txa", [_ldx_imm(0x77), _stx(2), _ldx_imm(0), _ldx_mem(2), _txa(), _ret_a()], 0x77),
    OpcodeCase("tax_txa", [_ld_imm(0x33), _tax(), _ld_imm(0), _txa(), _ret_a()], 0x33),
    OpcodeCase("alu_add_k", [_ld_imm(7), _alu_k(BPF_ADD, 5), _ret_a()], 12),
    OpcodeCase("alu_sub_k", [_ld_imm(9), _alu_k(BPF_SUB, 4), _ret_a()], 5),
    OpcodeCase("alu_mul_k", [_ld_imm(7), _alu_k(BPF_MUL, 6), _ret_a()], 42),
    OpcodeCase("alu_div_k", [_ld_imm(42), _alu_k(BPF_DIV, 7), _ret_a()], 6),
    OpcodeCase("alu_mod_k", [_ld_imm(43), _alu_k(BPF_MOD, 10), _ret_a()], 3),
    OpcodeCase("alu_or_k", [_ld_imm(0xA0), _alu_k(BPF_OR, 0x0F), _ret_a()], 0xAF),
    OpcodeCase("alu_and_k", [_ld_imm(0xAF), _alu_k(BPF_AND, 0x0F), _ret_a()], 0x0F),
    OpcodeCase("alu_lsh_k", [_ld_imm(3), _alu_k(BPF_LSH, 4), _ret_a()], 48),
    OpcodeCase("alu_rsh_k", [_ld_imm(0x80), _alu_k(BPF_RSH, 3), _ret_a()], 16),
    OpcodeCase("alu_neg", [_ld_imm(1), _alu_k(BPF_NEG, 0), _ret_a()], 0xFFFFFFFE),
    OpcodeCase("alu_xor_k", [_ld_imm(0xAA), _alu_k(BPF_XOR, 0xFF), _ret_a()], 0x55),
    OpcodeCase("alu_add_x", [_ld_imm(10), _ldx_imm(5), _alu_x(BPF_ADD), _ret_a()], 15),
    OpcodeCase("alu_sub_x", [_ld_imm(10), _ldx_imm(3), _alu_x(BPF_SUB), _ret_a()], 7),
    OpcodeCase("alu_mul_x", [_ld_imm(9), _ldx_imm(5), _alu_x(BPF_MUL), _ret_a()], 45),
    OpcodeCase("alu_div_x", [_ld_imm(40), _ldx_imm(5), _alu_x(BPF_DIV), _ret_a()], 8),
    OpcodeCase("alu_mod_x", [_ld_imm(41), _ldx_imm(5), _alu_x(BPF_MOD), _ret_a()], 1),
    OpcodeCase("alu_and_x", [_ld_imm(0xAB), _ldx_imm(0x0F), _alu_x(BPF_AND), _ret_a()], 0x0B),
    OpcodeCase("alu_or_x", [_ld_imm(0xA0), _ldx_imm(0x0F), _alu_x(BPF_OR), _ret_a()], 0xAF),
    OpcodeCase("alu_xor_x", [_ld_imm(0xAA), _ldx_imm(0xFF), _alu_x(BPF_XOR), _ret_a()], 0x55),
    OpcodeCase("alu_lsh_x", [_ld_imm(3), _ldx_imm(4), _alu_x(BPF_LSH), _ret_a()], 48),
    OpcodeCase("alu_rsh_x", [_ld_imm(0x80), _ldx_imm(3), _alu_x(BPF_RSH), _ret_a()], 16),
    OpcodeCase("ja", [_ja(1), _ret_k(0), _ret_k(9)], 9),
    OpcodeCase("jeq_k_taken", [_ld_imm(5), _jmp_k(BPF_JEQ, 5, jt=1, jf=0), _ret_k(0), _ret_k(1)], 1),
    OpcodeCase("jeq_k_not_taken", [_ld_imm(4), _jmp_k(BPF_JEQ, 5, jt=1, jf=0), _ret_k(0), _ret_k(1)], 0),
    OpcodeCase("jgt_k_taken", [_ld_imm(9), _jmp_k(BPF_JGT, 5, jt=1, jf=0), _ret_k(0), _ret_k(1)], 1),
    OpcodeCase("jge_k_taken", [_ld_imm(5), _jmp_k(BPF_JGE, 5, jt=1, jf=0), _ret_k(0), _ret_k(1)], 1),
    OpcodeCase("jset_k_taken", [_ld_imm(0xA0), _jmp_k(BPF_JSET, 0x80, jt=1, jf=0), _ret_k(0), _ret_k(1)], 1),
    OpcodeCase("jeq_x_taken", [_ld_imm(5), _ldx_imm(5), _jmp_x(BPF_JEQ, jt=1, jf=0), _ret_k(0), _ret_k(1)], 1),
    OpcodeCase("jgt_x_taken", [_ld_imm(9), _ldx_imm(5), _jmp_x(BPF_JGT, jt=1, jf=0), _ret_k(0), _ret_k(1)], 1),
    OpcodeCase("jge_x_taken", [_ld_imm(5), _ldx_imm(5), _jmp_x(BPF_JGE, jt=1, jf=0), _ret_k(0), _ret_k(1)], 1),
    OpcodeCase("jset_x_taken", [_ld_imm(0xA0), _ldx_imm(0x80), _jmp_x(BPF_JSET, jt=1, jf=0), _ret_k(0), _ret_k(1)], 1),
]


SUITE_RESULTS: list[OpcodeCaseOutcome] = []
SUITE_REPORT_PATH = unique_artifact_path(Path("reports") / "bpf_opcode_execution_suite.md")


def _write_suite_report() -> None:
    """Write a suite-level Markdown summary for the opcode execution run."""
    if not SUITE_RESULTS:
        return

    passed = sum(1 for item in SUITE_RESULTS if item.passed)
    failed = len(SUITE_RESULTS) - passed
    failed_rows = [item for item in SUITE_RESULTS if not item.passed]

    lines = [
        "# BPF Opcode Execution Suite",
        "",
        "## Summary",
        "",
        f"- Total cases: `{len(SUITE_RESULTS)}`",
        f"- Passed cases: `{passed}`",
        f"- Failed cases: `{failed}`",
        "",
        "## Case Results",
        "",
        "| Case | Returned | Expected Ret | Actual Ret | Expected Accept | Actual Accept | Passed | Trace | Report |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in SUITE_RESULTS:
        lines.append(
            f"| `{item.name}` | `{item.returned}` | `0x{item.expected_ret:08x}` | `0x{item.actual_ret:08x}` | "
            f"`{item.expected_accept}` | `{item.accepted}` | `{item.passed}` | `{item.trace_path}` | `{item.report_path}` |"
        )

    lines.extend(["", "## Failed Cases", ""])
    if not failed_rows:
        lines.append("All opcode-suite cases passed.")
    else:
        lines.extend(
            [
                "| Case | Failure Detail |",
                "| --- | --- |",
            ]
        )
        for item in failed_rows:
            lines.append(
                f"| `{item.name}` | `expected ret=0x{item.expected_ret:08x}, actual ret=0x{item.actual_ret:08x}, "
                f"expected accept={item.expected_accept}, actual accept={item.accepted}, returned={item.returned}` |"
            )

    SUITE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUITE_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(scope="module", autouse=True)
def _opcode_suite_report_fixture():
    """Emit the suite-level summary after all parameterized cases finish."""
    SUITE_RESULTS.clear()
    yield
    _write_suite_report()


def _run_case(case: OpcodeCase):
    """Run one opcode case end to end on the DUT."""
    dut = build_bpf_env(waveform=waveform_path_for_test(f"test_bpf_env_opcode_{case.name}"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / f"bpf_opcode_{case.name}.csv")
    tb.init_signals()
    print(f"Opcode suite case: {case.name}")
    tb.load_packet(PACKET)
    tb.load_program(case.program)
    tb.print_program()
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=128)
    tb.print_run_result(result)
    return result


@pytest.mark.integration
@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_bpf_env_opcode_execution_suite(case: OpcodeCase):
    """Verify that representative BPF opcodes execute with the expected result."""
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

    assert result.returned
    assert result.ret_value == case.expected_ret
    assert result.accepted == expected_accept
    if reports_enabled():
        assert result.trace_path.exists()
        assert result.report_path.exists()
