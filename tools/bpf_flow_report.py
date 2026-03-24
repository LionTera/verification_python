#!/usr/bin/env python3
import argparse
import re
from collections import defaultdict
from pathlib import Path

COMMENT_SL_RE = re.compile(r"//.*?$", re.M)
COMMENT_ML_RE = re.compile(r"/\*.*?\*/", re.S)
MODULE_BLOCK_RE = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b(.*?)\bendmodule\b", re.S)
INSTANTIATION_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\(.*?\))?\s+([A-Za-z_][A-Za-z0-9_$]*)\s*\(", re.S)

def strip_comments(text: str) -> str:
    text = COMMENT_ML_RE.sub("", text)
    text = COMMENT_SL_RE.sub("", text)
    return text

def find_files(folder: Path):
    files = []
    for ext in ("*.v", "*.sv"):
        files.extend(folder.rglob(ext))
    return sorted(files)

def parse_modules(files):
    db = {}
    for f in files:
        txt = strip_comments(f.read_text(encoding="utf-8", errors="ignore"))
        for m in MODULE_BLOCK_RE.finditer(txt):
            db[m.group(1)] = {"file": f, "text": m.group(0)}
    return db

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtl", required=True)
    ap.add_argument("--out", default="reports/bpf_flow_report.md")
    args = ap.parse_args()

    rtl = Path(args.rtl).resolve()
    files = find_files(rtl)
    db = parse_modules(files)
    known = set(db.keys())
    parents = defaultdict(list)

    for mod, info in db.items():
        for m in INSTANTIATION_RE.finditer(info["text"]):
            child = m.group(1)
            inst = m.group(2)
            if child in known:
                parents[child].append((mod, inst))

    tops = sorted([m for m in db if m not in parents])

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# BPF Flow Report", "", "## Top Candidates", ""]
    for t in tops:
        lines.append(f"- `{t}`")
    lines.append("")
    lines.append("## Modules")
    lines.append("")
    for mod in sorted(db):
        lines.append(f"- `{mod}` -> `{db[mod]['file']}`")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] wrote: {out}")

if __name__ == "__main__":
    main()
