"""Compare expected packet-loss events in a report against the CSV trace."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


LOSS_SECTION_HEADER = "## Golden Loss Events"


def parse_loss_events(report_path: Path) -> list[dict[str, int]]:
    text = report_path.read_text(encoding="utf-8")
    if LOSS_SECTION_HEADER not in text:
        raise ValueError(f"Could not find '{LOSS_SECTION_HEADER}' in {report_path}")

    section = text.split(LOSS_SECTION_HEADER, 1)[1]
    lines = section.splitlines()
    events: list[dict[str, int]] = []
    row_pattern = re.compile(
        r"^\|\s*`(?P<loss_event>\d+)`\s*\|\s*`(?P<packet_index>\d+)`\s*\|\s*`(?P<assert_cycle>\d+)`\s*\|\s*`(?P<release_cycle>\d+)`\s*\|\s*`(?P<expected_loss_count>\d+)`\s*\|$"
    )
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and stripped != LOSS_SECTION_HEADER:
            break
        match = row_pattern.match(stripped)
        if not match:
            continue
        events.append({key: int(value) for key, value in match.groupdict().items()})

    if not events:
        raise ValueError(f"No loss-event rows found in {report_path}")
    return events


def parse_actual_loss_cycles(csv_path: Path) -> list[dict[str, int]]:
    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    actual: list[dict[str, int]] = []
    for row in rows:
        try:
            if int(row.get("bpf_packet_loss", "0")) != 1:
                continue
        except ValueError:
            continue
        actual.append(
            {
                "cycle": int(row["cycle"]),
                "tb_cycle_counter": int(row.get("tb_cycle_counter", "0") or 0),
            }
        )
    if not actual:
        raise ValueError(f"No bpf_packet_loss=1 rows found in {csv_path}")
    return actual


def verify_loss_schedule(report_path: Path, csv_path: Path) -> tuple[bool, list[str]]:
    expected = parse_loss_events(report_path)
    actual = parse_actual_loss_cycles(csv_path)
    problems: list[str] = []

    expected_cycles = [event["assert_cycle"] for event in expected]
    actual_cycles = [event["cycle"] for event in actual]

    if len(expected_cycles) != len(actual_cycles):
        problems.append(
            f"Loss pulse count mismatch: expected {len(expected_cycles)} events, found {len(actual_cycles)} CSV rows with bpf_packet_loss=1."
        )

    for index, (expected_cycle, actual_cycle) in enumerate(zip(expected_cycles, actual_cycles)):
        if expected_cycle != actual_cycle:
            problems.append(
                f"Event {index}: expected loss at cycle {expected_cycle}, found cycle {actual_cycle}."
            )

    if len(expected_cycles) > len(actual_cycles):
        for index in range(len(actual_cycles), len(expected_cycles)):
            problems.append(f"Missing actual loss pulse for expected event {index} at cycle {expected_cycles[index]}.")
    elif len(actual_cycles) > len(expected_cycles):
        for index in range(len(expected_cycles), len(actual_cycles)):
            problems.append(f"Unexpected extra actual loss pulse at cycle {actual_cycles[index]}.")

    return not problems, problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that the golden loss-event schedule in a BPF report matches the CSV trace."
    )
    parser.add_argument("--report", required=True, help="Path to the markdown report")
    parser.add_argument("--csv", required=True, help="Path to the CSV trace")
    parser.add_argument(
        "--show-first",
        type=int,
        default=10,
        help="How many matching loss events to print when verification succeeds",
    )
    args = parser.parse_args()

    report_path = Path(args.report)
    csv_path = Path(args.csv)
    ok, problems = verify_loss_schedule(report_path, csv_path)
    expected = parse_loss_events(report_path)
    actual = parse_actual_loss_cycles(csv_path)

    print(f"Report: {report_path}")
    print(f"CSV:    {csv_path}")
    print(f"Expected loss events: {len(expected)}")
    print(f"Actual CSV loss rows: {len(actual)}")

    if ok:
        print("Verification: PASS")
        count = min(args.show_first, len(expected))
        print(f"First {count} expected/actual loss cycles:")
        for index in range(count):
            print(
                f"  event {index}: expected_cycle={expected[index]['assert_cycle']} "
                f"actual_cycle={actual[index]['cycle']} tb_cycle_counter={actual[index]['tb_cycle_counter']}"
            )
        return 0

    print("Verification: FAIL")
    for problem in problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
