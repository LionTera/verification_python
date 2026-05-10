"""Integration test for the unified opcode-coverage program.

Loads a single 75-instruction program that exercises every implemented
instruction type in one linear run:

  ldb abs · ldh abs · ld word abs · ldb ind (ldxb MSH)
  st/stx/ld/ldx M[]
  add/sub/mul/div/mod/or/and/xor/lsh/rsh x  ·  tax · txa
  add/sub/mul/div/or/and/xor/lsh/rsh/mod #k  ·  neg
  jal (jump-and-link)  ·  jra (jump-return-address)
  jeq/jge/jgt/jset  with K and with X
  ja  with negative k (backwards loop)
  ret a

Expected packet: Ethernet + IPv4/TCP, IHL=5, src_ip=10.10.1.1
Expected result: ret a with A=1  →  accepted, ret_value=1

Every `ret #0` in the program is a guard — if any jump misbehaves the
test will fail via `assert result.accepted`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import BpfPythonTB, reports_enabled
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.packets import make_tcp_packet

# generate_bpf.py lives at the repo root (same directory as conftest.py).
# The repo root is always on sys.path when pytest is invoked normally.
from generate_bpf import _cov_unified


# Packet matching the offsets baked into the unified program:
#   offset 23  → protocol = 6 (TCP)
#   offset 22  → TTL byte (IHL=5 → no options, so offsets are standard)
#   offset 26  → src IP = 10.10.1.1 = 0x0A0A0101
_PACKET = make_tcp_packet(
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
)

# The program is 75 instructions; each runs in ~3 pipeline cycles
# plus the backwards loop (3 iterations × 3 instr). 400 cycles is
# comfortable headroom.
_MAX_CYCLES = 400


@pytest.mark.integration
def test_bpf_coverage_unified():
    """Run the unified coverage program end-to-end on the DUT."""
    if not verilator_available():
        pytest.skip("verilator is not installed")

    program = _cov_unified()

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_coverage_unified"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_coverage_unified.csv")

    tb.init_signals()
    tb.load_packet(_PACKET)
    tb.load_program(program)
    tb.configure_start_address(0)
    tb.pulse_start()
    result = tb.run_until_return(max_cycles=_MAX_CYCLES)
    tb.print_run_result(result)

    # Program must complete before the cycle budget runs out
    assert result.returned, (
        f"DUT did not return within {_MAX_CYCLES} cycles — "
        "pipeline stall or infinite loop"
    )

    # All conditional-jump guards in the program lead to ret #0 on failure.
    # If any section misbehaved, accepted will be False.
    assert result.accepted, (
        f"Program returned ret_value=0x{result.ret_value:08x} — "
        "a guard ret #0 was hit; check which instruction section failed"
    )

    # ret a with A=1 at the very end
    assert result.ret_value == 1, (
        f"Expected ret_value=1 (from ret a with A=1), "
        f"got 0x{result.ret_value:08x}"
    )

    if reports_enabled():
        assert result.trace_path.exists()
        assert result.report_path.exists()
