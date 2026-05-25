"""Waveform inspection tools backed by `waveform-cli` (jiegec/waveform-mcp).

Each MCP call shells out to a single `waveform-cli` invocation that chains
`open_waveform <path> --alias w -- <subcommand> w ...`. The alias only lives
for the duration of one process, so we open + query in the same chain every
time. Fine for small VCDs; if it ever becomes too slow we can keep a long-
lived `waveform-mcp` stdio child instead.
"""
from __future__ import annotations

from typing import Annotated

from pydantic import Field
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
        vcd_path: Annotated[str, Field(description='workspace-relative path to the waveform (e.g. "build/tb_counter/dump.vcd")')],
        pattern: Annotated[str | None, Field(description='substring or glob to filter signal names (e.g. "clk", "data_*")')] = None,
        hierarchy: Annotated[str | None, Field(description='only show signals under this scope (e.g. "tb.dut")')] = None,
        recursive: Annotated[bool, Field(description="include signals in sub-scopes (default True)")] = True,
        limit: Annotated[int, Field(description="max number of signals to return (default 200)")] = 200,
    ) -> dict:
        """List signal names in a VCD/FST waveform file.

        Use this as the first step when exploring an unfamiliar waveform — it
        tells you what signals exist and their hierarchical paths.

        Args:
            vcd_path: workspace-relative path to the waveform (e.g. "build/tb_counter/dump.vcd").
            pattern: substring or glob to filter signal names (e.g. "clk", "data_*").
            hierarchy: only show signals under this scope (e.g. "tb.dut").
            recursive: include signals in sub-scopes (default True).
            limit: max number of signals to return (default 200).
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
        vcd_path: Annotated[str, Field(description="workspace-relative path to the waveform file")],
        scope: Annotated[str | None, Field(description='start from this scope instead of the root (e.g. "tb.dut")')] = None,
        recursive: Annotated[bool, Field(description="include sub-scopes (default True)")] = True,
        limit: Annotated[int, Field(description="max entries to return (default 200)")] = 200,
    ) -> dict:
        """Show the module/scope hierarchy of a waveform file as an indented tree.

        Use this to understand the design structure before drilling into
        specific signals. Useful when you don't know the full signal path.

        Args:
            vcd_path: workspace-relative path to the waveform file.
            scope: start from this scope instead of the root (e.g. "tb.dut").
        """
        sub = ["read_hierarchy", ALIAS]
        if scope:
            sub += ["--scope", scope]
        sub += ["--recursive", str(recursive).lower(), "--limit", str(limit)]
        return _run_chain(vcd_path, sub)

    @mcp.tool(annotations=READ_ONLY)
    def waveform_read_signal(
        vcd_path: Annotated[str, Field(description="workspace-relative path to the waveform file")],
        signal: Annotated[str, Field(description='full hierarchical signal path (e.g. "tb.dut.clk", "tb.dut.data_out")')],
        time_indices: Annotated[list[int] | None, Field(description="list of simulation time points to read at once (mutually exclusive with time_index)")] = None,
        time_index: Annotated[int | None, Field(description="a single simulation time point (integer, in the waveform's native time unit from $timescale)")] = None,
    ) -> dict:
        """Read a signal's value at specific simulation time points.

        Use this to check signal states at known timestamps (e.g. after a
        clock edge, at the moment of failure). Get time points from
        waveform_find_signal_events or waveform_find_conditional_events first.

        Args:
            vcd_path: workspace-relative path to the waveform file.
            signal: full hierarchical path (e.g. "tb.dut.clk", "tb.dut.data_out").
            time_index: a single simulation time point (integer, in the
                        waveform's native time unit — typically from $timescale).
            time_indices: list of time points to read at once.
                          Use either time_index or time_indices, not both.
        """
        sub = ["read_signal", ALIAS, signal]
        if time_index is not None:
            sub += ["--time-index", str(time_index)]
        elif time_indices:
            sub += ["--time-indices", ",".join(str(i) for i in time_indices)]
        return _run_chain(vcd_path, sub)

    @mcp.tool(annotations=READ_ONLY)
    def waveform_signal_info(
        vcd_path: Annotated[str, Field(description="workspace-relative path to the waveform file")],
        signal: Annotated[str, Field(description='full hierarchical signal path (e.g. "tb.dut.data_out")')],
    ) -> dict:
        """Get metadata for a signal: bit width, type, and time-index range.

        Use this when you need to know a signal's width before interpreting
        its value, or to find the valid time range for queries.

        Args:
            vcd_path: workspace-relative path to the waveform file.
            signal: full hierarchical path (e.g. "tb.dut.data_out").
        """
        return _run_chain(vcd_path, ["get_signal_info", ALIAS, signal])

    @mcp.tool(annotations=READ_ONLY)
    def waveform_find_signal_events(
        vcd_path: Annotated[str, Field(description="workspace-relative path to the waveform file")],
        signal: Annotated[str, Field(description='full hierarchical signal path (e.g. "tb.dut.state")')],
        start: Annotated[int | None, Field(description="earliest simulation time to search from (inclusive, default: beginning)")] = None,
        end: Annotated[int | None, Field(description="latest simulation time to search to (inclusive, default: end of trace)")] = None,
        limit: Annotated[int, Field(description="max events to return (default 100)")] = 100,
    ) -> dict:
        """Find all value-change events on a signal within a time range.

        Returns a list of (time, new_value) pairs. Use this to trace how a
        signal evolves over time, or to find when a specific transition happened.
        The returned time values can be passed to waveform_read_signal.

        Args:
            vcd_path: workspace-relative path to the waveform file.
            signal: full hierarchical path (e.g. "tb.dut.state").
            start: earliest simulation time to search from (inclusive, default: beginning).
            end: latest simulation time to search to (inclusive, default: end of trace).
            limit: max events to return (default 100).
        """
        sub = ["find_signal_events", ALIAS, signal]
        if start is not None:
            sub += ["--start", str(start)]
        if end is not None:
            sub += ["--end", str(end)]
        sub += ["--limit", str(limit)]
        return _run_chain(vcd_path, sub)

    @mcp.tool(annotations=READ_ONLY)
    def waveform_find_conditional_events(
        vcd_path: Annotated[str, Field(description="workspace-relative path to the waveform file")],
        condition: Annotated[str, Field(description='Verilog-style boolean expression. Supports ==, !=, &, |, ^, &&, ||, $past(). Signal names must use full paths. Examples: "tb.dut.full == 1\'b1", "tb.dut.q != 8\'hFF && $past(tb.dut.en)"')],
        start: Annotated[int | None, Field(description="earliest simulation time (inclusive)")] = None,
        end: Annotated[int | None, Field(description="latest simulation time (inclusive)")] = None,
        limit: Annotated[int, Field(description="max matching time points to return (default 100)")] = 100,
    ) -> dict:
        """Find simulation times where a boolean condition over signals is true.

        Use this for targeted debugging — e.g. "when did the FIFO overflow?"
        or "find cycles where output doesn't match expected".

        Args:
            vcd_path: workspace-relative path to the waveform file.
            condition: Verilog-style boolean expression. Supports ==, !=, &, |,
                       ^, &&, ||, $past(). Signal names must use full paths.
                       Examples:
                         "tb.dut.full == 1'b1"
                         "tb.dut.q != 8'hFF && $past(tb.dut.en)"
            start: earliest simulation time (inclusive).
            end: latest simulation time (inclusive).
            limit: max matching time points to return (default 100).
        """
        sub = ["find_conditional_events", ALIAS, condition]
        if start is not None:
            sub += ["--start", str(start)]
        if end is not None:
            sub += ["--end", str(end)]
        sub += ["--limit", str(limit)]
        return _run_chain(vcd_path, sub)
