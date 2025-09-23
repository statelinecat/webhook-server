import os
from typing import Dict, Any


class Settings:
    """Настройки приложения"""

    def __init__(self):
        self.db_path = os.getenv("DB_PATH", "signals.db")
        self.port = int(os.getenv("PORT", "8001"))
        self.rate_limit_ms = float(os.getenv("RATE_LIMIT_MS", "300"))
        self.request_timeout = float(os.getenv("REQUEST_TIMEOUT", "10.0"))
        self.log_limit = int(os.getenv("LOG_LIMIT", "20"))


settings = Settings()