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
    "1000CHEEMSUSDT": "https://hook.finandy.com/oGKYnFSG8EcfFUUXrlUK",
    "1000CHEEMSUSDTS": "https://hook.finandy.com/qoOE5ObxuJ9fVFoXrlUK",
    "1000PEPEUSDT": "https://hook.finandy.com/0O0Famu12xI3IT7ZrlUK",
    "1000PEPEUSDTS": "https://hook.finandy.com/jmpa1C-AJJB2vD_ZrlUK",
    "1000RATSUSDT": "https://hook.finandy.com/l8JsSEjNzZd0CTzZrlUK",
    "1000RATSUSDTS": "https://hook.finandy.com/QcFtY7IJXTyUuD3ZrlUK",
    "1000SATSUSDT": "https://hook.finandy.com/dMOLd-EEPHPv84ICrlUK",
    "1000SATSUSDTS": "https://hook.finandy.com/y-ihQVJF3B_TYoMCrlUK",
    "1000WHYUSDT": "https://hook.finandy.com/vD6Y-C5FcYVTF5clrlUK",
    "1000WHYUSDTS": "https://hook.finandy.com/HmIQ65EkmnIe0ZQlrlUK",
    "B3USDT": "https://hook.finandy.com/3BD-SHeKq6e-90P5rlUK",
    "B3USDTS": "https://hook.finandy.com/mPjmmUyexOLbrkD5rlUK",
    "BANANAS31USDT": "https://hook.finandy.com/2-mBZ4Wlq8LXvkjyrlUK",
    "BANANAS31USDTS": "https://hook.finandy.com/XgZw33-Ev83LI0nyrlUK",
    "BEAMXUSDT": "https://hook.finandy.com/8WdHzLmWBXeiMKQ1rlUK",
    "BEAMXUSDTS": "https://hook.finandy.com/2GJI0BxNg1tMpqU1rlUK",
    "BOMEUSDT": "https://hook.finandy.com/3Z-yX4GNQeM4qPACrlUK",
    "BOMEUSDTS": "https://hook.finandy.com/_QAms23yOJcA7fECrlUK",
    "BROCCOLIF3BUSDT": "https://hook.finandy.com/w-SfCLt30P5Z9IL4rlUK",
    "BROCCOLIF3BUSDTS": "https://hook.finandy.com/8_YNXd82OWD4y4P4rlUK",
    "CELRUSDT": "https://hook.finandy.com/E2q8PleUx0Clrjn-rlUK",
    "CELRUSDTS": "https://hook.finandy.com/oYAmmkFkTKq5cz7-rlUK",
    "CKBUSDT": "https://hook.finandy.com/mKHiVM5w3QCqJ0f5rlUK",
    "CKBUSDTS": "https://hook.finandy.com/b4zcdlFQlxDkSUT5rlUK",
    "COSUSDT": "https://hook.finandy.com/73omqoO70CTVXvwtrlUK",
    "COSUSDTS": "https://hook.finandy.com/WtiT7uH62Cjicv0trlUK",
    "DEGENUSDT": "https://hook.finandy.com/ZoBsmeXKzXHw3zDerlUK",
    "DEGENUSDTS": "https://hook.finandy.com/g4V2H5Kj6ng4gTHerlUK",
    "DENTUSDT": "https://hook.finandy.com/0WRavvY9biMkgPMtrlUK",
    "DENTUSDTS": "https://hook.finandy.com/ISVXOhtIabW3lfAtrlUK",
    "DMCUSDT": "https://hook.finandy.com/L0m_xYpcNeUuQYH4rlUK",
    "DMCUSDTS": "https://hook.finandy.com/LMXJJ72EFfoE4Ib4rlUK",
    "DOGSUSDT": "https://hook.finandy.com/mxgs6_cHVKKbY8YhrlUK",
    "DOGSUSDTS": "https://hook.finandy.com/rOo7l98bSAg0WschrlUK",
    "DOODUSDT": "https://hook.finandy.com/78octjd6rqzYLjL-rlUK",
    "DOODUSDTS": "https://hook.finandy.com/AuBB1OrOASJHQjP-rlUK",
    "EPTUSDT": "https://hook.finandy.com/ptmBF5EjFn4mqTX8rlUK",
    "EPTUSDTS": "https://hook.finandy.com/tY3hP1Si-ndJ6gr8rlUK",
    "FUNUSDT": "https://hook.finandy.com/FIUiR1IcxvWXg-74rlUK",
    "FUNUSDTS": "https://hook.finandy.com/WeGAwI45NLdRIuz4rlUK",
    "FUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "FUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "HIPPOUSDT": "https://hook.finandy.com/3-VIPLYwTT_XtY7_rlUK",
    "HIPPOUSDTS": "https://hook.finandy.com/6gIuSVhToG1QZ4__rlUK",
    "HMSTRUSDT": "https://hook.finandy.com/C_Exh3VRAtItxcIKrlUK",
    "HMSTRUSDTS": "https://hook.finandy.com/ASzznQdKSKvTm8MKrlUK",
    "HOTUSDT": "https://hook.finandy.com/Qd9tI_oAai-O6yYgrlUK",
    "HOTUSDTS": "https://hook.finandy.com/6amhMUdQG3laMCcgrlUK",
    "IOSTUSDT": "https://hook.finandy.com/TbocZZQl062XLMcCrlUK",
    "IOSTUSDTS": "https://hook.finandy.com/kFrYgZyWL14zqsQCrlUK",
    "LEVERUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "LEVERUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "MEMEUSDT": "https://hook.finandy.com/l_LcerLhBB94_qgWrlUK",
    "MEMEUSDTS": "https://hook.finandy.com/d9S-G2jUp1coJKkWrlUK",
    "MEWUSDT": "https://hook.finandy.com/7O15qM2ob8JQKhwNrlUK",
    "MEWUSDTS": "https://hook.finandy.com/Iglvjwiy5jvnFB0NrlUK",
    "NEIROUSDT": "https://hook.finandy.com/_03ZicWPN_n1DRs0rlUK",
    "NEIROUSDTS": "https://hook.finandy.com/9iD3KT2sKOgGdhg0rlUK",
    "NKNUSDT": "https://hook.finandy.com/P20hv2o1EeOCdVY1rlUK",
    "NKNUSDTS": "https://hook.finandy.com/hnMDzgChuIMYeVc1rlUK",
    "NOTUSDT": "https://hook.finandy.com/1cvd7IPoCnv1Ly0BrlUK",
    "NOTUSDTS": "https://hook.finandy.com/gGyHVX1KYXrmcCcBrlUK",
    "ONEUSDT": "https://hook.finandy.com/Si6RP6TjxZZUIH75rlUK",
    "ONEUSDTS": "https://hook.finandy.com/VAs8O2qqa7jfOX_5rlUK",
    "PUMPUSDT": "https://hook.finandy.com/WXWYMgd52xHsd3__rlUK",
    "PUMPUSDTS": "https://hook.finandy.com/JUMptnFmcCRHfXz_rlUK",
    "REZUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "REZUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "RSRUSDT": "https://hook.finandy.com/KNpzFD8q9jwk_rg1rlUK",
    "RSRUSDTS": "https://hook.finandy.com/fh2GgaLX42ohhLk1rlUK",
    "SPELLUSDT": "https://hook.finandy.com/G6aXQMYcICy7fj8grlUK",
    "SPELLUSDTS": "https://hook.finandy.com/P3un26JCdqtnyTwgrlUK",
    "SWELLUSDT": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "SWELLUSDTS": "https://hook.finandy.com/XXXXXXXXXXXXXXX",
    "TAGUSDT": "https://hook.finandy.com/daUsKIeoxz2QBw0grlUK",
    "TAGUSDTS": "https://hook.finandy.com/xjlhjmkMp8P6NgIgrlUK",
    "TLMUSDT": "https://hook.finandy.com/4N-tpFdE0OAl8Qr7rlUK",
    "TLMUSDTS": "https://hook.finandy.com/TT0qsdmWK7MJgQv7rlUK",
    "TURBOUSDT": "https://hook.finandy.com/26aJyAfUjChC8fgWrlUK",
    "TURBOUSDTS": "https://hook.finandy.com/TRY3KwYjRR2JGvkWrlUK",
    "VTHOUSDT": "https://hook.finandy.com/NwdY1tNyGZQ43f4MrlUK",
    "VTHOUSDTS": "https://hook.finandy.com/WXyOhFD6o7q_ov8MrlUK",
    "XVGUSDT": "https://hook.finandy.com/mEE7zt8Dxm1ChQj7rlUK",
    "XVGUSDTS": "https://hook.finandy.com/eorucMVltQjPNQn7rlUK"
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