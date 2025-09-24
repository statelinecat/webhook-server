import asyncio
import time
from typing import Dict
from config.settings import settings
from config import webhooks
from database.repository import SignalRepository  # ← ИСПРАВЛЕННЫЙ ИМПОРТ
from services.webhook_service import WebhookClient
from core.exceptions import WebhookSendException


class SignalWorker:
    """Воркер для обработки сигналов конкретного инструмента"""

    def __init__(self, symbol: str, queue_manager: 'QueueManager',
                 repository: SignalRepository, webhook_client: WebhookClient):
        self.symbol = symbol
        self.queue_manager = queue_manager
        self.repository = repository
        self.webhook_client = webhook_client
        self.last_sent = 0

    async def run(self) -> None:
        """Запустить воркер"""
        print(f"🚀 Воркер запущен для {self.symbol}")

        while True:
            try:
                data, original_data, name, created_at = await self.queue_manager.get(self.symbol)
                await self._process_signal(data, original_data, name, created_at)
                self.queue_manager.task_done(self.symbol)
            except Exception as e:
                print(f"[{self.symbol}] ❌ Ошибка воркера: {e}")

    async def _process_signal(self, data: Dict, original_data: Dict,
                              name: str, created_at: float) -> None:
        """Обработать сигнал"""
        webhook_url = webhooks.get_webhook_url(name)

        if not webhook_url:
            error_msg = f"No webhook found for: {name}"
            self._log_error(name, original_data, created_at, error_msg)
            return

        await self._rate_limit()

        try:
            status_code, response_text = await self.webhook_client.send(webhook_url, original_data)
            await self._handle_response(name, original_data, created_at, status_code, response_text)
        except WebhookSendException as e:
            self._log_error(name, original_data, created_at, str(e))

    async def _rate_limit(self) -> None:
        """Ограничение частоты запросов"""
        now = time.time()
        delay = settings.rate_limit_ms / 1000  # Convert to seconds

        if now - self.last_sent < delay:
            await asyncio.sleep(delay - (now - self.last_sent))

        self.last_sent = time.time()

    async def _handle_response(self, name: str, original_data: Dict, created_at: float,
                               status_code: int, response_text: str) -> None:
        """Обработать ответ от вебхука"""
        sent_at = time.time()

        if status_code == 200:
            status = f"sent {status_code}"
            print(f"[{self.symbol}] ✅ Успешно отправлен: {status_code}")
        else:
            status = f"error {status_code}"
            print(f"[{self.symbol}] ⚠️ Ошибка сервера: {status_code}")

        self.repository.log_signal(
            self.symbol, name, original_data, status, created_at,
            sent_at, status_code, response_text
        )

    def _log_error(self, name: str, original_data: Dict,
                   created_at: float, error_msg: str) -> None:
        """Записать ошибку в лог"""
        self.repository.log_signal(
            self.symbol, name, original_data, f"error {error_msg}",
            created_at, None, None, error_msg
        )
        print(f"[{self.symbol}] ❌ {error_msg}")