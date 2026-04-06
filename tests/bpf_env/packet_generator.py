"""Deterministic packet generation for configurable verification scenarios."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace
import random
from typing import Iterable

from tests.bpf_env.bpf_python_tb import analyze_packet
from tests.bpf_env.network_ingress import mutate_ethertype, with_ethernet_fcs
from tests.bpf_env.packets import make_tcp_packet, make_udp_packet

DEFAULT_UNIQUE_PACKETS = 32
DEFAULT_PROTOCOL_MODE = 3
DEFAULT_ERROR_LEVEL = 1
DEFAULT_PACKET_GENERATOR_SEED = 0x5EED5EED
EXPECTED_DST_MAC = bytes.fromhex("020000000002")
PACKET_GENERATOR_PROTOCOLS = {
    1: ("tcp",),
    2: ("udp",),
    3: ("tcp", "udp"),
    4: ("tcp", "udp", "ip"),
}


@dataclass(frozen=True)
class PacketSpec:
    """Declarative description of one generated packet."""
    l4: str = "tcp"
    src_mac: bytes = b"\x02\x00\x00\x00\x00\x01"
    dst_mac: bytes = b"\x02\x00\x00\x00\x00\x02"
    src_ip: str = "192.168.1.10"
    dst_ip: str = "192.168.1.20"
    src_port: int = 1234
    dst_port: int = 80
    seq: int = 1
    ack: int = 0
    flags: int = 0x02
    payload: bytes = b""
    name: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TrafficConfig:
    """Configuration for configurable packet generation flows."""
    unique_packets: int = DEFAULT_UNIQUE_PACKETS
    protocol_mode: int = DEFAULT_PROTOCOL_MODE
    error_level: int = DEFAULT_ERROR_LEVEL
    seed: int = DEFAULT_PACKET_GENERATOR_SEED


def build_packet(spec: PacketSpec) -> bytes:
    """Materialize a PacketSpec into raw frame bytes."""
    if spec.l4 == "tcp":
        return make_tcp_packet(
            src_mac=spec.src_mac,
            dst_mac=spec.dst_mac,
            src_ip=spec.src_ip,
            dst_ip=spec.dst_ip,
            src_port=spec.src_port,
            dst_port=spec.dst_port,
            seq=spec.seq,
            ack=spec.ack,
            flags=spec.flags,
            payload=spec.payload,
        )
    if spec.l4 == "udp":
        return make_udp_packet(
            src_mac=spec.src_mac,
            dst_mac=spec.dst_mac,
            src_ip=spec.src_ip,
            dst_ip=spec.dst_ip,
            src_port=spec.src_port,
            dst_port=spec.dst_port,
            payload=spec.payload,
        )
    if spec.l4 == "ip":
        return make_ipv4_packet(
            src_mac=spec.src_mac,
            dst_mac=spec.dst_mac,
            src_ip=spec.src_ip,
            dst_ip=spec.dst_ip,
            protocol=int(spec.metadata.get("ip_protocol", 1)),
            payload=spec.payload,
        )
    raise ValueError(f"Unsupported l4 protocol: {spec.l4}")


def derive_packet(base: PacketSpec, **changes) -> PacketSpec:
    """Create a modified copy of an existing packet specification."""
    return replace(base, **changes)


def packet_stream(specs: Iterable[PacketSpec]) -> list[dict[str, object]]:
    """Convert packet specifications into the dict structure used by tests."""
    items: list[dict[str, object]] = []
    for index, spec in enumerate(specs):
        items.append(
            {
                "index": index,
                "name": spec.name or f"packet_{index}",
                "spec": spec,
                "packet": build_packet(spec),
                "metadata": dict(spec.metadata),
            }
        )
    return items


def make_ipv4_packet(
    *,
    src_mac: bytes = b"\x02\x00\x00\x00\x00\x01",
    dst_mac: bytes = b"\x02\x00\x00\x00\x00\x02",
    src_ip: str = "192.168.1.10",
    dst_ip: str = "192.168.1.20",
    protocol: int = 1,
    payload: bytes = b"",
) -> bytes:
    """Build a minimal Ethernet + IPv4 packet with no L4 header."""
    from tests.bpf_env.packets import _checksum
    import ipaddress

    eth_type = b"\x08\x00"
    version_ihl = 0x45
    dscp_ecn = 0
    total_length = 20 + len(payload)
    identification = 0x1234
    flags_fragment = 0x4000
    ttl = 64
    src_ip_bytes = ipaddress.ip_address(src_ip).packed
    dst_ip_bytes = ipaddress.ip_address(dst_ip).packed

    ipv4_header = bytearray(20)
    ipv4_header[0] = version_ihl
    ipv4_header[1] = dscp_ecn
    ipv4_header[2:4] = total_length.to_bytes(2, "big")
    ipv4_header[4:6] = identification.to_bytes(2, "big")
    ipv4_header[6:8] = flags_fragment.to_bytes(2, "big")
    ipv4_header[8] = ttl
    ipv4_header[9] = protocol & 0xFF
    ipv4_header[10:12] = b"\x00\x00"
    ipv4_header[12:16] = src_ip_bytes
    ipv4_header[16:20] = dst_ip_bytes
    ipv4_header[10:12] = _checksum(bytes(ipv4_header)).to_bytes(2, "big")

    return dst_mac + src_mac + eth_type + bytes(ipv4_header) + payload


def random_packet_stream(
    count: int,
    *,
    seed: int,
    tcp_accept_ratio: float = 0.45,
    tcp_reject_ratio: float = 0.40,
    accepted_dst_port: int = 0x5678,
    rejected_dst_port: int = 0x56BB,
) -> list[dict[str, object]]:
    """Generate deterministic mixed random traffic for stress-style tests."""
    if count <= 0:
        raise ValueError("count must be > 0")
    if tcp_accept_ratio < 0 or tcp_reject_ratio < 0 or tcp_accept_ratio + tcp_reject_ratio > 1:
        raise ValueError("invalid traffic ratios")

    rng = random.Random(seed)
    specs: list[PacketSpec] = []
    for index in range(count):
        selector = rng.random()
        seq = 0x01000000 + index
        ack = 0xA1000000 + index
        src_port = 0x1200 + (index % 200)
        payload = index.to_bytes(4, "big")
        base = PacketSpec(
            src_mac=bytes.fromhex("112233445566"),
            dst_mac=bytes.fromhex("aabbccddeeff"),
            src_ip=f"10.1.{(index // 256) % 256}.{index % 256}",
            dst_ip="192.0.2.99",
            src_port=src_port,
            seq=seq,
            ack=ack,
            flags=0x12,
            payload=payload,
        )
        if selector < tcp_accept_ratio:
            spec = derive_packet(
                base,
                l4="tcp",
                dst_port=accepted_dst_port,
                name=f"tcp_accept_{index}",
                metadata={"kind": "tcp_accept", "expected_accept": True},
            )
        elif selector < tcp_accept_ratio + tcp_reject_ratio:
            spec = derive_packet(
                base,
                l4="tcp",
                dst_port=rejected_dst_port,
                name=f"tcp_reject_{index}",
                metadata={"kind": "tcp_reject", "expected_accept": False},
            )
        else:
            spec = derive_packet(
                base,
                l4="udp",
                dst_port=accepted_dst_port,
                name=f"udp_reject_{index}",
                metadata={"kind": "udp_reject", "expected_accept": False},
            )
        specs.append(spec)
    return packet_stream(specs)


def validate_traffic_config(config: TrafficConfig) -> TrafficConfig:
    """Validate configurable traffic settings before generation."""
    if config.unique_packets <= 0:
        raise ValueError("unique_packets must be > 0")
    if config.protocol_mode not in PACKET_GENERATOR_PROTOCOLS:
        raise ValueError("protocol_mode must be one of 1, 2, 3, 4")
    if config.error_level not in (1, 2):
        raise ValueError("error_level must be 1 or 2")
    return config


def _build_configurable_packet_spec(index: int, protocol: str) -> PacketSpec:
    """Build one deterministic packet template for a configurable run."""
    base = PacketSpec(
        l4=protocol,
        src_mac=bytes.fromhex("020000000001"),
        dst_mac=EXPECTED_DST_MAC,
        src_ip=f"10.1.{(index // 256) % 256}.{index % 256}",
        dst_ip="192.168.1.20",
        src_port=0x1200 + (index % 200),
        dst_port=0x5678 if index % 2 == 0 else 0x56BB,
        seq=0x01000000 + index,
        ack=0xA1000000 + index,
        flags=0x12,
        payload=index.to_bytes(4, "big") + bytes([0xD0 | (index & 0x0F), 0xAD, 0xBE, 0xEF]),
        name=f"{protocol}_{index}",
    )
    if protocol == "tcp":
        expected_accept = index % 2 == 0
        kind = "tcp_accept" if expected_accept else "tcp_reject"
        return derive_packet(base, metadata={"kind": kind, "expected_accept": expected_accept})
    if protocol == "udp":
        return derive_packet(base, metadata={"kind": "udp_reject", "expected_accept": False})
    if protocol == "ip":
        return derive_packet(
            base,
            metadata={"kind": "ip_reject", "expected_accept": False, "ip_protocol": 1},
        )
    raise ValueError(f"Unsupported protocol {protocol}")


def generate_configurable_packet_stream(config: TrafficConfig) -> list[dict[str, object]]:
    """Generate packet items and ingress metadata for configurable tests."""
    config = validate_traffic_config(config)
    rng = random.Random(config.seed)
    protocols = PACKET_GENERATOR_PROTOCOLS[config.protocol_mode]
    packet_specs = [
        _build_configurable_packet_spec(index, protocols[index % len(protocols)])
        for index in range(config.unique_packets)
    ]
    items = packet_stream(packet_specs)

    packet_loss_count = max(1, config.unique_packets // 5)
    available_indices = list(range(config.unique_packets))
    packet_loss_indices = set(rng.sample(available_indices, min(packet_loss_count, len(available_indices))))
    crc_error_indices: set[int] = set()
    if config.error_level >= 2:
        crc_error_count = max(1, config.unique_packets // 6)
        remaining_indices = [idx for idx in available_indices if idx not in packet_loss_indices]
        crc_error_indices = set(rng.sample(remaining_indices, min(crc_error_count, len(remaining_indices))))

    generated: list[dict[str, object]] = []
    for item in items:
        index = int(item["index"])
        packet = item["packet"]
        frame = with_ethernet_fcs(packet)
        ingress_error = "none"
        if index in crc_error_indices:
            frame = frame[:-4] + b"\x00\x00\x00\x00"
            ingress_error = "bad_crc"
        elif config.protocol_mode == 4 and item["spec"].l4 == "ip" and index % 5 == 4:
            frame = with_ethernet_fcs(mutate_ethertype(packet, 0x86DD))
            ingress_error = "unsupported_ethertype"

        metadata = dict(item["metadata"])
        metadata.update(
            {
                "packet_loss_injected": index in packet_loss_indices,
                "ingress_error": ingress_error,
                "protocol": item["spec"].l4,
            }
        )
        generated.append(
            {
                **item,
                "frame": frame,
                "metadata": metadata,
            }
        )
    return generated


def describe_generated_item(item: dict[str, object]) -> str:
    """Render one generated packet item as human-readable text."""
    metadata = dict(item["metadata"])
    lines = [
        (
            f"[{item['index']:02d}] {item['name']} "
            f"protocol={metadata['protocol']} expected_accept={metadata['expected_accept']} "
            f"packet_loss={metadata['packet_loss_injected']} ingress_error={metadata['ingress_error']}"
        ),
        analyze_packet(item["packet"]),
        f"Frame bytes with FCS: {item['frame'].hex()}",
    ]
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for standalone packet generation."""
    parser = argparse.ArgumentParser(description="Generate configurable BPF traffic and print the resulting frames.")
    parser.add_argument("--unique-packets", type=lambda value: int(value, 0), default=DEFAULT_UNIQUE_PACKETS)
    parser.add_argument("--protocol-mode", type=lambda value: int(value, 0), default=DEFAULT_PROTOCOL_MODE)
    parser.add_argument("--error-level", type=lambda value: int(value, 0), default=DEFAULT_ERROR_LEVEL)
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=DEFAULT_PACKET_GENERATOR_SEED)
    parser.add_argument("--show-limit", type=lambda value: int(value, 0), default=0)
    return parser.parse_args()


def main() -> int:
    """CLI entry point for previewing generated packets."""
    args = _parse_args()
    config = validate_traffic_config(
        TrafficConfig(
            unique_packets=args.unique_packets,
            protocol_mode=args.protocol_mode,
            error_level=args.error_level,
            seed=args.seed,
        )
    )
    items = generate_configurable_packet_stream(config)
    print(
        "Generated traffic: "
        f"unique_packets={config.unique_packets} protocol_mode={config.protocol_mode} "
        f"error_level={config.error_level} seed=0x{config.seed:08x}"
    )
    limit = config.unique_packets if args.show_limit <= 0 else min(args.show_limit, config.unique_packets)
    for item in items[:limit]:
        print(describe_generated_item(item))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
