"""Packet construction helpers for the Python verification flow."""

from __future__ import annotations

import ipaddress


def _checksum(data: bytes) -> int:
    """Compute the standard Internet checksum."""
    if len(data) % 2:
        data += b"\x00"
    total = 0
    for idx in range(0, len(data), 2):
        total += int.from_bytes(data[idx:idx + 2], "big")
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def make_tcp_packet(
    *,
    src_mac: bytes = b"\x02\x00\x00\x00\x00\x01",
    dst_mac: bytes = b"\x02\x00\x00\x00\x00\x02",
    src_ip: str = "192.168.1.10",
    dst_ip: str = "192.168.1.20",
    src_port: int = 1234,
    dst_port: int = 80,
    seq: int = 1,
    ack: int = 0,
    flags: int = 0x02,
    payload: bytes = b"",
) -> bytes:
    """Build an Ethernet + IPv4 + TCP packet with valid checksums."""
    eth_type = b"\x08\x00"
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
    ipv4_header[10:12] = b"\x00\x00"
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
    tcp_header[16:18] = b"\x00\x00"
    tcp_header[18:20] = b"\x00\x00"

    pseudo_header = (
        src_ip_bytes
        + dst_ip_bytes
        + b"\x00"
        + bytes([protocol])
        + (len(tcp_header) + len(payload)).to_bytes(2, "big")
    )
    tcp_header[16:18] = _checksum(pseudo_header + bytes(tcp_header) + payload).to_bytes(2, "big")

    return dst_mac + src_mac + eth_type + bytes(ipv4_header) + bytes(tcp_header) + payload


def make_udp_packet(
    *,
    src_mac: bytes = b"\x02\x00\x00\x00\x00\x01",
    dst_mac: bytes = b"\x02\x00\x00\x00\x00\x02",
    src_ip: str = "192.168.1.10",
    dst_ip: str = "192.168.1.20",
    src_port: int = 1234,
    dst_port: int = 80,
    payload: bytes = b"",
) -> bytes:
    """Build an Ethernet + IPv4 + UDP packet with valid checksums."""
    eth_type = b"\x08\x00"
    version_ihl = 0x45
    dscp_ecn = 0
    total_length = 20 + 8 + len(payload)
    identification = 0x1234
    flags_fragment = 0x4000
    ttl = 64
    protocol = 17
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
    ipv4_header[10:12] = b"\x00\x00"
    ipv4_header[12:16] = src_ip_bytes
    ipv4_header[16:20] = dst_ip_bytes
    ipv4_header[10:12] = _checksum(bytes(ipv4_header)).to_bytes(2, "big")

    udp_header = bytearray(8)
    udp_header[0:2] = src_port.to_bytes(2, "big")
    udp_header[2:4] = dst_port.to_bytes(2, "big")
    udp_header[4:6] = (8 + len(payload)).to_bytes(2, "big")
    udp_header[6:8] = b"\x00\x00"

    pseudo_header = (
        src_ip_bytes
        + dst_ip_bytes
        + b"\x00"
        + bytes([protocol])
        + (len(udp_header) + len(payload)).to_bytes(2, "big")
    )
    udp_header[6:8] = _checksum(pseudo_header + bytes(udp_header) + payload).to_bytes(2, "big")

    return dst_mac + src_mac + eth_type + bytes(ipv4_header) + bytes(udp_header) + payload
