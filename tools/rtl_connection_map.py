#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple


VERILOG_EXTENSIONS = {".v", ".sv"}

# Very lightweight parsing:
# - Removes comments
# - Finds module blocks
# - Finds instantiations of known modules
# - Extracts named port connections
#
# This is intentionally pragmatic, not a full Verilog parser.


def strip_comments(text: str) -> str:
    # Remove /* ... */ comments first
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # Remove // comments
    text = re.sub(r"//.*", "", text)
    return text


def find_verilog_files(root: Path) -> List[Path]:
    files = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in VERILOG_EXTENSIONS:
            files.append(path)
    return sorted(files)


def extract_module_blocks(text: str) -> List[Tuple[str, str]]:
    """
    Return list of (module_name, module_body_plus_header_text)
    """
    blocks = []
    pattern = re.compile(
        r"\bmodule\s+([A-Za-z_]\w*)\b(.*?)(?=\bendmodule\b)",
        flags=re.DOTALL,
    )
    for m in pattern.finditer(text):
        module_name = m.group(1)
        block_text = m.group(0)
        blocks.append((module_name, block_text))
    return blocks


def collect_module_definitions(files: List[Path]) -> Dict[str, Dict]:
    modules: Dict[str, Dict] = {}

    for path in files:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text = strip_comments(raw)

        for module_name, block_text in extract_module_blocks(text):
            modules[module_name] = {
                "name": module_name,
                "file": str(path),
                "text": block_text,
                "instances": [],
            }

    return modules


def extract_named_port_connections(conn_blob: str) -> List[Dict[str, str]]:
    """
    Extract .port(signal) pairs
    """
    pairs = []
    pattern = re.compile(r"\.(\w+)\s*\(\s*([^)]+?)\s*\)", flags=re.DOTALL)
    for m in pattern.finditer(conn_blob):
        port = m.group(1).strip()
        signal = " ".join(m.group(2).split())
        pairs.append({"port": port, "signal": signal})
    return pairs


def extract_instantiations_from_module(module_text: str, known_modules: Set[str]) -> List[Dict]:
    """
    Looks for patterns like:
      child_mod u_child ( .a(sig), .b(sig2) );
      child_mod #(.W(8)) u_child ( .a(sig), .b(sig2) );

    Only detects instantiations where child_mod is in known_modules.
    """
    instances = []

    # Match:
    # <modname> [#(...)] <instname> ( ... );
    pattern = re.compile(
        r"""
        \b(?P<mod>[A-Za-z_]\w*)\b
        \s*
        (?:\#\s*\((?P<params>.*?)\)\s*)?
        (?P<inst>[A-Za-z_]\w*)
        \s*
        \(
            (?P<ports>.*?)
        \)
        \s*;
        """,
        flags=re.DOTALL | re.VERBOSE,
    )

    for m in pattern.finditer(module_text):
        mod_name = m.group("mod")
        inst_name = m.group("inst")
        ports_blob = m.group("ports")

        if mod_name not in known_modules:
            continue

        # Avoid matching the module declaration itself in weird cases
        if inst_name == "module":
            continue

        port_connections = extract_named_port_connections(ports_blob)

        instances.append(
            {
                "module_type": mod_name,
                "instance_name": inst_name,
                "connections": port_connections,
            }
        )

    return instances


def populate_instantiations(modules: Dict[str, Dict]) -> None:
    known = set(modules.keys())
    for mod in modules.values():
        mod["instances"] = extract_instantiations_from_module(mod["text"], known)


def find_top_modules(modules: Dict[str, Dict]) -> List[str]:
    instantiated = set()
    all_modules = set(modules.keys())

    for mod in modules.values():
        for inst in mod["instances"]:
            instantiated.add(inst["module_type"])

    tops = sorted(all_modules - instantiated)
    return tops


def build_edges(modules: Dict[str, Dict]) -> List[Dict]:
    edges = []
    for parent_name, mod in modules.items():
        for inst in mod["instances"]:
            edges.append(
                {
                    "parent": parent_name,
                    "child": inst["module_type"],
                    "instance": inst["instance_name"],
                    "connections": inst["connections"],
                }
            )
    return edges


def build_signal_usage(modules: Dict[str, Dict]) -> Dict[str, List[Dict]]:
    """
    Aggregate signals by module->instance->port mapping to help understand fanout.
    """
    signal_map: Dict[str, List[Dict]] = {}

    for parent_name, mod in modules.items():
        for inst in mod["instances"]:
            for conn in inst["connections"]:
                sig = conn["signal"]
                signal_map.setdefault(sig, []).append(
                    {
                        "parent_module": parent_name,
                        "child_module": inst["module_type"],
                        "instance_name": inst["instance_name"],
                        "port": conn["port"],
                    }
                )

    return dict(sorted(signal_map.items(), key=lambda x: x[0]))


def generate_text_report(modules: Dict[str, Dict], out_path: Path) -> None:
    tops = find_top_modules(modules)
    edges = build_edges(modules)
    signal_map = build_signal_usage(modules)

    lines = []
    lines.append("RTL CONNECTION REPORT")
    lines.append("=" * 80)
    lines.append("")

    lines.append("TOP MODULE CANDIDATES")
    lines.append("-" * 80)
    if tops:
        for t in tops:
            lines.append(f"- {t}")
    else:
        lines.append("No obvious top module found.")
    lines.append("")

    lines.append("MODULES")
    lines.append("-" * 80)
    for mod_name in sorted(modules.keys()):
        mod = modules[mod_name]
        rel_file = mod["file"]
        lines.append(f"{mod_name}")
        lines.append(f"  file: {rel_file}")
        if mod["instances"]:
            lines.append(f"  instantiates: {len(mod['instances'])}")
            for inst in mod["instances"]:
                lines.append(
                    f"    - {inst['instance_name']}: {inst['module_type']}"
                )
        else:
            lines.append("  instantiates: 0")
        lines.append("")

    lines.append("PARENT -> CHILD CONNECTIONS")
    lines.append("-" * 80)
    if not edges:
        lines.append("No child module instantiations found.")
    else:
        for edge in edges:
            lines.append(
                f"{edge['parent']} --> {edge['child']}  "
                f"(instance: {edge['instance']})"
            )
            if edge["connections"]:
                for conn in edge["connections"]:
                    lines.append(f"    .{conn['port']}({conn['signal']})")
            else:
                lines.append("    [No named connections parsed]")
            lines.append("")

    lines.append("SIGNAL USAGE SUMMARY")
    lines.append("-" * 80)
    if not signal_map:
        lines.append("No named signal connections parsed.")
    else:
        for signal, uses in signal_map.items():
            lines.append(signal)
            for u in uses:
                lines.append(
                    f"  - {u['parent_module']} -> "
                    f"{u['child_module']}:{u['instance_name']} .{u['port']}"
                )
            lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def generate_mermaid(modules: Dict[str, Dict], out_path: Path) -> None:
    tops = find_top_modules(modules)
    edges = build_edges(modules)

    lines = []
    lines.append("# RTL Module Connection Diagram")
    lines.append("")
    if tops:
        lines.append("**Top module candidates:** " + ", ".join(f"`{t}`" for t in tops))
        lines.append("")

    lines.append("```mermaid")
    lines.append("flowchart TD")

    # Declare nodes
    for mod_name in sorted(modules.keys()):
        safe = mod_name.replace("-", "_")
        lines.append(f'    {safe}["{mod_name}"]')

    # Declare edges
    for edge in edges:
        parent = edge["parent"].replace("-", "_")
        child = edge["child"].replace("-", "_")
        label = edge["instance"]
        lines.append(f'    {parent} -->|"{label}"| {child}')

    lines.append("```")
    lines.append("")
    lines.append("## Instance Connection Details")
    lines.append("")

    for edge in edges:
        lines.append(
            f"### {edge['parent']} -> {edge['child']} "
            f"(instance `{edge['instance']}`)"
        )
        lines.append("")
        if edge["connections"]:
            lines.append("| Child Port | Connected Signal |")
            lines.append("|---|---|")
            for conn in edge["connections"]:
                port = conn["port"].replace("|", "\\|")
                sig = conn["signal"].replace("|", "\\|")
                lines.append(f"| `{port}` | `{sig}` |")
        else:
            lines.append("_No named port connections parsed._")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def generate_json(modules: Dict[str, Dict], out_path: Path) -> None:
    tops = find_top_modules(modules)
    edges = build_edges(modules)
    signal_map = build_signal_usage(modules)

    payload = {
        "top_modules": tops,
        "modules": {
            name: {
                "file": data["file"],
                "instances": data["instances"],
            }
            for name, data in sorted(modules.items())
        },
        "edges": edges,
        "signal_usage": signal_map,
    }

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan RTL directory and generate module connection reports."
    )
    parser.add_argument(
        "rtl_dir",
        help="Root directory containing Verilog/SystemVerilog files",
    )
    parser.add_argument(
        "--outdir",
        default="reports",
        help="Output directory for generated reports",
    )
    args = parser.parse_args()

    rtl_dir = Path(args.rtl_dir).resolve()
    outdir = Path(args.outdir).resolve()

    if not rtl_dir.exists() or not rtl_dir.is_dir():
        raise SystemExit(f"Not a directory: {rtl_dir}")

    outdir.mkdir(parents=True, exist_ok=True)

    files = find_verilog_files(rtl_dir)
    if not files:
        raise SystemExit(f"No .v or .sv files found under: {rtl_dir}")

    modules = collect_module_definitions(files)
    populate_instantiations(modules)

    txt_out = outdir / "rtl_connections_report.txt"
    md_out = outdir / "rtl_connections_mermaid.md"
    json_out = outdir / "rtl_connections.json"

    generate_text_report(modules, txt_out)
    generate_mermaid(modules, md_out)
    generate_json(modules, json_out)

    print(f"[OK] Scanned RTL directory: {rtl_dir}")
    print(f"[OK] Found {len(files)} source files")
    print(f"[OK] Found {len(modules)} modules")
    print(f"[OK] Wrote: {txt_out}")
    print(f"[OK] Wrote: {md_out}")
    print(f"[OK] Wrote: {json_out}")


if __name__ == "__main__":
    main()