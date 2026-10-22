"""Small, non-sensitive provenance helpers for pipeline and MLflow records."""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import sklearn


def directory_sha256(root: str | Path) -> str:
    """Hash filenames and contents in deterministic order."""

    path = Path(root)
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = file_path.relative_to(path).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def git_commit() -> str | None:
    """Return an explicitly available commit without logging credentials."""

    configured = os.getenv("GIT_COMMIT")
    if configured:
        return configured
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None


def build_provenance(data_dir: str | Path, feature_schema_version: str) -> dict[str, Any]:
    """Build provenance suitable for metrics and MLflow parameters."""

    return {
        "data_sha256": directory_sha256(data_dir),
        "feature_schema_version": feature_schema_version,
        "git_commit": git_commit(),
        "python_version": platform.python_version(),
        "scikit_learn_version": sklearn.__version__,
        "platform": sys.platform,
    }
