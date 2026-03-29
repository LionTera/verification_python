from __future__ import annotations

from pathlib import Path

import pytest

from tests.bpf_env.bpf_python_tb import (
    BPF_ACCEPT_COUNTER_ADDR,
    BPF_PACKET_LOSS_COUNTER_ADDR,
    BPF_REJECT_COUNTER_ADDR,
    BpfPythonTB,
    RET_K_OPCODE,
    encode_bpf_instruction,
)
from tests.bpf_env.dut_builders import build_bpf_env, verilator_available, waveform_path_for_test
from tests.bpf_env.packets import make_tcp_packet


@pytest.mark.integration
@pytest.mark.slow
def test_bpf_env_packet_loss_long_run():
    if not verilator_available():
        pytest.skip("verilator is not installed")

    packet = make_tcp_packet(
        src_port=0x1234,
        dst_port=0x5678,
        seq=0x01020304,
        ack=0xA1B2C3D4,
        payload=bytes.fromhex("deadbeefcafebabe"),
    )
    program = [encode_bpf_instruction(RET_K_OPCODE, k=1)]
    loss_schedule = [0, 2, 1, 0, 4, 3]

    dut = build_bpf_env(waveform=waveform_path_for_test("test_bpf_env_packet_loss_long_run"))
    tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_packet_loss_long_run.csv")
    tb.init_signals()
    print("Long packet-loss test")
    print(f"Loss schedule (cycles per iteration): {loss_schedule}")
    tb.print_packet_summary(packet)
    tb.print_packet_memory_map(packet)
    tb.load_packet(packet)
    tb.load_program(program)
    tb.print_program()

    tb.write_mmap(BPF_ACCEPT_COUNTER_ADDR, 0)
    tb.write_mmap(BPF_REJECT_COUNTER_ADDR, 0)
    tb.write_mmap(BPF_PACKET_LOSS_COUNTER_ADDR, 0)

    for iteration, loss_cycles in enumerate(loss_schedule):
        print(f"Iteration {iteration}: loss_cycles={loss_cycles}")
        if loss_cycles:
            tb.set_packet_loss(1)
            tb.step(loss_cycles)
            tb.set_packet_loss(0)
            tb.step(1)

        tb.configure_start_address(0)
        tb.pulse_start()
        result = tb.run_until_return(max_cycles=96)
        tb.print_run_result(result)

        assert result.returned
        assert result.accepted
        assert result.ret_value == 1
        tb.step(1)
        accept_count_now = tb.read_mmap(BPF_ACCEPT_COUNTER_ADDR)
        print(f"Accept counter after iteration {iteration}: 0x{accept_count_now:08x}")
        assert accept_count_now == iteration + 1

        for _ in range(8):
            if not int(tb.dut.bpf_return) and not int(tb.dut.bpf_active):
                break
            tb.step(1)

    accept_count = tb.read_mmap(BPF_ACCEPT_COUNTER_ADDR)
    reject_count = tb.read_mmap(BPF_REJECT_COUNTER_ADDR)
    packet_loss_count = tb.read_mmap(BPF_PACKET_LOSS_COUNTER_ADDR)

    print(
        "Final counters: "
        f"accept=0x{accept_count:08x} reject=0x{reject_count:08x} "
        f"packet_loss=0x{packet_loss_count:08x}"
    )

    assert accept_count == len(loss_schedule)
    assert reject_count == 0
    assert packet_loss_count == sum(loss_schedule)
    assert tb.trace_path.exists()
    assert tb.report_path.exists()
