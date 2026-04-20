#!/usr/bin/env bash
# pack-for-work.sh — Encode a directory or zip into a plain .txt file
# that survives corporate email filters.
# Usage: ./pack-for-work.sh <source_dir_or_zip> [output_name]
# Output: <output_name>.b64.txt — email this as a plain text attachment

set -euo pipefail

SOURCE="${1:-}"
OUTNAME="${2:-payload}"
OUTFILE="${OUTNAME}.b64.txt"
TMPZIP="/tmp/${OUTNAME}_pack_$$.zip"

if [[ -z "$SOURCE" ]]; then
    echo "Usage: $0 <source_dir_or_zip> [output_name]"
    exit 1
fi

echo "=== pack-for-work ==="

# If source is already a zip, use it directly
if [[ "$SOURCE" == *.zip ]]; then
    cp "$SOURCE" "$TMPZIP"
else
    echo "Zipping $SOURCE..."
    zip -r "$TMPZIP" "$SOURCE" -x "*.pyc" -x "*/__pycache__/*" -x "*/.git/*" -x "*/node_modules/*"
fi

echo "Encoding to base64..."
base64 "$TMPZIP" > "$OUTFILE"

SIZE=$(wc -c < "$OUTFILE")
echo ""
echo "✓ Output: $OUTFILE ($SIZE bytes)"
echo "✓ Email this file as a plain .txt attachment"
echo "✓ Recipient runs: bash unpack-from-work.sh $OUTFILE"
echo ""

rm -f "$TMPZIP"
