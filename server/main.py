"""eda-mcp server entrypoint. Runs FastMCP over stdio."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .tools import files, iverilog, verilator, waveform, yosys

mcp = FastMCP("eda-mcp")

files.register(mcp)
yosys.register(mcp)
iverilog.register(mcp)
verilator.register(mcp)
waveform.register(mcp)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
