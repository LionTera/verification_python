"""Deterministic packet generation for configurable verification scenarios."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace
from pathlib import Path
import random
import sys
from typing import Iterable

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

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
DEFAULT_RANDOMIZE_FIELDS: tuple[str, ...] = ()
SUPPORTED_RANDOMIZE_FIELDS = {
    "length",
    "payload_len",
    "payload_bytes",
    "ttl",
    "dscp_ecn",
    "src_ip",
    "dst_ip",
    "identification",
    "flags_fragment",
    "src_port",
    "seq",
    "ack",
    "tcp_flags",
    "tcp_window",
    "ip_protocol",
}
TCP_FLAG_RANDOM_CHOICES = (0x02, 0x10, 0x12, 0x18, 0x11, 0x04)
FLAGS_FRAGMENT_RANDOM_CHOICES = (0x0000, 0x4000)


@dataclass(frozen=True)
class PacketSpec:
    """Declarative description of one generated packet."""
    l4: str = "tcp"
    src_mac: bytes = b"\x02\x00\x00\x00\x00\x01"
    dst_mac: bytes = b"\x02\x00\x00\x00\x00\x02"
    src_ip: str = "192.168.1.10"
    dst_ip: str = "192.168.1.20"
    dscp_ecn: int = 0
    identification: int = 0x1234
    flags_fragment: int = 0x4000
    ttl: int = 64
    ip_options: bytes = b""
    src_port: int = 1234
    dst_port: int = 80
    seq: int = 1
    ack: int = 0
    flags: int = 0x02
    tcp_window: int = 4096
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
    randomize_fields: tuple[str, ...] = DEFAULT_RANDOMIZE_FIELDS
    payload_len_min: int = 0
    payload_len_max: int = 32


def build_packet(spec: PacketSpec) -> bytes:
    """Materialize a PacketSpec into raw frame bytes."""
    if spec.l4 == "tcp":
        return make_tcp_packet(
            src_mac=spec.src_mac,
            dst_mac=spec.dst_mac,
            src_ip=spec.src_ip,
            dst_ip=spec.dst_ip,
            dscp_ecn=spec.dscp_ecn,
            identification=spec.identification,
            flags_fragment=spec.flags_fragment,
            ttl=spec.ttl,
            ip_options=spec.ip_options,
            src_port=spec.src_port,
            dst_port=spec.dst_port,
            seq=spec.seq,
            ack=spec.ack,
            flags=spec.flags,
            window=spec.tcp_window,
            payload=spec.payload,
        )
    if spec.l4 == "udp":
        return make_udp_packet(
            src_mac=spec.src_mac,
            dst_mac=spec.dst_mac,
            src_ip=spec.src_ip,
            dst_ip=spec.dst_ip,
            dscp_ecn=spec.dscp_ecn,
            identification=spec.identification,
            flags_fragment=spec.flags_fragment,
            ttl=spec.ttl,
            ip_options=spec.ip_options,
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
            dscp_ecn=spec.dscp_ecn,
            identification=spec.identification,
            flags_fragment=spec.flags_fragment,
            ttl=spec.ttl,
            ip_options=spec.ip_options,
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
    dscp_ecn: int = 0,
    identification: int = 0x1234,
    flags_fragment: int = 0x4000,
    ttl: int = 64,
    ip_options: bytes = b"",
    protocol: int = 1,
    payload: bytes = b"",
) -> bytes:
    """Build a minimal Ethernet + IPv4 packet with no L4 header."""
    from tests.bpf_env.packets import _checksum
    import ipaddress

    if len(ip_options) % 4:
        raise ValueError("ip_options length must be a multiple of 4 bytes")

    eth_type = b"\x08\x00"
    ihl_words = 5 + (len(ip_options) // 4)
    version_ihl = (4 << 4) | ihl_words
    total_length = ihl_words * 4 + len(payload)
    src_ip_bytes = ipaddress.ip_address(src_ip).packed
    dst_ip_bytes = ipaddress.ip_address(dst_ip).packed

    ipv4_header = bytearray(ihl_words * 4)
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
    if ip_options:
        ipv4_header[20:] = ip_options
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
    if config.payload_len_min < 0:
        raise ValueError("payload_len_min must be >= 0")
    if config.payload_len_max < config.payload_len_min:
        raise ValueError("payload_len_max must be >= payload_len_min")
    return replace(config, randomize_fields=_normalize_randomize_fields(config.randomize_fields))


def _normalize_randomize_fields(raw_fields: Iterable[str] | str) -> tuple[str, ...]:
    """Normalize the randomization field list into a validated tuple."""
    if isinstance(raw_fields, str):
        pieces = [piece.strip().lower() for piece in raw_fields.split(",")]
    else:
        pieces = [str(piece).strip().lower() for piece in raw_fields]
    normalized = tuple(dict.fromkeys(piece for piece in pieces if piece))
    unsupported = sorted(set(normalized) - SUPPORTED_RANDOMIZE_FIELDS)
    if unsupported:
        raise ValueError(
            "Unsupported randomize fields: "
            + ", ".join(unsupported)
            + ". Supported fields are: "
            + ", ".join(sorted(SUPPORTED_RANDOMIZE_FIELDS))
        )
    return normalized


def _random_private_ip(rng: random.Random, *, prefix_octets: tuple[int, int]) -> str:
    """Create a deterministic private/test IP address from the RNG."""
    return f"{prefix_octets[0]}.{prefix_octets[1]}.{rng.randrange(0, 256)}.{rng.randrange(1, 255)}"


def _random_payload(
    index: int,
    rng: random.Random,
    fields: set[str],
    *,
    payload_len_min: int,
    payload_len_max: int,
) -> bytes:
    """Create deterministic payload bytes under the selected randomization policy."""
    payload_len = 8
    if "length" in fields or "payload_len" in fields:
        payload_len = rng.randrange(payload_len_min, payload_len_max + 1)
    if "payload_bytes" in fields:
        return bytes(rng.getrandbits(8) for _ in range(payload_len))

    base = index.to_bytes(4, "big") + bytes([0xD0 | (index & 0x0F), 0xAD, 0xBE, 0xEF])
    if payload_len <= len(base):
        return base[:payload_len]
    return base + bytes((index + offset) & 0xFF for offset in range(payload_len - len(base)))


def _apply_selected_randomization(
    base: PacketSpec,
    *,
    index: int,
    rng: random.Random,
    payload_len_min: int,
    payload_len_max: int,
) -> PacketSpec:
    """Apply the selected deterministic randomization knobs to a packet spec."""
    fields = set(base.metadata.get("randomize_fields", ()))
    updates: dict[str, object] = {}

    if "src_ip" in fields:
        updates["src_ip"] = _random_private_ip(rng, prefix_octets=(10, 1))
    if "dst_ip" in fields:
        updates["dst_ip"] = _random_private_ip(rng, prefix_octets=(192, 168))
    if "dscp_ecn" in fields:
        updates["dscp_ecn"] = rng.randrange(0, 256)
    if "identification" in fields:
        updates["identification"] = rng.randrange(0, 0x10000)
    if "flags_fragment" in fields:
        updates["flags_fragment"] = rng.choice(FLAGS_FRAGMENT_RANDOM_CHOICES)
    if "ttl" in fields:
        updates["ttl"] = rng.randrange(1, 256)
    if "src_port" in fields:
        updates["src_port"] = rng.randrange(1024, 65536)
    if "seq" in fields:
        updates["seq"] = rng.randrange(0, 0x100000000)
    if "ack" in fields:
        updates["ack"] = rng.randrange(0, 0x100000000)
    if "tcp_flags" in fields and base.l4 == "tcp":
        updates["flags"] = rng.choice(TCP_FLAG_RANDOM_CHOICES)
    if "tcp_window" in fields and base.l4 == "tcp":
        updates["tcp_window"] = rng.randrange(512, 65536)
    if "ip_protocol" in fields and base.l4 == "ip":
        metadata = dict(base.metadata)
        metadata["ip_protocol"] = rng.choice((1, 2, 6, 17, 47))
        updates["metadata"] = metadata

    if {"length", "payload_len", "payload_bytes"} & fields:
        updates["payload"] = _random_payload(
            index,
            rng,
            fields,
            payload_len_min=payload_len_min,
            payload_len_max=payload_len_max,
        )

    return derive_packet(base, **updates) if updates else base


def _build_configurable_packet_spec(
    index: int,
    protocol: str,
    *,
    rng: random.Random,
    randomize_fields: tuple[str, ...],
    payload_len_min: int,
    payload_len_max: int,
) -> PacketSpec:
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
        payload=_random_payload(
            index,
            rng,
            set(randomize_fields),
            payload_len_min=payload_len_min,
            payload_len_max=payload_len_max,
        ),
        name=f"{protocol}_{index}",
        metadata={"randomize_fields": randomize_fields},
    )
    base = _apply_selected_randomization(
        base,
        index=index,
        rng=rng,
        payload_len_min=payload_len_min,
        payload_len_max=payload_len_max,
    )
    if protocol == "tcp":
        expected_accept = index % 2 == 0
        kind = "tcp_accept" if expected_accept else "tcp_reject"
        metadata = dict(base.metadata)
        metadata.update({"kind": kind, "expected_accept": expected_accept})
        return derive_packet(base, metadata=metadata)
    if protocol == "udp":
        metadata = dict(base.metadata)
        metadata.update({"kind": "udp_reject", "expected_accept": False})
        return derive_packet(base, metadata=metadata)
    if protocol == "ip":
        metadata = dict(base.metadata)
        metadata.update({"kind": "ip_reject", "expected_accept": False})
        metadata.setdefault("ip_protocol", 1)
        return derive_packet(
            base,
            metadata=metadata,
        )
    raise ValueError(f"Unsupported protocol {protocol}")


def generate_configurable_packet_stream(config: TrafficConfig) -> list[dict[str, object]]:
    """Generate packet items and ingress metadata for configurable tests."""
    config = validate_traffic_config(config)
    rng = random.Random(config.seed)
    protocols = PACKET_GENERATOR_PROTOCOLS[config.protocol_mode]
    packet_specs = [
        _build_configurable_packet_spec(
            index,
            protocols[index % len(protocols)],
            rng=rng,
            randomize_fields=config.randomize_fields,
            payload_len_min=config.payload_len_min,
            payload_len_max=config.payload_len_max,
        )
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
                "randomize_fields": config.randomize_fields,
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
        f"Randomized fields: {', '.join(metadata.get('randomize_fields', ())) or 'none'}",
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
    parser.add_argument(
        "--randomize-fields",
        default="",
        help=(
            "Comma-separated fields to randomize deterministically. "
            "Supported: " + ", ".join(sorted(SUPPORTED_RANDOMIZE_FIELDS))
        ),
    )
    parser.add_argument("--payload-len-min", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--payload-len-max", type=lambda value: int(value, 0), default=32)
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
            randomize_fields=_normalize_randomize_fields(args.randomize_fields),
            payload_len_min=args.payload_len_min,
            payload_len_max=args.payload_len_max,
        )
    )
    items = generate_configurable_packet_stream(config)
    print(
        "Generated traffic: "
        f"unique_packets={config.unique_packets} protocol_mode={config.protocol_mode} "
        f"error_level={config.error_level} seed=0x{config.seed:08x} "
        f"randomize_fields={','.join(config.randomize_fields) or 'none'} "
        f"payload_len_range=[{config.payload_len_min},{config.payload_len_max}]"
    )
    limit = config.unique_packets if args.show_limit <= 0 else min(args.show_limit, config.unique_packets)
    for item in items[:limit]:
        print(describe_generated_item(item))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
