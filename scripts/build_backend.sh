#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT/build/backend"

rm -rf "$ROOT/build"
mkdir -p "$BUILD_DIR"

python3 -m pip install -r "$ROOT/backend/requirements.txt" -t "$BUILD_DIR" >/dev/null
cp -R "$ROOT/backend/app" "$BUILD_DIR/"
mkdir -p "$BUILD_DIR/data"
cp "$ROOT/backend/data/synthetic_dataset.json" "$BUILD_DIR/data/"
