#!/usr/bin/env bash
# unpack-from-work.sh — Decode a .b64.txt file back to the original directory/zip
# Usage: bash unpack-from-work.sh <file.b64.txt> [output_dir]
# Works on Mac, Linux, Windows Git Bash

set -euo pipefail

INFILE="${1:-}"
OUTDIR="${2:-.}"

if [[ -z "$INFILE" || ! -f "$INFILE" ]]; then
    echo "Usage: bash unpack-from-work.sh <file.b64.txt> [output_dir]"
    exit 1
fi

TMPZIP="/tmp/unpacked_$$.zip"
BASENAME=$(basename "$INFILE" .b64.txt)

echo "=== unpack-from-work ==="
echo "Decoding $INFILE..."

# Handle both GNU base64 and macOS base64
if base64 --version 2>/dev/null | grep -q GNU; then
    base64 -d "$INFILE" > "$TMPZIP"
else
    base64 -D -i "$INFILE" -o "$TMPZIP"
fi

echo "Extracting to $OUTDIR/$BASENAME/ ..."
mkdir -p "$OUTDIR/$BASENAME"
unzip -q "$TMPZIP" -d "$OUTDIR/$BASENAME"

echo ""
echo "✓ Extracted to: $OUTDIR/$BASENAME/"
echo "✓ Contents:"
ls "$OUTDIR/$BASENAME/" | head -20

rm -f "$TMPZIP"
