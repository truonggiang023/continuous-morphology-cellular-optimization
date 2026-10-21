#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing system dependencies"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  curl unzip gmsh ca-certificates

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64)
    ASSET="OpenCourant_linux64.zip"
    ;;
  aarch64|arm64)
    ASSET="OpenCourant_linuxa64.zip"
    ;;
  *)
    echo "Unsupported Codespace architecture: $ARCH" >&2
    exit 2
    ;;
esac

API="https://api.github.com/repos/OpenCourant/OpenCourant/releases/latest"
CACHE_DIR="$HOME/.cache/opencourant"
EXTRACT_DIR="$HOME/.local/opencourant-extracted"
LINK_PATH="$HOME/.local/OpenCourant"
ZIP_PATH="$CACHE_DIR/$ASSET"

mkdir -p "$CACHE_DIR" "$HOME/.local"

echo "==> Resolving latest OpenCourant release asset: $ASSET"
URL="$(
  curl -fsSL "$API" | python3 -c '
import json, sys
asset = sys.argv[1]
data = json.load(sys.stdin)
for item in data.get("assets", []):
    if item.get("name") == asset:
        print(item["browser_download_url"])
        break
else:
    raise SystemExit("Requested asset was not found in the latest release")
' "$ASSET"
)"

echo "==> Downloading $URL"
curl -fL --retry 3 --retry-delay 2 -o "$ZIP_PATH" "$URL"

echo "==> Extracting OpenCourant"
rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"
unzip -q "$ZIP_PATH" -d "$EXTRACT_DIR"

STARTER="$(find "$EXTRACT_DIR" -type f -name 'starter_linux*' | head -n 1 || true)"
if [[ -z "$STARTER" ]]; then
  echo "Could not locate OpenCourant starter executable after extraction." >&2
  exit 3
fi

OPENCOURANT_ROOT="$(dirname "$(dirname "$STARTER")")"
ln -sfn "$OPENCOURANT_ROOT" "$LINK_PATH"

chmod +x "$LINK_PATH"/exec/* 2>/dev/null || true

echo "==> OpenCourant installed at: $LINK_PATH"
echo "==> Gmsh version: $(gmsh --version 2>/dev/null || true)"

bash scripts/check_toolchain.sh

echo
echo "Codespace setup complete."
echo "Next:"
echo "  source scripts/env_opencourant.sh"
echo "  bash scripts/check_toolchain.sh"
