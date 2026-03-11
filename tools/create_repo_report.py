    #!/usr/bin/env python3
    from pathlib import Path
    import json

    IGNORE = {
        ".git",
        "venv",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        "build",
        "dist",
        "obj_dir",
    }

    def scan(root: Path):
        report = {
            "root": str(root),
            "directories": [],
            "files": [],
        }

        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            parts = set(rel.parts)
            if parts & IGNORE:
                continue

            if path.is_dir():
                report["directories"].append(str(rel))
            else:
                report["files"].append(str(rel))

        return report

    def main():
        root = Path(__file__).resolve().parents[1]
        reports_dir = root / "reports"
        reports_dir.mkdir(exist_ok=True)

        report = scan(root)
        out_file = reports_dir / "repo_report.json"
        out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote: {out_file}")

    if __name__ == "__main__":
        main()
    