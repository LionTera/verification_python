from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def classify(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name
    if suffix == ".csv":
        return "csv"
    if suffix == ".md":
        return "md"
    if suffix == ".vcd":
        return "vcd"
    if name.endswith(".verilator1.vcd"):
        return "vcd"
    if suffix == ".json":
        return "json"
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser(description="Organize generated BPF report artifacts under reports/.")
    parser.add_argument("--reports-dir", default="reports", help="Reports directory to organize")
    parser.add_argument(
        "--mode",
        choices=("copy", "move"),
        default="copy",
        help="Copy files into typed subdirectories or move them there",
    )
    parser.add_argument(
        "--pattern",
        default="*",
        help="Glob pattern for generated files to organize from the reports root",
    )
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    if not reports_dir.exists():
        raise SystemExit(f"Reports directory does not exist: {reports_dir}")

    destinations = {
        "csv": reports_dir / "organized" / "csv",
        "md": reports_dir / "organized" / "md",
        "vcd": reports_dir / "organized" / "vcd",
        "json": reports_dir / "organized" / "json",
        "other": reports_dir / "organized" / "other",
    }
    for dest in destinations.values():
        dest.mkdir(parents=True, exist_ok=True)

    for path in sorted(reports_dir.glob(args.pattern)):
        if not path.is_file():
            continue
        if path.parent.name == "organized":
            continue
        category = classify(path)
        dest = destinations[category] / path.name
        if args.mode == "move":
            shutil.move(str(path), str(dest))
            action = "moved"
        else:
            shutil.copy2(path, dest)
            action = "copied"
        print(f"{action}: {path} -> {dest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
