#!/usr/bin/env python3
import argparse
from pathlib import Path
from textwrap import dedent


DUT_BUILDERS = dedent("""\
from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholderPass, VerilogTranslationImportPass
from pymtl3.passes.PassGroups import DefaultPassGroup

from pymtl.wrappers.bpf_env_wrapper import BpfEnv


def build_bpf_env():
    dut = BpfEnv()
    dut.elaborate()
    dut.apply( VerilogPlaceholderPass() )
    dut = VerilogTranslationImportPass()( dut )
    dut.apply( DefaultPassGroup() )
    dut.sim_reset()
    return dut
""")


PACKETS = dedent("""\
def make_tcp_packet():
    # Ethernet + IPv4 + TCP minimal example
    eth = bytes.fromhex(
        "001122334455"  # dst mac
        "66778899aabb"  # src mac
        "0800"          # ethertype IPv4
    )

    ip = bytes([
        0x45, 0x00,             # version/ihl, dscp
        0x00, 0x28,             # total length
        0x00, 0x01,             # identification
        0x00, 0x00,             # flags/frag
        0x40,                   # ttl
        0x06,                   # protocol = TCP
        0x00, 0x00,             # checksum
        192, 168, 1, 10,        # src ip
        192, 168, 1, 20,        # dst ip
    ])

    tcp = bytes([
        0x1F, 0x90,             # src port 8080
        0x00, 0x50,             # dst port 80
        0x00, 0x00, 0x00, 0x01, # seq
        0x00, 0x00, 0x00, 0x00, # ack
        0x50, 0x02,             # data offset, SYN
        0x72, 0x10,             # window
        0x00, 0x00,             # checksum
        0x00, 0x00,             # urgent
    ])

    return eth + ip + tcp


def make_zero_program(n_words=4):
    return [0] * n_words
""")


BPF_PYTHON_TB = dedent("""\
import csv
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class BpfCycle:
    cycle: int
    bpf_start: int
    bpf_return: int
    bpf_active: int
    bpf_accept: int
    bpf_reject: int
    bpf_ret_value: int
    bpf_mmap_addr: int
    bpf_mmap_wdata: int
    bpf_mmap_wr: int
    bpf_pram_waddr: int
    bpf_pram_wdata: int
    bpf_pram_wr: int
    bpf_packet_len: int


class BpfPythonTB:
    # IMPORTANT:
    # BPF_START_ADDR is used by the Verilog TB but its numeric value is not shown
    # in tb_bpf.v directly. Set it here once you locate it in the package/include files.
    BPF_START_ADDR = 0

    def __init__(self, dut):
        self.dut = dut
        self.trace = []

    def init_signals(self):
        d = self.dut

        d.bpf_start        @= 0
        d.bpf_packet_len   @= 0
        d.bpf_packet_loss  @= 0

        d.bpf_mmap_addr    @= 0
        d.bpf_mmap_wdata   @= 0
        d.bpf_mmap_wr      @= 0
        d.bpf_mmap_rd      @= 0

        d.bpf_pram_waddr   @= 0
        d.bpf_pram_wdata   @= 0
        d.bpf_pram_wr      @= 0
        d.bpf_pram_raddr   @= 0

        d.bpf_pram_bank_rx   @= 0
        d.bpf_pram_bank_bpf  @= 0
        d.bpf_pram_bank_tx   @= 0

        d.sim_eval_combinational()

    def log_cycle(self, cycle):
        d = self.dut
        self.trace.append(BpfCycle(
            cycle=cycle,
            bpf_start=int(d.bpf_start),
            bpf_return=int(d.bpf_return),
            bpf_active=int(d.bpf_active),
            bpf_accept=int(d.bpf_accept),
            bpf_reject=int(d.bpf_reject),
            bpf_ret_value=int(d.bpf_ret_value),
            bpf_mmap_addr=int(d.bpf_mmap_addr),
            bpf_mmap_wdata=int(d.bpf_mmap_wdata),
            bpf_mmap_wr=int(d.bpf_mmap_wr),
            bpf_pram_waddr=int(d.bpf_pram_waddr),
            bpf_pram_wdata=int(d.bpf_pram_wdata),
            bpf_pram_wr=int(d.bpf_pram_wr),
            bpf_packet_len=int(d.bpf_packet_len),
        ))

    def dump_trace_csv(self, path):
        if not self.trace:
            return
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=asdict(self.trace[0]).keys())
            writer.writeheader()
            for row in self.trace:
                writer.writerow(asdict(row))

    def load_program(self, instructions, start_addr=0):
        # Mirrors the Verilog TB approach:
        # each 64-bit instruction is written as two 32-bit MMAP writes.
        d = self.dut

        for i, inst in enumerate(instructions):
            low  = inst & 0xffffffff
            high = (inst >> 32) & 0xffffffff

            d.bpf_mmap_addr  @= start_addr + (i << 1)
            d.bpf_mmap_wdata @= low
            d.bpf_mmap_wr    @= 1
            d.sim_tick()

            d.bpf_mmap_addr  @= start_addr + (i << 1) + 1
            d.bpf_mmap_wdata @= high
            d.bpf_mmap_wr    @= 1
            d.sim_tick()

        d.bpf_mmap_wr @= 0

        # Enable bit + start address, same style as Verilog TB.
        d.bpf_mmap_addr  @= self.BPF_START_ADDR
        d.bpf_mmap_wdata @= 0x80000000 | start_addr
        d.bpf_mmap_wr    @= 1
        d.sim_tick()
        d.bpf_mmap_wr    @= 0

    def load_packet(self, packet_bytes: bytes):
        # Mirrors Verilog init_packet_mem:
        # packet is written as 32-bit words with byte swap
        d = self.dut

        for addr in range(0, len(packet_bytes), 4):
            chunk = packet_bytes[addr:addr+4]
            while len(chunk) < 4:
                chunk += b'\\x00'

            # same byte ordering idea as the Verilog TB
            word = (chunk[3] << 24) | (chunk[2] << 16) | (chunk[1] << 8) | chunk[0]

            d.bpf_pram_waddr @= addr
            d.bpf_pram_wdata @= word
            d.bpf_pram_wr    @= 1
            d.sim_tick()

        d.bpf_pram_wr @= 0

    def start(self, packet_len):
        d = self.dut
        d.bpf_packet_len @= packet_len
        d.bpf_start      @= 1
        d.sim_tick()
        d.bpf_start      @= 0
        d.sim_eval_combinational()

    def run_until_return(self, max_cycles=1000):
        d = self.dut
        cycle = 0

        while not int(d.bpf_return):
            self.log_cycle(cycle)
            d.sim_tick()
            cycle += 1
            if cycle >= max_cycles:
                raise RuntimeError("Timeout waiting for bpf_return")

        self.log_cycle(cycle)
        return cycle

    def print_summary(self):
        d = self.dut
        print("\\n[BPF SUMMARY]")
        print("  bpf_return   =", int(d.bpf_return))
        print("  bpf_active   =", int(d.bpf_active))
        print("  bpf_accept   =", int(d.bpf_accept))
        print("  bpf_reject   =", int(d.bpf_reject))
        print("  bpf_ret_value=", hex(int(d.bpf_ret_value)))
""")


TEST_SMOKE = dedent("""\
from tests.bpf_env.dut_builders import build_bpf_env
from tests.bpf_env.bpf_python_tb import BpfPythonTB
from tests.bpf_env.packets import make_zero_program


def test_bpf_env_smoke():
    dut = build_bpf_env()
    tb = BpfPythonTB(dut)
    tb.init_signals()

    # Very small placeholder program
    tb.load_program(make_zero_program(2), start_addr=0)
    tb.start(packet_len=0)

    try:
        tb.run_until_return(max_cycles=50)
    except RuntimeError:
        # still useful during bring-up
        pass

    tb.print_summary()
    tb.dump_trace_csv("reports/bpf_env_smoke_trace.csv")

    assert int(dut.bpf_active) in (0, 1)
    assert int(dut.bpf_return) in (0, 1)
""")


TEST_TCP = dedent("""\
import pytest

from tests.bpf_env.dut_builders import build_bpf_env
from tests.bpf_env.bpf_python_tb import BpfPythonTB
from tests.bpf_env.packets import make_tcp_packet, make_zero_program


@pytest.mark.skip(reason="Replace placeholder program with real compiled BPF instructions first")
def test_bpf_env_tcp_placeholder():
    dut = build_bpf_env()
    tb = BpfPythonTB(dut)
    tb.init_signals()

    packet = make_tcp_packet()

    # Replace with real 64-bit instructions compiled from your BPF assembly.
    program = make_zero_program(4)

    tb.load_packet(packet)
    tb.load_program(program, start_addr=0)
    tb.start(packet_len=len(packet))
    tb.run_until_return(max_cycles=300)

    tb.print_summary()
    tb.dump_trace_csv("reports/bpf_env_tcp_trace.csv")

    # Replace these with real expectations once the program is known
    assert int(dut.bpf_return) == 1
""")


README = dedent("""\
# Python BPF TB Bootstrap

This scaffold was generated from the flow seen in `tb_bpf.v`.

It mirrors these steps:

1. initialize DUT signals
2. load packet into PRAM
3. load instructions into IRAM through MMAP
4. pulse `bpf_start`
5. run until `bpf_return`

Generated files:
- tests/bpf_env/dut_builders.py
- tests/bpf_env/packets.py
- tests/bpf_env/bpf_python_tb.py
- tests/integration/test_bpf_env_smoke.py
- tests/integration/test_bpf_env_tcp_placeholder.py

Notes:
- DUT target is `bpf_env`
- `BPF_START_ADDR` still needs the real constant from your RTL package/include files
- the TCP test is intentionally skipped until you provide real compiled instructions
""")


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Bootstrap Python TB scaffold for bpf_env from the Verilog TB flow.")
    ap.add_argument("--repo-root", default=".", help="Repo root")
    ap.add_argument("--force", action="store_true", help="Overwrite generated files")
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()

    targets = [
        root / "tests" / "bpf_env" / "__init__.py",
        root / "tests" / "bpf_env" / "dut_builders.py",
        root / "tests" / "bpf_env" / "packets.py",
        root / "tests" / "bpf_env" / "bpf_python_tb.py",
        root / "tests" / "integration" / "test_bpf_env_smoke.py",
        root / "tests" / "integration" / "test_bpf_env_tcp_placeholder.py",
        root / "tests" / "README_bpf_tb.md",
    ]

    if not args.force:
        existing = [p for p in targets if p.exists()]
        if existing:
            print("[INFO] Existing files found:")
            for p in existing:
                print("  -", p)
            print("[INFO] Re-run with --force to overwrite.")
            return

    write_file(root / "tests" / "bpf_env" / "__init__.py", "")
    write_file(root / "tests" / "bpf_env" / "dut_builders.py", DUT_BUILDERS)
    write_file(root / "tests" / "bpf_env" / "packets.py", PACKETS)
    write_file(root / "tests" / "bpf_env" / "bpf_python_tb.py", BPF_PYTHON_TB)
    write_file(root / "tests" / "integration" / "test_bpf_env_smoke.py", TEST_SMOKE)
    write_file(root / "tests" / "integration" / "test_bpf_env_tcp_placeholder.py", TEST_TCP)
    write_file(root / "tests" / "README_bpf_tb.md", README)

    print("[OK] Generated Python TB scaffold:")
    for p in targets:
        print("  -", p)


if __name__ == "__main__":
    main()