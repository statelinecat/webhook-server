from typing import List, Dict, Any, Optional
from pydantic import BaseModel

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

class WebhookResponse(BaseModel):
    status: str
    target_symbol: str
    queue_symbol: str
    queued: bool
    webhook: str
    timestamp: float

class HealthStatus(BaseModel):
    status: str
    timestamp: float
    instruments_loaded: int
    queues_active: int
    placeholder_webhooks: int
    valid_webhooks: int