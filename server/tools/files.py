"""Workspace file I/O tools — the LLM uses these to place source files."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .. import workspace

READ_ONLY = ToolAnnotations(readOnlyHint=True)


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    def list_files(
        subdir: Annotated[str, Field(description='subdirectory to list (e.g. "src", "build"). Empty = workspace root')] = "",
    ) -> dict:
        """List files inside the EDA workspace (Docker /workspace directory).

        This is the shared workspace where Verilog sources and build artifacts
        live. Use this (not the host read_file) to see files available to EDA tools.

        Args:
            subdir: subdirectory to list (e.g. "src", "build"). Empty = workspace root.

        Returns dict with files: list of {path, size} entries.
        """
        root = workspace.resolve(subdir)
        if not root.exists():
            return {"subdir": subdir, "files": [], "exists": False}
        entries = []
        for p in sorted(root.rglob("*")):
            if p.is_file():
                entries.append({"path": workspace.rel(p), "size": p.stat().st_size})
        return {"subdir": subdir, "files": entries, "exists": True}

    @mcp.tool(annotations=READ_ONLY)
    def read_file(
        path: Annotated[str, Field(description='workspace-relative file path (e.g. "src/counter.v")')],
    ) -> dict:
        """Read a text file from the EDA workspace (Docker /workspace directory).

        Use this to read Verilog sources, build logs, or netlist outputs that
        were created by EDA tools. Paths are relative to /workspace.

        Args:
            path: workspace-relative file path (e.g. "src/counter.v").
        """
        full = workspace.resolve(path)
        if not full.is_file():
            return {"path": path, "error": "not a file"}
        return {"path": path, "content": full.read_text()}

    @mcp.tool()
    def write_file(
        path: Annotated[str, Field(description='workspace-relative file path (e.g. "src/counter.v")')],
        content: Annotated[str, Field(description="full file content to write")],
    ) -> dict:
        """Write a text file to the EDA workspace (Docker /workspace directory).

        Use this to create or overwrite Verilog source files and testbenches
        before running synthesis, simulation, or lint. Creates parent dirs.

        Args:
            path: workspace-relative file path (e.g. "src/counter.v").
            content: full file content to write.

        Returns dict with path and bytes written.
        """
        full = workspace.resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
        return {"path": path, "bytes": len(content.encode())}
