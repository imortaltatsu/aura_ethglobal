#!/bin/bash
# Run bot with CUDA 12 libs for Whisper (fixes libcublas.so.12 on CUDA 13 systems)
set -e
cd "$(dirname "$0")"
CUBLAS_PATH=$(uv run python -c "import nvidia.cublas.lib; print(nvidia.cublas.lib.__path__[0])")
export LD_LIBRARY_PATH="${CUBLAS_PATH}:${LD_LIBRARY_PATH:-}"
exec uv run run_server.py "$@"
