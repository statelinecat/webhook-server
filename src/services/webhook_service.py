# src/services/webhook_service.py
import aiohttp
import asyncio
from typing import Tuple
from config.settings import settings
from core.exceptions import WebhookSendException


class WebhookClient:
    """Клиент для надёжной отправки вебхуков в Finandy"""

    def __init__(self, timeout: int = None):
        self.timeout = timeout or settings.request_timeout
        self._session = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Закрыть сессию при завершении работы"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def send(self, url: str, data: dict) -> Tuple[int, str]:
        """
        Отправить POST-запрос на указанный URL с JSON-данными.

        Возвращает: (status_code, response_text)
        Выбрасывает: WebhookSendException в случае ошибки
        """
        try:
            async with self.session.post(
                    url,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    headers={"Content-Type": "application/json"}
            ) as response:
                response_text = await response.text()
                return response.status, response_text

        except asyncio.TimeoutError:
            raise WebhookSendException(f"Timeout after {self.timeout} seconds")

        except aiohttp.ClientError as e:
            raise WebhookSendException(f"Client error: {str(e)}")

        except Exception as e:
            raise WebhookSendException(f"Unexpected error: {str(e)}")

    async def send_webhook(self, symbol: str, signal_data: dict) -> bool:
        """Утилита для отправки сигнала по символу (для тестов или внутреннего использования)"""
        from config import webhooks

        webhook_url = webhooks.get_webhook_url(symbol)
        if not webhook_url or not webhooks.is_valid_webhook(webhook_url):
            return False

        try:
            status_code, _ = await self.send(webhook_url, signal_data)
            return status_code == 200
        except WebhookSendException:
            return False