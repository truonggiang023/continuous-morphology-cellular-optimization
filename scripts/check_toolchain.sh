#!/usr/bin/env bash
set -euo pipefail

source scripts/env_opencourant.sh

echo "================ OpenFEM toolchain check ================"
echo "Architecture       : $(uname -m)"
echo "Python             : $(python3 --version)"
echo "Gmsh               : $(gmsh --version)"
echo "OPENCOURANT_PATH   : $OPENCOURANT_PATH"
echo "RAD_CFG_PATH       : $RAD_CFG_PATH"

STARTER="$(find "$OPENCOURANT_PATH/exec" -maxdepth 1 -type f -name 'starter_linux*' | sort | head -n 1 || true)"
ENGINE="$(find "$OPENCOURANT_PATH/exec" -maxdepth 1 -type f -name 'engine_linux*' ! -name '*ompi*' | sort | head -n 1 || true)"

if [[ -z "$STARTER" || -z "$ENGINE" ]]; then
  echo "ERROR: starter or engine executable not found." >&2
  exit 1
fi

echo "Starter            : $STARTER"
echo "Engine             : $ENGINE"
echo "=========================================================="
