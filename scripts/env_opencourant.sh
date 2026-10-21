#!/usr/bin/env bash

export OPENCOURANT_PATH="${OPENCOURANT_PATH:-$HOME/.local/OpenCourant}"

if [[ ! -d "$OPENCOURANT_PATH" ]]; then
  echo "OpenCourant not found at $OPENCOURANT_PATH" >&2
  echo "Run: bash scripts/setup_codespace.sh" >&2
  return 1 2>/dev/null || exit 1
fi

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64)
    LIB_ARCH="linux64"
    ;;
  aarch64|arm64)
    LIB_ARCH="linuxa64"
    ;;
  *)
    echo "Unsupported architecture: $ARCH" >&2
    return 2 2>/dev/null || exit 2
    ;;
esac

export RAD_CFG_PATH="$OPENCOURANT_PATH/hm_cfg_files"
export LD_LIBRARY_PATH="$OPENCOURANT_PATH/extlib/hm_reader/$LIB_ARCH:$OPENCOURANT_PATH/extlib/h3d/lib/$LIB_ARCH:${LD_LIBRARY_PATH:-}"
export PATH="$OPENCOURANT_PATH/exec:$PATH"
export KMP_STACKSIZE="${KMP_STACKSIZE:-400m}"
