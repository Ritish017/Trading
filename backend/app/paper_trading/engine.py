import time
import uuid
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class PaperOrderRequest(BaseModel):
    symbol: str
    companyName: Optional[str] = None
    productType: str # CNC (Delivery) or MIS (Intraday)
    side: str # BUY or SELL
    quantity: int
    price: float
    targetPrice: Optional[float] = None
    stopLoss: Optional[float] = None

class PaperPositionResponse(BaseModel):
    id: str
    symbol: str
    companyName: str
    productType: str
    side: str
    quantity: int
    entryPrice: float
    currentPrice: float
    unrealizedPnL: float
    unrealizedPnLPercent: float
    targetPrice: Optional[float] = None
    stopLoss: Optional[float] = None
    timestamp: float

class PaperTradingEngine:
    """
    Realistic Paper Trading Simulator Engine
    Enforces margin requirements:
    - CNC (Delivery): 100% margin required
    - MIS (Intraday): 20% margin required (5x leverage)
    Applies flat ₹20 brokerage fee and 0.05% slippage simulation per order.
    """

    def __init__(self, initial_capital: float = 1000000.0, brokerage: float = 20.0, slippage_pct: float = 0.05):
        self.capital = initial_capital
        self.brokerage = brokerage
        self.slippage_pct = slippage_pct
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.order_history: List[Dict[str, Any]] = []

    def execute_order(self, order: PaperOrderRequest) -> Dict[str, Any]:
        total_val = order.quantity * order.price
        slippage = total_val * (self.slippage_pct / 100.0)
        filled_price = round(order.price + (slippage / order.quantity if order.side == "BUY" else -slippage / order.quantity), 2)
        margin_required = total_val * 0.20 if order.productType == "MIS (Intraday)" else total_val

        if margin_required + self.brokerage > self.capital:
            return {
                "status": "REJECTED",
                "reason": f"Insufficient margin. Required ₹{margin_required + self.brokerage:.2f}, Available ₹{self.capital:.2f}"
            }

        self.capital -= (margin_required + self.brokerage)
        pos_id = f"paper-{int(time.time() * 1000)}"

        pos = {
            "id": pos_id,
            "symbol": order.symbol,
            "companyName": order.companyName or order.symbol,
            "productType": order.productType,
            "side": order.side,
            "quantity": order.quantity,
            "entryPrice": filled_price,
            "currentPrice": filled_price,
            "unrealizedPnL": 0.0,
            "unrealizedPnLPercent": 0.0,
            "targetPrice": order.targetPrice,
            "stopLoss": order.stopLoss,
            "timestamp": time.time()
        }

        self.positions[pos_id] = pos
        self.order_history.append(pos)

        return {
            "status": "FILLED",
            "position": pos,
            "available_capital": round(self.capital, 2)
        }

    def close_position(self, pos_id: str, close_price: float) -> Dict[str, Any]:
        pos = self.positions.get(pos_id)
        if not pos:
            return {"status": "ERROR", "reason": "Position not found"}

        qty = pos["quantity"]
        diff = close_price - pos["entryPrice"] if pos["side"] == "BUY" else pos["entryPrice"] - close_price
        realized_pnl = (diff * qty) - self.brokerage
        returned_margin = pos["quantity"] * pos["entryPrice"] * 0.20 if pos["productType"] == "MIS (Intraday)" else pos["quantity"] * pos["entryPrice"]

        self.capital += (returned_margin + realized_pnl)
        del self.positions[pos_id]

        return {
            "status": "CLOSED",
            "pos_id": pos_id,
            "realized_pnl": round(realized_pnl, 2),
            "available_capital": round(self.capital, 2)
        }
