import asyncio
import time
import sqlite3
import os
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import httpx

# --- Конфигурация ---
DB_PATH = os.getenv("DB_PATH", "signals.db")
PORT = int(os.getenv("PORT", 8001))


# --- Модели для сигналов ---
class CloseOrder(BaseModel):
    action: str
    decrease: Dict[str, Any]
    checkProfit: bool
    price: str


class OpenOrder(BaseModel):
    amountType: str
    amount: str
    enabled: bool


class DCAOrder(BaseModel):
    amountType: str
    amount: str
    checkProfit: bool


class TPOrder(BaseModel):
    price: str
    piece: str


class TPConfig(BaseModel):
    orders: List[TPOrder]
    update: bool


class SLConfig(BaseModel):
    price: str
    update: bool


class TradingSignal(BaseModel):
    name: str
    secret: str
    side: str
    symbol: str
    close: CloseOrder
    open: OpenOrder
    dca: DCAOrder
    tp: TPConfig
    sl: SLConfig


# --- Полный список инструментов ---
INSTRUMENTS = [
    "1MBABYDOGEUSDT", "1MBABYDOGEUSDTS",
    "1000CATUSDT", "1000CATUSDTS",
    "1000CHEEMSUSDT", "1000CHEEMSUSDTS",
    "1000PEPEUSDT", "1000PEPEUSDTS",
    "1000RATSUSDT", "1000RATSUSDTS",
    "1000SATSUSDT", "1000SATSUSDTS",
    "1000WHYUSDT", "1000WHYUSDTS",
    "B3USDT", "B3USDTS",
    "BANANAS31USDT", "BANANAS31USDTS",
    "BEAMXUSDT", "BEAMXUSDTS",
    "BOMEUSDT", "BOMEUSDTS",
    "BROCCOLIF3BUSDT", "BROCCOLIF3BUSDTS",
    "CELRUSDT", "CELRUSDTS",
    "CKBUSDT", "CKBUSDTS",
    "COSUSDT", "COSUSDTS",
    "DEGENUSDT", "DEGENUSDTS",
    "DENTUSDT", "DENTUSDTS",
    "DMCUSDT", "DMCUSDTS",
    "DOGSUSDT", "DOGSUSDTS",
    "DOODUSDT", "DOODUSDTS",
    "EPTUSDT", "EPTUSDTS",
    "FUNUSDT", "FUNUSDTS",
    "FUSDT", "FUSDTS",
    "HIPPOUSDT", "HIPPOUSDTS",
    "HMSTRUSDT", "HMSTRUSDTS",
    "HOTUSDT", "HOTUSDTS",
    "IOSTUSDT", "IOSTUSDTS",
    "LEVERUSDT", "LEVERUSDTS",
    "MEMEUSDT", "MEMEUSDTS",
    "MEWUSDT", "MEWUSDTS",
    "NEIROUSDT", "NEIROUSDTS",
    "NKNUSDT", "NKNUSDTS",
    "NOTUSDT", "NOTUSDTS",
    "ONEUSDT", "ONEUSDTS",
    "PUMPUSDT", "PUMPUSDTS",
    "REZUSDT", "REZUSDTS",
    "RSRUSDT", "RSRUSDTS",
    "SPELLUSDT", "SPELLUSDTS",
    "SWELLUSDT", "SWELLUSDTS",
    "TAGUSDT", "TAGUSDTS",
    "TLMUSDT", "TLMUSDTS",
    "TURBOUSDT", "TURBOUSDTS",
    "VTHOUSDT", "VTHOUSDTS",
    "XVGUSDT", "XVGUSDTS"
]

# --- Вебхуки для каждого инструмента ---
FINANDY_WEBHOOKS = {
    "1MBABYDOGEUSDT": "https://hook.finandy.com/TuaL5bAQjTO2kP4trlUK",
    "1MBABYDOGEUSDTS": "https://hook.finandy.com/09V1WmbUktZCq_8trlUK",
    "1000CATUSDT": "https://hook.finandy.com/iFh_Ic-r0LeOFkz5rlUK",
    "1000CATUSDTS": "https://hook.finandy.com/dPpzETmR50zRbU35rlUK",
    "1000CHEEMSUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "1000CHEEMSUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "1000PEPEUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "1000PEPEUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "1000RATSUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "1000RATSUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "1000SATSUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "1000SATSUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "1000WHYUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "1000WHYUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "B3USDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "B3USDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "BANANAS31USDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "BANANAS31USDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "BEAMXUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "BEAMXUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "BOMEUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "BOMEUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "BROCCOLIF3BUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "BROCCOLIF3BUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "CELRUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "CELRUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "CKBUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "CKBUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "COSUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "COSUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "DEGENUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "DEGENUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "DENTUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "DENTUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "DMCUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "DMCUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "DOGSUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "DOGSUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "DOODUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "DOODUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "EPTUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "EPTUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "FUNUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "FUNUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "FUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "FUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "HIPPOUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "HIPPOUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "HMSTRUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "HMSTRUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "HOTUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "HOTUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "IOSTUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "IOSTUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "LEVERUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "LEVERUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "MEMEUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "MEMEUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "MEWUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "MEWUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "NEIROUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "NEIROUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "NKNUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "NKNUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "NOTUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "NOTUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "ONEUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "ONEUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "PUMPUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "PUMPUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "REZUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "REZUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "RSRUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "RSRUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "SPELLUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "SPELLUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "SWELLUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "SWELLUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "TAGUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "TAGUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "TLMUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "TLMUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "TURBOUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "TURBOUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "VTHOUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "VTHOUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "XVGUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "XVGUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX"
}

# Заполняем недостающие вебхуки заглушками
for symbol in INSTRUMENTS:
    if symbol not in FINANDY_WEBHOOKS:
        FINANDY_WEBHOOKS[symbol] = f"https://hook.finandy.com/PLACEHOLDER_{symbol}"

# Очереди для каждого инструмента
queues = {symbol: asyncio.Queue() for symbol in INSTRUMENTS}


# --- Работа с БД ---
def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            data TEXT,
            status TEXT,
            created_at REAL,
            sent_at REAL,
            response_code INTEGER,
            response_text TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_signal(symbol: str, data: dict, status: str, created_at: float,
               sent_at: float | None = None, response_code: int = None,
               response_text: str = None):
    """Логирование сигнала в БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO signals 
        (symbol, data, status, created_at, sent_at, response_code, response_text) 
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (symbol, str(data), status, created_at, sent_at, response_code, response_text)
    )
    conn.commit()
    conn.close()


def get_logs(symbol: str, limit: int = 20):
    """Получение логов из БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if symbol == "all":
        cursor.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,))
    else:
        cursor.execute(
            "SELECT * FROM signals WHERE symbol=? ORDER BY id DESC LIMIT ?",
            (symbol, limit)
        )
    rows = cursor.fetchall()
    conn.close()
    return rows


# --- Воркеры для отправки сигналов ---
async def worker(symbol: str):
    """Обработка очереди сигналов для конкретного инструмента"""
    last_sent = 0
    webhook_url = FINANDY_WEBHOOKS[symbol]

    print(f"🚀 Воркер запущен для {symbol} -> {webhook_url}")

    while True:
        data, created_at = await queues[symbol].get()
        now = time.time()

        # Ограничение 300 мс между запросами
        if now - last_sent < 0.3:
            await asyncio.sleep(0.3 - (now - last_sent))

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    webhook_url,
                    json=data,
                    timeout=10.0
                )

                sent_at = time.time()
                response_text = resp.text[:500]

                if resp.status_code == 200:
                    status = f"sent {resp.status_code}"
                    print(f"[{symbol}] ✅ Успешно отправлен: {resp.status_code}")
                else:
                    status = f"error {resp.status_code}"
                    print(f"[{symbol}] ⚠️ Ошибка сервера: {resp.status_code}")

                log_signal(symbol, data, status, created_at, sent_at,
                           resp.status_code, response_text)

        except httpx.TimeoutException:
            error_msg = "Timeout"
            log_signal(symbol, data, f"error {error_msg}", created_at, None,
                       None, error_msg)
            print(f"[{symbol}] ❌ Таймаут при отправке")

        except httpx.RequestError as e:
            error_msg = str(e)
            log_signal(symbol, data, f"error {error_msg}", created_at, None,
                       None, error_msg)
            print(f"[{symbol}] ❌ Ошибка соединения: {e}")

        except Exception as e:
            error_msg = str(e)
            log_signal(symbol, data, f"error {error_msg}", created_at, None,
                       None, error_msg)
            print(f"[{symbol}] ❌ Неожиданная ошибка: {e}")

        last_sent = time.time()
        queues[symbol].task_done()


# --- Lifespan manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    init_db()
    for symbol in queues:
        asyncio.create_task(worker(symbol))
    print(f"🚀 Сервер запущен. Обрабатываем {len(INSTRUMENTS)} инструментов")
    print("📋 Поддерживаемые символы:", INSTRUMENTS)

    yield
    # Shutdown (можно добавить cleanup при необходимости)


# --- FastAPI приложение ---
app = FastAPI(
    lifespan=lifespan,
    title="Webhook Proxy Server",
    version="1.0",
    description="Прокси-сервер для обработки торговых сигналов между TradingView и Finandy"
)


# --- API Endpoints ---
@app.post("/webhook/{symbol}", response_model=dict)
async def webhook(symbol: str, signal: TradingSignal):
    """
    Прием сигналов от TradingView

    - **symbol**: Торговый инструмент (например: 1000CATUSDT)
    - **signal**: Данные торгового сигнала в формате Finandy
    """
    if symbol not in queues:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown symbol {symbol}. Supported symbols: {INSTRUMENTS}"
        )

    # Проверяем что symbol в URL совпадает с symbol в данных
    if signal.symbol != symbol:
        raise HTTPException(
            status_code=400,
            detail=f"Symbol mismatch: URL={symbol}, Data={signal.symbol}"
        )

    created_at = time.time()
    data = signal.dict()

    # Логируем входящий сигнал
    log_signal(symbol, data, "received", created_at)

    # Кладем в очередь на отправку
    await queues[symbol].put((data, created_at))

    print(f"[{symbol}] 📩 Принят сигнал: {signal.side.upper()} для {signal.name}")

    return {
        "status": "accepted",
        "symbol": symbol,
        "queued": True,
        "webhook": FINANDY_WEBHOOKS[symbol],
        "timestamp": created_at
    }


@app.get("/webhooks", response_model=dict)
async def list_webhooks():
    """Получить список всех вебхуков"""
    return {
        "total_instruments": len(INSTRUMENTS),
        "webhooks": {symbol: FINANDY_WEBHOOKS[symbol] for symbol in INSTRUMENTS}
    }


@app.get("/instruments", response_model=dict)
async def list_instruments():
    """Получить список всех инструментов"""
    return {
        "total": len(INSTRUMENTS),
        "instruments": INSTRUMENTS
    }


@app.get("/logs/{symbol}", response_model=List[dict])
async def logs(symbol: str, limit: int = 20):
    """Получить последние сигналы в JSON формате"""
    if symbol != "all" and symbol not in INSTRUMENTS:
        raise HTTPException(status_code=404, detail=f"Unknown symbol {symbol}")

    rows = get_logs(symbol, limit)
    columns = ["id", "symbol", "data", "status", "created_at", "sent_at", "response_code", "response_text"]
    results = [dict(zip(columns, row)) for row in rows]
    return results


@app.get("/logs/html/{symbol}", response_class=HTMLResponse)
async def logs_html(symbol: str, limit: int = 20):
    """Просмотр логов в виде HTML-таблицы"""
    if symbol != "all" and symbol not in INSTRUMENTS:
        return HTMLResponse(content=f"<h1>Unknown symbol: {symbol}</h1>")

    rows = get_logs(symbol, limit)
    columns = ["id", "symbol", "data", "status", "created_at", "sent_at", "response_code", "response_text"]

    html_template = """
    <html>
    <head>
        <title>Webhook Logs</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            h2 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background-color: #007bff; color: white; font-weight: bold; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            tr:hover { background-color: #f1f1f1; }
            .success { color: #28a745; font-weight: bold; }
            .error { color: #dc3545; font-weight: bold; }
            .info { color: #17a2b8; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>📊 Logs for: {symbol}</h2>
            <p class="info">🔄 Total instruments: {total_count}</p>
            <table>
                <tr>{headers}</tr>
                {rows}
            </table>
        </div>
    </body>
    </html>
    """

    headers = "".join(f"<th>{col}</th>" for col in columns)
    rows_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )

    return HTMLResponse(content=html_template.format(
        symbol=symbol,
        total_count=len(INSTRUMENTS),
        headers=headers,
        rows=rows_html
    ))


@app.get("/", response_model=dict)
async def root():
    """Главная страница с информацией о API"""
    return {
        "message": "Webhook Proxy Server for Finandy",
        "version": "1.0",
        "total_instruments": len(INSTRUMENTS),
        "endpoints": {
            "webhook": "POST /webhook/{symbol}",
            "logs": "GET /logs/{symbol}",
            "webhooks_list": "GET /webhooks",
            "instruments_list": "GET /instruments",
            "health_check": "GET /health",
            "docs": "GET /docs",
            "redoc": "GET /redoc"
        }
    }


@app.get("/health", response_model=dict)
async def health_check():
    """Health check endpoint для мониторинга"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "instruments_loaded": len(INSTRUMENTS),
        "queues_active": len([q for q in queues.values() if not q.empty()])
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)