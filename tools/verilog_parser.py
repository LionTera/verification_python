"""Shared Verilog parsing utilities used by the wrapper generator and bootstrapper."""

from __future__ import annotations

import re
from pathlib import Path

COMMENT_SL_RE = re.compile(r"//.*?$", re.M)
COMMENT_ML_RE = re.compile(r"/\*.*?\*/", re.S)

MODULE_BLOCK_RE = re.compile(
    r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b(.*?)\bendmodule\b",
    re.S,
)

HEADER_RE = re.compile(
    r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\(.*?\))?\s*\((.*?)\)\s*;",
    re.S,
)

PORT_RE = re.compile(
    r"^\s*(input|output|inout)\s+"
    r"(?:(?:wire|reg|logic|signed)\s+)*"
    r"(?:\[\s*([^:\]]+)\s*:\s*([^\]]+)\s*\]\s+)?"
    r"([A-Za-z_][A-Za-z0-9_$]*)\s*$"
)

PARAM_RE = re.compile(
    r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\s*#\s*\((.*?)\)\s*\(",
    re.S,
)

PARAM_ITEM_RE = re.compile(
    r"parameter\s+([A-Za-z_][A-Za-z0-9_$]*)\s*=\s*([^,\n)]+)"
)

INSTANTIATION_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\(.*?\))?\s+([A-Za-z_][A-Za-z0-9_$]*)\s*\(",
    re.S,
)

IMPLICIT_PYMTL_PORTS = {"clk", "reset"}


def strip_comments(text: str) -> str:
    text = COMMENT_ML_RE.sub("", text)
    text = COMMENT_SL_RE.sub("", text)
    return text


def camel_case(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def find_verilog_files(folder: Path) -> list[Path]:
    files: list[Path] = []
    for ext in ("*.v", "*.sv"):
        files.extend(folder.rglob(ext))
    return sorted(f for f in files if f.is_file())


def parse_modules_from_file(path: Path) -> list[tuple[str, str]]:
    text = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
    return [(m.group(1), m.group(0)) for m in MODULE_BLOCK_RE.finditer(text)]


def parse_ports(module_text: str, module_name: str) -> list[dict]:
    for m in HEADER_RE.finditer(module_text):
        if m.group(1) != module_name:
            continue
        raw_ports = [p.strip() for p in m.group(2).split(",") if p.strip()]
        ports = []
        for raw in raw_ports:
            raw = " ".join(raw.split())
            pm = PORT_RE.match(raw)
            if not pm:
                continue
            direction, msb, lsb, name = pm.groups()
            width_expr = "1" if msb is None else f"{msb.strip()}:{lsb.strip()}"
            ports.append({"direction": direction, "name": name, "width_expr": width_expr})
        return ports
    return []


def parse_params(module_text: str, module_name: str) -> list[tuple[str, str]]:
    out = []
    for m in PARAM_RE.finditer(module_text):
        if m.group(1) != module_name:
            continue
        for pm in PARAM_ITEM_RE.finditer(m.group(2)):
            out.append((pm.group(1), pm.group(2).strip().rstrip(",")))
        break
    return out


def width_to_bits_name(width_expr: str) -> tuple[str, int | None]:
    if width_expr == "1":
        return "Bits1", 1

    mm = re.match(r"(\d+)\s*:\s*(\d+)", width_expr)
    if mm:
        a, b = int(mm.group(1)), int(mm.group(2))
        w = abs(a - b) + 1
        return f"Bits{w}", w

    mm = re.match(r"([A-Za-z_][A-Za-z0-9_$]*)\s*-\s*1\s*:\s*0", width_expr)
    if mm:
        return mm.group(1), None

    return "Bits1", 1


def build_module_db(rtl_dir: Path) -> dict:
    db: dict = {}
    for vf in find_verilog_files(rtl_dir):
        for mod_name, mod_text in parse_modules_from_file(vf):
            db[mod_name] = {
                "file": vf,
                "text": mod_text,
                "ports": parse_ports(mod_text, mod_name),
                "params": parse_params(mod_text, mod_name),
                "children": [],
            }
    known = set(db.keys())
    for mod_name, info in db.items():
        for m in INSTANTIATION_RE.finditer(info["text"]):
            child, inst = m.group(1), m.group(2)
            if child in known:
                info["children"].append((child, inst))
    return db
