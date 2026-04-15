"""Shared Python-side testbench for driving and observing the BPF DUT.

This module provides:

- BPF instruction encoding helpers
- packet decoding and reporting helpers
- a reusable DUT driver class used by the integration tests
- CSV and Markdown artifact generation
"""

from __future__ import annotations

import csv
import ipaddress
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from tests.bpf_env.artifacts import unique_artifact_path

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
REPORTS_ENV_VAR = "BPF_REPORTS"
FULL_ARTIFACTS_ENV_VAR = "BPF_FULL_ARTIFACTS"


def encode_bpf_instruction(code: int, *, jt: int = 0, jf: int = 0, k: int = 0) -> int:
    """Pack a classic BPF instruction into the DUT's 64-bit instruction format."""
    return ((code & 0xFF) << 48) | ((jt & 0xFF) << 40) | ((jf & 0xFF) << 32) | (k & 0xFFFFFFFF)


def bpf_stmt(code: int, k: int = 0) -> int:
    """Encode a simple BPF statement with no jump targets."""
    return encode_bpf_instruction(code, k=k)


def bpf_jump(code: int, k: int, jt: int, jf: int) -> int:
    """Encode a BPF jump instruction."""
    return encode_bpf_instruction(code, jt=jt, jf=jf, k=k)


def bpf_ldb_abs(offset: int) -> int:
    """Encode `ldb [offset]`."""
    return bpf_stmt(BPF_LD | BPF_B | BPF_ABS, offset)


def bpf_ldh_abs(offset: int) -> int:
    """Encode `ldh [offset]`."""
    return bpf_stmt(BPF_LD | BPF_H | BPF_ABS, offset)


def bpf_jeq_k(value: int, *, jt: int, jf: int) -> int:
    """Encode `jeq #value` with explicit true/false offsets."""
    return bpf_jump(BPF_JMP | BPF_JEQ | BPF_K, value, jt, jf)


def bpf_ret_k(value: int) -> int:
    """Encode `ret #value`."""
    return bpf_stmt(BPF_RET | BPF_K, value)


def bpf_ret_a() -> int:
    """Encode `ret a`."""
    return bpf_stmt(BPF_RET | BPF_A, 0)


def decode_bpf_instruction(instruction: int) -> dict[str, int]:
    """Split a packed 64-bit instruction into its classic BPF fields."""
    return {
        "code": (instruction >> 48) & 0xFF,
        "jt": (instruction >> 40) & 0xFF,
        "jf": (instruction >> 32) & 0xFF,
        "k": instruction & 0xFFFFFFFF,
    }


def format_bpf_instruction(instruction: int) -> str:
    """Render one packed instruction in a descriptive debug format."""
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
    """Render one packed instruction in assembly-like form."""
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
    """Render a whole BPF program for console output."""
    lines = ["BPF program:"]
    for index, instruction in enumerate(instructions):
        lines.append(
            f"  [{index:02d}] 0x{instruction:016x}  {format_bpf_instruction_asm(instruction)}"
            f"    ; {format_bpf_instruction(instruction)}"
        )
    return "\n".join(lines)


def reports_enabled() -> bool:
    """Return True when CSV/Markdown report emission is enabled."""
    value = os.environ.get(REPORTS_ENV_VAR, "")
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def full_artifacts_enabled() -> bool:
    """Return True when probe/full-artifact retention is enabled."""
    value = os.environ.get(FULL_ARTIFACTS_ENV_VAR, "")
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def _format_mac(raw: bytes) -> str:
    """Format a MAC address for human-readable output."""
    return ":".join(f"{byte:02x}" for byte in raw)


def _format_tcp_flags(flags: int) -> str:
    """Format a TCP flag byte as a comma-separated name list."""
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
    """Decode the packet into a concise human-readable summary."""
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


def packet_csv_fields(packet: bytes) -> dict[str, str | int]:
    """Extract packet fields into one flat CSV-friendly dictionary."""
    fields: dict[str, str | int] = {
        "packet_len": len(packet),
        "packet_raw": packet.hex(),
        "packet_l2": "",
        "packet_l3": "",
        "packet_l4": "",
        "eth_dst_mac": "",
        "eth_src_mac": "",
        "eth_type": "",
        "ipv4_version": "",
        "ipv4_ihl": "",
        "ipv4_total_length": "",
        "ipv4_ttl": "",
        "ipv4_protocol": "",
        "ipv4_src_ip": "",
        "ipv4_dst_ip": "",
        "ipv4_header_raw": "",
        "tcp_src_port": "",
        "tcp_dst_port": "",
        "tcp_seq": "",
        "tcp_ack": "",
        "tcp_flags": "",
        "tcp_window": "",
        "tcp_checksum": "",
        "tcp_header_raw": "",
        "udp_src_port": "",
        "udp_dst_port": "",
        "udp_length": "",
        "udp_checksum": "",
        "udp_header_raw": "",
        "l4_payload_raw": "",
    }

    if len(packet) < 14:
        return fields

    fields["packet_l2"] = "ethernet"
    fields["eth_dst_mac"] = _format_mac(packet[0:6])
    fields["eth_src_mac"] = _format_mac(packet[6:12])
    eth_type = int.from_bytes(packet[12:14], "big")
    fields["eth_type"] = f"0x{eth_type:04x}"

    if eth_type != 0x0800 or len(packet) < 34:
        return fields

    fields["packet_l3"] = "ipv4"
    ipv4 = packet[14:]
    version = ipv4[0] >> 4
    ihl = (ipv4[0] & 0x0F) * 4
    total_length = int.from_bytes(ipv4[2:4], "big")
    ttl = ipv4[8]
    protocol = ipv4[9]
    src_ip = str(ipaddress.ip_address(ipv4[12:16]))
    dst_ip = str(ipaddress.ip_address(ipv4[16:20]))
    fields["ipv4_version"] = version
    fields["ipv4_ihl"] = ihl
    fields["ipv4_total_length"] = total_length
    fields["ipv4_ttl"] = ttl
    fields["ipv4_protocol"] = protocol
    fields["ipv4_src_ip"] = src_ip
    fields["ipv4_dst_ip"] = dst_ip
    fields["ipv4_header_raw"] = packet[14:14 + min(ihl, len(ipv4))].hex()

    l4_start = 14 + ihl
    if len(packet) < l4_start:
        return fields

    if protocol == 6 and len(packet) >= l4_start + 20:
        fields["packet_l4"] = "tcp"
        tcp = packet[l4_start:]
        data_offset = (tcp[12] >> 4) * 4
        fields["tcp_src_port"] = int.from_bytes(tcp[0:2], "big")
        fields["tcp_dst_port"] = int.from_bytes(tcp[2:4], "big")
        fields["tcp_seq"] = int.from_bytes(tcp[4:8], "big")
        fields["tcp_ack"] = int.from_bytes(tcp[8:12], "big")
        fields["tcp_flags"] = _format_tcp_flags(tcp[13])
        fields["tcp_window"] = int.from_bytes(tcp[14:16], "big")
        fields["tcp_checksum"] = f"0x{int.from_bytes(tcp[16:18], 'big'):04x}"
        fields["tcp_header_raw"] = tcp[:data_offset].hex()
        if l4_start + data_offset < len(packet):
            fields["l4_payload_raw"] = packet[l4_start + data_offset:].hex()
    elif protocol == 17 and len(packet) >= l4_start + 8:
        fields["packet_l4"] = "udp"
        udp = packet[l4_start:]
        fields["udp_src_port"] = int.from_bytes(udp[0:2], "big")
        fields["udp_dst_port"] = int.from_bytes(udp[2:4], "big")
        fields["udp_length"] = int.from_bytes(udp[4:6], "big")
        fields["udp_checksum"] = f"0x{int.from_bytes(udp[6:8], 'big'):04x}"
        fields["udp_header_raw"] = udp[:8].hex()
        if l4_start + 8 < len(packet):
            fields["l4_payload_raw"] = packet[l4_start + 8:].hex()

    return fields


def packet_report_markdown(packet: bytes) -> str:
    """Render a Markdown summary of the currently loaded packet."""
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
    """Render the packet as 32-bit PRAM words in plain text."""
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
    """Render the packet PRAM word layout as Markdown."""
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


def _field_slice(packet: bytes, start: int, size: int) -> bytes:
    """Return a byte slice used by the packet field map helpers."""
    return packet[start:start + size]


def packet_field_map_entries(packet: bytes) -> list[dict[str, str | int]]:
    """Build structured field-to-byte/PRAM mapping entries for a packet."""
    entries: list[dict[str, str | int]] = []

    def add_entry(name: str, start: int, size: int, note: str = "") -> None:
        chunk = _field_slice(packet, start, size)
        if not chunk:
            return
        first_word = start & ~0x3
        last_word = (start + len(chunk) - 1) & ~0x3
        if first_word == last_word:
            pram_words = f"0x{first_word:04x}"
        else:
            pram_words = f"0x{first_word:04x}..0x{last_word:04x}"
        entries.append(
            {
                "field": name,
                "start": start,
                "end": start + len(chunk) - 1,
                "raw": chunk.hex(),
                "pram_words": pram_words,
                "note": note,
            }
        )

    add_entry("eth.dst_mac", 0, 6)
    add_entry("eth.src_mac", 6, 6)
    add_entry("eth.eth_type", 12, 2)

    if len(packet) < 34 or packet[12:14] != b"\x08\x00":
        return entries

    ipv4 = packet[14:]
    ihl = (ipv4[0] & 0x0F) * 4
    total_length = int.from_bytes(ipv4[2:4], "big")
    protocol = ipv4[9]

    add_entry("ipv4.base_header", 14, min(ihl, len(ipv4)), f"ihl={ihl} total_length={total_length}")
    add_entry("ipv4.version_ihl", 14, 1)
    add_entry("ipv4.total_length", 16, 2)
    add_entry("ipv4.protocol", 23, 1)
    add_entry("ipv4.src_ip", 26, 4)
    add_entry("ipv4.dst_ip", 30, 4)

    l4_start = 14 + ihl
    if len(packet) < l4_start + 8:
        return entries

    if protocol == 6 and len(packet) >= l4_start + 20:
        data_offset = ((packet[l4_start + 12] >> 4) & 0xF) * 4
        add_entry("tcp.src_port", l4_start + 0, 2)
        add_entry("tcp.dst_port", l4_start + 2, 2)
        add_entry("tcp.seq_num", l4_start + 4, 4)
        add_entry("tcp.ack_num", l4_start + 8, 4)
        add_entry("tcp.data_offset_flags", l4_start + 12, 2)
        add_entry("tcp.window", l4_start + 14, 2)
        add_entry("tcp.checksum", l4_start + 16, 2)
        add_entry("tcp.urgent_ptr", l4_start + 18, 2)
        payload_start = l4_start + data_offset
        if payload_start < len(packet):
            add_entry("tcp.payload", payload_start, len(packet) - payload_start)
    elif protocol == 17 and len(packet) >= l4_start + 8:
        add_entry("udp.src_port", l4_start + 0, 2)
        add_entry("udp.dst_port", l4_start + 2, 2)
        add_entry("udp.length", l4_start + 4, 2)
        add_entry("udp.checksum", l4_start + 6, 2)
        payload_start = l4_start + 8
        if payload_start < len(packet):
            add_entry("udp.payload", payload_start, len(packet) - payload_start)

    return entries


def packet_field_map_text(packet: bytes) -> str:
    """Render the packet field map in plain text."""
    lines = ["Packet field map:"]
    for entry in packet_field_map_entries(packet):
        note = f" note={entry['note']}" if entry["note"] else ""
        lines.append(
            f"  {entry['field']}: bytes[{entry['start']:02d}:{entry['end']:02d}] "
            f"raw={entry['raw']} pram={entry['pram_words']}{note}"
        )
    return "\n".join(lines)


def packet_field_map_markdown(packet: bytes) -> str:
    """Render the packet field map as a Markdown table."""
    lines = [
        "### Packet Field Map",
        "",
        "| Field | Byte Range | Raw Bytes | PRAM Word(s) | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in packet_field_map_entries(packet):
        lines.append(
            f"| `{entry['field']}` | `{entry['start']}-{entry['end']}` | "
            f"`{entry['raw']}` | `{entry['pram_words']}` | `{entry['note']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def program_report_markdown(instructions: Iterable[int]) -> str:
    """Render the currently loaded BPF program as Markdown."""
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


def register_snapshot_markdown(*, acc: int, pc: int, x_reg: int) -> str:
    """Render a final register snapshot for the current DUT run."""
    lines = [
        "## Register Snapshot",
        "",
        "| Register | Value |",
        "| --- | --- |",
        f"| A / ACC | `0x{acc:08x}` |",
        f"| X | `0x{x_reg:08x}` |",
        f"| PC | `0x{pc:08x}` |",
        "",
    ]
    return "\n".join(lines)


def register_snapshot_text(*, acc: int, pc: int, x_reg: int) -> str:
    """Render a one-block console view of the current register snapshot."""
    return (
        "Register snapshot:\n"
        f"  A / ACC = 0x{acc:08x}\n"
        f"  X       = 0x{x_reg:08x}\n"
        f"  PC      = 0x{pc:08x}"
    )


@dataclass
class BpfRunResult:
    """Summary of one DUT execution window."""
    cycles: int
    returned: bool
    accepted: bool
    ret_value: int
    trace_path: Path
    report_path: Path


class BpfPythonTB:
    """Reusable Python driver for the BPF DUT interface."""

    def __init__(
        self,
        dut,
        trace_path: str | Path = "reports/bpf_trace.csv",
        *,
        emit_reports: bool | None = None,
    ):
        self.dut = dut
        self.trace_path = unique_artifact_path(trace_path)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path = self.trace_path.with_suffix(".md")
        self.emit_reports = reports_enabled() if emit_reports is None else emit_reports
        self._cycle = 0
        self._trace_rows: list[dict[str, int]] = []
        self._loaded_program: list[int] = []
        self._loaded_packet: bytes = b""

    @property
    def current_cycle(self) -> int:
        """Return the current simulated cycle count."""
        return self._cycle

    @property
    def trace_rows(self) -> list[dict[str, int | str]]:
        """Return a copy of the collected CSV trace rows."""
        return list(self._trace_rows)

    def init_signals(self) -> None:
        """Initialize the DUT input interface to a known idle state."""
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
        """Capture one cycle of DUT-visible state into the trace buffer."""
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
            "bpf_acc": int(self.dut.bpf_acc),
            "bpf_pc": int(self.dut.bpf_pc),
            "bpf_x": int(self.dut.bpf_x),
            "tb_cycle_counter": int(self.dut.tb_cycle_counter),
        }
        row.update(packet_csv_fields(self._loaded_packet))
        self._trace_rows.append(row)
        LOGGER.info("cycle=%d return=%d accept=%d ret=0x%08x", row["cycle"], row["bpf_return"], row["bpf_accept"], row["bpf_ret_value"])

    def _flush_trace(self) -> None:
        """Write the in-memory trace buffer to CSV."""
        if not self._trace_rows:
            return
        with self.trace_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=list(self._trace_rows[0]))
            writer.writeheader()
            writer.writerows(self._trace_rows)

    def _tick(self, cycles: int = 1) -> None:
        """Advance simulation and collect trace rows for each cycle."""
        for _ in range(cycles):
            self.dut.sim_tick()
            self._record_trace()
            self._cycle += 1

    def write_mmap(self, addr: int, data: int, timeout: int = 20) -> None:
        """Perform one MMAP write transaction and wait for acknowledgment."""
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
        """Drive the packet-loss input signal."""
        self.dut.bpf_packet_loss @= 1 if value else 0

    def step(self, cycles: int = 1) -> None:
        """Advance simulation by a fixed number of cycles."""
        self._tick(cycles)

    def read_mmap(self, addr: int, timeout: int = 20) -> int:
        """Perform one MMAP read transaction and return the read data."""
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
        """Write a packet into PRAM and remember it for reporting."""
        self._loaded_packet = packet
        print(
            "DP packet load: "
            f"base_addr=0x{base_addr:04x} len={len(packet)} bytes={packet.hex()}"
        )
        print(analyze_packet(packet))
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
        """Write a packed BPF program into IRAM through MMAP."""
        self._loaded_program = list(instructions)
        for index, instruction in enumerate(self._loaded_program):
            low_word = instruction & 0xFFFFFFFF
            high_word = (instruction >> 32) & 0xFFFFFFFF
            self.write_mmap(base_addr + index * 2, low_word)
            self.write_mmap(base_addr + index * 2 + 1, high_word)

    def configure_start_address(self, start_addr: int = 0, enable: bool = True) -> None:
        """Program the DUT start-address register."""
        value = ((1 if enable else 0) << 31) | ((start_addr & 0x3FF) << 1)
        self.write_mmap(BPF_START_ADDR, value)

    def pulse_start(self, cycles: int = 1) -> None:
        """Pulse the DUT start signal for the requested number of cycles."""
        self.dut.bpf_start @= 1
        self._tick(cycles)
        self.dut.bpf_start @= 0
        self._tick()

    def run_until_return(self, max_cycles: int = 200) -> BpfRunResult:
        """Run until the DUT asserts return or the cycle budget expires."""
        for _ in range(max_cycles):
            if int(self.dut.bpf_return):
                break
            self._tick()
        returned = bool(int(self.dut.bpf_return))
        result = BpfRunResult(
            cycles=self._cycle,
            returned=returned,
            accepted=bool(int(self.dut.bpf_accept)),
            ret_value=int(self.dut.bpf_ret_value),
            trace_path=self.trace_path,
            report_path=self.report_path,
        )
        if self.emit_reports:
            self._flush_trace()
            self._write_report(result)
        return result

    def _write_report(self, result: BpfRunResult) -> None:
        """Write the shared Markdown report for the current run snapshot."""
        lines = [
            "# BPF Integration Report",
            "",
            "## Final DUT Run Snapshot",
            "",
            "This top section describes the final packet/program state visible to the shared Python testbench.",
            "For multi-packet or scenario-based tests, this is not the whole-test verdict by itself.",
            "See any appended summary sections later in the report for test-level pass/fail context, traffic history, counters, and golden-model comparisons.",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Cycles | `{result.cycles}` |",
            f"| Returned | `{result.returned}` |",
            f"| Accepted | `{result.accepted}` |",
            f"| Return Value | `0x{result.ret_value:08x}` |",
            f"| CSV Trace | `{result.trace_path}` |",
            "",
            register_snapshot_markdown(
                acc=int(self.dut.bpf_acc),
                pc=int(self.dut.bpf_pc),
                x_reg=int(self.dut.bpf_x),
            ),
            packet_report_markdown(self._loaded_packet),
            packet_field_map_markdown(self._loaded_packet),
            packet_memory_map_markdown(self._loaded_packet),
            program_report_markdown(self._loaded_program),
        ]
        result.report_path.write_text("\n".join(lines), encoding="utf-8")

    def print_packet_summary(self, packet: bytes) -> None:
        """Print the decoded packet summary to the console."""
        print(analyze_packet(packet))

    def print_packet_memory_map(self, packet: bytes) -> None:
        """Print the packet PRAM word layout to the console."""
        print(packet_memory_map_text(packet))

    def print_packet_field_map(self, packet: bytes) -> None:
        """Print the packet field map to the console."""
        print(packet_field_map_text(packet))

    def print_program(self) -> None:
        """Print the currently loaded BPF program to the console."""
        print(format_bpf_program(self._loaded_program))

    def print_register_snapshot(self) -> None:
        """Print the current A/X/PC snapshot to the console."""
        print(
            register_snapshot_text(
                acc=int(self.dut.bpf_acc),
                pc=int(self.dut.bpf_pc),
                x_reg=int(self.dut.bpf_x),
            )
        )

    def print_run_result(self, result: BpfRunResult) -> None:
        """Print a concise summary of one DUT run."""
        print(
            "Run result: "
            f"cycles={result.cycles} returned={result.returned} "
            f"accepted={result.accepted} ret_value=0x{result.ret_value:08x} "
            f"trace={result.trace_path} report={result.report_path}"
        )
