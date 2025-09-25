# src/services/worker_service.py
import asyncio
import time
import os
import traceback
from typing import Dict
from config import webhooks
from database.repository import SignalRepository
from services.webhook_service import WebhookClient


class SignalWorker:
    """Воркер для обработки сигналов конкретного инструмента"""

    def __init__(
        self,
        symbol: str,
        queue_manager: "QueueManager",
        repository: SignalRepository,
        webhook_client: WebhookClient,
    ):
        self.symbol = symbol
        self.queue_manager = queue_manager
        self.repository = repository
        self.webhook_client = webhook_client
        self.last_sent = 0
        self.rate_limit_ms = int(os.getenv("RATE_LIMIT_MS", "300"))

    async def run(self) -> None:
        """Основной цикл воркера"""
        print(f"🚀 Воркер запущен для {self.symbol}")

        while True:
            try:
                print(f"[{self.symbol}] ⏳ Ожидаю задачу из очереди...")
                item = await self.queue_manager.get(self.symbol)
                print(f"[{self.symbol}] 🧵 Получен элемент из очереди")

                if isinstance(item, tuple) and len(item) == 4:
                    data, original_data, name, created_at = item
                    await self._process_signal(data, original_data, name, created_at)
                else:
                    error_msg = f"Неверный формат элемента: {type(item)} (len={len(item) if hasattr(item, '__len__') else '?'})"
                    print(f"[{self.symbol}] ❌ {error_msg}")
                    self._log_error("unknown", {}, time.time(), error_msg)

                self.queue_manager.task_done(self.symbol)

            except Exception as e:
                error_msg = f"КРИТИЧЕСКАЯ ОШИБКА: {e}"
                print(f"[{self.symbol}] ❌ {error_msg}")
                traceback.print_exc()

                # Гарантируем вызов task_done, чтобы не заблокировать очередь
                try:
                    self.queue_manager.task_done(self.symbol)
                except ValueError:
                    pass  # уже помечено

    async def _process_signal(
        self,
        data: Dict,
        original_data: Dict,
        name: str,
        created_at: float,
    ) -> None:
        """Отправка сигнала в Finandy"""
        try:
            normalized_name = name.strip().upper()
            print(
                f"[{self.symbol}] 🔎 raw name='{name}' (len={len(name)}), normalized='{normalized_name}'"
            )

            raw_url = webhooks.get_webhook_url(normalized_name)
            webhook_url = raw_url.strip() if raw_url else None

            print(f"[{self.symbol}] 📤 Отправляю на URL: '{webhook_url}'")

            if not webhook_url or not webhooks.is_valid_webhook(webhook_url):
                error_msg = f"Недопустимый вебхук для '{normalized_name}': '{raw_url}'"
                self._log_error(normalized_name, original_data, created_at, error_msg)
                return

            await self._rate_limit()

            status_code, response_text = await self.webhook_client.send(
                webhook_url, original_data
            )
            await self._handle_response(
                normalized_name, original_data, created_at, status_code, response_text
            )

        except Exception as e:
            error_msg = f"Ошибка при отправке сигнала: {e}"
            print(f"[{self.symbol}] ❌ {error_msg}")
            self._log_error(name, original_data, created_at, error_msg)

    async def _rate_limit(self) -> None:
        """Ограничение частоты запросов (минимум 300 мс между отправками)"""
        now = time.time()
        delay = self.rate_limit_ms / 1000.0

        if now - self.last_sent < delay:
            sleep_time = delay - (now - self.last_sent)
            print(f"[{self.symbol}] ⏸️ Спим {sleep_time:.3f} сек")
            await asyncio.sleep(sleep_time)

        self.last_sent = time.time()

    async def _handle_response(
        self,
        name: str,
        original_data: Dict,
        created_at: float,
        status_code: int,
        response_text: str,
    ) -> None:
        """Обработка ответа от Finandy"""
        sent_at = time.time()

        if status_code == 200:
            status = "sent"
            print(f"[{self.symbol}] ✅ Успешно отправлен: {status_code}")
        else:
            status = "error"
            print(
                f"[{self.symbol}] ⚠️ Ошибка: {status_code} — {response_text[:200]}"
            )

        self.repository.log_signal(
            symbol=self.symbol,
            name=name,
            data=original_data,
            status=status,
            created_at=created_at,
            sent_at=sent_at,
            response_code=status_code,
            response_text=response_text,
        )

    def _log_error(
        self,
        name: str,
        original_data: Dict,
        created_at: float,
        error_msg: str,
    ) -> None:
        """Запись ошибки в БД и консоль"""
        self.repository.log_signal(
            symbol=self.symbol,
            name=name,
            data=original_data,
            status="error",
            created_at=created_at,
            sent_at=None,
            response_code=None,
            response_text=error_msg,
        )
        print(f"[{self.symbol}] ❌ Записана ошибка в БД: {error_msg}")
