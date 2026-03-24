#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

COMMENT_SL_RE = re.compile(r"//.*?$", re.M)
COMMENT_ML_RE = re.compile(r"/\*.*?\*/", re.S)
MODULE_BLOCK_RE = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b(.*?)\bendmodule\b", re.S)
HEADER_RE = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\(.*?\))?\s*\((.*?)\)\s*;", re.S)
PORT_RE = re.compile(
    r"^\s*(input|output|inout)\s+"
    r"(?:(?:wire|reg|logic|signed)\s+)*"
    r"(?:\[\s*([^:\]]+)\s*:\s*([^\]]+)\s*\]\s+)?"
    r"([A-Za-z_][A-Za-z0-9_$]*)\s*$"
)
PARAM_RE = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\s*#\s*\((.*?)\)\s*\(", re.S)
PARAM_ITEM_RE = re.compile(r"parameter\s+([A-Za-z_][A-Za-z0-9_$]*)\s*=\s*([^,\n)]+)")
IMPLICIT_PYMTL_PORTS = {"clk", "reset"}

def strip_comments(text: str) -> str:
    text = COMMENT_ML_RE.sub("", text)
    text = COMMENT_SL_RE.sub("", text)
    return text

def camel_case(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))

def find_verilog_files(folder: Path):
    files = []
    for ext in ("*.v", "*.sv"):
        files.extend(folder.rglob(ext))
    return sorted([f for f in files if f.is_file()])

def parse_modules_from_file(path: Path):
    text = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
    return [(m.group(1), m.group(0)) for m in MODULE_BLOCK_RE.finditer(text)]

def parse_ports(module_text: str, module_name: str):
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

def parse_params(module_text: str, module_name: str):
    out = []
    for m in PARAM_RE.finditer(module_text):
        if m.group(1) != module_name:
            continue
        for pm in PARAM_ITEM_RE.finditer(m.group(2)):
            out.append((pm.group(1), pm.group(2).strip().rstrip(",")))
        break
    return out

def width_to_bits_name(width_expr: str):
    if width_expr == "1":
        return "Bits1", 1
    mm = re.match(r"(\d+)\s*:\s*(\d+)", width_expr)
    if mm:
        a = int(mm.group(1)); b = int(mm.group(2))
        w = abs(a - b) + 1
        return f"Bits{w}", w
    mm = re.match(r"([A-Za-z_][A-Za-z0-9_$]*)\s*-\s*1\s*:\s*0", width_expr)
    if mm:
        pname = mm.group(1)
        return pname, None
    return "Bits1", 1

def build_module_db(rtl_dir: Path):
    db = {}
    for vf in find_verilog_files(rtl_dir):
        for mod_name, mod_text in parse_modules_from_file(vf):
            db[mod_name] = {
                "file": vf,
                "text": mod_text,
                "ports": parse_ports(mod_text, mod_name),
                "params": parse_params(mod_text, mod_name),
            }
    return db

def guess_default_param_value(pval: str):
    pval = pval.strip()
    if re.fullmatch(r"\d+", pval):
        return int(pval)
    return None

def make_wrapper_code(repo_root: Path, rtl_dir: Path, mod_name: str, info: dict, all_rtl_files):
    class_name = camel_case(mod_name)
    ports = info["ports"]
    params = info["params"]

    bit_defs = ["Bits1 = mk_bits(1)"]
    seen_numeric = {1}
    port_lines = []
    param_meta = []

    for pname, pval in params:
        guessed = guess_default_param_value(pval)
        if guessed is not None:
            param_meta.append(f'                "{pname}": {guessed},')

    for p in ports:
        if p["name"] in IMPLICIT_PYMTL_PORTS:
            continue
        bits_name, width_num = width_to_bits_name(p["width_expr"])
        if width_num is not None and width_num not in seen_numeric:
            bit_defs.append(f"Bits{width_num} = mk_bits({width_num})")
            seen_numeric.add(width_num)
        ctor_arg = f"mk_bits({bits_name})" if width_num is None else bits_name
        ctor = "InPort" if p["direction"] == "input" else "OutPort"
        port_lines.append(f"        s.{p['name']:<20} = {ctor}( {ctor_arg} )")

    src_rel = info["file"].resolve().relative_to(repo_root.resolve()).as_posix()
    vlibs_rel = [
        f.resolve().relative_to(repo_root.resolve()).as_posix()
        for f in all_rtl_files if f.resolve() != info["file"].resolve()
    ]

    libs_block = ""
    if vlibs_rel:
        libs_lines = "\n".join([f'                join( base, "{p}" ),' for p in vlibs_rel])
        libs_block = f'''
        s.set_metadata(
            VerilogPlaceholderPass.v_libs,
            [
{libs_lines}
            ]
        )
'''

    params_block = ""
    if param_meta:
        params_block = f'''
        s.set_metadata(
            VerilogPlaceholderPass.params,
            {{
{chr(10).join(param_meta)}
            }}
        )
'''

    body = "\n".join(port_lines) if port_lines else "        pass"
    code = f'''from os.path import dirname, join, abspath
from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholder, VerilogPlaceholderPass

{chr(10).join(bit_defs)}

class {class_name}( Component, VerilogPlaceholder ):
    def construct( s ):
{body}

        base = abspath( join( dirname(__file__), "..", ".." ) )

        s.set_metadata(
            VerilogPlaceholderPass.src_file,
            join( base, "{src_rel}" )
        )

        s.set_metadata(
            VerilogPlaceholderPass.top_module,
            "{mod_name}"
        ){params_block}{libs_block}
        s.set_metadata(
            VerilogPlaceholderPass.v_include,
            [
                join( base, "{rtl_dir.resolve().relative_to(repo_root.resolve()).as_posix()}" )
            ]
        )
'''
    return code

def main():
    ap = argparse.ArgumentParser(description="Generate one PyMTL wrapper per RTL module.")
    ap.add_argument("--rtl", required=True)
    ap.add_argument("--outdir", default="pymtl/wrappers")
    ap.add_argument("--repo-root", default=".")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    rtl_dir = Path(args.rtl).resolve()
    outdir = Path(args.outdir).resolve()

    db = build_module_db(rtl_dir)
    all_rtl_files = find_verilog_files(rtl_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "__init__.py").write_text("", encoding="utf-8")

    for mod_name, info in sorted(db.items()):
        wrapper_code = make_wrapper_code(repo_root, rtl_dir, mod_name, info, all_rtl_files)
        (outdir / f"{mod_name}_wrapper.py").write_text(wrapper_code, encoding="utf-8")
        print(f"[OK] wrote wrapper: {outdir / f'{mod_name}_wrapper.py'}")

if __name__ == "__main__":
    main()
