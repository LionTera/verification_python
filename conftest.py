from __future__ import annotations

import os


def pytest_addoption(parser):
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


def pytest_configure(config):
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
    )
    for option_name, env_name, forced_value in mappings:
        option_value = config.getoption(option_name)
        if option_value in (None, False):
            continue
        os.environ[env_name] = forced_value if forced_value is not None else str(option_value)
