"""Yosys synthesis tool."""
from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP

from .. import shell, workspace


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def yosys_synth(
        sources: list[str],
        top: str,
        target: Literal["verilog", "json"] = "verilog",
        timeout_s: int = 120,
    ) -> dict:
        """Synthesize Verilog to a gate-level netlist with Yosys.

        sources: workspace-relative paths to .v files.
        top: name of the top module.
        target: 'verilog' (gate-level .v, default) or 'json' (Yosys JSON netlist).
        Returns the output path under build/ plus yosys stdout/stderr.
        """
        src_paths = [str(workspace.resolve(s)) for s in sources]
        ext = "json" if target == "json" else "v"
        out = workspace.resolve(f"build/{top}.{ext}")
        out.parent.mkdir(parents=True, exist_ok=True)

        writer = "write_json" if target == "json" else "write_verilog"
        script = (
            f"read_verilog {' '.join(src_paths)}; "
            f"synth -top {top}; "
            f"{writer} {out}"
        )
        result = shell.run_cmd(
            ["yosys", "-q", "-p", script],
            cwd=workspace.WORKSPACE,
            timeout=timeout_s,
        )
        return {
            "output_path": workspace.rel(out) if out.exists() else None,
            **result,
        }
