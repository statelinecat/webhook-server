# src/debug_imports.py
import os
import sys

print("=== Debug Imports ===")
print("Current directory:", os.getcwd())
print("Python path:", sys.path)

print("\n=== Checking core module ===")
try:
    import core
    print("core module found")
    print("core contents:", dir(core))
except ImportError as e:
    print("core import error:", e)

print("\n=== Checking core.models ===")
try:
    import core.models
    print("core.models found")
    print("core.models contents:", dir(core.models))
except ImportError as e:
    print("core.models import error:", e)

print("\n=== Direct import test ===")
try:
    from core.models import TradingSignal
    print("✅ Direct import from core.models works")
except ImportError as e:
    print("❌ Direct import failed:", e)