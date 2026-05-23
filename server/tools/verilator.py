"""Verilator lint tool (placeholder — extend with full simulation later)."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .. import shell, workspace


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def verilator_lint(
        sources: list[str],
        top: str,
        timeout_s: int = 30,
    ) -> dict:
        """Lint Verilog sources with Verilator (--lint-only).

        Returns verilator's diagnostic output. Non-zero returncode means lint errors.
        """
        src_paths = [str(workspace.resolve(s)) for s in sources]
        result = shell.run_cmd(
            ["verilator", "--lint-only", "-Wall", "--top-module", top, *src_paths],
            cwd=workspace.WORKSPACE,
            timeout=timeout_s,
        )
        return result
