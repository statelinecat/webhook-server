import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from config import webhooks
from database.repository import SignalRepository
from services.queue_service import QueueManager
from services.webhook_service import WebhookClient
from services.worker_service import SignalWorker
from api.endpoints import router as api_router


def handle_shutdown(signum, frame):
    """Обработчик сигналов остановки"""
    print(f"🛑 Получен сигнал {signum}. Завершаем работу...")
    sys.exit(0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    workers = []
    worker_tasks = []

    try:
        # Инициализация зависимостей
        repository = SignalRepository()
        queue_manager = QueueManager()
        webhook_client = WebhookClient()

        # Инициализация БД
        repository.init_db()

        # Запуск воркеров
        for symbol in webhooks.get_supported_instruments():
            try:
                worker = SignalWorker(symbol, queue_manager, repository, webhook_client)
                workers.append(worker)
                task = asyncio.create_task(worker.run())
                worker_tasks.append(task)
                print(f"✅ Воркер запущен для {symbol}")
            except Exception as e:
                print(f"❌ Ошибка запуска воркера для {symbol}: {e}")

        # Сохраняем в состоянии приложения
        app.state.repository = repository
        app.state.queue_manager = queue_manager
        app.state.webhook_client = webhook_client
        app.state.workers = workers
        app.state.worker_tasks = worker_tasks

        print(f"🚀 Сервер запущен. Обрабатываем {len(workers)}/{len(webhooks.get_supported_instruments())} инструментов")
        print(f"🌐 Документация: http://0.0.0.0:{settings.port}/docs")

        yield

    except Exception as e:
        print(f"❌ Критическая ошибка при запуске: {e}")
        raise

    finally:
        # Graceful shutdown
        print("🛑 Останавливаем воркеры...")
        for task in worker_tasks:
            task.cancel()

        # Ждем завершения с таймаутом
        if worker_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*worker_tasks, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                print("⚠️ Таймаут при остановке воркеров")

        print("✅ Все воркеры остановлены")


def create_app() -> FastAPI:
    """Фабрика приложения"""
    app = FastAPI(
        lifespan=lifespan,
        title="Webhook Proxy Server",
        version="1.0",
        description="Прокси-сервер для обработки торговых сигналов между TradingView и Finandy",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Для продакшена укажите конкретные домены
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Подключаем роутеры
    app.include_router(api_router, prefix="/api/v1")

    # Корневой эндпоинт для проверки здоровья
    @app.get("/")
    async def root():
        return {
            "status": "running",
            "service": "webhook-proxy",
            "version": "1.0",
            "docs": "/docs"
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    # Регистрируем обработчики сигналов для graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Конфигурация для продакшена
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.port,
        log_level="info"
    )