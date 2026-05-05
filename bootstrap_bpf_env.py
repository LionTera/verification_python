#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from textwrap import dedent

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools.verilog_parser import (  # noqa: E402
    build_module_db,
    camel_case,
    find_verilog_files,
    IMPLICIT_PYMTL_PORTS,
    width_to_bits_name,
)

ROLE_RULES = {
    "top": ["top", "npu", "core", "engine"],
    "control": ["control", "ctrl", "fsm", "state", "pc", "instr", "sequencer"],
    "datapath": ["dp", "datapath", "acc", "alu", "execute"],
    "memory": ["iram", "pram", "sram", "mem", "ram", "rom", "fifo", "buffer", "table"],
    "alu_helper": ["div", "mult", "shift", "alu"],
    "packet": ["pkt", "packet", "hdr", "header", "parse", "parser", "tcp", "udp", "ip", "eth"],
    "env": ["env", "utils", "package"],
    "lcd": ["lcd"],
}

BPF_NAME_HINTS = {
    "control": ["bpf_control"],
    "datapath": ["bpf_dp"],
    "instruction_memory": ["bpf_iram"],
    "packet_memory": ["bpf_pram"],
    "scratch_memory": ["bpf_sram"],
    "alu_helpers": ["bpf_div", "bpf_mult", "bpf_shift"],
    "top_candidates": ["bpf_npu", "bpf_env"],
}

TOOL_GEN_WRAPPERS = dedent("""\
#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

COMMENT_SL_RE = re.compile(r"//.*?$", re.M)
COMMENT_ML_RE = re.compile(r"/\\*.*?\\*/", re.S)
MODULE_BLOCK_RE = re.compile(r"\\bmodule\\s+([A-Za-z_][A-Za-z0-9_$]*)\\b(.*?)\\bendmodule\\b", re.S)
HEADER_RE = re.compile(r"\\bmodule\\s+([A-Za-z_][A-Za-z0-9_$]*)\\s*(?:#\\s*\\(.*?\\))?\\s*\\((.*?)\\)\\s*;", re.S)
PORT_RE = re.compile(
    r"^\\s*(input|output|inout)\\s+"
    r"(?:(?:wire|reg|logic|signed)\\s+)*"
    r"(?:\\[\\s*([^:\\]]+)\\s*:\\s*([^\\]]+)\\s*\\]\\s+)?"
    r"([A-Za-z_][A-Za-z0-9_$]*)\\s*$"
)
PARAM_RE = re.compile(r"\\bmodule\\s+([A-Za-z_][A-Za-z0-9_$]*)\\s*#\\s*\\((.*?)\\)\\s*\\(", re.S)
PARAM_ITEM_RE = re.compile(r"parameter\\s+([A-Za-z_][A-Za-z0-9_$]*)\\s*=\\s*([^,\\n)]+)")
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
    mm = re.match(r"(\\d+)\\s*:\\s*(\\d+)", width_expr)
    if mm:
        a = int(mm.group(1)); b = int(mm.group(2))
        w = abs(a - b) + 1
        return f"Bits{w}", w
    mm = re.match(r"([A-Za-z_][A-Za-z0-9_$]*)\\s*-\\s*1\\s*:\\s*0", width_expr)
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
    if re.fullmatch(r"\\d+", pval):
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
        libs_lines = "\\n".join([f'                join( base, "{p}" ),' for p in vlibs_rel])
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

    body = "\\n".join(port_lines) if port_lines else "        pass"
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
""")

TOOL_ANALYZE = dedent("""\
#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

COMMENT_SL_RE = re.compile(r"//.*?$", re.M)
COMMENT_ML_RE = re.compile(r"/\\*.*?\\*/", re.S)
MODULE_RE = re.compile(r"\\bmodule\\s+([A-Za-z_][A-Za-z0-9_$]*)\\b", re.S)

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
""")

TOOL_FLOW = dedent("""\
#!/usr/bin/env python3
import argparse
import re
from collections import defaultdict
from pathlib import Path

COMMENT_SL_RE = re.compile(r"//.*?$", re.M)
COMMENT_ML_RE = re.compile(r"/\\*.*?\\*/", re.S)
MODULE_BLOCK_RE = re.compile(r"\\bmodule\\s+([A-Za-z_][A-Za-z0-9_$]*)\\b(.*?)\\bendmodule\\b", re.S)
INSTANTIATION_RE = re.compile(r"\\b([A-Za-z_][A-Za-z0-9_$]*)\\s*(?:#\\s*\\(.*?\\))?\\s+([A-Za-z_][A-Za-z0-9_$]*)\\s*\\(", re.S)

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
    out.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    print(f"[OK] wrote: {out}")

if __name__ == "__main__":
    main()
""")

TOOL_BUILD_IMPL = dedent("""\
#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtl", required=True)
    ap.add_argument("--outdir", default="reports/bpf_impl")
    args = ap.parse_args()

    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "bpf_implementation.json").write_text(json.dumps({"status": "generated"}, indent=2), encoding="utf-8")
    (outdir / "bpf_implementation.md").write_text("# BPF Implementation\\n\\nGenerated inventory.\\n", encoding="utf-8")
    (outdir / "bpf_implementation.mmd").write_text("flowchart TD\\n", encoding="utf-8")
    print(f"[OK] wrote: {outdir}")

if __name__ == "__main__":
    main()
""")

TOOL_GEN_TESTS = dedent("""\
#!/usr/bin/env python3
import argparse
from pathlib import Path

HELPERS = '''from pymtl3 import *
from pymtl3.passes.backends.verilog import VerilogPlaceholderPass, VerilogTranslationImportPass
from pymtl3.passes.PassGroups import DefaultPassGroup
from pymtl.wrappers.bpf_control_wrapper import BpfControl

def mk_dut():
    dut = BpfControl()
    dut.elaborate()
    dut.apply( VerilogPlaceholderPass() )
    dut = VerilogTranslationImportPass()( dut )
    dut.apply( DefaultPassGroup() )
    dut.sim_reset()
    return dut
'''

SMOKE = '''from tests.bpf_env.bpf_control_test_helpers import mk_dut

def test_bpf_control_smoke():
    dut = mk_dut()
    assert int(dut.bpf_active) in (0, 1)
'''

def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="tests")
    args = ap.parse_args()

    root = Path(args.outdir).resolve()
    write(root / "__init__.py", "")
    write(root / "bpf_env" / "__init__.py", "")
    write(root / "bpf_env" / "bpf_control_test_helpers.py", HELPERS)
    write(root / "unit" / "test_bpf_control_smoke.py", SMOKE)
    print(f"[OK] test scaffold under: {root}")

if __name__ == "__main__":
    main()
""")


def build_parent_map(db):
    parents = defaultdict(list)
    for mod, info in db.items():
        for child, inst in info["children"]:
            parents[child].append((mod, inst))
    return parents


def classify_role(mod_name: str, info: dict) -> str:
    text = " ".join([
        mod_name.lower(),
        info["file"].name.lower(),
        " ".join(p["name"].lower() for p in info["ports"]),
        " ".join(child.lower() for child, _ in info["children"]),
    ])

    best_role = "unknown"
    best_score = 0
    for role, terms in ROLE_RULES.items():
        score = sum(1 for t in terms if t in text)
        if score > best_score:
            best_score = score
            best_role = role

    return best_role


def score_top_candidate(mod_name: str, info: dict, parents: dict) -> int:
    score = 0
    name_l = mod_name.lower()
    file_l = info["file"].as_posix().lower()

    if mod_name not in parents:
        score += 50

    score += len(info["children"]) * 6
    score += len(info["ports"])
    score += len(info["params"]) * 2

    if "top" in name_l:
        score += 20
    if "core" in name_l:
        score += 12
    if "npu" in name_l:
        score += 20
    if "env" in name_l:
        score += 8
    if "control" in name_l:
        score += 10
    if "lcd" in name_l:
        score -= 50

    if "/top/" in file_l:
        score += 20
    if "/core/" in file_l:
        score += 10
    if "lcd" in file_l:
        score -= 50

    return score


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
        for f in all_rtl_files
        if f.resolve() != info["file"].resolve()
    ]

    libs_block = ""
    if vlibs_rel:
        libs_lines = "\n".join([f'                join( base, "{p}" ),' for p in vlibs_rel])
        libs_block = f"""
        s.set_metadata(
            VerilogPlaceholderPass.v_libs,
            [
{libs_lines}
            ]
        )
"""

    params_block = ""
    if param_meta:
        params_block = f"""
        s.set_metadata(
            VerilogPlaceholderPass.params,
            {{
{chr(10).join(param_meta)}
            }}
        )
"""

    body = "\n".join(port_lines) if port_lines else "        pass"
    return dedent(f"""\
    from os.path import dirname, join, abspath
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
    """)


def write_text(path: Path, content: str, executable: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | 0o111)


def safe_rmtree(path: Path):
    if path.exists():
        shutil.rmtree(path)


def generate_wrapper_index(repo_root: Path, db: dict, wrappers_dir: Path, reports_dir: Path):
    parents = build_parent_map(db)
    rows = []
    payload = []

    for mod_name, info in sorted(db.items()):
        role = classify_role(mod_name, info)
        top_score = score_top_candidate(mod_name, info, parents)
        wrapper_rel = wrappers_dir.joinpath(f"{mod_name}_wrapper.py").resolve().relative_to(repo_root.resolve()).as_posix()
        file_rel = info["file"].resolve().relative_to(repo_root.resolve()).as_posix()

        row = {
            "module": mod_name,
            "file": file_rel,
            "wrapper": wrapper_rel,
            "ports": len(info["ports"]),
            "params": len(info["params"]),
            "children": len(info["children"]),
            "role": role,
            "top_score": top_score,
        }
        rows.append(row)
        payload.append(row)

    md_lines = [
        "# Wrapper Index",
        "",
        "| Module | File | Wrapper | Ports | Params | Children | Role | Top Score |",
        "|---|---|---|---:|---:|---:|---|---:|",
    ]
    for r in rows:
        md_lines.append(
            f"| `{r['module']}` | `{r['file']}` | `{r['wrapper']}` | "
            f"{r['ports']} | {r['params']} | {r['children']} | {r['role']} | {r['top_score']} |"
        )

    write_text(reports_dir / "wrappers_index.md", "\n".join(md_lines) + "\n")
    write_text(reports_dir / "wrappers_index.json", json.dumps(payload, indent=2))


def choose_architecture_modules(db: dict):
    names = set(db.keys())

    def first_existing(candidates):
        for c in candidates:
            if c in names:
                return c
        return None

    parents = build_parent_map(db)
    ranked = sorted(
        [(m, score_top_candidate(m, info, parents)) for m, info in db.items()],
        key=lambda x: (-x[1], x[0])
    )

    chosen = {
        "top": first_existing(BPF_NAME_HINTS["top_candidates"]) or (ranked[0][0] if ranked else None),
        "control": first_existing(BPF_NAME_HINTS["control"]),
        "datapath": first_existing(BPF_NAME_HINTS["datapath"]),
        "instruction_memory": first_existing(BPF_NAME_HINTS["instruction_memory"]),
        "packet_memory": first_existing(BPF_NAME_HINTS["packet_memory"]),
        "scratch_memory": first_existing(BPF_NAME_HINTS["scratch_memory"]),
        "alu_helpers": [m for m in BPF_NAME_HINTS["alu_helpers"] if m in names],
    }

    if not chosen["control"]:
        for mod, info in db.items():
            if classify_role(mod, info) == "control":
                chosen["control"] = mod
                break

    if not chosen["datapath"]:
        for mod, info in db.items():
            if classify_role(mod, info) == "datapath":
                chosen["datapath"] = mod
                break

    return chosen, ranked


def generate_architecture_reports(repo_root: Path, db: dict, reports_dir: Path):
    chosen, ranked = choose_architecture_modules(db)

    md = [
        "# Suggested BPF Architecture",
        "",
        "## Suggested Full Implementation",
        "",
        f"- Top candidate: **{chosen['top']}**",
        f"- Control: **{chosen['control']}**",
        f"- Datapath: **{chosen['datapath']}**",
        f"- Instruction memory: **{chosen['instruction_memory']}**",
        f"- Packet memory: **{chosen['packet_memory']}**",
        f"- Scratch memory: **{chosen['scratch_memory']}**",
        f"- ALU helpers: **{', '.join(chosen['alu_helpers']) if chosen['alu_helpers'] else 'None detected'}**",
        "",
        "## Suggested Connection Model",
        "",
    ]

    if chosen["control"] and chosen["instruction_memory"]:
        md.append(f"- `{chosen['control']}` fetches instructions from `{chosen['instruction_memory']}`")
    if chosen["control"] and chosen["datapath"]:
        md.append(f"- `{chosen['control']}` drives control signals into `{chosen['datapath']}`")
    if chosen["datapath"] and chosen["packet_memory"]:
        md.append(f"- `{chosen['datapath']}` reads packet-related data from `{chosen['packet_memory']}`")
    if chosen["datapath"] and chosen["scratch_memory"]:
        md.append(f"- `{chosen['datapath']}` writes or reads scratch/state via `{chosen['scratch_memory']}`")
    if chosen["alu_helpers"] and chosen["datapath"]:
        md.append(f"- `{chosen['datapath']}` likely uses ALU helpers: `{', '.join(chosen['alu_helpers'])}`")

    md.extend([
        "",
        "## Verification Progression",
        "",
        "1. Verify control-only behavior on the control module.",
        "2. Verify datapath-only behavior on the datapath module.",
        "3. Verify control + datapath together.",
        "4. Verify packet memory + scratch/SRAM path.",
        "5. Verify full top-level integration.",
        "",
        "## Top Candidates Ranking",
        "",
    ])

    for mod, score in ranked[:10]:
        md.append(f"- `{mod}` (score={score})")

    write_text(reports_dir / "suggested_bpf_architecture.md", "\n".join(md) + "\n")

    top = chosen["top"] or "TOP"
    ctrl = chosen["control"] or "CONTROL"
    dp = chosen["datapath"] or "DATAPATH"
    iram = chosen["instruction_memory"] or "IRAM"
    pram = chosen["packet_memory"] or "PRAM"
    sram = chosen["scratch_memory"] or "SRAM"
    alu_helpers = chosen["alu_helpers"]

    mmd = ["flowchart TD"]
    mmd.append(f'    TOP["{top}"]')
    if chosen["control"]:
        mmd.append(f'    CTRL["{ctrl}"]')
        mmd.append("    TOP --> CTRL")
    if chosen["datapath"]:
        mmd.append(f'    DP["{dp}"]')
        mmd.append("    TOP --> DP")
    if chosen["instruction_memory"] and chosen["control"]:
        mmd.append(f'    IRAM["{iram}"]')
        mmd.append("    CTRL --> IRAM")
    if chosen["control"] and chosen["datapath"]:
        mmd.append("    CTRL --> DP")
    if chosen["packet_memory"] and chosen["datapath"]:
        mmd.append(f'    PRAM["{pram}"]')
        mmd.append("    DP --> PRAM")
    if chosen["scratch_memory"] and chosen["datapath"]:
        mmd.append(f'    SRAM["{sram}"]')
        mmd.append("    DP --> SRAM")
    for h in alu_helpers:
        node = h.upper()
        mmd.append(f'    {node}["{h}"]')
        mmd.append(f"    DP --> {node}")

    write_text(reports_dir / "suggested_bpf_architecture.mmd", "\n".join(mmd) + "\n")


def recreate_environment(repo_root: Path, rtl_dir: Path):
    target_wrappers = repo_root / "pymtl" / "wrappers"
    target_tools = repo_root / "tools"
    target_tb = repo_root / "tb"
    reports_dir = repo_root / "reports"

    # Preserve committed tool files before wiping the tools directory.
    _PRESERVED_TOOLS = ("verilog_parser.py", "gen_pymtl_wrapper.py")
    preserved = {}
    for fname in _PRESERVED_TOOLS:
        p = target_tools / fname
        if p.exists():
            preserved[fname] = p.read_text(encoding="utf-8")

    safe_rmtree(target_wrappers)
    safe_rmtree(target_tools)
    safe_rmtree(target_tb)

    (repo_root / "pymtl").mkdir(parents=True, exist_ok=True)
    write_text(repo_root / "pymtl" / "__init__.py", "")
    target_wrappers.mkdir(parents=True, exist_ok=True)
    write_text(target_wrappers / "__init__.py", "")

    target_tb.mkdir(parents=True, exist_ok=True)
    write_text(
        target_tb / "README.md",
        "# TB Area\n\nPut original Verilog/SystemVerilog testbench files here if needed.\n"
    )

    target_tools.mkdir(parents=True, exist_ok=True)
    for fname in _PRESERVED_TOOLS:
        if fname in preserved:
            write_text(target_tools / fname, preserved[fname], executable=(fname == "gen_pymtl_wrapper.py"))
    if "gen_pymtl_wrapper.py" not in preserved:
        write_text(target_tools / "gen_pymtl_wrapper.py", TOOL_GEN_WRAPPERS, executable=True)
    write_text(target_tools / "analyze_bpf_design.py", TOOL_ANALYZE, executable=True)
    write_text(target_tools / "bpf_flow_report.py", TOOL_FLOW, executable=True)
    write_text(target_tools / "build_bpf_implementation.py", TOOL_BUILD_IMPL, executable=True)
    write_text(target_tools / "gen_bpf_control_test_suite.py", TOOL_GEN_TESTS, executable=True)

    module_db = build_module_db(rtl_dir)
    all_rtl_files = find_verilog_files(rtl_dir)

    for mod_name, info in sorted(module_db.items()):
        wrapper_code = make_wrapper_code(repo_root, rtl_dir, mod_name, info, all_rtl_files)
        write_text(target_wrappers / f"{mod_name}_wrapper.py", wrapper_code)

    reports_dir.mkdir(parents=True, exist_ok=True)
    generate_wrapper_index(repo_root, module_db, target_wrappers, reports_dir)
    generate_architecture_reports(repo_root, module_db, reports_dir)

    print("[OK] recreated:")
    print(f"  - {target_wrappers}")
    print(f"  - {target_tools}")
    print(f"  - {target_tb}")
    print(f"[OK] generated {len(module_db)} wrappers from RTL")
    print("[OK] wrote reports:")
    print(f"  - {reports_dir / 'wrappers_index.md'}")
    print(f"  - {reports_dir / 'wrappers_index.json'}")
    print(f"  - {reports_dir / 'suggested_bpf_architecture.md'}")
    print(f"  - {reports_dir / 'suggested_bpf_architecture.mmd'}")


def main():
    ap = argparse.ArgumentParser(
        description="Recreate pymtl/wrappers, tools, and tb; generate wrappers index and BPF architecture suggestion."
    )
    ap.add_argument("--rtl", required=True, help="RTL directory")
    ap.add_argument("--repo-root", default=".", help="Repo root")
    ap.add_argument("--force", action="store_true", help="Actually wipe/recreate target folders")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    rtl_dir = Path(args.rtl).resolve()

    if not rtl_dir.exists():
        raise FileNotFoundError(f"RTL directory not found: {rtl_dir}")

    print("[INFO] This will recreate only:")
    print("  - pymtl/wrappers")
    print("  - tools")
    print("  - tb")
    print("[INFO] Other folders remain unchanged.")

    if not args.force:
        print("[DRY RUN] Re-run with --force to apply.")
        return

    recreate_environment(repo_root, rtl_dir)


if __name__ == "__main__":
    main()