import httpx
from typing import Tuple
from config.settings import settings
from core.exceptions import WebhookSendException


class WebhookClient:
    """Клиент для отправки вебхуков"""

    def __init__(self, timeout: float = None):
        self.timeout = timeout or settings.request_timeout

    async def send(self, url: str, data: dict) -> Tuple[int, str]:
        """Отправить вебхук"""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=data, timeout=self.timeout)
                return resp.status_code, resp.text[:500]
        except Exception as e:
            raise WebhookSendException(f"Failed to send webhook: {str(e)}")