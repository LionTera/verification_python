#!/usr/bin/env python3
from pathlib import Path
import argparse
import textwrap


def write_file(path: Path, content: str, overwrite: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        print(f"[skip] {path}")
        return
    path.write_text(content.lstrip("\n"), encoding="utf-8")
    print(f"[ ok ] {path}")


def mkdir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    print(f"[dir ] {path}")


def main():
    ap = argparse.ArgumentParser(
        description="Create a starter PyMTL/Verilog repo structure."
    )
    ap.add_argument(
        "--root",
        default=".",
        help="Target repo root directory (default: current directory)",
    )
    ap.add_argument(
        "--project-name",
        default="pymtl-verilog-project",
        help="Project name to place in README",
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    overwrite = args.overwrite
    project_name = args.project_name

    # ------------------------------------------------------------------
    # Directories
    # ------------------------------------------------------------------

    dirs = [
        "docs/architecture",
        "docs/guides",
        "rtl/top",
        "rtl/core",
        "rtl/common",
        "rtl/include",
        "pymtl/wrappers/generated",
        "pymtl/wrappers/manual",
        "pymtl/adapters",
        "sim/smoke",
        "sim/vectors",
        "sim/configs",
        "tests/unit",
        "tests/integration",
        "tests/regression",
        "tools",
        "scripts",
        "practice",
    ]

    for d in dirs:
        mkdir(root / d)

    # ------------------------------------------------------------------
    # Root files
    # ------------------------------------------------------------------

    gitignore = """
    # Python
    __pycache__/
    *.pyc
    *.pyo
    *.pyd
    .pytest_cache/
    .mypy_cache/

    # Virtual environments
    venv/
    .venv/

    # Build / packaging
    build/
    dist/
    *.egg-info/

    # Waveforms / simulation artifacts
    *.vcd
    *.fst
    *.log
    *.jou
    *.wdb

    # Verilator / generated artifacts
    obj_dir/
    .verilator/

    # Editors / OS
    .DS_Store
    Thumbs.db
    .idea/
    .vscode/

    # Local generated wrappers or reports
    reports/
    """

    readme = f"""
    # {project_name}

    Starter repository for a Verilog + PyMTL workflow.

    ## Intended structure

    - `rtl/` - Verilog/SystemVerilog source
    - `pymtl/` - PyMTL wrappers, adapters, and helper components
    - `sim/` - simulation harnesses and quick runners
    - `tests/` - pytest-based automated tests
    - `tools/` - developer utilities such as wrapper generation and repo inspection
    - `scripts/` - shell helpers for setup and test execution
    - `docs/` - architecture notes and design documentation

    ## Typical flow

    ```text
    rtl/ -> tools/gen_pymtl_wrapper.py -> pymtl/wrappers/generated/ -> sim/ + tests/
    ```

    ## Quick start

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pytest
    ```

    ## Notes

    - Generated wrappers should go in `pymtl/wrappers/generated/`
    - Handwritten adapters or custom wrappers should go in `pymtl/wrappers/manual/`
    """

    requirements = """
    pymtl3
    pytest
    pyverilog
    """

    pytest_ini = """
    [pytest]
    testpaths = tests
    python_files = test_*.py
    python_classes = Test*
    python_functions = test_*
    """

    write_file(root / ".gitignore", gitignore, overwrite)
    write_file(root / "README.md", readme, overwrite)
    write_file(root / "requirements.txt", requirements, overwrite)
    write_file(root / "pytest.ini", pytest_ini, overwrite)

    # ------------------------------------------------------------------
    # Package markers
    # ------------------------------------------------------------------

    init_files = [
        "pymtl/__init__.py",
        "pymtl/wrappers/__init__.py",
        "pymtl/wrappers/generated/__init__.py",
        "pymtl/wrappers/manual/__init__.py",
        "pymtl/adapters/__init__.py",
        "tests/__init__.py",
    ]

    for f in init_files:
        write_file(root / f, "", overwrite)

    # ------------------------------------------------------------------
    # Docs placeholders
    # ------------------------------------------------------------------

    architecture_md = """
    # Architecture Notes

    Fill this in once RTL modules are added.

    Suggested sections:
    - Top-level module
    - Main datapath blocks
    - Control path blocks
    - Input/output interfaces
    - Clock/reset assumptions
    - Data flow summary
    """

    wrapper_generation_md = """
    # Wrapper Generation

    Generated wrappers are expected to live under:

    - `pymtl/wrappers/generated/`

    Manual adjustments or higher-level adapters should live under:

    - `pymtl/wrappers/manual/`

    Recommended flow:

    1. Add Verilog files under `rtl/`
    2. Run `tools/gen_pymtl_wrapper.py`
    3. Review generated wrapper
    4. Add tests under `tests/`
    """

    write_file(root / "docs/architecture/overview.md", architecture_md, overwrite)
    write_file(root / "docs/guides/wrapper_generation.md", wrapper_generation_md, overwrite)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    gen_wrapper_placeholder = """
    #!/usr/bin/env python3
    \"\"\"
    Placeholder for a PyMTL wrapper generator.

    Intended future role:
    - Read Verilog module definitions from rtl/
    - Extract ports / widths / parameters
    - Emit wrapper files into pymtl/wrappers/generated/

    For now, this script just prints a message.
    \"\"\"

    from pathlib import Path

    def main():
        root = Path(__file__).resolve().parents[1]
        rtl_dir = root / "rtl"
        out_dir = root / "pymtl" / "wrappers" / "generated"

        print("Wrapper generator placeholder")
        print(f"RTL dir:      {rtl_dir}")
        print(f"Output dir:   {out_dir}")
        print("")
        print("Add Verilog files under rtl/ and then replace this placeholder")
        print("with the real parser/generator.")

    if __name__ == "__main__":
        main()
    """

    inspect_repo = """
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
    """

    create_report = """
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
    """

    create_module_stub = """
    #!/usr/bin/env python3
    import argparse
    from pathlib import Path

    TEMPLATE = \"\"\"module {module_name} (
        input  wire clk,
        input  wire reset
    );

    endmodule
    \"\"\"

    def main():
        ap = argparse.ArgumentParser(description="Create a basic Verilog module stub.")
        ap.add_argument("module_name", help="Module name")
        ap.add_argument("--subdir", default="core", help="Subdirectory under rtl/")
        args = ap.parse_args()

        root = Path(__file__).resolve().parents[1]
        out_dir = root / "rtl" / args.subdir
        out_dir.mkdir(parents=True, exist_ok=True)

        out_file = out_dir / f"{args.module_name}.v"
        if out_file.exists():
            print(f"Exists: {out_file}")
            return

        out_file.write_text(TEMPLATE.format(module_name=args.module_name), encoding="utf-8")
        print(f"Created: {out_file}")

    if __name__ == "__main__":
        main()
    """

    write_file(root / "tools/gen_pymtl_wrapper.py", gen_wrapper_placeholder, overwrite)
    write_file(root / "tools/inspect_repo.py", inspect_repo, overwrite)
    write_file(root / "tools/create_repo_report.py", create_report, overwrite)
    write_file(root / "tools/create_module_stub.py", create_module_stub, overwrite)

    # ------------------------------------------------------------------
    # Scripts
    # ------------------------------------------------------------------

    run_tests_sh = """
    #!/usr/bin/env bash
    set -e

    ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$ROOT_DIR"

    pytest -q
    """

    setup_env_sh = """
    #!/usr/bin/env bash
    set -e

    ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$ROOT_DIR"

    python3 -m venv venv
    source venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt

    echo "Environment ready."
    echo "Activate with: source venv/bin/activate"
    """

    repo_tree_sh = """
    #!/usr/bin/env bash
    set -e

    ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$ROOT_DIR"

    python tools/inspect_repo.py
    """

    write_file(root / "scripts/run_tests.sh", run_tests_sh, overwrite)
    write_file(root / "scripts/setup_env.sh", setup_env_sh, overwrite)
    write_file(root / "scripts/repo_tree.sh", repo_tree_sh, overwrite)

    # ------------------------------------------------------------------
    # Sim placeholders
    # ------------------------------------------------------------------

    smoke_runner = """
    #!/usr/bin/env python3
    \"\"\"
    Placeholder simulation smoke runner.

    Replace this with a real imported PyMTL DUT once wrappers exist.
    \"\"\"

    def main():
        print("Smoke simulation placeholder")
        print("Add a generated wrapper under pymtl/wrappers/generated/ and update this file.")

    if __name__ == "__main__":
        main()
    """

    write_file(root / "sim/smoke/run_smoke.py", smoke_runner, overwrite)

    # ------------------------------------------------------------------
    # Tests placeholders
    # ------------------------------------------------------------------

    test_smoke = """
    def test_repo_layout_smoke():
        assert True
    """

    write_file(root / "tests/unit/test_repo_layout.py", test_smoke, overwrite)

    # ------------------------------------------------------------------
    # Final note
    # ------------------------------------------------------------------

    print("\\nScaffold complete.")
    print(f"Root: {root}")
    print("")
    print("Recommended next steps:")
    print("1. Move your existing generator into tools/ if needed")
    print("2. Add Verilog files under rtl/")
    print("3. Replace tools/gen_pymtl_wrapper.py placeholder with the real generator")
    print("4. Add wrapper tests under tests/")


if __name__ == "__main__":
    main()