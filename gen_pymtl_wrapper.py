#!/usr/bin/env python3
import argparse
import os
from typing import List, Optional, Tuple

from pyverilog.vparser.parser import parse
from pyverilog.vparser.ast import (
    ModuleDef,
    Ioport,
    Input,
    Output,
    Inout,
    Width,
    IntConst,
    Identifier,
    Minus,
    Plus,
    Pointer,
    Partselect,
)

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

COMMON_IMPLICIT_PORTS = {"clk", "clock", "rst", "reset"}

def expr_to_str(node) -> str:
    """Convert a subset of PyVerilog AST expressions into Python-ish strings."""
    if node is None:
        return ""
    if isinstance(node, IntConst):
        return node.value
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, Plus):
        return f"({expr_to_str(node.left)} + {expr_to_str(node.right)})"
    if isinstance(node, Minus):
        return f"({expr_to_str(node.left)} - {expr_to_str(node.right)})"
    if isinstance(node, Pointer):
        return f"{expr_to_str(node.var)}[{expr_to_str(node.ptr)}]"
    if isinstance(node, Partselect):
        return f"{expr_to_str(node.var)}[{expr_to_str(node.msb)}:{expr_to_str(node.lsb)}]"
    return str(node)

def width_to_pymtl(width: Optional[Width]) -> Tuple[str, str]:
    """
    Return:
      (bits_type_str, width_expr_comment)
    Examples:
      [31:0] -> ("Bits32", "32")
      [W-1:0] -> ("mk_bits((W - 1) - 0 + 1)", "(W - 1) - 0 + 1")
      None -> ("Bits1", "1")
    """
    if width is None:
        return "Bits1", "1"

    msb = expr_to_str(width.msb)
    lsb = expr_to_str(width.lsb)

    # Try constant-folding simple integer widths
    try:
        msb_i = int(msb, 0)
        lsb_i = int(lsb, 0)
        nbits = abs(msb_i - lsb_i) + 1
        return f"Bits{nbits}", str(nbits)
    except Exception:
        width_expr = f"({msb}) - ({lsb}) + 1"
        return f"mk_bits({width_expr})", width_expr

def direction_of(port_decl) -> str:
    if isinstance(port_decl, Input):
        return "input"
    if isinstance(port_decl, Output):
        return "output"
    if isinstance(port_decl, Inout):
        return "inout"
    raise TypeError(f"Unsupported port decl type: {type(port_decl)}")

def port_type_to_pymtl(direction: str, bits_type: str) -> str:
    if direction == "input":
        return f"InPort({bits_type})"
    if direction == "output":
        return f"OutPort({bits_type})"
    if direction == "inout":
        return f"InPort({bits_type})  # TODO: replace with proper Inout strategy if needed"
    raise ValueError(direction)

def find_module(ast, top_module: Optional[str]) -> ModuleDef:
    modules = [d for d in ast.description.definitions if isinstance(d, ModuleDef)]
    if not modules:
        raise RuntimeError("No module definitions found.")

    if top_module:
        for m in modules:
            if m.name == top_module:
                return m
        found = ", ".join(m.name for m in modules)
        raise RuntimeError(f"Module '{top_module}' not found. Found: {found}")

    if len(modules) == 1:
        return modules[0]

    found = ", ".join(m.name for m in modules)
    raise RuntimeError(
        f"Multiple modules found. Please specify --top. Found: {found}"
    )

def extract_ports(module: ModuleDef):
    ports = []

    for p in module.portlist.ports:
        if not isinstance(p, Ioport):
            continue

        decl = p.first
        if decl is None:
            continue

        name = decl.name
        direction = direction_of(decl)
        bits_type, width_expr = width_to_pymtl(getattr(decl, "width", None))

        ports.append(
            {
                "name": name,
                "direction": direction,
                "bits_type": bits_type,
                "width_expr": width_expr,
                "is_implicit_clock_reset": name.lower() in COMMON_IMPLICIT_PORTS,
            }
        )

    return ports

def extract_params(module: ModuleDef):
    params = []
    if module.paramlist is None:
        return params

    for param_decl in module.paramlist.params:
        # Parameter nodes vary by source style; keep this simple and tolerant
        if hasattr(param_decl, "name"):
            name = param_decl.name
            value = expr_to_str(getattr(param_decl, "value", None))
            params.append((name, value))
    return params

def generate_wrapper(
    module_name: str,
    src_files: List[str],
    ports,
    params,
    class_name: Optional[str] = None,
) -> str:
    class_name = class_name or f"{module_name}Wrapper"

    lines = []
    lines.append("from pymtl3 import *")
    lines.append("from pymtl3.passes.backends.verilog import *")
    lines.append("")
    lines.append("")
    lines.append(f"class {class_name}( Component, VerilogPlaceholder ):")
    lines.append("")
    lines.append("    def construct( s ):")
    lines.append("        # PyMTL provides implicit clk/reset on Components.")
    lines.append("        # If your Verilog uses standard names like clk/reset,")
    lines.append("        # they usually map automatically during import.")
    lines.append("")

    active_ports = [p for p in ports if not p["is_implicit_clock_reset"]]

    if not active_ports:
        lines.append("        pass")
    else:
        for p in active_ports:
            lines.append(
                f"        s.{p['name']} = {port_type_to_pymtl(p['direction'], p['bits_type'])}"
            )

    lines.append("")
    lines.append(f'        s.set_metadata( VerilogPlaceholderPass.top_module, "{module_name}" )')

    if len(src_files) == 1:
        lines.append(
            f'        s.set_metadata( VerilogPlaceholderPass.src_file, r"{src_files[0]}" )'
        )
    else:
        flist_repr = "[" + ", ".join(f'r"{x}"' for x in src_files) + "]"
        lines.append(
            f"        s.set_metadata( VerilogPlaceholderPass.v_flist, {flist_repr} )"
        )

    if params:
        lines.append("")
        lines.append("        # Detected parameters from module header")
        lines.append("        s.set_metadata( VerilogPlaceholderPass.params, {")
        for name, value in params:
            val = value if value else "None"
            lines.append(f'            "{name}": {repr(val)},')
        lines.append("        })")

    lines.append("")
    lines.append("")

    lines.append("def make_dut():")
    lines.append(f"    dut = {class_name}()")
    lines.append("    dut.elaborate()")
    lines.append("    dut.apply( VerilogPlaceholderPass() )")
    lines.append("    dut = VerilogTranslationImportPass()( dut )")
    lines.append("    dut.apply( DefaultPassGroup() )")
    lines.append("    dut.sim_reset()")
    lines.append("    return dut")
    lines.append("")

    lines.append("")
    lines.append("# Notes")
    lines.append("# -----")
    lines.append("# 1. For non-standard clock/reset port names, add port_map metadata manually.")
    lines.append("# 2. For interface arrays / structs / very advanced SystemVerilog, manual edits may be needed.")
    lines.append("# 3. Parameter values above are emitted as strings; adjust manually if needed.")

    return "\n".join(lines)

def generate_test_stub(module_name: str, wrapper_py: str, ports) -> str:
    wrapper_mod = os.path.splitext(os.path.basename(wrapper_py))[0]

    inputs = [p for p in ports if p["direction"] == "input" and not p["is_implicit_clock_reset"]]
    outputs = [p for p in ports if p["direction"] == "output" and not p["is_implicit_clock_reset"]]

    lines = []
    lines.append(f"from {wrapper_mod} import make_dut")
    lines.append("")
    lines.append("")
    lines.append("def test_smoke():")
    lines.append("    dut = make_dut()")
    lines.append("")

    if not inputs:
        lines.append("    dut.sim_tick()")
    else:
        for p in inputs:
            lines.append(f"    dut.{p['name']} @= 0")
        lines.append("    dut.sim_tick()")

    if outputs:
        lines.append("")
        lines.append("    # Inspect outputs")
        for p in outputs:
            lines.append(f"    print('{p['name']} =', int(dut.{p['name']}))")

    return "\n".join(lines)

# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Generate a PyMTL VerilogPlaceholder wrapper from Verilog.")
    ap.add_argument("verilog", nargs="+", help="Verilog source files")
    ap.add_argument("--top", help="Top module name")
    ap.add_argument("--out", help="Output wrapper .py file")
    ap.add_argument("--class-name", help="Override generated wrapper class name")
    ap.add_argument("--gen-test", action="store_true", help="Generate a pytest smoke test")
    args = ap.parse_args()

    abs_files = [os.path.abspath(v) for v in args.verilog]

    ast, _ = parse(abs_files)
    module = find_module(ast, args.top)

    module_name = module.name
    wrapper_name = args.out or f"{module_name}Wrapper.py"

    ports = extract_ports(module)
    params = extract_params(module)

    wrapper_code = generate_wrapper(
        module_name=module_name,
        src_files=abs_files,
        ports=ports,
        params=params,
        class_name=args.class_name,
    )

    with open(wrapper_name, "w", encoding="utf-8") as f:
        f.write(wrapper_code)

    print(f"[OK] Wrote wrapper: {wrapper_name}")

    print("\nDetected ports:")
    for p in ports:
        implicit = " (implicit clk/reset skipped)" if p["is_implicit_clock_reset"] else ""
        print(f"  - {p['direction']:>6} {p['name']:<24} {p['bits_type']}{implicit}")

    if args.gen_test:
        test_name = f"test_{module_name.lower()}.py"
        test_code = generate_test_stub(module_name, wrapper_name, ports)
        with open(test_name, "w", encoding="utf-8") as f:
            f.write(test_code)
        print(f"[OK] Wrote test stub: {test_name}")

if __name__ == "__main__":
    main()