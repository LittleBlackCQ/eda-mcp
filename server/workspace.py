"""Workspace path resolution with sandbox enforcement.

All tool I/O must go through `resolve()` so the LLM cannot escape /workspace.
"""
from __future__ import annotations

import os
from pathlib import Path

WORKSPACE = Path(os.environ.get("EDA_MCP_WORKSPACE", "/workspace")).resolve()


class WorkspaceError(ValueError):
    pass


def resolve(rel_path: str) -> Path:
    """Resolve a workspace-relative path. Rejects absolute paths and `..` escapes."""
    if not rel_path or rel_path == ".":
        return WORKSPACE
    p = Path(rel_path)
    if p.is_absolute():
        raise WorkspaceError(f"absolute paths not allowed: {rel_path!r}")
    full = (WORKSPACE / p).resolve()
    try:
        full.relative_to(WORKSPACE)
    except ValueError:
        raise WorkspaceError(f"path escapes workspace: {rel_path!r}") from None
    return full


def rel(path: Path) -> str:
    """Render an absolute path back as a workspace-relative string."""
    return str(path.relative_to(WORKSPACE))
