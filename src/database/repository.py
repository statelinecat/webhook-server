import sqlite3
import os
from typing import List, Optional


class SignalRepository:
    """Репозиторий для работы с сигналами в БД"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv('DB_PATH', '/app/data/signals.db')
        self.log_limit = int(os.getenv('LOG_LIMIT', '50'))

    def init_db(self) -> None:
        """Инициализация базы данных"""
        # Создаем директорию если не существует
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                name TEXT,
                data TEXT,
                status TEXT,
                created_at REAL,
                sent_at REAL,
                response_code INTEGER,
                response_text TEXT
            )
        """)
        conn.commit()
        conn.close()

    def log_signal(self, symbol: str, name: str, data: dict, status: str,
                   created_at: float, sent_at: Optional[float] = None,
                   response_code: Optional[int] = None, response_text: Optional[str] = None) -> None:
        """Логирование сигнала в БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO signals 
            (symbol, name, data, status, created_at, sent_at, response_code, response_text) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, name, str(data), status, created_at, sent_at, response_code, response_text)
        )
        conn.commit()
        conn.close()

    def get_logs(self, symbol: str, limit: int = None) -> List[tuple]:
        """Получение логов из БД"""
        if limit is None:
            limit = self.log_limit

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if symbol == "all":
            cursor.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,))
        else:
            cursor.execute(
                "SELECT * FROM signals WHERE symbol=? OR name=? ORDER BY id DESC LIMIT ?",
                (symbol, symbol, limit)
            )
        rows = cursor.fetchall()
        conn.close()
        return rows