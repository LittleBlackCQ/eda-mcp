"""Icarus Verilog compile + simulate tool."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import shell, workspace


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def iverilog_simulate(
        sources: list[str],
        top: str,
        timeout_s: int = 30,
    ) -> dict:
        """Compile and run a Verilog testbench with Icarus Verilog.

        sources: workspace-relative .v files (include the testbench).
        top: top module to simulate (usually the testbench).
        Returns vvp stdout (where $display lands) and the VCD path if produced.
        """
        src_paths = [str(workspace.resolve(s)) for s in sources]
        out_dir = workspace.resolve(f"build/{top}")
        out_dir.mkdir(parents=True, exist_ok=True)
        binary = out_dir / "sim.vvp"

        compile_result = shell.run_cmd(
            ["iverilog", "-g2012", "-s", top, "-o", str(binary), *src_paths],
            cwd=workspace.WORKSPACE,
            timeout=timeout_s,
        )
        if compile_result["returncode"] != 0:
            return {"stage": "compile", **compile_result}

        run_result = shell.run_cmd(
            ["vvp", str(binary)],
            cwd=out_dir,
            timeout=timeout_s,
        )
        vcd_candidates = sorted(out_dir.glob("*.vcd"))
        return {
            "stage": "run",
            "vcd_path": workspace.rel(vcd_candidates[0]) if vcd_candidates else None,
            **run_result,
        }
