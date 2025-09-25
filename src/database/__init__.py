# src/database/__init__.py
from database.repository import SignalRepository  # ✅ Без точек

__all__ = ["SignalRepository"]