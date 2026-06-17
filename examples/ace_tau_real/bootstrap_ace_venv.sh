#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACE_ROOT="$(cd "${SCRIPT_DIR}/../../agentic-context-engine-22-04" && pwd)"
PYTHON_BIN="${ACE_PYTHON_BIN:-python3.12}"
TAU2_ROOT="${AUTOHARNESS_TAU2_ROOT:-$(cd "${ACE_ROOT}/../tau2-bench" 2>/dev/null && pwd || true)}"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/autoharness-ace-uv-cache}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp}"

echo "ACE root: ${ACE_ROOT}"
echo "Python: ${PYTHON_BIN}"
echo "UV cache: ${UV_CACHE_DIR}"

uv venv --python "${PYTHON_BIN}" "${ACE_ROOT}/.venv"
"${ACE_ROOT}/.venv/bin/python" -m ensurepip --upgrade

uv pip install --python "${ACE_ROOT}/.venv/bin/python" \
  "click>=8.1.0" \
  "litellm>=1.83.0" \
  "pydantic>=2.0.0" \
  "pydantic-ai-slim[litellm,bedrock]>=0.0.36" \
  "python-toon>=0.1.0" \
  "tenacity>=9.1.4" \
  "python-dotenv>=1.0.0" \
  "rank-bm25>=0.2.2" \
  "scipy>=1.14.0" \
  "websockets>=13.0"

if [[ -n "${TAU2_ROOT}" && -d "${TAU2_ROOT}" ]]; then
  echo "Installing local tau2 from ${TAU2_ROOT}"
  uv pip install --python "${ACE_ROOT}/.venv/bin/python" -e "${TAU2_ROOT}[knowledge]"
else
  echo "Skipping local tau2 install: AUTOHARNESS_TAU2_ROOT not set and ../tau2-bench not found"
fi

uv pip install --python "${ACE_ROOT}/.venv/bin/python" -e "${ACE_ROOT}" --no-deps

echo
echo "ACE venv ready at ${ACE_ROOT}/.venv"
echo "Interpreter: ${ACE_ROOT}/.venv/bin/python"
