#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SOURCE_DIR_ARG="${1:-source-of-truth}"
SOURCE_NAME="_resume.tex"
OUTPUT_NAME="Morgan_Le_Resume.pdf"

if (( $# > 1 )); then
  echo "Usage: $0 [resume-folder]" >&2
  echo "The output filename is always $OUTPUT_NAME." >&2
  exit 2
fi

SOURCE_DIR="$(cd "$REPO_ROOT/$SOURCE_DIR_ARG" && pwd -P)"
case "$SOURCE_DIR" in
  "$REPO_ROOT"/*) ;;
  *)
    echo "Resume folder must be inside $REPO_ROOT." >&2
    exit 2
    ;;
esac

if [[ ! -f "$SOURCE_DIR/$SOURCE_NAME" ]]; then
  echo "Resume source not found: $SOURCE_DIR/$SOURCE_NAME" >&2
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

(
  cd "$SOURCE_DIR"
  "$TECTONIC_BIN" --keep-logs --outdir "$BUILD_DIR" "$SOURCE_NAME"
)

cp "$BUILD_DIR/${SOURCE_NAME%.tex}.pdf" "$OUTPUT_PATH"
echo "Created $OUTPUT_PATH"
