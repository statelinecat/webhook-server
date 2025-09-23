import asyncio
from typing import Dict, Any
from src.config import webhooks
from src.core import QueueNotFoundException


class QueueManager:
    """Менеджер очередей для каждого инструмента"""

    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}
        self._init_queues()

    def _init_queues(self) -> None:
        """Инициализировать очереди для всех инструментов"""
        for symbol in webhooks.get_supported_instruments():
            self.queues[symbol] = asyncio.Queue()

    async def put(self, symbol: str, item: Any) -> None:
        """Положить элемент в очередь"""
        if symbol not in self.queues:
            raise QueueNotFoundException(f"Queue not found for symbol: {symbol}")
        await self.queues[symbol].put(item)

    async def get(self, symbol: str) -> Any:
        """Получить элемент из очереди"""
        if symbol not in self.queues:
            raise QueueNotFoundException(f"Queue not found for symbol: {symbol}")
        return await self.queues[symbol].get()

    def task_done(self, symbol: str) -> None:
        """Пометить задачу как выполненную"""
        if symbol in self.queues:
            self.queues[symbol].task_done()

    def get_active_queues_count(self) -> int:
        """Получить количество активных очередей"""
        return len([q for q in self.queues.values() if not q.empty()])