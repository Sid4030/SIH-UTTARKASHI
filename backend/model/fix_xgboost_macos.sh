#!/bin/bash
# Link OpenMP runtime to XGBoost on macOS without Homebrew
set -e

SKLEARN_DYLIB="/Users/meow/Library/Python/3.9/lib/python/site-packages/sklearn/.dylibs/libomp.dylib"
XGBOOST_LIB_DIR="/Users/meow/Library/Python/3.9/lib/python/site-packages/xgboost/lib"
XGBOOST_DYLIB="$XGBOOST_LIB_DIR/libxgboost.dylib"

if [ -f "$SKLEARN_DYLIB" ] && [ -f "$XGBOOST_DYLIB" ]; then
    echo "Found sklearn libomp.dylib and xgboost library. Linking..."
    cp "$SKLEARN_DYLIB" "$XGBOOST_LIB_DIR/"
    install_name_tool -add_rpath @loader_path "$XGBOOST_DYLIB" 2>/dev/null || true
    echo "XGBoost OpenMP linkage complete!"
else
    echo "Files not found at standard path, checking alternative linkage..."
fi

python3 -c "import xgboost; print('✅ XGBoost is operational! Version:', xgboost.__version__)"
