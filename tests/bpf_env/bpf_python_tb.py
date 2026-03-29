from __future__ import annotations

import csv
import ipaddress
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


LOGGER = logging.getLogger(__name__)

BPF_START_ADDR = 0x1000
BPF_ACCEPT_COUNTER_ADDR = 0x1010
BPF_REJECT_COUNTER_ADDR = 0x1011
BPF_PACKET_LOSS_COUNTER_ADDR = 0x1012
BPF_IRAM_ADDR = 0x2000
BPF_CLASS_MASK = 0x07
BPF_SIZE_MASK = 0x18
BPF_MODE_MASK = 0xE0
BPF_OP_MASK = 0xF0
BPF_SRC_MASK = 0x08

BPF_LD = 0x00
BPF_LDX = 0x01
BPF_ST = 0x02
BPF_STX = 0x03
BPF_ALU = 0x04
BPF_JMP = 0x05
BPF_RET = 0x06
BPF_MISC = 0x07

BPF_W = 0x00
BPF_H = 0x08
BPF_B = 0x10

BPF_IMM = 0x00
BPF_ABS = 0x20
BPF_IND = 0x40
BPF_MEM = 0x60
BPF_LEN = 0x80
BPF_MSH = 0xA0

BPF_ADD = 0x00
BPF_SUB = 0x10
BPF_MUL = 0x20
BPF_DIV = 0x30
BPF_OR = 0x40
BPF_AND = 0x50
BPF_LSH = 0x60
BPF_RSH = 0x70
BPF_NEG = 0x80
BPF_MOD = 0x90
BPF_XOR = 0xA0

BPF_JA = 0x00
BPF_JEQ = 0x10
BPF_JGT = 0x20
BPF_JGE = 0x30
BPF_JSET = 0x40

BPF_K = 0x00
BPF_X = 0x08
BPF_A = 0x10

RET_K_OPCODE = 0x06
RET_A_OPCODE = 0x16


def encode_bpf_instruction(code: int, *, jt: int = 0, jf: int = 0, k: int = 0) -> int:
    return ((code & 0xFF) << 48) | ((jt & 0xFF) << 40) | ((jf & 0xFF) << 32) | (k & 0xFFFFFFFF)


def bpf_stmt(code: int, k: int = 0) -> int:
    return encode_bpf_instruction(code, k=k)


def bpf_jump(code: int, k: int, jt: int, jf: int) -> int:
    return encode_bpf_instruction(code, jt=jt, jf=jf, k=k)


def bpf_ldb_abs(offset: int) -> int:
    return bpf_stmt(BPF_LD | BPF_B | BPF_ABS, offset)


def bpf_ldh_abs(offset: int) -> int:
    return bpf_stmt(BPF_LD | BPF_H | BPF_ABS, offset)


def bpf_jeq_k(value: int, *, jt: int, jf: int) -> int:
    return bpf_jump(BPF_JMP | BPF_JEQ | BPF_K, value, jt, jf)


def bpf_ret_k(value: int) -> int:
    return bpf_stmt(BPF_RET | BPF_K, value)


def bpf_ret_a() -> int:
    return bpf_stmt(BPF_RET | BPF_A, 0)


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


def format_bpf_instruction_asm(instruction: int) -> str:
    decoded = decode_bpf_instruction(instruction)
    code = decoded["code"]
    klass = code & BPF_CLASS_MASK
    size = code & BPF_SIZE_MASK
    mode = code & BPF_MODE_MASK
    op = code & BPF_OP_MASK
    src = code & BPF_SRC_MASK

    if code == RET_K_OPCODE:
        return f"ret #{decoded['k']}"
    if code == RET_A_OPCODE:
        return "ret a"
    if klass == BPF_LD:
        size_name = {
            BPF_W: "ld",
            BPF_H: "ldh",
            BPF_B: "ldb",
        }.get(size, f"ld?0x{size:02x}")
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
        if mode == BPF_IMM:
            return f"ldx #{decoded['k']}"
        if mode == BPF_LEN:
            return "ldx #pktlen"
        if mode == BPF_MEM:
            return f"ldx M[{decoded['k']}]"
        if mode == BPF_MSH:
            return f"ldxb 4*([{decoded['k']}] & 0xf)"
    if klass == BPF_ST:
        return f"st M[{decoded['k']}]"
    if klass == BPF_STX:
        return f"stx M[{decoded['k']}]"
    if klass == BPF_ALU:
        if op == BPF_NEG:
            return "neg"
        rhs = "x" if src == BPF_X else f"#{decoded['k']}"
        op_name = {
            BPF_ADD: "add",
            BPF_SUB: "sub",
            BPF_MUL: "mul",
            BPF_DIV: "div",
            BPF_OR: "or",
            BPF_AND: "and",
            BPF_LSH: "lsh",
            BPF_RSH: "rsh",
            BPF_MOD: "mod",
            BPF_XOR: "xor",
        }.get(op)
        if op_name is not None:
            return f"{op_name} {rhs}"
    if klass == BPF_JMP:
        if op == BPF_JA:
            return f"ja {decoded['k']}"
        rhs = "x" if src == BPF_X else f"#{decoded['k']}"
        op_name = {
            BPF_JEQ: "jeq",
            BPF_JGT: "jgt",
            BPF_JGE: "jge",
            BPF_JSET: "jset",
        }.get(op)
        if op_name is not None:
            return f"{op_name} {rhs}, jt {decoded['jt']}, jf {decoded['jf']}"
    return f".word 0x{instruction:016x}"


def format_bpf_program(instructions: Iterable[int]) -> str:
    lines = ["BPF program:"]
    for index, instruction in enumerate(instructions):
        lines.append(
            f"  [{index:02d}] 0x{instruction:016x}  {format_bpf_instruction_asm(instruction)}"
            f"    ; {format_bpf_instruction(instruction)}"
        )
    return "\n".join(lines)


def _format_mac(raw: bytes) -> str:
    return ":".join(f"{byte:02x}" for byte in raw)


def _format_tcp_flags(flags: int) -> str:
    names = [
        (0x80, "CWR"),
        (0x40, "ECE"),
        (0x20, "URG"),
        (0x10, "ACK"),
        (0x08, "PSH"),
        (0x04, "RST"),
        (0x02, "SYN"),
        (0x01, "FIN"),
    ]
    active = [name for mask, name in names if flags & mask]
    return ",".join(active) if active else "none"


def analyze_packet(packet: bytes) -> str:
    lines = [
        f"Packet length: {len(packet)} bytes",
        f"Packet bytes:  {packet.hex()}",
    ]

    if len(packet) < 14:
        lines.append("Ethernet: truncated header")
        return "\n".join(lines)

    dst_mac = _format_mac(packet[0:6])
    src_mac = _format_mac(packet[6:12])
    eth_type = int.from_bytes(packet[12:14], "big")
    lines.append(f"Ethernet: dst={dst_mac} src={src_mac} eth_type=0x{eth_type:04x}")

    if eth_type != 0x0800:
        lines.append("L3: not IPv4")
        return "\n".join(lines)

    if len(packet) < 34:
        lines.append("IPv4: truncated header")
        return "\n".join(lines)

    ipv4 = packet[14:]
    version = ipv4[0] >> 4
    ihl = (ipv4[0] & 0x0F) * 4
    total_length = int.from_bytes(ipv4[2:4], "big")
    ttl = ipv4[8]
    protocol = ipv4[9]
    src_ip = ipaddress.ip_address(ipv4[12:16])
    dst_ip = ipaddress.ip_address(ipv4[16:20])
    lines.append(
        "IPv4: "
        f"version={version} ihl={ihl} total_length={total_length} ttl={ttl} "
        f"protocol={protocol} src={src_ip} dst={dst_ip}"
    )

    if protocol != 6:
        lines.append("L4: not TCP")
        return "\n".join(lines)

    if len(ipv4) < ihl + 20:
        lines.append("TCP: truncated header")
        return "\n".join(lines)

    tcp = ipv4[ihl:]
    src_port = int.from_bytes(tcp[0:2], "big")
    dst_port = int.from_bytes(tcp[2:4], "big")
    seq = int.from_bytes(tcp[4:8], "big")
    ack = int.from_bytes(tcp[8:12], "big")
    data_offset = (tcp[12] >> 4) * 4
    flags = tcp[13]
    window = int.from_bytes(tcp[14:16], "big")
    payload_len = max(total_length - ihl - data_offset, 0)
    lines.append(
        "TCP: "
        f"src_port={src_port} dst_port={dst_port} seq={seq} ack={ack} "
        f"flags={_format_tcp_flags(flags)} window={window} payload_len={payload_len}"
    )
    return "\n".join(lines)


def packet_report_markdown(packet: bytes) -> str:
    lines = [
        "## Packet",
        "",
        f"- Length: `{len(packet)}` bytes",
        f"- Raw bytes: `{packet.hex()}`",
        "",
    ]

    if len(packet) < 14:
        lines.extend(["Truncated Ethernet header.", ""])
        return "\n".join(lines)

    dst_mac = _format_mac(packet[0:6])
    src_mac = _format_mac(packet[6:12])
    eth_type = int.from_bytes(packet[12:14], "big")
    lines.extend(
        [
            "### Ethernet",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Destination MAC | `{dst_mac}` |",
            f"| Source MAC | `{src_mac}` |",
            f"| EtherType | `0x{eth_type:04x}` |",
            "",
        ]
    )

    if eth_type != 0x0800 or len(packet) < 34:
        return "\n".join(lines)

    ipv4 = packet[14:]
    version = ipv4[0] >> 4
    ihl = (ipv4[0] & 0x0F) * 4
    total_length = int.from_bytes(ipv4[2:4], "big")
    ttl = ipv4[8]
    protocol = ipv4[9]
    src_ip = ipaddress.ip_address(ipv4[12:16])
    dst_ip = ipaddress.ip_address(ipv4[16:20])
    lines.extend(
        [
            "### IPv4",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Version | `{version}` |",
            f"| Header Length | `{ihl}` bytes |",
            f"| Total Length | `{total_length}` bytes |",
            f"| TTL | `{ttl}` |",
            f"| Protocol | `{protocol}` |",
            f"| Source IP | `{src_ip}` |",
            f"| Destination IP | `{dst_ip}` |",
            "",
        ]
    )

    if protocol != 6 or len(ipv4) < ihl + 20:
        return "\n".join(lines)

    tcp = ipv4[ihl:]
    src_port = int.from_bytes(tcp[0:2], "big")
    dst_port = int.from_bytes(tcp[2:4], "big")
    seq = int.from_bytes(tcp[4:8], "big")
    ack = int.from_bytes(tcp[8:12], "big")
    data_offset = (tcp[12] >> 4) * 4
    flags = tcp[13]
    window = int.from_bytes(tcp[14:16], "big")
    checksum = int.from_bytes(tcp[16:18], "big")
    urgent_ptr = int.from_bytes(tcp[18:20], "big")
    payload_len = max(total_length - ihl - data_offset, 0)
    lines.extend(
        [
            "### TCP",
            "",
            "| Field | Byte Range | Value |",
            "| --- | --- | --- |",
            f"| Source Port | `0-1` | `{src_port}` |",
            f"| Destination Port | `2-3` | `{dst_port}` |",
            f"| Sequence Number | `4-7` | `{seq}` |",
            f"| Acknowledgment Number | `8-11` | `{ack}` |",
            f"| Header Length | `12[7:4]` | `{data_offset}` bytes |",
            f"| Flags | `13` | `{_format_tcp_flags(flags)}` (`0x{flags:02x}`) |",
            f"| Window | `14-15` | `{window}` |",
            f"| Checksum | `16-17` | `0x{checksum:04x}` |",
            f"| Urgent Pointer | `18-19` | `{urgent_ptr}` |",
            f"| Payload Length | `20+` | `{payload_len}` bytes |",
            "",
        ]
    )
    return "\n".join(lines)


def packet_memory_map_text(packet: bytes) -> str:
    lines = ["Packet memory words:"]
    for offset in range(0, len(packet), 4):
        chunk = packet[offset:offset + 4]
        padded = chunk.ljust(4, b"\x00")
        lines.append(
            f"  addr=0x{offset:04x} bytes[{offset:02d}:{offset + len(chunk) - 1:02d}] "
            f"word=0x{int.from_bytes(padded, 'big'):08x} raw={chunk.hex()}"
        )
    return "\n".join(lines)


def packet_memory_map_markdown(packet: bytes) -> str:
    lines = [
        "### Packet Memory Words",
        "",
        "| PRAM Address | Packet Byte Range | 32-bit Word | Raw Bytes |",
        "| --- | --- | --- | --- |",
    ]
    for offset in range(0, len(packet), 4):
        chunk = packet[offset:offset + 4]
        padded = chunk.ljust(4, b"\x00")
        lines.append(
            f"| `0x{offset:04x}` | `{offset}-{offset + len(chunk) - 1}` | "
            f"`0x{int.from_bytes(padded, 'big'):08x}` | `{chunk.hex()}` |"
        )
    lines.append("")
    return "\n".join(lines)


def program_report_markdown(instructions: Iterable[int]) -> str:
    lines = [
        "## BPF Program",
        "",
        "| Index | Raw | Assembly | Details |",
        "| --- | --- | --- | --- |",
    ]
    for index, instruction in enumerate(instructions):
        lines.append(
            f"| `{index}` | `0x{instruction:016x}` | `{format_bpf_instruction_asm(instruction)}` | `{format_bpf_instruction(instruction)}` |"
        )
    lines.append("")
    return "\n".join(lines)


@dataclass
class BpfRunResult:
    cycles: int
    returned: bool
    accepted: bool
    ret_value: int
    trace_path: Path
    report_path: Path


class BpfPythonTB:
    def __init__(self, dut, trace_path: str | Path = "reports/bpf_trace.csv"):
        self.dut = dut
        self.trace_path = Path(trace_path)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path = self.trace_path.with_suffix(".md")
        self._cycle = 0
        self._trace_rows: list[dict[str, int]] = []
        self._loaded_program: list[int] = []
        self._loaded_packet: bytes = b""

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
            "bpf_packet_loss": int(self.dut.bpf_packet_loss),
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

    def set_packet_loss(self, value: int | bool) -> None:
        self.dut.bpf_packet_loss @= 1 if value else 0

    def step(self, cycles: int = 1) -> None:
        self._tick(cycles)

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
        self._loaded_packet = packet
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
        result = BpfRunResult(
            cycles=self._cycle,
            returned=returned,
            accepted=bool(int(self.dut.bpf_accept)),
            ret_value=int(self.dut.bpf_ret_value),
            trace_path=self.trace_path,
            report_path=self.report_path,
        )
        self._write_report(result)
        return result

    def _write_report(self, result: BpfRunResult) -> None:
        lines = [
            "# BPF Integration Report",
            "",
            "## Result",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Cycles | `{result.cycles}` |",
            f"| Returned | `{result.returned}` |",
            f"| Accepted | `{result.accepted}` |",
            f"| Return Value | `0x{result.ret_value:08x}` |",
            f"| CSV Trace | `{result.trace_path}` |",
            "",
            packet_report_markdown(self._loaded_packet),
            packet_memory_map_markdown(self._loaded_packet),
            program_report_markdown(self._loaded_program),
        ]
        result.report_path.write_text("\n".join(lines), encoding="utf-8")

    def print_packet_summary(self, packet: bytes) -> None:
        print(analyze_packet(packet))

    def print_packet_memory_map(self, packet: bytes) -> None:
        print(packet_memory_map_text(packet))

    def print_program(self) -> None:
        print(format_bpf_program(self._loaded_program))

    def print_run_result(self, result: BpfRunResult) -> None:
        print(
            "Run result: "
            f"cycles={result.cycles} returned={result.returned} "
            f"accepted={result.accepted} ret_value=0x{result.ret_value:08x} "
            f"trace={result.trace_path} report={result.report_path}"
        )
