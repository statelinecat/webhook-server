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


# --- Модели для сигналов (ОБНОВЛЕННЫЕ) ---
class CloseDecrease(BaseModel):
    type: str
    amount: str


class CloseOrder(BaseModel):
    action: str
    decrease: CloseDecrease
    checkProfit: bool
    price: str = ""


class OpenOrder(BaseModel):
    amountType: str
    amount: str
    enabled: bool


class DCAOrder(BaseModel):
    amountType: str
    amount: str
    checkProfit: bool


class SLConfig(BaseModel):
    price: str = ""
    update: bool


class TradingSignal(BaseModel):
    name: str
    secret: str
    side: str
    symbol: str
    close: CloseOrder
    open: OpenOrder
    dca: DCAOrder
    sl: SLConfig
    tp: Optional[Dict[str, Any]] = None


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
    "BROCCOLIF3BUSDTS": "https://hook.finandy.com/8_YNXd82OWD4y4P4trlUK",
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
    "SWELLUSDT": "https://hook.finandy.com/t7CL16DKN3y4gM7rrlUK",
    "SWELLUSDTS": "https://hook.finandy.com/YpkjwyP7yHQC_THrrlUK",
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
            name TEXT,
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


def log_signal(symbol: str, name: str, data: dict, status: str, created_at: float,
               sent_at: float | None = None, response_code: int = None,
               response_text: str = None):
    """Логирование сигнала в БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO signals 
        (symbol, name, data, status, created_at, sent_at, response_code, response_text) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (symbol, name, str(data), status, created_at, sent_at, response_code, response_text)
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
            "SELECT * FROM signals WHERE symbol=? OR name=? ORDER BY id DESC LIMIT ?",
            (symbol, symbol, limit)
        )
    rows = cursor.fetchall()
    conn.close()
    return rows


# --- Воркеры для отправки сигналов ---
async def worker(symbol: str):
    """Обработка очереди сигналов для конкретного инструмента"""
    last_sent = 0

    print(f"🚀 Воркер запущен для {symbol}")

    while True:
        # Получаем данные сигнала и оригинальные данные (без изменений)
        data, original_data, name, created_at = await queues[symbol].get()

        # Определяем вебхук на основе name из данных сигнала
        target_symbol = name  # Используем name для определения вебхука
        webhook_url = FINANDY_WEBHOOKS.get(target_symbol)

        if not webhook_url:
            error_msg = f"No webhook found for name: {target_symbol}"
            print(f"[{symbol}] ❌ {error_msg}")
            log_signal(symbol, name, original_data, f"error {error_msg}", created_at, None, None, error_msg)
            queues[symbol].task_done()
            continue

        now = time.time()

        # Ограничение 300 мс между запросами
        if now - last_sent < 0.3:
            await asyncio.sleep(0.3 - (now - last_sent))

        try:
            # Детальное логирование отправляемых данных
            print(f"\n[{symbol}] 📤 Отправка данных на Finandy:")
            print(f"[{symbol}] Target symbol from name: {target_symbol}")
            print(f"[{symbol}] URL: {webhook_url}")
            print(f"[{symbol}] Оригинальные данные: {original_data}")

            # Отправляем ОРИГИНАЛЬНЫЕ данные без изменений
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    webhook_url,
                    json=original_data,  # Отправляем оригинальные данные
                    timeout=10.0
                )

                sent_at = time.time()
                response_text = resp.text[:500]

                # Детальное логирование ответа
                print(f"[{symbol}] 📥 Ответ от Finandy:")
                print(f"[{symbol}] Status: {resp.status_code}")
                print(f"[{symbol}] Response: {response_text}")

                if resp.status_code == 200:
                    status = f"sent {resp.status_code}"
                    print(f"[{symbol}] ✅ Успешно отправлен: {resp.status_code}")
                else:
                    status = f"error {resp.status_code}"
                    print(f"[{symbol}] ⚠️ Ошибка сервера: {resp.status_code}")

                # Логируем оригинальные данные
                log_signal(symbol, name, original_data, status, created_at, sent_at,
                           resp.status_code, response_text)

        except httpx.TimeoutException as e:
            error_msg = f"Timeout: {str(e)}"
            log_signal(symbol, name, original_data, f"error {error_msg}", created_at, None,
                       None, error_msg)
            print(f"[{symbol}] ❌ Таймаут при отправке: {e}")

        except httpx.RequestError as e:
            error_msg = f"Request Error: {str(e)}"
            log_signal(symbol, name, original_data, f"error {error_msg}", created_at, None,
                       None, error_msg)
            print(f"[{symbol}] ❌ Ошибка соединения: {e}")

        except Exception as e:
            error_msg = f"Unexpected Error: {str(e)}"
            log_signal(symbol, name, original_data, f"error {error_msg}", created_at, None,
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


# --- УНИВЕРСАЛЬНЫЙ эндпоинт для всех инструментов ---
@app.post("/webhook", response_model=dict)
async def universal_webhook(signal: TradingSignal):
    """
    Универсальный вебхук для приема сигналов от TradingView

    - **signal**: Данные торгового сигнала в формате Finandy
    - Автоматически определяет инструмент из поля 'name' сигнала
    """
    # Используем name из сигнала для определения целевого инструмента
    target_symbol = signal.name

    if target_symbol not in FINANDY_WEBHOOKS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown target symbol '{target_symbol}'. Supported symbols: {INSTRUMENTS}"
        )

    # Детальная проверка данных
    print(f"\n📩 Получен сигнал через универсальный вебхук:")
    print(f"   Target symbol from name: {target_symbol}")
    print(f"   Side: {signal.side}")
    print(f"   Full data: {signal.model_dump()}")

    created_at = time.time()

    # Сохраняем ОРИГИНАЛЬНЫЕ данные без изменений
    original_data = signal.model_dump()

    # Создаем копию данных для внутренней обработки
    processed_data = original_data.copy()

    # Логируем входящий сигнал с оригинальными данными
    log_signal("universal", target_symbol, original_data, "received", created_at)

    # Определяем в какую очередь положить (используем target_symbol)
    queue_symbol = target_symbol
    if queue_symbol not in queues:
        error_msg = f"No queue found for symbol: {target_symbol}"
        log_signal("universal", target_symbol, original_data, f"error {error_msg}", created_at)
        raise HTTPException(status_code=400, detail=error_msg)

    # Кладем в очередь на отправку
    await queues[queue_symbol].put((processed_data, original_data, target_symbol, created_at))

    print(f"[{queue_symbol}] 📩 Принят сигнал: {signal.side.upper()} для {target_symbol}")

    return {
        "status": "accepted",
        "target_symbol": target_symbol,
        "queue_symbol": queue_symbol,
        "queued": True,
        "webhook": FINANDY_WEBHOOKS[target_symbol],
        "timestamp": created_at
    }


# --- Старый эндпоинт (для обратной совместимости) ---
@app.post("/webhook/{symbol}", response_model=dict)
async def webhook_with_symbol(symbol: str, signal: TradingSignal):
    """
    Вебхук с указанием символа в URL (для обратной совместимости)
    """
    # Используем name из сигнала для определения целевого инструмента
    target_symbol = signal.name

    if target_symbol not in FINANDY_WEBHOOKS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown target symbol {target_symbol}. Supported symbols: {INSTRUMENTS}"
        )

    print(f"\n📩 Получен сигнал через вебхук с символом:")
    print(f"   URL symbol: {symbol}")
    print(f"   Target symbol from name: {target_symbol}")
    print(f"   Side: {signal.side}")

    created_at = time.time()
    original_data = signal.model_dump()
    processed_data = original_data.copy()

    log_signal(symbol, target_symbol, original_data, "received", created_at)

    queue_symbol = target_symbol
    if queue_symbol not in queues:
        queue_symbol = symbol
        print(f"⚠️ Очередь для {target_symbol} не найдена, используем {symbol}")

    await queues[queue_symbol].put((processed_data, original_data, target_symbol, created_at))

    print(f"[{queue_symbol}] 📩 Принят сигнал: {signal.side.upper()} для {target_symbol}")

    return {
        "status": "accepted",
        "url_symbol": symbol,
        "target_symbol": target_symbol,
        "queue_symbol": queue_symbol,
        "queued": True,
        "webhook": FINANDY_WEBHOOKS[target_symbol],
        "timestamp": created_at
    }


# Остальные эндпоинты остаются без изменений...
@app.post("/test-webhook/{symbol}")
async def test_webhook(symbol: str):
    """Тестовый запрос к Finandy для проверки соединения"""
    if symbol not in FINANDY_WEBHOOKS:
        return {"error": "Symbol not found"}

    webhook_url = FINANDY_WEBHOOKS[symbol]

    if "PLACEHOLDER" in webhook_url or "XXXXXXXX" in webhook_url:
        return {"error": "Webhook URL is a placeholder", "url": webhook_url}

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

        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=test_data, timeout=10.0)

            result = {
                "status_code": resp.status_code,
                "response": resp.text[:500],
                "url": webhook_url,
                "success": resp.status_code == 200
            }

            print(f"Результат: {result}")
            return result

    except Exception as e:
        error_result = {"error": str(e), "url": webhook_url}
        print(f"Ошибка теста: {error_result}")
        return error_result


@app.get("/webhooks", response_model=dict)
async def list_webhooks():
    """Получить список всех вебхуков"""
    valid_webhooks = {}
    placeholder_webhooks = {}

    for symbol, url in FINANDY_WEBHOOKS.items():
        if "PLACEHOLDER" in url or "XXXXXXXX" in url:
            placeholder_webhooks[symbol] = url
        else:
            valid_webhooks[symbol] = url

    return {
        "total_instruments": len(INSTRUMENTS),
        "valid_webhooks_count": len(valid_webhooks),
        "placeholder_webhooks_count": len(placeholder_webhooks),
        "valid_webhooks": valid_webhooks,
        "placeholder_webhooks": placeholder_webhooks
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
    rows = get_logs(symbol, limit)
    columns = ["id", "symbol", "name", "data", "status", "created_at", "sent_at", "response_code", "response_text"]
    results = [dict(zip(columns, row)) for row in rows]
    return results


@app.get("/", response_model=dict)
async def root():
    """Главная страница с информацией о API"""
    return {
        "message": "Webhook Proxy Server for Finandy",
        "version": "1.0",
        "total_instruments": len(INSTRUMENTS),
        "endpoints": {
            "universal_webhook": "POST /webhook (для всех инструментов)",
            "webhook_with_symbol": "POST /webhook/{symbol} (для обратной совместимости)",
            "test_webhook": "POST /test-webhook/{symbol}",
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
    active_queues = len([q for q in queues.values() if not q.empty()])
    placeholder_count = len([url for url in FINANDY_WEBHOOKS.values()
                             if "PLACEHOLDER" in url or "XXXXXXXX" in url])

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "instruments_loaded": len(INSTRUMENTS),
        "queues_active": active_queues,
        "placeholder_webhooks": placeholder_count,
        "valid_webhooks": len(INSTRUMENTS) - placeholder_count
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)