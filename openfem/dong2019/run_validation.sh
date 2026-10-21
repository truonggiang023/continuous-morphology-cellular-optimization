#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
source scripts/env_opencourant.sh

CASE_DIR="${DONG2019_CASE_DIR:-$REPO_ROOT/openfem/dong2019/generated_natural_dt}"
if [[ -e "$CASE_DIR/starter.log" || -e "$CASE_DIR/engine.log" ]]; then
  echo "Refusing to overwrite an existing solver run: $CASE_DIR" >&2
  echo "Set DONG2019_CASE_DIR to a new empty directory." >&2
  exit 3
fi
mkdir -p "$CASE_DIR"

python3 openfem/dong2019/generate_model.py --out "$CASE_DIR" | tee "$CASE_DIR/generate.log"

STARTER="$OPENCOURANT_PATH/exec/starter_linux64_gf"
ENGINE="$OPENCOURANT_PATH/exec/engine_linux64_gf"

cd "$CASE_DIR"
echo "==> Starter"
"$STARTER" -i Dong2019_thin_0000.rad -nt "${OC_THREADS:-4}" -np 1 2>&1 | tee starter.log

if grep -Eq "[0-9]+ INCOMPATIBLE KINEMATIC CONDITIONS" starter.log; then
  echo "ERROR: Starter reports incompatible kinematic conditions; will not run engine." >&2
  python3 "$REPO_ROOT/openfem/dong2019/physics_audit.py" --case "$CASE_DIR" || true
  exit 4
fi

echo "==> Engine"
"$ENGINE" -i Dong2019_thin_0001.rad -nt "${OC_THREADS:-4}" 2>&1 | tee engine.log

TH_FILE="$(find . -maxdepth 1 -type f -name 'Dong2019_thinT*' | sort | head -n 1 || true)"
TH_CONVERTER="$(find "$OPENCOURANT_PATH/exec" -maxdepth 1 -type f -name 'th_to_csv_linux64*' | sort | head -n 1 || true)"
if [[ -n "$TH_FILE" && -n "$TH_CONVERTER" ]]; then
  "$TH_CONVERTER" "${TH_FILE#./}" 2>&1 | tee th_to_csv.log || true
fi

ANIM_CONVERTER="$(find "$OPENCOURANT_PATH/exec" -maxdepth 1 -type f -name 'anim_to_vtk_linux64*' | sort | head -n 1 || true)"
FIRST_ANIM="$(find . -maxdepth 1 -type f -name 'Dong2019_thinA*' | sort | head -n 1 || true)"
if [[ -n "$FIRST_ANIM" && -n "$ANIM_CONVERTER" ]]; then
  "$ANIM_CONVERTER" "${FIRST_ANIM#./}" 2>&1 | tee anim_to_vtk.log || true
fi

python3 "$REPO_ROOT/openfem/dong2019/postprocess.py" "$CASE_DIR" | tee postprocess.log || true
python3 "$REPO_ROOT/openfem/dong2019/physics_audit.py" --case "$CASE_DIR" | tee physics_audit.log || true

echo "==> Generated result files"
find . -maxdepth 1 -type f -printf '%f\n' | sort
