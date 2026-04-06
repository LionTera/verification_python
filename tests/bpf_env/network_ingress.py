"""Software ingress checks used by ingress-oriented verification tests."""

from __future__ import annotations

from dataclasses import dataclass
import zlib

from tests.bpf_env.bpf_python_tb import (
    BPF_ACCEPT_COUNTER_ADDR,
    BPF_PACKET_LOSS_COUNTER_ADDR,
    BPF_REJECT_COUNTER_ADDR,
    BpfPythonTB,
)


ETHERTYPE_IPV4 = 0x0800
BROADCAST_MAC = b"\xff\xff\xff\xff\xff\xff"


def ethernet_fcs(payload: bytes) -> bytes:
    """Return the Ethernet FCS for the provided payload."""
    return (zlib.crc32(payload) & 0xFFFFFFFF).to_bytes(4, "little")


def with_ethernet_fcs(frame_without_fcs: bytes) -> bytes:
    """Append a valid FCS to a frame."""
    return frame_without_fcs + ethernet_fcs(frame_without_fcs)


def mutate_ethertype(frame_without_fcs: bytes, ethertype: int) -> bytes:
    """Return a copy of a frame with a replaced ethertype field."""
    updated = bytearray(frame_without_fcs)
    updated[12:14] = ethertype.to_bytes(2, "big")
    return bytes(updated)


@dataclass(frozen=True)
class IngressDecision:
    """Result of software ingress evaluation for one frame."""
    accepted: bool
    reason: str
    packet_for_bpf: bytes | None


def evaluate_ingress_frame(
    frame_with_fcs: bytes,
    *,
    expected_dst_mac: bytes,
    accept_broadcast: bool = True,
    expected_ethertype: int = ETHERTYPE_IPV4,
) -> IngressDecision:
    """Apply ingress checks before deciding whether BPF should see the frame."""
    if len(frame_with_fcs) < 18:
        return IngressDecision(False, "too_short", None)

    frame = frame_with_fcs[:-4]
    observed_fcs = frame_with_fcs[-4:]
    expected_fcs = ethernet_fcs(frame)
    if observed_fcs != expected_fcs:
        return IngressDecision(False, "bad_crc", None)

    dst_mac = frame[:6]
    if dst_mac != expected_dst_mac and not (accept_broadcast and dst_mac == BROADCAST_MAC):
        return IngressDecision(False, "wrong_dst_mac", None)

    ethertype = int.from_bytes(frame[12:14], "big")
    if ethertype != expected_ethertype:
        return IngressDecision(False, "unsupported_ethertype", None)

    return IngressDecision(True, "accepted", frame)


def drive_ingress_frame(
    tb: BpfPythonTB,
    frame_with_fcs: bytes,
    *,
    expected_dst_mac: bytes,
    packet_loss_cycles: int = 1,
) -> IngressDecision:
    """Drive a frame through the ingress model and update loss signaling."""
    decision = evaluate_ingress_frame(frame_with_fcs, expected_dst_mac=expected_dst_mac)
    if decision.accepted:
        assert decision.packet_for_bpf is not None
        tb.load_packet(decision.packet_for_bpf)
        return decision

    tb.set_packet_loss(1)
    tb.step(packet_loss_cycles)
    tb.set_packet_loss(0)
    tb.step(1)
    return decision


def read_counters(tb: BpfPythonTB) -> tuple[int, int, int]:
    """Read accept, reject, and packet-loss counters from MMAP."""
    accept_now = tb.read_mmap(BPF_ACCEPT_COUNTER_ADDR)
    reject_now = tb.read_mmap(BPF_REJECT_COUNTER_ADDR)
    loss_now = tb.read_mmap(BPF_PACKET_LOSS_COUNTER_ADDR)
    return accept_now, reject_now, loss_now
