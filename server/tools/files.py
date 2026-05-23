"""Workspace file I/O tools — the LLM uses these to place source files."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .. import workspace

READ_ONLY = ToolAnnotations(readOnlyHint=True)


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    def list_files(subdir: str = "") -> dict:
        """List files in the workspace (or a subdirectory). Paths are workspace-relative."""
        root = workspace.resolve(subdir)
        if not root.exists():
            return {"subdir": subdir, "files": [], "exists": False}
        entries = []
        for p in sorted(root.rglob("*")):
            if p.is_file():
                entries.append({"path": workspace.rel(p), "size": p.stat().st_size})
        return {"subdir": subdir, "files": entries, "exists": True}

    @mcp.tool(annotations=READ_ONLY)
    def read_file(path: str) -> dict:
        """Read a text file from the workspace."""
        full = workspace.resolve(path)
        if not full.is_file():
            return {"path": path, "error": "not a file"}
        return {"path": path, "content": full.read_text()}

    @mcp.tool()
    def write_file(path: str, content: str) -> dict:
        """Write a text file to the workspace. Creates parent directories."""
        full = workspace.resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
        return {"path": path, "bytes": len(content.encode())}
