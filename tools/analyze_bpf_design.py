#!/usr/bin/env python3
"""Generate a lightweight structural summary of the BPF RTL design."""

import argparse
import re
from pathlib import Path

COMMENT_SL_RE = re.compile(r"//.*?$", re.M)
COMMENT_ML_RE = re.compile(r"/\*.*?\*/", re.S)
MODULE_RE = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b", re.S)

def strip_comments(text: str) -> str:
    text = COMMENT_ML_RE.sub("", text)
    text = COMMENT_SL_RE.sub("", text)
    return text

def find_files(folder: Path):
    files = []
    for ext in ("*.v", "*.sv"):
        files.extend(folder.rglob(ext))
    return sorted(files)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtl", required=True)
    args = ap.parse_args()

    rtl = Path(args.rtl).resolve()
    for f in find_files(rtl):
        txt = strip_comments(f.read_text(encoding="utf-8", errors="ignore"))
        mods = MODULE_RE.findall(txt)
        if mods:
            print(f"{f}: {', '.join(mods)}")

if __name__ == "__main__":
    main()
