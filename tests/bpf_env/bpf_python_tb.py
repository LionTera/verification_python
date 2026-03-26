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


def decode_bpf_instruction(instruction: int) -> dict[str, int]:
    return {
        "code": (instruction >> 48) & 0xFF,
        "jt": (instruction >> 40) & 0xFF,
        "jf": (instruction >> 32) & 0xFF,
        "k": instruction & 0xFFFFFFFF,
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


def format_bpf_program(instructions: Iterable[int]) -> str:
    lines = ["BPF program:"]
    for index, instruction in enumerate(instructions):
        lines.append(f"  [{index:02d}] 0x{instruction:016x}  {format_bpf_instruction(instruction)}")
    return "\n".join(lines)


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
        self._loaded_program: list[int] = []

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
            chunk = packet[offset:offset + 4].ljust(4, b"\x00")
            word = int.from_bytes(chunk, "big")
            self.dut.bpf_pram_waddr @= base_addr + offset
            self.dut.bpf_pram_wdata @= word
            self.dut.bpf_pram_wr @= 1
            self._tick()
            self.dut.bpf_pram_wr @= 0
            self._tick()

    def load_program(self, instructions: Iterable[int], base_addr: int = BPF_IRAM_ADDR) -> None:
        self._loaded_program = list(instructions)
        for index, instruction in enumerate(self._loaded_program):
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

    def print_packet_summary(self, packet: bytes) -> None:
        print(f"Packet length: {len(packet)} bytes")
        print(f"Packet bytes:  {packet.hex()}")

    def print_program(self) -> None:
        print(format_bpf_program(self._loaded_program))

    def print_run_result(self, result: BpfRunResult) -> None:
        print(
            "Run result: "
            f"cycles={result.cycles} returned={result.returned} "
            f"accepted={result.accepted} ret_value=0x{result.ret_value:08x} "
            f"trace={result.trace_path}"
        )
