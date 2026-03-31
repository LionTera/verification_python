from __future__ import annotations

from dataclasses import dataclass, field, replace
import random
from typing import Iterable

from tests.bpf_env.packets import make_tcp_packet, make_udp_packet


@dataclass(frozen=True)
class PacketSpec:
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


def build_packet(spec: PacketSpec) -> bytes:
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
    raise ValueError(f"Unsupported l4 protocol: {spec.l4}")


def derive_packet(base: PacketSpec, **changes) -> PacketSpec:
    return replace(base, **changes)


def packet_stream(specs: Iterable[PacketSpec]) -> list[dict[str, object]]:
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


def random_packet_stream(
    count: int,
    *,
    seed: int,
    tcp_accept_ratio: float = 0.45,
    tcp_reject_ratio: float = 0.40,
    accepted_dst_port: int = 0x5678,
    rejected_dst_port: int = 0x56BB,
) -> list[dict[str, object]]:
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
