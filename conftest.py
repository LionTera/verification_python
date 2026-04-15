"""Pytest configuration for the BPF verification environment.

This module registers CLI knobs for waveform dumping, reports, traffic sizing,
deterministic seeds, and per-run artifact IDs. Selected CLI options are also
mirrored into environment variables so the shared helpers can consume one
consistent configuration source.
"""

from __future__ import annotations

import os
from datetime import datetime


def pytest_addoption(parser):
    """Register BPF-specific pytest command-line options."""
    group = parser.getgroup("bpf")
    group.addoption(
        "--bpf-waveform",
        action="store_true",
        default=False,
        help="Enable BPF waveform dumping for tests that support it.",
    )
    group.addoption(
        "--bpf-reports",
        action="store_true",
        default=False,
        help="Enable BPF CSV/Markdown report generation for tests that support it.",
    )
    group.addoption(
        "--bpf-full-artifacts",
        action="store_true",
        default=False,
        help="Enable full probe/report artifacts in addition to main test artifacts.",
    )
    group.addoption(
        "--bpf-packet-count",
        action="store",
        default=None,
        help="Override packet count for configurable BPF traffic stress tests.",
    )
    group.addoption(
        "--bpf-packet-loss-percent",
        action="store",
        default=None,
        help="Override packet-loss percentage for configurable BPF traffic stress tests.",
    )
    group.addoption(
        "--bpf-packet-rng-seed",
        action="store",
        default=None,
        help="Override RNG seed for configurable BPF traffic stress tests.",
    )
    group.addoption(
        "--bpf-progress-interval",
        action="store",
        default=None,
        help="Override progress print interval for configurable BPF traffic stress tests.",
    )
    group.addoption(
        "--bpf-unique-packets",
        action="store",
        default=None,
        help="Override the number of unique packets generated for configurable BPF traffic tests.",
    )
    group.addoption(
        "--bpf-protocol-mode",
        action="store",
        default=None,
        help="Protocol mode for configurable BPF traffic tests: 1=TCP, 2=UDP, 3=TCP+UDP, 4=TCP+UDP+IP.",
    )
    group.addoption(
        "--bpf-error-level",
        action="store",
        default=None,
        help="Error level for configurable BPF traffic tests: 1=packet loss, 2=CRC errors and packet loss.",
    )
    group.addoption(
        "--bpf-run-id",
        action="store",
        default=None,
        help="Optional artifact run ID suffix. If omitted, a timestamp-based run ID is generated per pytest run.",
    )
    group.addoption(
        "--bpf-randomize-fields",
        action="store",
        default=None,
        help=(
            "Comma-separated packet fields to randomize deterministically in configurable-generator flows "
            "(for example: ttl,dscp_ecn,payload_len,payload_bytes,tcp_flags)."
        ),
    )
    group.addoption(
        "--bpf-payload-len-min",
        action="store",
        default=None,
        help="Minimum randomized payload length for configurable-generator flows.",
    )
    group.addoption(
        "--bpf-payload-len-max",
        action="store",
        default=None,
        help="Maximum randomized payload length for configurable-generator flows.",
    )
    group.addoption(
        "--bpf-program-randomness",
        action="store",
        default=None,
        help="Generated-program request randomness level: low, medium, or high.",
    )
    group.addoption(
        "--bpf-program-ttl-min",
        action="store",
        default=None,
        help="Minimum TTL threshold for generated-program request tests.",
    )
    group.addoption(
        "--bpf-program-tcp-flags-mask",
        action="store",
        default=None,
        help="TCP flags bitmask for generated-program request tests, for example 0x02.",
    )
    group.addoption(
        "--bpf-program-min-packet-len",
        action="store",
        default=None,
        help="Minimum packet length for generated-program request tests.",
    )


def pytest_configure(config):
    """Publish selected pytest options into environment variables."""
    mappings = (
        ("--bpf-waveform", "BPF_WAVEFORM", "1"),
        ("--bpf-reports", "BPF_REPORTS", "1"),
        ("--bpf-full-artifacts", "BPF_FULL_ARTIFACTS", "1"),
        ("--bpf-packet-count", "BPF_PACKET_COUNT", None),
        ("--bpf-packet-loss-percent", "BPF_PACKET_LOSS_PERCENT", None),
        ("--bpf-packet-rng-seed", "BPF_PACKET_RNG_SEED", None),
        ("--bpf-progress-interval", "BPF_PACKET_PROGRESS_INTERVAL", None),
        ("--bpf-unique-packets", "BPF_UNIQUE_PACKETS", None),
        ("--bpf-protocol-mode", "BPF_PROTOCOL_MODE", None),
        ("--bpf-error-level", "BPF_ERROR_LEVEL", None),
        ("--bpf-run-id", "BPF_RUN_ID", None),
        ("--bpf-randomize-fields", "BPF_RANDOMIZE_FIELDS", None),
        ("--bpf-payload-len-min", "BPF_PAYLOAD_LEN_MIN", None),
        ("--bpf-payload-len-max", "BPF_PAYLOAD_LEN_MAX", None),
        ("--bpf-program-randomness", "BPF_PROGRAM_RANDOMNESS", None),
        ("--bpf-program-ttl-min", "BPF_PROGRAM_TTL_MIN", None),
        ("--bpf-program-tcp-flags-mask", "BPF_PROGRAM_TCP_FLAGS_MASK", None),
        ("--bpf-program-min-packet-len", "BPF_PROGRAM_MIN_PACKET_LEN", None),
    )
    for option_name, env_name, forced_value in mappings:
        option_value = config.getoption(option_name)
        if option_value in (None, False):
            continue
        os.environ[env_name] = forced_value if forced_value is not None else str(option_value)
    if not os.environ.get("BPF_RUN_ID", "").strip():
        os.environ["BPF_RUN_ID"] = datetime.now().strftime("%Y%m%d_%H%M%S")
