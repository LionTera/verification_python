    #!/usr/bin/env python3
    from pathlib import Path

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

    def walk(root: Path, max_depth: int = 3):
        root = root.resolve()

        def _walk(path: Path, depth: int):
            if depth > max_depth:
                return
            entries = sorted([p for p in path.iterdir() if p.name not in IGNORE], key=lambda p: (p.is_file(), p.name.lower()))
            for entry in entries:
                rel = entry.relative_to(root)
                indent = "  " * depth
                suffix = "/" if entry.is_dir() else ""
                print(f"{indent}{rel.name}{suffix}")
                if entry.is_dir():
                    _walk(entry, depth + 1)

        print(root.name + "/")
        _walk(root, 1)

    def main():
        repo_root = Path(__file__).resolve().parents[1]
        walk(repo_root, max_depth=3)

    if __name__ == "__main__":
        main()
    