"""Waveform inspection tools backed by `waveform-cli` (jiegec/waveform-mcp).

Each MCP call shells out to a single `waveform-cli` invocation that chains
`open_waveform <path> --alias w -- <subcommand> w ...`. The alias only lives
for the duration of one process, so we open + query in the same chain every
time. Fine for small VCDs; if it ever becomes too slow we can keep a long-
lived `waveform-mcp` stdio child instead.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .. import shell, workspace

ALIAS = "w"
READ_ONLY = ToolAnnotations(readOnlyHint=True)


def _run_chain(vcd_path: str, subcommand: list[str], timeout_s: int = 30) -> dict:
    abs_path = workspace.resolve(vcd_path)
    if not abs_path.is_file():
        return {"error": f"waveform file not found: {vcd_path}"}
    cmd = [
        "waveform-cli",
        "open_waveform", str(abs_path), "--alias", ALIAS,
        "--",
        *subcommand,
    ]
    return shell.run_cmd(cmd, cwd=workspace.WORKSPACE, timeout=timeout_s)


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    def waveform_list_signals(
        vcd_path: str,
        pattern: str | None = None,
        hierarchy: str | None = None,
        recursive: bool = True,
        limit: int = 200,
    ) -> dict:
        """List signals in a VCD/FST file.

        pattern: substring or glob to filter signal names (optional).
        hierarchy: only list signals under this scope (optional).
        """
        sub = ["list_signals", ALIAS]
        if pattern:
            sub += ["--pattern", pattern]
        if hierarchy:
            sub += ["--hierarchy", hierarchy]
        sub += ["--recursive", str(recursive).lower(), "--limit", str(limit)]
        return _run_chain(vcd_path, sub)

    @mcp.tool(annotations=READ_ONLY)
    def waveform_read_hierarchy(
        vcd_path: str,
        scope: str | None = None,
        recursive: bool = True,
        limit: int = 200,
    ) -> dict:
        """Show the module hierarchy of a waveform file as an indented tree."""
        sub = ["read_hierarchy", ALIAS]
        if scope:
            sub += ["--scope", scope]
        sub += ["--recursive", str(recursive).lower(), "--limit", str(limit)]
        return _run_chain(vcd_path, sub)

    @mcp.tool(annotations=READ_ONLY)
    def waveform_read_signal(
        vcd_path: str,
        signal: str,
        time_indices: list[int] | None = None,
        time_index: int | None = None,
    ) -> dict:
        """Read a signal's value at one or more time indices.

        signal: dotted path like 'top.dut.clk'.
        Use either time_index (single) or time_indices (list).
        """
        sub = ["read_signal", ALIAS, signal]
        if time_index is not None:
            sub += ["--time-index", str(time_index)]
        elif time_indices:
            sub += ["--time-indices", ",".join(str(i) for i in time_indices)]
        return _run_chain(vcd_path, sub)

    @mcp.tool(annotations=READ_ONLY)
    def waveform_signal_info(vcd_path: str, signal: str) -> dict:
        """Get type/width/index metadata for one signal."""
        return _run_chain(vcd_path, ["get_signal_info", ALIAS, signal])

    @mcp.tool(annotations=READ_ONLY)
    def waveform_find_signal_events(
        vcd_path: str,
        signal: str,
        start: int | None = None,
        end: int | None = None,
        limit: int = 100,
    ) -> dict:
        """Find all value-change events on a signal within a time-index range."""
        sub = ["find_signal_events", ALIAS, signal]
        if start is not None:
            sub += ["--start", str(start)]
        if end is not None:
            sub += ["--end", str(end)]
        sub += ["--limit", str(limit)]
        return _run_chain(vcd_path, sub)

    @mcp.tool(annotations=READ_ONLY)
    def waveform_find_conditional_events(
        vcd_path: str,
        condition: str,
        start: int | None = None,
        end: int | None = None,
        limit: int = 100,
    ) -> dict:
        """Find time indices where a boolean expression over signals is true.

        condition: Verilog-style expression, supports bitwise/boolean ops and $past().
                   Example: "top.dut.q == 4'h5 && $past(top.dut.rst_n)".
        """
        sub = ["find_conditional_events", ALIAS, condition]
        if start is not None:
            sub += ["--start", str(start)]
        if end is not None:
            sub += ["--end", str(end)]
        sub += ["--limit", str(limit)]
        return _run_chain(vcd_path, sub)
