from __future__ import annotations

import os
from pathlib import Path


RUN_ID_ENV_VAR = "BPF_RUN_ID"


def current_run_id() -> str:
    return os.environ.get(RUN_ID_ENV_VAR, "").strip()


def unique_artifact_path(path: str | Path) -> Path:
    artifact_path = Path(path)
    run_id = current_run_id()
    if not run_id:
        return artifact_path
    return artifact_path.with_name(f"{artifact_path.stem}__{run_id}{artifact_path.suffix}")


def unique_artifact_base(path: str | Path) -> Path:
    artifact_path = Path(path)
    run_id = current_run_id()
    if not run_id:
        return artifact_path
    return artifact_path.with_name(f"{artifact_path.name}__{run_id}")
