# src/check_structure.py
import os

print("=== Project Structure Check ===")

# Проверка существования файлов
files_to_check = [
    'core/__init__.py',
    'core/models.py',
    'core/exceptions.py',
    'api/__init__.py',
    'api/endpoints.py',
    'main.py'
]

for file in files_to_check:
    exists = os.path.exists(file)
    print(f"{'✅' if exists else '❌'} {file}: {'Exists' if exists else 'Missing'}")

print("\n=== core/__init__.py content ===")
try:
    with open('core/__init__.py', 'r') as f:
        content = f.read()
        print(content)
except Exception as e:
    print(f"Error reading core/__init__.py: {e}")

print("\n=== Import test ===")
try:
    from core.models import TradingSignal
    print("✅ TradingSignal imports successfully")
except ImportError as e:
    print(f"❌ TradingSignal import failed: {e}")

try:
    from core.exceptions import QueueNotFoundException
    print("✅ QueueNotFoundException imports successfully")
except ImportError as e:
    print(f"❌ QueueNotFoundException import failed: {e}")