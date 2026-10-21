#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 STARTER_0000.rad ENGINE_0001.rad [threads]" >&2
  exit 2
fi

source scripts/env_opencourant.sh

STARTER_INPUT="$(realpath "$1")"
ENGINE_INPUT="$(realpath "$2")"
THREADS="${3:-4}"

if [[ ! -f "$STARTER_INPUT" ]]; then
  echo "Starter input not found: $STARTER_INPUT" >&2
  exit 3
fi
if [[ ! -f "$ENGINE_INPUT" ]]; then
  echo "Engine input not found: $ENGINE_INPUT" >&2
  exit 4
fi

STARTER_EXE="$(find "$OPENCOURANT_PATH/exec" -maxdepth 1 -type f -name 'starter_linux*' | sort | head -n 1)"
ENGINE_EXE="$(find "$OPENCOURANT_PATH/exec" -maxdepth 1 -type f -name 'engine_linux*' ! -name '*ompi*' | sort | head -n 1)"

echo "Starter : $STARTER_EXE"
echo "Engine  : $ENGINE_EXE"
echo "Threads : $THREADS"

WORKDIR="$(dirname "$STARTER_INPUT")"
cd "$WORKDIR"

"$STARTER_EXE" -i "$STARTER_INPUT" -nt "$THREADS" -np 1
"$ENGINE_EXE" -i "$ENGINE_INPUT" -nt "$THREADS"

echo "OpenCourant run completed."
