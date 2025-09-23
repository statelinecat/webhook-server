import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from config.settings import settings
from config import webhooks
from database.repository import SignalRepository
from services.queue_service import QueueManager
from services.webhook_service import WebhookClient
from services.worker_service import SignalWorker
from api.endpoints import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Инициализация зависимостей
    repository = SignalRepository()
    queue_manager = QueueManager()
    webhook_client = WebhookClient()

    # Инициализация БД
    repository.init_db()

    # Запуск воркеров
    workers = []
    for symbol in webhooks.get_supported_instruments():
        worker = SignalWorker(symbol, queue_manager, repository, webhook_client)
        workers.append(worker)
        asyncio.create_task(worker.run())

    print(f"🚀 Сервер запущен. Обрабатываем {len(webhooks.get_supported_instruments())} инструментов")

    yield

    # Cleanup (если нужно)
    print("🛑 Сервер останавливается")


def create_app() -> FastAPI:
    """Фабрика приложения"""
    app = FastAPI(
        lifespan=lifespan,
        title="Webhook Proxy Server",
        version="1.0",
        description="Прокси-сервер для обработки торговых сигналов"
    )

    # Подключаем роутеры
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)