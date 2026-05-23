# eda-mcp

A Model Context Protocol (MCP) server that exposes a curated set of open-source EDA tools so that LLM agents — Claude Code, MCP Inspector, or any MCP-compatible client — can drive synthesis, simulation, lint, and waveform analysis through tool calls.

The server, its Python wrappers, and the EDA toolchain are packaged into a single Docker image and speak MCP over stdio.

## Tools

| MCP tool | Backed by | Function |
|---|---|---|
| `list_files`, `read_file`, `write_file` | Python stdlib | Workspace I/O |
| `yosys_synth` | Yosys | Verilog synthesis to gate-level netlist (default) or JSON netlist |
| `iverilog_simulate` | Icarus Verilog (`iverilog` + `vvp`) | Event-driven Verilog simulation; returns `$display` output and the VCD path |
| `verilator_lint` | Verilator (`--lint-only`) | Static lint of Verilog sources |
| `waveform_list_signals`, `waveform_read_hierarchy`, `waveform_read_signal`, `waveform_signal_info`, `waveform_find_signal_events`, `waveform_find_conditional_events` | `waveform-cli` from [jiegec/waveform-mcp](https://github.com/jiegec/waveform-mcp) | VCD/FST inspection: hierarchy, signal values at given time indices, value-change events, and Verilog-expression-conditional events |

Read-only tools (file reads, lint, all `waveform_*` queries) carry the MCP `readOnlyHint` annotation so clients can grant them lower-friction permissions.

## Layout

```
server/
  main.py            FastMCP server, registers all tools, runs over stdio
  shell.py           subprocess wrapper (timeout, capture, structured result)
  workspace.py       /workspace path resolution and sandbox enforcement
  tools/
    files.py         list_files / read_file / write_file
    yosys.py         yosys_synth
    iverilog.py      iverilog_simulate
    verilator.py     verilator_lint
    waveform.py      six waveform_* tools backed by waveform-cli
Dockerfile           Multi-stage: Rust builder for waveform-cli + Ubuntu 24.04 runtime
pyproject.toml       Python project metadata; declares entry points eda-mcp-server and eda-mcp-smoke
smoke_test.py        Stand-alone end-to-end test of every tool
workspace/           Host-mounted into /workspace; designs, build artefacts, and VCDs live here
  examples/          Sample 4-bit counter and testbench used by smoke_test.py
```

## Build

```bash
docker build -t eda-mcp .
```

If the default PyPI is slow, override the pip index at build time:

```bash
docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t eda-mcp .
```

## Usage

The container speaks MCP over stdio. Mount the host workspace into `/workspace` so designs and build artefacts remain accessible from the host.

### Register with Claude Code

```bash
claude mcp add --scope project eda-mcp -- docker run --rm -i \
    --user "$(id -u):$(id -g)" \
    -v "$PWD/workspace:/workspace" eda-mcp
```

### Explore interactively with MCP Inspector

```bash
npx @modelcontextprotocol/inspector \
    docker run --rm -i --user "$(id -u):$(id -g)" \
    -v "$PWD/workspace:/workspace" eda-mcp
```

The `--user "$(id -u):$(id -g)"` flag is important — without it the container runs as root, and any files produced by tools (synthesis netlists, VCDs) end up root-owned on the host and can only be cleaned up with `sudo`. The shell expands `$(id -u)` at registration time, so the stored command holds a literal numeric UID.

### Run the smoke test

The smoke test exercises every tool against the example counter design and reports pass/fail. It has no dependencies outside the Python standard library.

```bash
python3 smoke_test.py
```

Exit code is `0` on success, non-zero on any failed check.

## Workspace conventions

- All tool arguments accept paths **relative to `/workspace`**. Absolute paths and `..` traversal are rejected by `server.workspace.resolve`.
- Generated artefacts land under `workspace/build/<top>/...`.
- `workspace/examples/` ships a 4-bit counter (`counter.v`) and testbench (`counter_tb.v`) used as smoke-test fixtures.

## Extending

To add a new EDA tool:

1. Install the binary in the `Dockerfile` (either via `apt-get install` or by copying it in through a dedicated build stage).
2. Create `server/tools/<name>.py` exposing a `register(mcp)` function whose body declares `@mcp.tool()`-decorated callables. Mark non-mutating tools with `annotations=ToolAnnotations(readOnlyHint=True)`.
3. Import the module and call `register(mcp)` in `server/main.py`.
4. Route all process invocations through `server.shell.run_cmd` and all paths through `server.workspace.resolve`; direct `subprocess` calls or absolute paths bypass the sandbox.
5. Add coverage in `smoke_test.py`.
