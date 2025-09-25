# src/api/endpoints.py
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


# === Зависимости: используются общие экземпляры из состояния приложения ===

def get_repository(request: Request) -> SignalRepository:
    return request.app.state.repository

def get_queue_manager(request: Request) -> QueueManager:
    return request.app.state.queue_manager

def get_webhook_client(request: Request) -> WebhookClient:
    return request.app.state.webhook_client


# === Эндпоинты ===

@router.post("/webhook", response_model=WebhookResponse)
async def universal_webhook(
    signal: TradingSignal,
    repository: SignalRepository = Depends(get_repository),
    queue_manager: QueueManager = Depends(get_queue_manager),
):
    return await _process_webhook(signal, None, repository, queue_manager)


@router.post("/webhook/{symbol}", response_model=WebhookResponse)
async def webhook_with_symbol(
    symbol: str,
    signal: TradingSignal,
    repository: SignalRepository = Depends(get_repository),
    queue_manager: QueueManager = Depends(get_queue_manager),
):
    return await _process_webhook(signal, symbol, repository, queue_manager)


async def _process_webhook(
    signal: TradingSignal,
    url_symbol: str,
    repository: SignalRepository,
    queue_manager: QueueManager,
) -> WebhookResponse:
    target_symbol = signal.name

    if target_symbol not in webhooks.FINANDY_WEBHOOKS:
        supported_symbols = webhooks.get_supported_instruments()[:10]
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Unknown target symbol '{target_symbol}'",
                "supported_symbols_sample": supported_symbols,
                "total_supported": len(webhooks.get_supported_instruments()),
            },
        )

    print(f"\n📩 Получен сигнал:")
    print(f"   URL symbol: {url_symbol}")
    print(f"   Target symbol from name: {target_symbol}")
    print(f"   Side: {signal.side}")

    created_at = time.time()
    original_data = signal.model_dump()

    log_symbol = url_symbol or "universal"
    repository.log_signal(log_symbol, target_symbol, original_data, "received", created_at)

    queue_symbol = target_symbol
    if queue_symbol not in webhooks.get_supported_instruments():
        queue_symbol = url_symbol
        print(f"⚠️ Очередь для {target_symbol} не найдена, используем {url_symbol}")

    if not queue_symbol or queue_symbol not in webhooks.get_supported_instruments():
        error_msg = f"No queue available for symbol: {target_symbol}"
        repository.log_signal(log_symbol, target_symbol, original_data, f"error {error_msg}", created_at)
        raise HTTPException(status_code=400, detail=error_msg)

    try:
        print(f"📥 Кладу сигнал в очередь: {queue_symbol}")
        await queue_manager.put(
            queue_symbol,
            (original_data.copy(), original_data, target_symbol, created_at),
        )
        print(f"[{queue_symbol}] ✅ Сигнал положен в очередь")
    except QueueNotFoundException as e:
        raise HTTPException(status_code=400, detail=str(e))

    print(f"[{queue_symbol}] 📩 Принят сигнал: {signal.side.upper()} для {target_symbol}")

    return WebhookResponse(
        status="accepted",
        target_symbol=target_symbol,
        queue_symbol=queue_symbol,
        queued=True,
        webhook=webhooks.get_webhook_url(target_symbol),
        timestamp=created_at,
    )


@router.post("/test-webhook/{symbol}")
async def test_webhook(
    symbol: str,
    webhook_client: WebhookClient = Depends(get_webhook_client),
):
    if symbol not in webhooks.FINANDY_WEBHOOKS:
        return {
            "error": "Symbol not found",
            "supported_symbols": webhooks.get_supported_instruments()[:5],
        }

    webhook_url = webhooks.get_webhook_url(symbol)

    if not webhooks.is_valid_webhook(webhook_url):
        return {
            "error": "Webhook URL is a placeholder",
            "url": webhook_url,
            "message": "Please configure a valid webhook URL for this symbol",
        }

    test_data = {
        "name": symbol,
        "secret": "test_secret",
        "symbol": symbol,
        "side": "buy",
        "open": {"enabled": True, "amountType": "sumUsd", "amount": "6"},
        "dca": {"amountType": "sumUsd", "amount": "6", "checkProfit": False},
        "close": {
            "price": "",
            "action": "decrease",
            "decrease": {"type": "posAmountPct", "amount": "1"},
            "checkProfit": True,
        },
        "sl": {"price": "", "update": False},
    }

    try:
        print(f"\n🧪 Тестовый запрос для {symbol}:")
        status_code, response_text = await webhook_client.send(webhook_url, test_data)

        return {
            "status_code": status_code,
            "response": response_text,
            "url": webhook_url,
            "success": status_code == 200,
            "symbol": symbol,
        }

    except Exception as e:
        return {"error": str(e), "url": webhook_url, "symbol": symbol}


@router.get("/webhooks", response_model=Dict[str, Any])
async def list_webhooks():
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
        "placeholder_webhooks": placeholder_webhooks,
    }


@router.get("/instruments", response_model=Dict[str, Any])
async def list_instruments():
    instruments = webhooks.get_supported_instruments()
    return {"total": len(instruments), "instruments": instruments}


@router.get("/logs/{symbol}", response_model=List[Dict[str, Any]])
async def get_logs_json(
    symbol: str,
    limit: int = Query(20, ge=1, le=100),
    repository: SignalRepository = Depends(get_repository),
):
    try:
        rows = repository.get_logs(symbol, limit)
        columns = [
            "id",
            "symbol",
            "name",
            "data",
            "status",
            "created_at",
            "sent_at",
            "response_code",
            "response_text",
        ]

        results = []
        for row in rows:
            result_dict = dict(zip(columns, row))
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
    limit: int = Query(20, ge=1, le=100),
    repository: SignalRepository = Depends(get_repository),
):
    try:
        rows = repository.get_logs(symbol, limit)
        columns = [
            "id",
            "symbol",
            "name",
            "data",
            "status",
            "created_at",
            "sent_at",
            "response_code",
            "response_text",
        ]

        html_template = """<!DOCTYPE html>
<html>
<head>
    <title>Webhook Logs - {symbol}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h2 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; font-size: 14px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; word-break: break-all; }}
        th {{ background-color: #007bff; color: white; font-weight: bold; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        tr:hover {{ background-color: #f1f1f1; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>📊 Webhook Logs: {symbol}</h2>
        <p>🔄 Total instruments: {total_count} | 📋 Showing: {row_count} records</p>
        <table>
            <thead><tr>{headers}</tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
</body>
</html>"""

        headers = "".join(f"<th>{col.upper()}</th>" for col in columns)
        rows_html = "".join(
            f"<tr>{''.join(f'<td>{cell}</td>' for cell in row)}</tr>" for row in rows
        )

        return HTMLResponse(
            content=html_template.format(
                symbol=symbol,
                total_count=len(webhooks.get_supported_instruments()),
                row_count=len(rows),
                headers=headers,
                rows=rows_html,
            )
        )

    except Exception as e:
        error_html = f"<html><body><div style='color: red; padding: 20px;'><h2>Error loading logs</h2><p>{str(e)}</p></div></body></html>"
        return HTMLResponse(content=error_html, status_code=500)


@router.get("/health", response_model=HealthStatus)
async def health_check(
    queue_manager: QueueManager = Depends(get_queue_manager),
):
    placeholder_count = sum(
        1 for url in webhooks.FINANDY_WEBHOOKS.values() if not webhooks.is_valid_webhook(url)
    )

    return HealthStatus(
        status="healthy",
        timestamp=time.time(),
        instruments_loaded=len(webhooks.get_supported_instruments()),
        queues_active=queue_manager.get_active_queues_count(),
        placeholder_webhooks=placeholder_count,
        valid_webhooks=len(webhooks.get_supported_instruments()) - placeholder_count,
    )


@router.get("/", response_model=Dict[str, Any])
async def root():
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
            "docs": "/docs",
        },
    }


@router.get("/stats", response_model=Dict[str, Any])
async def get_stats(
    repository: SignalRepository = Depends(get_repository),
):
    try:
        rows = repository.get_logs("all", 1000)

        if not rows:
            return {"message": "No data available for statistics"}

        stats = {
            "total_signals": len(rows),
            "status_distribution": {},
            "symbol_distribution": {},
            "recent_activity": {},
        }

        for row in rows:
            status = row[4]
            symbol = row[1]
            created_at = row[5]

            stats["status_distribution"][status] = stats["status_distribution"].get(status, 0) + 1
            stats["symbol_distribution"][symbol] = stats["symbol_distribution"].get(symbol, 0) + 1

            if time.time() - created_at <= 86400:
                hour = time.strftime("%H:00", time.localtime(created_at))
                stats["recent_activity"][hour] = stats["recent_activity"].get(hour, 0) + 1

        stats["status_distribution"] = dict(
            sorted(stats["status_distribution"].items(), key=lambda x: x[1], reverse=True)
        )
        stats["symbol_distribution"] = dict(
            sorted(stats["symbol_distribution"].items(), key=lambda x: x[1], reverse=True)[:10]
        )
        stats["recent_activity"] = dict(sorted(stats["recent_activity"].items()))

        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating stats: {str(e)}")