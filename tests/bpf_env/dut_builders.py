from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from contextlib import contextmanager
import re

from pymtl3 import DefaultPassGroup
from pymtl3.passes.backends.verilog import VerilogPlaceholderPass
from pymtl3.passes.backends.verilog.VerilogTranslationImportPass import VerilogTranslationImportPass
from pymtl3.passes.backends.verilog.import_.VerilogVerilatorImportPass import VerilogVerilatorImportPass
from pymtl3.passes.backends.verilog.import_.VerilogVerilatorImportConfigs import VerilogVerilatorImportConfigs
from pymtl3.passes.backends.verilog.translation.VerilogTranslationPass import VerilogTranslationPass

from pymtl.wrappers.bpf_env_wrapper import BpfEnv


REPO_ROOT = Path(__file__).resolve().parents[2]
VERILATOR_ROOT = REPO_ROOT / "verilator"
PUBLIC_ROOT = Path("C:/Users/Public")
REPO_ALIAS = PUBLIC_ROOT / "vp_repo"
VERILATOR_ALIAS = PUBLIC_ROOT / "vp_verilator"
MSYS2_UCRT_BIN = Path("C:/msys64/ucrt64/bin")
DLL_DIR_HANDLES = []
REPO_PATH_MARKERS = (
    "bpf_test",
    "pymtl",
    "verilator",
)
WAVEFORM_ENV_VAR = "BPF_WAVEFORM"


class PatchedVerilogImportPass(VerilogVerilatorImportPass):
    def traverse_hierarchy(self, m):
        c = self.__class__
        ph_pass = c.get_placeholder_pass()
        if m.has_metadata(ph_pass.enable) and m.get_metadata(ph_pass.enable):
            if not m.has_metadata(c.import_config):
                m.set_metadata(c.import_config, c.get_import_config()(m))
            return self.do_import(m)
        for child in m.get_child_components(repr):
            self.traverse_hierarchy(child)


def _ensure_junction(link: Path, target: Path) -> Path:
    if link.exists():
        return link
    link.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(["cmd", "/c", "mklink", "/J", str(link), str(target)])
    return link


def _ensure_verilator_cmd(verilator_root: Path) -> Path:
    release_dir = verilator_root / "build" / "src" / "Release"
    release_dir.mkdir(parents=True, exist_ok=True)
    exe_path = release_dir / "verilator.exe"
    bin_path = release_dir / "verilator_bin.exe"
    cmd_path = release_dir / "verilator.bat"

    if exe_path.exists():
        return release_dir

    if bin_path.exists() and not cmd_path.exists():
        cmd_path.write_text('@echo off\r\n"%~dp0verilator_bin.exe" %*\r\n', encoding="utf-8")
    return release_dir


def _rewrite_path(path_str: str) -> str:
    path_str = _normalize_repo_path(path_str)
    if os.name != "nt":
        return path_str.replace("\\", "/")
    repo_alias = _ensure_junction(REPO_ALIAS, REPO_ROOT)
    verilator_alias = _ensure_junction(VERILATOR_ALIAS, VERILATOR_ROOT)
    rewritten = path_str.replace(str(REPO_ROOT), str(repo_alias))
    rewritten = rewritten.replace(str(VERILATOR_ROOT), str(verilator_alias))
    return rewritten.replace("\\", "/")


def _normalize_repo_path(path_str: str) -> str:
    normalized = Path(path_str)
    if normalized.exists():
        return str(normalized)

    parts = normalized.parts
    for marker in REPO_PATH_MARKERS:
        if marker not in parts:
            continue
        marker_idx = parts.index(marker)
        candidate = REPO_ROOT.joinpath(*parts[marker_idx:])
        if candidate.exists():
            return str(candidate)
    return path_str


def _prepare_windows_verilator_env() -> None:
    repo_alias = _ensure_junction(REPO_ALIAS, REPO_ROOT)
    verilator_alias = _ensure_junction(VERILATOR_ALIAS, VERILATOR_ROOT)
    verilator_bin_dir = _ensure_verilator_cmd(verilator_alias)
    os.environ["VERILATOR_ROOT"] = str(verilator_alias)
    os.environ["PYMTL_VERILATOR_INCLUDE_DIR"] = str(verilator_alias / "include")
    extra_paths = [str(verilator_bin_dir)]
    if MSYS2_UCRT_BIN.exists():
        extra_paths.append(str(MSYS2_UCRT_BIN))
        if hasattr(os, "add_dll_directory"):
            DLL_DIR_HANDLES.append(os.add_dll_directory(str(MSYS2_UCRT_BIN)))
    os.environ["PATH"] = ";".join(extra_paths + [os.environ["PATH"]])
    os.chdir(repo_alias)


@contextmanager
def _build_cwd():
    prev_cwd = Path.cwd()
    try:
        if os.name == "nt":
            _prepare_windows_verilator_env()
        else:
            os.chdir(REPO_ROOT)
        yield
    finally:
        os.chdir(prev_cwd)


def verilator_available() -> bool:
    if os.name == "nt":
        _prepare_windows_verilator_env()
    return shutil.which("verilator") is not None


def waveform_enabled() -> bool:
    value = os.environ.get(WAVEFORM_ENV_VAR, "")
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def waveform_path_for_test(test_name: str) -> Path | None:
    if not waveform_enabled():
        return None
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", test_name).strip("._")
    if not safe_name:
        safe_name = "bpf_waveform"
    return REPO_ROOT / "reports" / f"{safe_name}"


def _cleanup_pymtl_artifacts() -> None:
    for pattern in ("BpfEnv*_pickled.v", "BpfEnv*_pickled.v.tmp", "obj_dir_BpfEnv*"):
        for path in Path(".").glob(pattern):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)


def _sanitize_translated_verilog(dut) -> None:
    candidates = sorted(Path(".").glob("BpfEnv*_pickled.v"))
    if not candidates:
        return
    path = candidates[0]
    text = path.read_text(encoding="utf-8")

    def fix_line_directive(match: re.Match[str]) -> str:
        line_no, file_name, level = match.groups()
        normalized = file_name.replace("\\", "/")
        return f'`line {line_no} "{normalized}" {level}'

    text = re.sub(r'`line\s+(\d+)\s+"([^"]+)"\s+(\d+)', fix_line_directive, text)
    path.write_text(text, encoding="utf-8")


def _set_translation_metadata(dut) -> None:
    candidates = sorted(Path(".").glob("BpfEnv*_pickled.v"))
    if not candidates:
        return
    path = candidates[0]
    text = path.read_text(encoding="utf-8")
    matches = re.findall(r"^module\s+([A-Za-z_]\w*)", text, flags=re.MULTILINE)
    top_module = matches[-1] if matches else path.stem
    dut.set_metadata(VerilogTranslationPass.translated_filename, str(path))
    dut.set_metadata(VerilogTranslationPass.translated_top_module, top_module)


def build_bpf_env(*, waveform: str | os.PathLike[str] | None = None):
    if not verilator_available():
        raise RuntimeError("verilator is required for VerilogTranslationImportPass")

    with _build_cwd():
        _cleanup_pymtl_artifacts()
        dut = BpfEnv()
        dut.elaborate()
        vti_pass = VerilogTranslationImportPass()
        vti_pass.traverse_hierarchy(dut)

        dut.set_metadata(VerilogPlaceholderPass.src_file, _rewrite_path(dut.get_metadata(VerilogPlaceholderPass.src_file)))
        dut.set_metadata(
            VerilogPlaceholderPass.v_libs,
            [_rewrite_path(path) for path in dut.get_metadata(VerilogPlaceholderPass.v_libs)],
        )
        dut.set_metadata(
            VerilogPlaceholderPass.v_include,
            [_rewrite_path(path) for path in dut.get_metadata(VerilogPlaceholderPass.v_include)],
        )

        dut.apply(VerilogPlaceholderPass())
        dut.apply(VerilogTranslationPass())
        _sanitize_translated_verilog(dut)
        _set_translation_metadata(dut)
        vti_pass.add_placeholder_marks(dut)
        import_cfg = VerilogVerilatorImportConfigs(dut)
        import_cfg.vl_W_fatal = False
        import_cfg.vl_Wno_list = sorted(set(import_cfg.vl_Wno_list + ["TIMESCALEMOD", "IMPLICIT", "CASEINCOMPLETE"]))
        if waveform is not None:
            waveform_path = Path(waveform)
            waveform_path.parent.mkdir(parents=True, exist_ok=True)
            import_cfg.vl_trace = True
            import_cfg.vl_trace_filename = str(waveform_path.with_suffix(""))
        if os.name == "nt":
            import_cfg.c_include_path = [str(VERILATOR_ALIAS / "build" / "include")]
        else:
            import_cfg.c_include_path = [str(VERILATOR_ROOT / "build" / "include")]
        dut.set_metadata(VerilogVerilatorImportPass.import_config, import_cfg)
        dut = PatchedVerilogImportPass()(dut)
        dut.apply(DefaultPassGroup())
        dut.sim_reset()
        return dut
