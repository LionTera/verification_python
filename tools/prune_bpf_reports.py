from __future__ import annotations

import argparse
import time
from pathlib import Path


def is_generated_bpf_artifact(path: Path) -> bool:
    name = path.name
    return (
        path.is_file()
        and (
            name.startswith("bpf_")
            or name.endswith(".verilator1.vcd")
            or name.endswith(".vcd")
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete older generated BPF report artifacts.")
    parser.add_argument("--reports-dir", default="reports", help="Reports directory to prune")
    parser.add_argument(
        "--keep",
        type=int,
        default=20,
        help="Keep this many newest generated artifacts in the reports root",
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=7,
        help="Only prune files older than this many days",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting it",
    )
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    if not reports_dir.exists():
        raise SystemExit(f"Reports directory does not exist: {reports_dir}")

    cutoff = time.time() - args.older_than_days * 86400
    artifacts = [p for p in reports_dir.iterdir() if is_generated_bpf_artifact(p)]
    artifacts.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    keep_set = set(artifacts[: args.keep])
    deleted = 0
    for path in artifacts[args.keep :]:
        if path.stat().st_mtime >= cutoff:
            continue
        if args.dry_run:
            print(f"would delete: {path}")
        else:
            path.unlink(missing_ok=True)
            print(f"deleted: {path}")
        deleted += 1

    print(
        f"kept newest={min(len(artifacts), args.keep)} "
        f"considered={len(artifacts)} deleted={deleted} dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
