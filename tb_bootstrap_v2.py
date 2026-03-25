#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
from textwrap import dedent


BOOTSTRAP_FILES = {
    "tests/bpf_env/dut_builders.py": dedent(
        """
        from __future__ import annotations

        import shutil

        from pymtl3 import DefaultPassGroup
        from pymtl3.passes.backends.verilog import VerilogPlaceholderPass, VerilogTranslationImportPass

        from pymtl.wrappers.bpf_env_wrapper import BpfEnv


        def verilator_available() -> bool:
            return shutil.which("verilator") is not None


        def build_bpf_env():
            if not verilator_available():
                raise RuntimeError("verilator is required for VerilogTranslationImportPass")

            dut = BpfEnv()
            dut.elaborate()
            dut.apply(VerilogPlaceholderPass())
            dut = VerilogTranslationImportPass()(dut)
            dut.apply(DefaultPassGroup())
            dut.sim_reset()
            return dut
        """
    ).strip()
    + "\n",
    "tests/bpf_env/packets.py": dedent(
        """
        from __future__ import annotations

        import ipaddress


        def _checksum(data: bytes) -> int:
            if len(data) % 2:
                data += b"\\x00"
            total = 0
            for idx in range(0, len(data), 2):
                total += int.from_bytes(data[idx:idx + 2], "big")
                total = (total & 0xFFFF) + (total >> 16)
            return (~total) & 0xFFFF


        def make_tcp_packet(
            *,
            src_mac: bytes = b"\\x02\\x00\\x00\\x00\\x00\\x01",
            dst_mac: bytes = b"\\x02\\x00\\x00\\x00\\x00\\x02",
            src_ip: str = "192.168.1.10",
            dst_ip: str = "192.168.1.20",
            src_port: int = 1234,
            dst_port: int = 80,
            seq: int = 1,
            ack: int = 0,
            flags: int = 0x02,
            payload: bytes = b"",
        ) -> bytes:
            eth_type = b"\\x08\\x00"
            version_ihl = 0x45
            dscp_ecn = 0
            total_length = 20 + 20 + len(payload)
            identification = 0x1234
            flags_fragment = 0x4000
            ttl = 64
            protocol = 6
            src_ip_bytes = ipaddress.ip_address(src_ip).packed
            dst_ip_bytes = ipaddress.ip_address(dst_ip).packed

            ipv4_header = bytearray(20)
            ipv4_header[0] = version_ihl
            ipv4_header[1] = dscp_ecn
            ipv4_header[2:4] = total_length.to_bytes(2, "big")
            ipv4_header[4:6] = identification.to_bytes(2, "big")
            ipv4_header[6:8] = flags_fragment.to_bytes(2, "big")
            ipv4_header[8] = ttl
            ipv4_header[9] = protocol
            ipv4_header[10:12] = b"\\x00\\x00"
            ipv4_header[12:16] = src_ip_bytes
            ipv4_header[16:20] = dst_ip_bytes
            ipv4_header[10:12] = _checksum(bytes(ipv4_header)).to_bytes(2, "big")

            data_offset = 5
            tcp_header = bytearray(20)
            tcp_header[0:2] = src_port.to_bytes(2, "big")
            tcp_header[2:4] = dst_port.to_bytes(2, "big")
            tcp_header[4:8] = seq.to_bytes(4, "big")
            tcp_header[8:12] = ack.to_bytes(4, "big")
            tcp_header[12] = data_offset << 4
            tcp_header[13] = flags
            tcp_header[14:16] = (4096).to_bytes(2, "big")
            tcp_header[16:18] = b"\\x00\\x00"
            tcp_header[18:20] = b"\\x00\\x00"

            pseudo_header = (
                src_ip_bytes
                + dst_ip_bytes
                + b"\\x00"
                + bytes([protocol])
                + (len(tcp_header) + len(payload)).to_bytes(2, "big")
            )
            tcp_header[16:18] = _checksum(pseudo_header + bytes(tcp_header) + payload).to_bytes(2, "big")

            return dst_mac + src_mac + eth_type + bytes(ipv4_header) + bytes(tcp_header) + payload
        """
    ).strip()
    + "\n",
    "tests/bpf_env/bpf_python_tb.py": dedent(
        """
        from __future__ import annotations

        import csv
        import logging
        from dataclasses import dataclass
        from pathlib import Path
        from typing import Iterable


        LOGGER = logging.getLogger(__name__)

        BPF_START_ADDR = 0x1000
        BPF_IRAM_ADDR = 0x2000
        RET_K_OPCODE = 0x06
        RET_A_OPCODE = 0x16


        def encode_bpf_instruction(code: int, *, jt: int = 0, jf: int = 0, k: int = 0) -> int:
            return ((code & 0xFF) << 48) | ((jt & 0xFF) << 40) | ((jf & 0xFF) << 32) | (k & 0xFFFFFFFF)


        @dataclass
        class BpfRunResult:
            cycles: int
            returned: bool
            accepted: bool
            ret_value: int
            trace_path: Path


        class BpfPythonTB:
            def __init__(self, dut, trace_path: str | Path = "reports/bpf_trace.csv"):
                self.dut = dut
                self.trace_path = Path(trace_path)
                self.trace_path.parent.mkdir(parents=True, exist_ok=True)
                self._cycle = 0
                self._trace_rows: list[dict[str, int]] = []

            def init_signals(self) -> None:
                self.dut.bpf_start @= 0
                self.dut.bpf_packet_len @= 0
                self.dut.bpf_packet_loss @= 0
                self.dut.bpf_mmap_addr @= 0
                self.dut.bpf_mmap_wdata @= 0
                self.dut.bpf_mmap_wr @= 0
                self.dut.bpf_mmap_rd @= 0
                self.dut.bpf_pram_waddr @= 0
                self.dut.bpf_pram_wdata @= 0
                self.dut.bpf_pram_wr @= 0
                self.dut.bpf_pram_raddr @= 0
                self.dut.bpf_pram_bank_rx @= 0
                self.dut.bpf_pram_bank_bpf @= 0
                self.dut.bpf_pram_bank_tx @= 0
                self._tick()

            def _record_trace(self) -> None:
                row = {
                    "cycle": self._cycle,
                    "bpf_start": int(self.dut.bpf_start),
                    "bpf_return": int(self.dut.bpf_return),
                    "bpf_accept": int(self.dut.bpf_accept),
                    "bpf_active": int(self.dut.bpf_active),
                    "bpf_ret_value": int(self.dut.bpf_ret_value),
                    "bpf_mmap_addr": int(self.dut.bpf_mmap_addr),
                    "bpf_mmap_ack": int(self.dut.bpf_mmap_ack),
                    "bpf_pram_waddr": int(self.dut.bpf_pram_waddr),
                    "bpf_pram_wr": int(self.dut.bpf_pram_wr),
                    "bpf_pram_raddr": int(self.dut.bpf_pram_raddr),
                }
                self._trace_rows.append(row)
                LOGGER.info("cycle=%d return=%d accept=%d ret=0x%08x", row["cycle"], row["bpf_return"], row["bpf_accept"], row["bpf_ret_value"])

            def _flush_trace(self) -> None:
                if not self._trace_rows:
                    return
                with self.trace_path.open("w", newline="", encoding="utf-8") as csv_file:
                    writer = csv.DictWriter(csv_file, fieldnames=list(self._trace_rows[0]))
                    writer.writeheader()
                    writer.writerows(self._trace_rows)

            def _tick(self, cycles: int = 1) -> None:
                for _ in range(cycles):
                    self.dut.sim_tick()
                    self._record_trace()
                    self._cycle += 1

            def write_mmap(self, addr: int, data: int, timeout: int = 20) -> None:
                self.dut.bpf_mmap_addr @= addr
                self.dut.bpf_mmap_wdata @= data
                self.dut.bpf_mmap_wr @= 1
                self.dut.bpf_mmap_rd @= 0
                for _ in range(timeout):
                    self._tick()
                    if int(self.dut.bpf_mmap_ack):
                        break
                else:
                    raise TimeoutError(f"write_mmap ack timeout at 0x{addr:04x}")
                self.dut.bpf_mmap_wr @= 0
                self._tick()

            def read_mmap(self, addr: int, timeout: int = 20) -> int:
                self.dut.bpf_mmap_addr @= addr
                self.dut.bpf_mmap_rd @= 1
                self.dut.bpf_mmap_wr @= 0
                for _ in range(timeout):
                    self._tick()
                    if int(self.dut.bpf_mmap_ack):
                        value = int(self.dut.bpf_mmap_rdata)
                        break
                else:
                    raise TimeoutError(f"read_mmap ack timeout at 0x{addr:04x}")
                self.dut.bpf_mmap_rd @= 0
                self._tick()
                return value

            def load_packet(self, packet: bytes, base_addr: int = 0) -> None:
                self.dut.bpf_packet_len @= len(packet)
                for offset in range(0, len(packet), 4):
                    chunk = packet[offset:offset + 4].ljust(4, b"\\x00")
                    word = int.from_bytes(chunk, "big")
                    self.dut.bpf_pram_waddr @= base_addr + offset
                    self.dut.bpf_pram_wdata @= word
                    self.dut.bpf_pram_wr @= 1
                    self._tick()
                    self.dut.bpf_pram_wr @= 0
                    self._tick()

            def load_program(self, instructions: Iterable[int], base_addr: int = BPF_IRAM_ADDR) -> None:
                for index, instruction in enumerate(instructions):
                    low_word = instruction & 0xFFFFFFFF
                    high_word = (instruction >> 32) & 0xFFFFFFFF
                    self.write_mmap(base_addr + index * 2, low_word)
                    self.write_mmap(base_addr + index * 2 + 1, high_word)

            def configure_start_address(self, start_addr: int = 0, enable: bool = True) -> None:
                value = ((1 if enable else 0) << 31) | ((start_addr & 0x3FF) << 1)
                self.write_mmap(BPF_START_ADDR, value)

            def pulse_start(self, cycles: int = 1) -> None:
                self.dut.bpf_start @= 1
                self._tick(cycles)
                self.dut.bpf_start @= 0
                self._tick()

            def run_until_return(self, max_cycles: int = 200) -> BpfRunResult:
                for _ in range(max_cycles):
                    if int(self.dut.bpf_return):
                        break
                    self._tick()
                returned = bool(int(self.dut.bpf_return))
                self._flush_trace()
                return BpfRunResult(
                    cycles=self._cycle,
                    returned=returned,
                    accepted=bool(int(self.dut.bpf_accept)),
                    ret_value=int(self.dut.bpf_ret_value),
                    trace_path=self.trace_path,
                )
        """
    ).strip()
    + "\n",
    "tests/integration/test_bpf_env_smoke.py": dedent(
        """
        from __future__ import annotations

        from pathlib import Path

        import pytest

        from tests.bpf_env.bpf_python_tb import BpfPythonTB, RET_K_OPCODE, encode_bpf_instruction
        from tests.bpf_env.dut_builders import build_bpf_env, verilator_available


        @pytest.mark.integration
        def test_bpf_env_smoke():
            if not verilator_available():
                pytest.skip("verilator is not installed")

            dut = build_bpf_env()
            tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_trace.csv")
            tb.init_signals()
            tb.load_packet(bytes.fromhex("00112233445566778899aabb0800"))
            tb.load_program([encode_bpf_instruction(RET_K_OPCODE, k=1)])
            tb.configure_start_address(0)
            tb.pulse_start()
            result = tb.run_until_return(max_cycles=64)

            assert result.returned
            assert result.accepted
            assert result.ret_value == 1
            assert result.trace_path.exists()
        """
    ).strip()
    + "\n",
    "tests/integration/test_bpf_env_tcp.py": dedent(
        """
        from __future__ import annotations

        from pathlib import Path

        import pytest

        from tests.bpf_env.bpf_python_tb import BpfPythonTB, RET_K_OPCODE, encode_bpf_instruction
        from tests.bpf_env.dut_builders import build_bpf_env, verilator_available
        from tests.bpf_env.packets import make_tcp_packet


        @pytest.mark.integration
        def test_bpf_env_tcp():
            if not verilator_available():
                pytest.skip("verilator is not installed")

            packet = make_tcp_packet()
            dut = build_bpf_env()
            tb = BpfPythonTB(dut, trace_path=Path("reports") / "bpf_trace.csv")
            tb.init_signals()
            tb.load_packet(packet)
            tb.load_program([encode_bpf_instruction(RET_K_OPCODE, k=1)])
            tb.configure_start_address(0)
            tb.pulse_start()
            result = tb.run_until_return(max_cycles=64)

            assert result.returned
            assert result.accepted
            assert len(packet) >= 54
        """
    ).strip()
    + "\n",
}


def bootstrap(repo_root: Path) -> None:
    for relative_path, content in BOOTSTRAP_FILES.items():
        target = repo_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the BPF PyMTL3 testbench scaffold.")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent),
        help="Repository root where the tests directory should be written",
    )
    args = parser.parse_args()
    bootstrap(Path(args.repo_root).resolve())
    print("Bootstrapped BPF testbench files.")


if __name__ == "__main__":
    main()
