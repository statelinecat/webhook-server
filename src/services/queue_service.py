import asyncio
from typing import Dict, Any
from config.webhooks import get_supported_instruments  # ✅ Правильный импорт
from core.exceptions import QueueNotFoundException


class QueueManager:
    """Менеджер очередей для обработки сигналов"""

    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}
        self._init_queues()

    def _init_queues(self) -> None:
        """Инициализация очередей для всех инструментов"""
        for symbol in get_supported_instruments():  # ✅ Теперь функция доступна
            self.queues[symbol] = asyncio.Queue()
        print(f"✅ Инициализировано {len(self.queues)} очередей")

    async def put(self, symbol: str, item: Any) -> None:
        """Добавить элемент в очередь"""
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
        return len(self.queues)