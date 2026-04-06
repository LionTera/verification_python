"""Shared helpers for event-based golden models in Python tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class GoldenEvent:
    """One expected event in a test-level golden model."""
    event_type: str
    cycle: int
    reason: str
    item_index: int
    expected_counter: int
    entered_bpf: bool
    name: str = ""
    protocol: str = ""
    start_cycle: int | None = None
    end_cycle: int | None = None


def collect_signal_cycles(trace_rows: Iterable[dict[str, int | str]], signal_name: str) -> list[int]:
    """Return all cycles where the given trace signal is asserted."""
    return [int(row["cycle"]) for row in trace_rows if int(row[signal_name]) == 1]


class GoldenModelTracker:
    """Track expected events and their running counters."""

    def __init__(self) -> None:
        self._events: list[GoldenEvent] = []
        self._counter_by_type: dict[str, int] = {}

    @property
    def events(self) -> list[GoldenEvent]:
        """Return a copy of the recorded golden events."""
        return list(self._events)

    def count(self, event_type: str) -> int:
        """Return the current expected count for an event type."""
        return self._counter_by_type.get(event_type, 0)

    def record(
        self,
        *,
        event_type: str,
        cycle: int,
        reason: str,
        item_index: int,
        entered_bpf: bool,
        name: str = "",
        protocol: str = "",
        start_cycle: int | None = None,
        end_cycle: int | None = None,
    ) -> GoldenEvent:
        """Record an expected event and advance its event counter."""
        expected_counter = self.count(event_type) + 1
        event = GoldenEvent(
            event_type=event_type,
            cycle=cycle,
            reason=reason,
            item_index=item_index,
            expected_counter=expected_counter,
            entered_bpf=entered_bpf,
            name=name,
            protocol=protocol,
            start_cycle=start_cycle,
            end_cycle=end_cycle,
        )
        self._events.append(event)
        self._counter_by_type[event_type] = expected_counter
        return event

    def cycles(self, event_type: str) -> list[int]:
        """Return the expected cycle list for one event type."""
        return [event.cycle for event in self._events if event.event_type == event_type]

    def compare_cycles(self, actual_cycles: list[int], event_type: str) -> None:
        """Assert that actual cycles match the golden model exactly."""
        expected_cycles = self.cycles(event_type)
        assert actual_cycles == expected_cycles, (
            f"{event_type} cycle mismatch: expected={expected_cycles} actual={actual_cycles}"
        )


def event_cycles_comparison_markdown(
    *,
    title: str,
    expected_cycles: list[int],
    actual_cycles: list[int],
) -> str:
    """Render a Markdown table comparing expected and actual cycles."""
    lines = [
        f"## {title}",
        "",
        "| Event | Expected Cycle | Actual Cycle | Match |",
        "| --- | --- | --- | --- |",
    ]
    max_len = max(len(expected_cycles), len(actual_cycles))
    for index in range(max_len):
        expected_cycle = expected_cycles[index] if index < len(expected_cycles) else "-"
        actual_cycle = actual_cycles[index] if index < len(actual_cycles) else "-"
        lines.append(
            f"| `{index}` | `{expected_cycle}` | `{actual_cycle}` | `{expected_cycle == actual_cycle}` |"
        )
    lines.append("")
    return "\n".join(lines)


def golden_events_markdown(
    *,
    title: str,
    events: Iterable[GoldenEvent],
) -> str:
    """Render a Markdown table listing golden events."""
    lines = [
        f"## {title}",
        "",
        "| Index | Name | Protocol | Event Type | Reason | Cycle | Expected Counter | Entered BPF | Start Cycle | End Cycle |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for event in events:
        lines.append(
            f"| `{event.item_index}` | `{event.name}` | `{event.protocol}` | `{event.event_type}` | `{event.reason}` | "
            f"`{event.cycle}` | `{event.expected_counter}` | `{event.entered_bpf}` | `{event.start_cycle}` | `{event.end_cycle}` |"
        )
    lines.append("")
    return "\n".join(lines)


def append_markdown_sections(report_path: Path, sections: Iterable[str]) -> None:
    """Append Markdown sections to an existing report file."""
    with report_path.open("a", encoding="utf-8") as report_file:
        report_file.write("\n".join(sections))
