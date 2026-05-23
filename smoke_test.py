#!/usr/bin/env python3
"""End-to-end smoke test for eda-mcp.

Spawns the docker container, speaks MCP JSON-RPC over stdio, calls every tool
in a sensible order, and reports PASS/FAIL.

No dependencies outside the standard library. Run from the project root:

    python3 smoke_test.py

Exits 0 if all checks pass, 1 otherwise.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE = PROJECT_ROOT / "workspace"
IMAGE = os.environ.get("EDA_MCP_IMAGE", "eda-mcp")

USE_COLOR = sys.stdout.isatty()
GREEN = "\033[32m" if USE_COLOR else ""
RED = "\033[31m" if USE_COLOR else ""
DIM = "\033[2m" if USE_COLOR else ""
RESET = "\033[0m" if USE_COLOR else ""


def _docker_user_args() -> list[str]:
    """Pass the host UID/GID into the container so generated files are owned by the
    invoking user (otherwise they end up root-owned and unremovable from the host)."""
    if hasattr(os, "getuid"):
        return ["--user", f"{os.getuid()}:{os.getgid()}"]
    return []


def _docker_rm(rel_path: str, image: str, workspace: Path) -> None:
    """Remove a workspace path from inside the container — handles root-owned
    artefacts left by previous runs that lacked --user."""
    subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "rm",
         "-v", f"{workspace}:/workspace", image,
         "-rf", f"/workspace/{rel_path}"],
        check=True, capture_output=True,
    )


def _clean_path(path: Path, image: str, workspace: Path) -> None:
    """Remove a file or directory, falling back to docker on PermissionError."""
    if not path.exists() and not path.is_symlink():
        return
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except PermissionError:
        rel = path.relative_to(workspace)
        _docker_rm(str(rel), image, workspace)


class MCPClient:
    """Minimal JSON-RPC client speaking to an MCP stdio server inside docker."""

    def __init__(self, image: str, workspace: Path):
        self.proc = subprocess.Popen(
            ["docker", "run", "--rm", "-i",
             *_docker_user_args(),
             "-v", f"{workspace}:/workspace", image],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._id = 0

    def _send(self, msg: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def _recv(self) -> dict:
        assert self.proc.stdout is not None and self.proc.stderr is not None
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read()
            raise RuntimeError(
                f"server closed before responding. stderr:\n{err}"
            )
        return json.loads(line)

    def request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id,
                    "method": method, "params": params or {}})
        return self._recv()

    def notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def initialize(self) -> dict:
        resp = self.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "smoke-test", "version": "0.0.1"},
        })
        self.notify("notifications/initialized")
        return resp

    def list_tools(self) -> dict:
        return self.request("tools/list")

    def call_tool(self, name: str, args: dict) -> dict:
        return self.request("tools/call",
                            {"name": name, "arguments": args})

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def tool_payload(resp: dict):
    """Unwrap FastMCP's content envelope. Returns (parsed_dict_or_text, is_error)."""
    result = resp.get("result", {})
    is_error = bool(result.get("isError"))
    content = result.get("content", [])
    if not content:
        return None, is_error
    text = content[0].get("text", "")
    try:
        return json.loads(text), is_error
    except json.JSONDecodeError:
        return text, is_error


_results: list[tuple[str, bool]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    badge = f"{GREEN}PASS{RESET}" if condition else f"{RED}FAIL{RESET}"
    suffix = f"  {DIM}{detail}{RESET}" if detail else ""
    print(f"  {badge}  {name}{suffix}")
    _results.append((name, condition))
    return condition


def section(title: str) -> None:
    print(f"\n{DIM}── {title} ──{RESET}")


def main() -> int:
    if shutil.which("docker") is None:
        print(f"{RED}docker not found in PATH{RESET}", file=sys.stderr)
        return 2

    print(f"workspace: {WORKSPACE}")
    print(f"image:     {IMAGE}")

    # Clean prior test artefacts so each run is reproducible. Some files may be
    # root-owned (from runs before --user was wired in); _clean_path falls back
    # to docker for those.
    for stray in ("build", "smoke.txt", "shift.v",
                  "shift_reg.v", "shift_reg_tb.v"):
        _clean_path(WORKSPACE / stray, IMAGE, WORKSPACE)

    client = MCPClient(IMAGE, WORKSPACE)
    try:
        section("handshake")
        resp = client.initialize()
        server_info = resp.get("result", {}).get("serverInfo", {})
        check("initialize returns serverInfo", "name" in server_info,
              detail=str(server_info))

        section("tools/list")
        resp = client.list_tools()
        tools = resp.get("result", {}).get("tools", [])
        names = sorted(t["name"] for t in tools)
        check("12 tools exposed", len(tools) == 12,
              detail=f"got {len(tools)}")
        ro = [t["name"] for t in tools
              if (t.get("annotations") or {}).get("readOnlyHint")]
        check("9 tools tagged readOnlyHint", len(ro) == 9,
              detail=f"got {len(ro)}: {sorted(ro)}")
        expected_writers = {"write_file", "yosys_synth", "iverilog_simulate"}
        writers = set(names) - set(ro)
        check("correct writers (no readOnlyHint)",
              writers == expected_writers,
              detail=f"got {sorted(writers)}")

        section("files: list / read")
        resp = client.call_tool("list_files", {"subdir": "examples"})
        data, _ = tool_payload(resp)
        files = {f["path"] for f in (data or {}).get("files", [])}
        check("examples/counter.v listed",
              "examples/counter.v" in files)
        check("examples/counter_tb.v listed",
              "examples/counter_tb.v" in files)

        resp = client.call_tool("read_file", {"path": "examples/counter.v"})
        data, _ = tool_payload(resp)
        check("read counter.v content",
              "module counter" in (data or {}).get("content", ""))

        section("files: write + sandbox")
        resp = client.call_tool("write_file",
                                {"path": "smoke.txt", "content": "hello"})
        data, _ = tool_payload(resp)
        check("write_file bytes=5", (data or {}).get("bytes") == 5)
        check("file visible on host",
              (WORKSPACE / "smoke.txt").is_file())

        resp = client.call_tool("write_file",
                                {"path": "../escape.txt", "content": "x"})
        _, is_error = tool_payload(resp)
        check("sandbox escape rejected", is_error)
        check("no escape file on host",
              not (WORKSPACE.parent / "escape.txt").exists())

        section("verilator_lint")
        resp = client.call_tool("verilator_lint",
                                {"sources": ["examples/counter.v"],
                                 "top": "counter"})
        data, _ = tool_payload(resp)
        check("verilator rc=0",
              (data or {}).get("returncode") == 0,
              detail=f"rc={(data or {}).get('returncode')}")

        section("yosys_synth (default target=verilog)")
        resp = client.call_tool("yosys_synth",
                                {"sources": ["examples/counter.v"],
                                 "top": "counter"})
        data, _ = tool_payload(resp)
        check("yosys rc=0", (data or {}).get("returncode") == 0)
        check("default output_path == build/counter.v",
              (data or {}).get("output_path") == "build/counter.v")
        check("netlist file on host",
              (WORKSPACE / "build" / "counter.v").is_file())

        section("iverilog_simulate")
        resp = client.call_tool("iverilog_simulate", {
            "sources": ["examples/counter.v", "examples/counter_tb.v"],
            "top": "counter_tb",
        })
        data, _ = tool_payload(resp)
        check("iverilog stage=run", (data or {}).get("stage") == "run")
        check("iverilog rc=0", (data or {}).get("returncode") == 0)
        check("$display in stdout",
              "final q" in (data or {}).get("stdout", ""))
        vcd_path = (data or {}).get("vcd_path")
        check("VCD produced",
              bool(vcd_path) and (WORKSPACE / vcd_path).is_file(),
              detail=f"vcd_path={vcd_path}")

        if not vcd_path:
            print(f"\n{RED}cannot continue without VCD{RESET}")
            return 1

        section("waveform tools")
        resp = client.call_tool("waveform_read_hierarchy",
                                {"vcd_path": vcd_path})
        data, _ = tool_payload(resp)
        check("hierarchy mentions counter_tb",
              "counter_tb" in (data or {}).get("stdout", ""))

        resp = client.call_tool("waveform_list_signals",
                                {"vcd_path": vcd_path, "pattern": "q"})
        data, _ = tool_payload(resp)
        check("list_signals rc=0",
              (data or {}).get("returncode") == 0)

        resp = client.call_tool("waveform_signal_info",
                                {"vcd_path": vcd_path,
                                 "signal": "counter_tb.q"})
        data, _ = tool_payload(resp)
        check("signal_info rc=0",
              (data or {}).get("returncode") == 0)

        resp = client.call_tool("waveform_read_signal", {
            "vcd_path": vcd_path, "signal": "counter_tb.q",
            "time_indices": [0, 5, 10, 20],
        })
        data, _ = tool_payload(resp)
        check("read_signal rc=0",
              (data or {}).get("returncode") == 0)

        resp = client.call_tool("waveform_find_signal_events", {
            "vcd_path": vcd_path, "signal": "counter_tb.q", "limit": 10,
        })
        data, _ = tool_payload(resp)
        check("find_signal_events rc=0",
              (data or {}).get("returncode") == 0)

        resp = client.call_tool("waveform_find_conditional_events", {
            "vcd_path": vcd_path,
            "condition": "counter_tb.q == 4'h5",
            "limit": 5,
        })
        data, _ = tool_payload(resp)
        check("find_conditional_events rc=0",
              (data or {}).get("returncode") == 0)

    finally:
        client.close()

    passed = sum(1 for _, ok in _results if ok)
    total = len(_results)
    print()
    color = GREEN if passed == total else RED
    print(f"{color}=== {passed}/{total} passed ==={RESET}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
