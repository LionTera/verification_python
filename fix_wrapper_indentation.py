#!/usr/bin/env python3
from pathlib import Path
import argparse


def fix_wrapper_text(text: str) -> str:
    lines = text.splitlines()

    fixed = []
    in_construct = False

    for line in lines:
        stripped = line.lstrip()

        if stripped == "":
            fixed.append("")
            continue

        # top-level imports
        if stripped.startswith("from ") or stripped.startswith("import "):
            fixed.append(stripped)
            continue

        # top-level constants like Bits1 = mk_bits(1)
        if " = mk_bits(" in stripped and not stripped.startswith("s."):
            fixed.append(stripped)
            continue

        # class definition
        if stripped.startswith("class "):
            in_construct = False
            fixed.append(stripped)
            continue

        # construct method
        if stripped.startswith("def construct"):
            in_construct = True
            fixed.append("    " + stripped)
            continue

        # anything inside construct should be indented 8 spaces
        if in_construct:
            fixed.append("        " + stripped)
            continue

        # fallback: keep top-level unindented
        fixed.append(stripped)

    return "\n".join(fixed) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Fix indentation in generated PyMTL wrapper files.")
    ap.add_argument("--wrappers-dir", default="pymtl/wrappers", help="Directory containing wrapper files")
    ap.add_argument("--dry-run", action="store_true", help="Show files that would be changed")
    args = ap.parse_args()

    wrappers_dir = Path(args.wrappers_dir).resolve()
    if not wrappers_dir.exists():
        raise FileNotFoundError(f"Wrappers directory not found: {wrappers_dir}")

    files = sorted(wrappers_dir.glob("*_wrapper.py"))
    if not files:
        print("[INFO] No wrapper files found.")
        return

    changed = 0

    for path in files:
        original = path.read_text(encoding="utf-8")
        fixed = fix_wrapper_text(original)

        if fixed != original:
            changed += 1
            if args.dry_run:
                print(f"[DRY RUN] would fix: {path}")
            else:
                path.write_text(fixed, encoding="utf-8")
                print(f"[OK] fixed: {path}")

    if args.dry_run:
        print(f"[INFO] {changed} file(s) would be changed.")
    else:
        print(f"[INFO] {changed} file(s) fixed.")


if __name__ == "__main__":
    main()