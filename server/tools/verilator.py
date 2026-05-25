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
        """Run static lint checks on Verilog sources using Verilator.

        Use this BEFORE simulation or synthesis to catch common issues:
        unused signals, width mismatches, implicit wire declarations, and
        coding style violations. Runs with -Wall for maximum diagnostics.

        Args:
            sources: workspace-relative .v files to lint.
            top: the top-level module name.
            timeout_s: max seconds (default 30).

        Returns dict with:
            returncode: 0 = clean, non-zero = lint errors found.
            stdout/stderr: Verilator diagnostic messages (warnings and errors).
        """
        src_paths = [str(workspace.resolve(s)) for s in sources]
        result = shell.run_cmd(
            ["verilator", "--lint-only", "-Wall", "--top-module", top, *src_paths],
            cwd=workspace.WORKSPACE,
            timeout=timeout_s,
        )
        return result
