#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SOURCE_DIR_ARG="${1:-}"
SOURCE_NAME="_resume.tex"
OUTPUT_NAME="Morgan_Le_Resume.pdf"
SHARED_LATEX_DIR="$REPO_ROOT/shared/latex"
NORMALIZER="$REPO_ROOT/scripts/normalize_pdf.py"

if [[ -z "$SOURCE_DIR_ARG" || $# -gt 1 ]]; then
  echo "Usage: $0 <resume-folder>" >&2
  echo "Example: $0 pre-made/software-engineer" >&2
  echo "The output filename is always $OUTPUT_NAME." >&2
  exit 2
fi

REQUESTED_DIR="$(cd "$REPO_ROOT/$SOURCE_DIR_ARG" && pwd -P)"
case "$REQUESTED_DIR" in
  "$REPO_ROOT"|"$REPO_ROOT"/*) ;;
  *)
    echo "Resume folder must be inside $REPO_ROOT." >&2
    exit 2
    ;;
esac

if [[ -f "$REQUESTED_DIR/$SOURCE_NAME" ]]; then
  SOURCE_DIR="$REQUESTED_DIR"
elif [[ -f "$REQUESTED_DIR/Jake/$SOURCE_NAME" ]]; then
  SOURCE_DIR="$REQUESTED_DIR/Jake"
else
  echo "Resume source not found in $REQUESTED_DIR or its default Jake folder." >&2
  exit 2
fi

if [[ ! -d "$SHARED_LATEX_DIR" ]]; then
  echo "Shared LaTeX support directory not found: $SHARED_LATEX_DIR" >&2
  exit 2
fi

if [[ ! -f "$NORMALIZER" ]]; then
  echo "PDF normalizer not found: $NORMALIZER" >&2
  exit 2
fi

OUTPUT_PATH="$SOURCE_DIR/$OUTPUT_NAME"
BUILD_DIR="$(mktemp -d /tmp/morgan-resume-build.XXXXXX)"

cleanup() {
  case "$BUILD_DIR" in
    /tmp/morgan-resume-build.*) rm -rf -- "$BUILD_DIR" ;;
  esac
}
trap cleanup EXIT

if [[ -n "${RESUME_TECTONIC_BIN:-}" ]]; then
  TECTONIC_BIN="$RESUME_TECTONIC_BIN"
elif command -v tectonic >/dev/null 2>&1; then
  TECTONIC_BIN="$(command -v tectonic)"
else
  echo "Tectonic is required. Install it with: brew install tectonic" >&2
  exit 2
fi

cp -R "$SHARED_LATEX_DIR/." "$BUILD_DIR/"
cp "$SOURCE_DIR/$SOURCE_NAME" "$BUILD_DIR/$SOURCE_NAME"

(
  cd "$BUILD_DIR"
  "$TECTONIC_BIN" --keep-logs --outdir "$BUILD_DIR" "$SOURCE_NAME"
)

if [[ -n "${RESUME_PYTHON_BIN:-}" ]]; then
  PYTHON_BIN="$RESUME_PYTHON_BIN"
elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "Python 3 is required for PDF compatibility normalization." >&2
  exit 2
fi

RAW_PDF="$BUILD_DIR/${SOURCE_NAME%.tex}.pdf"
NORMALIZED_PDF="$BUILD_DIR/$OUTPUT_NAME"
"$PYTHON_BIN" "$NORMALIZER" "$RAW_PDF" "$NORMALIZED_PDF"

cp "$NORMALIZED_PDF" "$OUTPUT_PATH"
echo "Created $OUTPUT_PATH"
