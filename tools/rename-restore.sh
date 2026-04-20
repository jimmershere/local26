#!/usr/bin/env bash
# rename-restore.sh — Rename code files to/from .txt for email attachment
# Mode 1 (pack):    ./rename-restore.sh pack <source_dir>   → renames all .py .js .sh etc to .txt
# Mode 2 (restore): ./rename-restore.sh restore <source_dir> → renames .txt back to original extensions
# Include THIS script in the zip so recipient can restore.

set -euo pipefail

MODE="${1:-}"
DIR="${2:-.}"

# Extensions to rename
EXTS=(py js ts sh bash json yaml yml toml cfg ini md html css)

if [[ "$MODE" == "pack" ]]; then
    echo "=== Packing: renaming code files to .txt ==="
    find "$DIR" -type f | while read -r f; do
        for ext in "${EXTS[@]}"; do
            if [[ "$f" == *".${ext}" ]]; then
                mv "$f" "${f}.txt"
                echo "  $f → ${f}.txt"
                break
            fi
        done
    done
    echo "✓ Done. Zip this folder and email it."

elif [[ "$MODE" == "restore" ]]; then
    echo "=== Restoring: renaming .ext.txt back to .ext ==="
    find "$DIR" -type f -name "*.txt" | while read -r f; do
        for ext in "${EXTS[@]}"; do
            if [[ "$f" == *".${ext}.txt" ]]; then
                original="${f%.txt}"
                mv "$f" "$original"
                echo "  $f → $original"
                break
            fi
        done
    done
    echo "✓ Done. All files restored."

else
    echo "Usage:"
    echo "  $0 pack <source_dir>     — rename code files to .txt before zipping"
    echo "  $0 restore <source_dir>  — restore .txt files back to original extensions"
fi
