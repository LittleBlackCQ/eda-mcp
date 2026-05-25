"""Yosys synthesis tool."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field
from mcp.server.fastmcp import FastMCP

from .. import shell, workspace


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def yosys_synth(
        sources: Annotated[list[str], Field(description='workspace-relative paths to .v files (e.g. ["src/counter.v"])')],
        top: Annotated[str, Field(description="name of the top-level module to synthesize")],
        target: Annotated[Literal["verilog", "json"], Field(description="output format: 'verilog' for gate-level .v (default), 'json' for Yosys JSON netlist")] = "verilog",
        timeout_s: Annotated[int, Field(description="max seconds before the process is killed (default 120)")] = 120,
    ) -> dict:
        """Synthesize Verilog sources into a gate-level netlist using Yosys.

        Use this after writing Verilog source files to check synthesizability
        or to inspect the gate-level structure.

        Args:
            sources: workspace-relative paths to .v files (e.g. ["src/counter.v"]).
            top: name of the top-level module to synthesize.
            target: output format — 'verilog' for gate-level .v (default),
                    'json' for Yosys JSON netlist.
            timeout_s: max seconds before the process is killed (default 120).

        Returns dict with:
            output_path: workspace-relative path to the netlist (e.g. "build/counter.v"),
                         or null if synthesis failed.
            returncode: 0 on success, non-zero on failure.
            stdout/stderr: Yosys log output (warnings, cell counts, etc.).
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
