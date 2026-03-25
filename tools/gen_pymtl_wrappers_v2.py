#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


MODULE_RE = re.compile(
    r"module\s+"
    r"(?P<name>[A-Za-z_]\w*)"
    r"\s*"
    r"(?P<params>#\s*\((?P<param_body>.*?)\))?"
    r"\s*"
    r"\((?P<ports>.*?)\)\s*;"
    r"(?P<body>.*?)"
    r"endmodule",
    re.DOTALL | re.MULTILINE,
)

PARAM_RE = re.compile(
    r"^(?:parameter|localparam)\s+"
    r"(?:\w+\s+)?"
    r"(?P<name>[A-Za-z_]\w*)"
    r"\s*=\s*"
    r"(?P<expr>.+)$",
    re.DOTALL,
)

PORT_RE = re.compile(
    r"^(?P<direction>input|output|inout)\s+"
    r"(?P<rest>.+)$",
    re.DOTALL,
)

WIDTH_RE = re.compile(r"\[(?P<msb>.+?):(?P<lsb>.+?)\]")
VERILOG_LITERAL_RE = re.compile(r"(?P<size>\d+)?'(?P<signed>s)?(?P<base>[bodhBODH])(?P<value>[0-9a-fA-F_xXzZ?]+)")
IDENT_RE = re.compile(r"\b[A-Za-z_]\w*\b")

SKIP_PORTS = {"clk", "reset"}


@dataclass
class Port:
    name: str
    direction: str
    width: int


@dataclass
class ModuleDef:
    name: str
    source_file: Path
    parameters: dict[str, int]
    ports: list[Port]
    children: list[str]


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    return text


def split_top_level(text: str, delimiter: str = ",") -> list[str]:
    items: list[str] = []
    current: list[str] = []
    depth_paren = 0
    depth_brack = 0
    depth_brace = 0
    for ch in text:
        if ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        elif ch == "[":
            depth_brack += 1
        elif ch == "]":
            depth_brack -= 1
        elif ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1

        if ch == delimiter and depth_paren == 0 and depth_brack == 0 and depth_brace == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
        else:
            current.append(ch)

    tail = "".join(current).strip()
    if tail:
        items.append(tail)
    return items


def replace_verilog_literals(expr: str) -> str:
    def repl(match: re.Match[str]) -> str:
        base = match.group("base").lower()
        value = match.group("value").replace("_", "")
        cleaned = re.sub(r"[xXzZ?]", "0", value)
        radix = {"b": 2, "o": 8, "d": 10, "h": 16}[base]
        return str(int(cleaned, radix))

    return VERILOG_LITERAL_RE.sub(repl, expr)


def eval_verilog_expr(expr: str, env: dict[str, int]) -> int:
    expr = replace_verilog_literals(expr)
    expr = expr.replace("`", "")
    expr = expr.replace("$clog2", "clog2")
    expr = re.sub(r"\bclog2\s*\((.+)\)", r"(0)", expr)

    unresolved: set[str] = set()

    def repl_ident(match: re.Match[str]) -> str:
        name = match.group(0)
        if name in env:
            return str(env[name])
        if name in {"and", "or", "not"}:
            return name
        unresolved.add(name)
        return name

    expr = IDENT_RE.sub(repl_ident, expr)
    expr = expr.replace("&&", " and ")
    expr = expr.replace("||", " or ")
    expr = re.sub(r"(?<![<>=!])!(?!=)", " not ", expr)

    if unresolved:
        raise ValueError(f"unresolved identifiers in expression '{expr}': {sorted(unresolved)}")

    try:
        value = eval(expr, {"__builtins__": {}}, {})
    except Exception as exc:  # pragma: no cover - diagnostic path
        raise ValueError(f"failed to evaluate expression '{expr}'") from exc
    if isinstance(value, bool):
        return int(value)
    return int(value)


def parse_parameter_items(param_text: str, env: dict[str, int]) -> dict[str, int]:
    params: dict[str, int] = {}
    if not param_text.strip():
        return params

    for item in split_top_level(param_text):
        item = " ".join(item.split())
        match = PARAM_RE.match(item)
        if not match:
            continue
        name = match.group("name")
        expr = match.group("expr").strip()
        value = eval_verilog_expr(expr, {**env, **params})
        params[name] = value
    return params


def parse_package_parameters(files: Iterable[Path]) -> dict[str, int]:
    env: dict[str, int] = {}
    for file_path in sorted(files):
        text = strip_comments(file_path.read_text(encoding="utf-8"))
        package_bodies = re.findall(r"package\s+\w+\s*;(?P<body>.*?)endpackage", text, re.DOTALL | re.MULTILINE)
        for body in package_bodies:
            body_items = re.findall(r"(?:parameter|localparam)\b.*?;", body, re.DOTALL)
            joined = ",".join(item.rstrip(";") for item in body_items)
            env.update(parse_parameter_items(joined, env))
    return env


def parse_port(item: str, env: dict[str, int]) -> Port:
    item = " ".join(item.split())
    match = PORT_RE.match(item)
    if not match:
        raise ValueError(f"unsupported port declaration: {item}")

    direction = match.group("direction")
    rest = match.group("rest")
    rest = re.sub(r"\b(?:wire|reg|logic|signed|unsigned)\b", "", rest)
    rest = " ".join(rest.split())

    width = 1
    width_match = WIDTH_RE.search(rest)
    if width_match:
        msb = eval_verilog_expr(width_match.group("msb"), env)
        lsb = eval_verilog_expr(width_match.group("lsb"), env)
        width = abs(msb - lsb) + 1
        rest = WIDTH_RE.sub("", rest, count=1).strip()

    name = rest.split()[-1].strip()
    return Port(name=name, direction=direction, width=width)


def choose_module_source(existing: ModuleDef | None, candidate_file: Path) -> bool:
    if existing is None:
        return True
    existing_score = (existing.source_file.name.count("."), len(existing.source_file.name))
    candidate_score = (candidate_file.name.count("."), len(candidate_file.name))
    return candidate_score < existing_score


def find_children(body: str, known_modules: Iterable[str]) -> list[str]:
    children: list[str] = []
    for module_name in known_modules:
        pattern = re.compile(
            rf"\b{re.escape(module_name)}\b\s*(?:#\s*\(.*?\)\s*)?[A-Za-z_]\w*\s*\(",
            re.DOTALL,
        )
        children.extend([module_name] * len(pattern.findall(body)))
    return children


def camel_case(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def guess_role(module: ModuleDef, all_module_names: set[str]) -> str:
    name = module.name.lower()
    port_names = {port.name.lower() for port in module.ports}
    if name == "bpf_env" or (module.children and "env" in name):
        return "top"
    if "ram" in name or {"rd_addr", "wr_addr", "rd_data", "wr_data"} & port_names:
        return "memory"
    if "control" in name or "ctrl" in name:
        return "control"
    if module.children and module.name in all_module_names:
        return "top"
    return "datapath"


def top_score(module: ModuleDef) -> int:
    score = len(module.children) * 10 + len(module.ports)
    if module.name.endswith("_env"):
        score += 100
    if "top" in module.name:
        score += 50
    return score


def render_wrapper(module: ModuleDef, repo_root: Path, rtl_root: Path, module_source_files: list[Path], support_files: list[Path]) -> str:
    class_name = camel_case(module.name)
    widths = sorted({port.width for port in module.ports if port.name not in SKIP_PORTS})
    bit_aliases = [f"Bits{width} = mk_bits({width})" for width in widths]

    port_lines: list[str] = []
    for port in module.ports:
        if port.name in SKIP_PORTS:
            continue
        port_type = {"input": "InPort", "output": "OutPort", "inout": "InPort"}[port.direction]
        port_lines.append(f"        s.{port.name} = {port_type}( Bits{port.width} )")

    param_lines = [f'            "{name}": {value},' for name, value in module.parameters.items()]
    rel_src = module.source_file.relative_to(repo_root).as_posix()
    lib_files = [path for path in support_files + module_source_files if path != module.source_file]
    lib_lines = [f'            join( base, "{path.relative_to(repo_root).as_posix()}" ),' for path in lib_files]
    include_rel = rtl_root.relative_to(repo_root).as_posix()

    lines = [
        "from os.path import dirname, join, abspath",
        "from pymtl3 import *",
        "from pymtl3.passes.backends.verilog import VerilogPlaceholder, VerilogPlaceholderPass",
        "",
    ]
    lines.extend(bit_aliases)
    lines.extend(
        [
            "",
            f"class {class_name}( Component, VerilogPlaceholder ):",
            "    def construct( s ):",
        ]
    )
    lines.extend(port_lines or ["        pass"])
    lines.extend(
        [
            "",
            '        base = abspath( join( dirname(__file__), "..", ".." ) )',
            "",
            "        s.set_metadata(",
            "            VerilogPlaceholderPass.src_file,",
            f'            join( base, "{rel_src}" ),',
            "        )",
            "        s.set_metadata(",
            "            VerilogPlaceholderPass.top_module,",
            f'            "{module.name}",',
            "        )",
            "        s.set_metadata(",
            "            VerilogPlaceholderPass.params,",
            "            {",
        ]
    )
    lines.extend(param_lines)
    lines.extend(
        [
            "            },",
            "        )",
            "        s.set_metadata(",
            "            VerilogPlaceholderPass.v_libs,",
            "            [",
        ]
    )
    lines.extend(lib_lines)
    lines.extend(
        [
            "            ],",
            "        )",
            "        s.set_metadata(",
            "            VerilogPlaceholderPass.v_include,",
            "            [",
            f'                join( base, "{include_rel}" ),',
            "            ],",
            "        )",
            "",
        ]
    )
    return "\n".join(lines)


def render_index_md(index_rows: list[dict[str, object]]) -> str:
    header = [
        "# PyMTL Wrapper Index",
        "",
        "| Rank | Module | Source | Wrapper | Ports | Params | Children | Role | Score |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: |",
    ]
    body = [
        "| {rank} | {module_name} | `{source_file}` | `{wrapper_path}` | {num_ports} | {num_params} | {num_children} | {role} | {top_score} |".format(
            **row
        )
        for row in index_rows
    ]
    return "\n".join(header + body + [""])


def collect_modules(rtl_files: list[Path], package_env: dict[str, int]) -> dict[str, ModuleDef]:
    modules: dict[str, ModuleDef] = {}
    parsed_blocks: list[tuple[Path, re.Match[str]]] = []

    for rtl_file in rtl_files:
        text = strip_comments(rtl_file.read_text(encoding="utf-8"))
        for match in MODULE_RE.finditer(text):
            parsed_blocks.append((rtl_file, match))

    module_names = {match.group("name") for _, match in parsed_blocks}

    for rtl_file, match in parsed_blocks:
        module_name = match.group("name")
        param_text = match.group("param_body") or ""
        port_text = match.group("ports")
        body = match.group("body")
        env = dict(package_env)
        params = parse_parameter_items(param_text, env)
        env.update(params)
        ports = [parse_port(item, env) for item in split_top_level(port_text)]
        children = find_children(body, module_names - {module_name})

        candidate = ModuleDef(
            name=module_name,
            source_file=rtl_file,
            parameters=params,
            ports=ports,
            children=children,
        )

        if choose_module_source(modules.get(module_name), rtl_file):
            modules[module_name] = candidate

    return modules


def write_wrapper_package_init(wrappers_dir: Path, modules: list[ModuleDef]) -> None:
    lines = []
    for module in modules:
        lines.append(f"from .{module.name}_wrapper import {camel_case(module.name)}")
    lines.append("")
    wrappers_dir.joinpath("__init__.py").write_text("\n".join(lines), encoding="utf-8")


def generate(rtl_root: Path, wrappers_dir: Path, reports_dir: Path) -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[1]
    rtl_files = sorted(path for path in rtl_root.rglob("*") if path.suffix.lower() in {".v", ".sv"})
    if not rtl_files:
        raise SystemExit(f"no RTL files found under {rtl_root}")

    package_env = parse_package_parameters(rtl_files)
    modules = collect_modules(rtl_files, package_env)
    ordered_modules = sorted(modules.values(), key=lambda item: item.name)
    module_source_files = sorted({item.source_file for item in ordered_modules})
    support_files = sorted(path for path in rtl_files if path.suffix.lower() == ".sv" and path not in module_source_files)

    wrappers_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    for module in ordered_modules:
        wrapper_text = render_wrapper(
            module,
            repo_root,
            rtl_root,
            module_source_files,
            support_files,
        )
        wrapper_path = wrappers_dir / f"{module.name}_wrapper.py"
        wrapper_path.write_text(wrapper_text, encoding="utf-8")

    write_wrapper_package_init(wrappers_dir, ordered_modules)

    module_name_set = set(modules)
    index_rows: list[dict[str, object]] = []
    ranked_modules = sorted(ordered_modules, key=lambda item: (-top_score(item), item.name))
    for rank, module in enumerate(ranked_modules, start=1):
        index_rows.append(
            {
                "rank": rank,
                "module_name": module.name,
                "source_file": module.source_file.relative_to(repo_root).as_posix(),
                "wrapper_path": wrappers_dir.joinpath(f"{module.name}_wrapper.py").relative_to(repo_root).as_posix(),
                "num_ports": len([port for port in module.ports if port.name not in SKIP_PORTS]),
                "num_params": len(module.parameters),
                "num_children": len(module.children),
                "children": module.children,
                "role": guess_role(module, module_name_set),
                "top_score": top_score(module),
            }
        )

    reports_dir.joinpath("wrappers_index.json").write_text(json.dumps(index_rows, indent=2), encoding="utf-8")
    reports_dir.joinpath("wrappers_index.md").write_text(render_index_md(index_rows), encoding="utf-8")

    return {
        "rtl_root": str(rtl_root),
        "modules": len(ordered_modules),
        "wrappers_dir": str(wrappers_dir),
        "reports_dir": str(reports_dir),
    }


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Generate PyMTL3 VerilogPlaceholder wrappers from RTL.")
    parser.add_argument(
        "rtl_dir",
        nargs="?",
        default=str(repo_root / "bpf_test" / "u2u_v401" / "tf_bpf" / "rtl"),
        help="RTL directory to scan recursively",
    )
    parser.add_argument(
        "--wrappers-dir",
        default=str(repo_root / "pymtl" / "wrappers"),
        help="Output directory for generated wrappers",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(repo_root / "reports"),
        help="Output directory for generated reports",
    )
    args = parser.parse_args()

    result = generate(Path(args.rtl_dir).resolve(), Path(args.wrappers_dir).resolve(), Path(args.reports_dir).resolve())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
