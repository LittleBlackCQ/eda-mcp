# --- Stage 1: build waveform-cli from crates.io ---
FROM rust:1-slim AS waveform-builder
RUN apt-get update && apt-get install -y --no-install-recommends \
        pkg-config \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN cargo install waveform-mcp --version 0.5.0 --root /opt/waveform

# --- Stage 2: runtime image ---
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# EDA toolchain
#
# make + g++ are required by Verilator's --binary flow: Verilator emits C++ and
# then invokes make/g++ to build the simulation executable (e.g. RealBench's
# verification Makefiles). Without them, --binary compilation fails.
RUN apt-get update && apt-get install -y --no-install-recommends \
        yosys \
        iverilog \
        verilator \
        gtkwave \
        make \
        g++ \
        python3 \
        python3-pip \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# MCP Python SDK. Default uses the official PyPI; override via --build-arg to
# pick a mirror when needed, e.g.
#   docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t eda-mcp .
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip3 install --no-cache-dir --break-system-packages \
        --index-url "${PIP_INDEX_URL}" \
        --timeout 120 --retries 5 \
        "mcp[cli]>=1.0"

# waveform-cli and waveform-mcp (placed after pip so its content changes don't
# invalidate the pip layer cache above).
COPY --from=waveform-builder /opt/waveform/bin/waveform-cli /usr/local/bin/waveform-cli
COPY --from=waveform-builder /opt/waveform/bin/waveform-mcp /usr/local/bin/waveform-mcp

WORKDIR /app
COPY server/ /app/server/
ENV PYTHONPATH=/app

RUN mkdir -p /workspace
WORKDIR /workspace
VOLUME ["/workspace"]

ENTRYPOINT ["python3", "-m", "server.main"]
