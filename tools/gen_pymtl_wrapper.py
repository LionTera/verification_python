#!/usr/bin/env python3
"""Generate a PyMTL wrapper for a selected Verilog RTL module."""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.verilog_parser import (
    build_module_db,
    camel_case,
    find_verilog_files,
    IMPLICIT_PYMTL_PORTS,
    width_to_bits_name,
)


def guess_default_param_value(pval: str) -> int | None:
    pval = pval.strip()
    if re.fullmatch(r"\d+", pval):
        return int(pval)
    return None


def make_wrapper_code(repo_root: Path, rtl_dir: Path, mod_name: str, info: dict, all_rtl_files: list[Path]) -> str:
    class_name = camel_case(mod_name)
    ports = info["ports"]
    params = info["params"]

    bit_defs = ["Bits1 = mk_bits(1)"]
    seen_numeric: set[int] = {1}
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
    return f'''from os.path import dirname, join, abspath
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


def main() -> None:
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
        out_path = outdir / f"{mod_name}_wrapper.py"
        out_path.write_text(wrapper_code, encoding="utf-8")
        print(f"[OK] wrote wrapper: {out_path}")


if __name__ == "__main__":
    main()
