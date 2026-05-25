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
        """Compile and simulate a Verilog testbench using Icarus Verilog.

        Use this to run functional simulation. The testbench should use
        $display to print "TEST PASSED" or "TEST FAILED", and optionally
        $dumpfile/$dumpvars to generate a VCD waveform for analysis.

        Args:
            sources: workspace-relative .v files — must include both the
                     design under test AND the testbench.
            top: the testbench module name (e.g. "tb_counter").
            timeout_s: max seconds before the simulation is killed (default 30).

        Returns dict with:
            stage: 'compile' if compilation failed, 'run' if simulation ran.
            vcd_path: workspace-relative path to the VCD file (e.g.
                      "build/tb_counter/dump.vcd"), or null if no VCD was generated.
            returncode: 0 on success.
            stdout: simulation output ($display messages, pass/fail verdict).
            stderr: compiler or runtime warnings/errors.
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
