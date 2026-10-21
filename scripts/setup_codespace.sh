#!/usr/bin/env bash
set -euo pipefail

echo "==> Preparing system package sources"

# Some Codespaces/devcontainer images carry an old Yarn APT source whose
# signing key has expired or is missing. Yarn is unrelated to this project,
# but that broken source makes *every* apt-get update fail before we can
# install Gmsh. Disable only that unrelated source when present.
for src in /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
  [[ -f "$src" ]] || continue
  if grep -qs "dl.yarnpkg.com" "$src"; then
    echo "==> Disabling unrelated broken Yarn APT source: $src"
    sudo mv "$src" "$src.disabled"
  fi
done

echo "==> Installing system dependencies"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
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

CACHE_DIR="$HOME/.cache/opencourant"
EXTRACT_DIR="$HOME/.local/opencourant-extracted"
LINK_PATH="$HOME/.local/OpenCourant"
ZIP_PATH="$CACHE_DIR/$ASSET"
mkdir -p "$CACHE_DIR" "$HOME/.local"

echo "==> Downloading latest OpenCourant asset: $ASSET"
rm -f "$ZIP_PATH"

# Prefer GitHub CLI inside Codespaces because it uses the authenticated
# GitHub session and avoids browser download restrictions on the local PC.
if command -v gh >/dev/null 2>&1; then
  gh release download \
    --repo OpenCourant/OpenCourant \
    --pattern "$ASSET" \
    --dir "$CACHE_DIR" \
    --clobber
else
  API="https://api.github.com/repos/OpenCourant/OpenCourant/releases/latest"
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
fi

if [[ ! -s "$ZIP_PATH" ]]; then
  echo "OpenCourant download failed: $ZIP_PATH is missing or empty." >&2
  exit 3
fi

echo "==> Extracting OpenCourant"
rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"
unzip -q "$ZIP_PATH" -d "$EXTRACT_DIR"

STARTER="$(find "$EXTRACT_DIR" -type f -name 'starter_linux*' | head -n 1 || true)"
if [[ -z "$STARTER" ]]; then
  echo "Could not locate OpenCourant starter executable after extraction." >&2
  echo "Extracted files (first 50):"
  find "$EXTRACT_DIR" -maxdepth 4 -type f | head -n 50
  exit 4
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
