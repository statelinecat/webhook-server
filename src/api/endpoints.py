# api/endpoints.py
import time
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import HTMLResponse
from config import webhooks
from database.repository import SignalRepository
from services.queue_service import QueueManager
from services.webhook_service import WebhookClient
from core.models import TradingSignal, WebhookResponse, HealthStatus
from core.exceptions import QueueNotFoundException

router = APIRouter()


# Dependency injections
def get_repository() -> SignalRepository:
    return SignalRepository()


def get_queue_manager() -> QueueManager:
    return QueueManager()


def get_webhook_client() -> WebhookClient:
    return WebhookClient()


@router.post("/webhook", response_model=WebhookResponse)
async def universal_webhook(
        signal: TradingSignal,
        repository: SignalRepository = Depends(get_repository),
        queue_manager: QueueManager = Depends(get_queue_manager)
):
    """
    Универсальный вебхук для приема сигналов от TradingView

    - **signal**: Данные торгового сигнала в формате Finandy
    - Автоматически определяет инструмент из поля 'name' сигнала
    """
    return await _process_webhook(signal, None, repository, queue_manager)


@router.post("/webhook/{symbol}", response_model=WebhookResponse)
async def webhook_with_symbol(
        symbol: str,
        signal: TradingSignal,
        repository: SignalRepository = Depends(get_repository),
        queue_manager: QueueManager = Depends(get_queue_manager)
):
    """
    Вебхук с указанием символа в URL (для обратной совместимости)

    - **symbol**: Торговый инструмент в URL
    - **signal**: Данные торгового сигнала
    """
    return await _process_webhook(signal, symbol, repository, queue_manager)


async def _process_webhook(
        signal: TradingSignal,
        url_symbol: str,
        repository: SignalRepository,
        queue_manager: QueueManager
) -> WebhookResponse:
    """Обработать входящий вебхук"""
    target_symbol = signal.name

    # Проверяем поддерживается ли символ
    if target_symbol not in webhooks.FINANDY_WEBHOOKS:
        supported_symbols = webhooks.get_supported_instruments()[:10]  # Показываем первые 10
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Unknown target symbol '{target_symbol}'",
                "supported_symbols_sample": supported_symbols,
                "total_supported": len(webhooks.get_supported_instruments())
            }
        )

    # Детальная проверка данных
    print(f"\n📩 Получен сигнал:")
    print(f"   URL symbol: {url_symbol}")
    print(f"   Target symbol from name: {target_symbol}")
    print(f"   Side: {signal.side}")
    print(f"   Full data: {signal.model_dump()}")

    created_at = time.time()
    original_data = signal.model_dump()

    # Логируем получение сигнала
    log_symbol = url_symbol or "universal"
    repository.log_signal(log_symbol, target_symbol, original_data, "received", created_at)

    # Определяем очередь для обработки
    queue_symbol = target_symbol
    if queue_symbol not in webhooks.get_supported_instruments():
        queue_symbol = url_symbol
        print(f"⚠️ Очередь для {target_symbol} не найдена, используем {url_symbol}")

    if not queue_symbol or queue_symbol not in webhooks.get_supported_instruments():
        error_msg = f"No queue available for symbol: {target_symbol}"
        repository.log_signal(log_symbol, target_symbol, original_data, f"error {error_msg}", created_at)
        raise HTTPException(status_code=400, detail=error_msg)

    # Помещаем в очередь на обработку
    try:
        await queue_manager.put(queue_symbol, (
            original_data.copy(), original_data, target_symbol, created_at
        ))
    except QueueNotFoundException as e:
        raise HTTPException(status_code=400, detail=str(e))

    print(f"[{queue_symbol}] 📩 Принят сигнал: {signal.side.upper()} для {target_symbol}")

    return WebhookResponse(
        status="accepted",
        target_symbol=target_symbol,
        queue_symbol=queue_symbol,
        queued=True,
        webhook=webhooks.get_webhook_url(target_symbol),
        timestamp=created_at
    )


@router.post("/test-webhook/{symbol}")
async def test_webhook(
        symbol: str,
        webhook_client: WebhookClient = Depends(get_webhook_client)
):
    """
    Тестовый запрос к Finandy для проверки соединения

    - **symbol**: Торговый инструмент для теста
    """
    if symbol not in webhooks.FINANDY_WEBHOOKS:
        return {"error": "Symbol not found", "supported_symbols": webhooks.get_supported_instruments()[:5]}

    webhook_url = webhooks.get_webhook_url(symbol)

    # Проверяем, не является ли URL заглушкой
    if not webhooks.is_valid_webhook(webhook_url):
        return {
            "error": "Webhook URL is a placeholder",
            "url": webhook_url,
            "message": "Please configure a valid webhook URL for this symbol"
        }

    # Тестовые данные по актуальному шаблону
    test_data = {
        "name": symbol,
        "secret": "test_secret",
        "symbol": symbol,
        "side": "buy",
        "open": {
            "enabled": True,
            "amountType": "sumUsd",
            "amount": "6"
        },
        "dca": {
            "amountType": "sumUsd",
            "amount": "6",
            "checkProfit": False
        },
        "close": {
            "price": "",
            "action": "decrease",
            "decrease": {
                "type": "posAmountPct",
                "amount": "1"
            },
            "checkProfit": True
        },
        "sl": {
            "price": "",
            "update": False
        }
    }

    try:
        print(f"\n🧪 Тестовый запрос для {symbol}:")
        print(f"URL: {webhook_url}")
        print(f"Данные: {test_data}")

        status_code, response_text = await webhook_client.send(webhook_url, test_data)

        result = {
            "status_code": status_code,
            "response": response_text,
            "url": webhook_url,
            "success": status_code == 200,
            "symbol": symbol
        }

        print(f"Результат: {result}")
        return result

    except Exception as e:
        error_result = {
            "error": str(e),
            "url": webhook_url,
            "symbol": symbol
        }
        print(f"Ошибка теста: {error_result}")
        return error_result


@router.get("/webhooks", response_model=Dict[str, Any])
async def list_webhooks():
    """
    Получить список всех вебхуков с разделением на валидные и заглушки
    """
    valid_webhooks = {}
    placeholder_webhooks = {}

    for symbol, url in webhooks.FINANDY_WEBHOOKS.items():
        if webhooks.is_valid_webhook(url):
            valid_webhooks[symbol] = url
        else:
            placeholder_webhooks[symbol] = url

    return {
        "total_instruments": len(webhooks.get_supported_instruments()),
        "valid_webhooks_count": len(valid_webhooks),
        "placeholder_webhooks_count": len(placeholder_webhooks),
        "valid_webhooks": valid_webhooks,
        "placeholder_webhooks": placeholder_webhooks
    }


@router.get("/instruments", response_model=Dict[str, Any])
async def list_instruments():
    """
    Получить список всех поддерживаемых инструментов
    """
    instruments = webhooks.get_supported_instruments()
    return {
        "total": len(instruments),
        "instruments": instruments
    }


@router.get("/logs/{symbol}", response_model=List[Dict[str, Any]])
async def get_logs_json(
        symbol: str,
        limit: int = Query(20, ge=1, le=100, description="Количество записей"),
        repository: SignalRepository = Depends(get_repository)
):
    """
    Получить последние сигналы в JSON формате

    - **symbol**: Инструмент или 'all' для всех инструментов
    - **limit**: Лимит записей (1-100)
    """
    try:
        rows = repository.get_logs(symbol, limit)
        columns = ["id", "symbol", "name", "data", "status", "created_at", "sent_at", "response_code", "response_text"]

        results = []
        for row in rows:
            result_dict = dict(zip(columns, row))
            # Конвертируем временные метки в читаемый формат
            if result_dict["created_at"]:
                result_dict["created_at_readable"] = time.ctime(result_dict["created_at"])
            if result_dict["sent_at"]:
                result_dict["sent_at_readable"] = time.ctime(result_dict["sent_at"])
            results.append(result_dict)

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving logs: {str(e)}")


@router.get("/logs/html/{symbol}", response_class=HTMLResponse)
async def get_logs_html(
        symbol: str,
        limit: int = Query(20, ge=1, le=100, description="Количество записей"),
        repository: SignalRepository = Depends(get_repository)
):
    """
    Просмотр логов в виде HTML-таблицы

    - **symbol**: Инструмент или 'all' для всех инструментов
    - **limit**: Лимит записей (1-100)
    """
    try:
        rows = repository.get_logs(symbol, limit)
        columns = ["id", "symbol", "name", "data", "status", "created_at", "sent_at", "response_code", "response_text"]

        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Webhook Logs - {symbol}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                h2 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
                .filters {{ margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 4px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; font-size: 14px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; word-break: break-all; }}
                th {{ background-color: #007bff; color: white; font-weight: bold; position: sticky; top: 0; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                tr:hover {{ background-color: #f1f1f1; }}
                .success {{ color: #28a745; font-weight: bold; }}
                .error {{ color: #dc3545; font-weight: bold; }}
                .warning {{ color: #ffc107; font-weight: bold; }}
                .info {{ color: #17a2b8; }}
                .timestamp {{ font-size: 12px; color: #666; }}
                .badge {{ padding: 2px 6px; border-radius: 3px; font-size: 12px; }}
                .badge-success {{ background: #d4edda; color: #155724; }}
                .badge-error {{ background: #f8d7da; color: #721c24; }}
                .badge-warning {{ background: #fff3cd; color: #856404; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>📊 Webhook Logs: {symbol}</h2>
                <div class="info">
                    <p>🔄 Total instruments: {total_count} | 📋 Showing: {row_count} records | 🕒 Last update: {current_time}</p>
                </div>
                <div class="filters">
                    <strong>Quick Links:</strong>
                    <a href="/api/v1/logs/html/all?limit=50">All Symbols</a> |
                    <a href="/api/v1/logs/html/SWELLUSDT">SWELLUSDT</a> |
                    <a href="/api/v1/logs/html/BOMEUSDT">BOMEUSDT</a> |
                    <a href="/api/v1/logs/html/1000PEPEUSDT">1000PEPEUSDT</a>
                </div>
                <table>
                    <thead>
                        <tr>
                            {headers}
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """

        headers = "".join(f"<th>{col.upper()}</th>" for col in columns)

        rows_html = ""
        for row in rows:
            row_html = "<tr>"
            for i, cell in enumerate(row):
                cell_class = ""
                if columns[i] == "status":
                    if "sent" in str(cell):
                        cell_class = "class='success'"
                    elif "error" in str(cell):
                        cell_class = "class='error'"
                    elif "received" in str(cell):
                        cell_class = "class='warning'"

                # Форматирование временных меток
                if columns[i] in ["created_at", "sent_at"] and cell:
                    cell = f"<div class='timestamp'>{time.ctime(cell)}</div><div>{cell}</div>"

                row_html += f"<td {cell_class}>{cell}</td>"
            row_html += "</tr>"
            rows_html += row_html

        return HTMLResponse(content=html_template.format(
            symbol=symbol,
            total_count=len(webhooks.get_supported_instruments()),
            row_count=len(rows),
            current_time=time.ctime(),
            headers=headers,
            rows=rows_html
        ))

    except Exception as e:
        error_html = f"""
        <html>
        <body>
            <div style="color: red; padding: 20px;">
                <h2>Error loading logs</h2>
                <p>{str(e)}</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=500)


@router.get("/health", response_model=HealthStatus)
async def health_check(
        queue_manager: QueueManager = Depends(get_queue_manager)
):
    """
    Health check endpoint для мониторинга состояния сервиса
    """
    placeholder_count = sum(
        1 for url in webhooks.FINANDY_WEBHOOKS.values()
        if not webhooks.is_valid_webhook(url)
    )

    return HealthStatus(
        status="healthy",
        timestamp=time.time(),
        instruments_loaded=len(webhooks.get_supported_instruments()),
        queues_active=queue_manager.get_active_queues_count(),
        placeholder_webhooks=placeholder_count,
        valid_webhooks=len(webhooks.get_supported_instruments()) - placeholder_count
    )


@router.get("/", response_model=Dict[str, Any])
async def root():
    """
    Главная страница с информацией о API
    """
    return {
        "message": "Webhook Proxy Server for Finandy",
        "version": "1.0",
        "total_instruments": len(webhooks.get_supported_instruments()),
        "endpoints": {
            "universal_webhook": "POST /api/v1/webhook",
            "webhook_with_symbol": "POST /api/v1/webhook/{symbol}",
            "test_webhook": "POST /api/v1/test-webhook/{symbol}",
            "logs_json": "GET /api/v1/logs/{symbol}",
            "logs_html": "GET /api/v1/logs/html/{symbol}",
            "webhooks_list": "GET /api/v1/webhooks",
            "instruments_list": "GET /api/v1/instruments",
            "health_check": "GET /api/v1/health",
            "docs": "GET /docs",
            "redoc": "GET /redoc"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }
    }


@router.get("/stats", response_model=Dict[str, Any])
async def get_stats(
        repository: SignalRepository = Depends(get_repository)
):
    """
    Получить статистику по обработке сигналов
    """
    try:
        # Получаем последние 1000 записей для статистики
        rows = repository.get_logs("all", 1000)

        if not rows:
            return {"message": "No data available for statistics"}

        stats = {
            "total_signals": len(rows),
            "status_distribution": {},
            "symbol_distribution": {},
            "recent_activity": {}
        }

        # Анализ статусов и символов
        for row in rows:
            status = row[4]  # status column
            symbol = row[1]  # symbol column
            created_at = row[5]  # created_at column

            # Распределение по статусам
            stats["status_distribution"][status] = stats["status_distribution"].get(status, 0) + 1

            # Распределение по символам
            stats["symbol_distribution"][symbol] = stats["symbol_distribution"].get(symbol, 0) + 1

            # Активность по часам (последние 24 часа)
            if time.time() - created_at <= 86400:  # 24 часа
                hour = time.strftime("%H:00", time.localtime(created_at))
                stats["recent_activity"][hour] = stats["recent_activity"].get(hour, 0) + 1

        # Сортируем по количеству
        stats["status_distribution"] = dict(sorted(
            stats["status_distribution"].items(),
            key=lambda x: x[1],
            reverse=True
        ))

        stats["symbol_distribution"] = dict(sorted(
            stats["symbol_distribution"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10])  # Топ 10 символов

        stats["recent_activity"] = dict(sorted(stats["recent_activity"].items()))

        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating stats: {str(e)}")