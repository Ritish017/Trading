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
    Authoritative Backend Paper Trading Simulator Engine.
    Enforces margin requirements:
    - CNC (Delivery): 100% margin required
    - MIS (Intraday): 20% margin required (5x leverage)
    Applies flat ₹20 brokerage fee and 0.05% slippage simulation per order.
    """

    def __init__(self, initial_capital: float = 1000000.0, brokerage: float = 20.0, slippage_pct: float = 0.05):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.brokerage = brokerage
        self.slippage_pct = slippage_pct
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: List[Dict[str, Any]] = []
        self.order_history: List[Dict[str, Any]] = []

    def execute_order(self, order: PaperOrderRequest) -> Dict[str, Any]:
        total_val = order.quantity * order.price
        slippage = total_val * (self.slippage_pct / 100.0)
        filled_price = round(order.price + (slippage / order.quantity if order.side == "BUY" else -slippage / order.quantity), 2)
        margin_required = total_val * 0.20 if "MIS" in order.productType else total_val

        if margin_required + self.brokerage > self.capital:
            return {
                "status": "REJECTED",
                "reason": f"Insufficient margin. Required ₹{margin_required + self.brokerage:,.2f}, Available ₹{self.capital:,.2f}"
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
            "marginLocked": margin_required,
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

    def update_market_price(self, symbol: str, current_price: float):
        """Update mark-to-market prices and unrealized PnL for active positions."""
        if current_price <= 0:
            return
        for pos_id, pos in self.positions.items():
            if pos["symbol"] == symbol:
                pos["currentPrice"] = current_price
                diff = current_price - pos["entryPrice"] if pos["side"] == "BUY" else pos["entryPrice"] - current_price
                pos["unrealizedPnL"] = round(diff * pos["quantity"], 2)
                pos["unrealizedPnLPercent"] = round((diff / pos["entryPrice"]) * 100.0, 2) if pos["entryPrice"] > 0 else 0.0

    def close_position(self, pos_id: str, close_price: Optional[float] = None) -> Dict[str, Any]:
        pos = self.positions.get(pos_id)
        if not pos:
            return {"status": "ERROR", "reason": "Position not found"}

        price_to_use = close_price if close_price and close_price > 0 else pos.get("currentPrice", pos["entryPrice"])
        qty = pos["quantity"]
        diff = price_to_use - pos["entryPrice"] if pos["side"] == "BUY" else pos["entryPrice"] - price_to_use
        realized_pnl = (diff * qty) - self.brokerage
        returned_margin = pos.get("marginLocked", (pos["quantity"] * pos["entryPrice"] * 0.20 if "MIS" in pos["productType"] else pos["quantity"] * pos["entryPrice"]))

        self.capital += (returned_margin + realized_pnl)
        
        closed_record = dict(pos)
        closed_record["exitPrice"] = price_to_use
        closed_record["realizedPnL"] = round(realized_pnl, 2)
        closed_record["closedAt"] = time.time()
        self.closed_trades.append(closed_record)
        
        del self.positions[pos_id]

        return {
            "status": "CLOSED",
            "pos_id": pos_id,
            "realized_pnl": round(realized_pnl, 2),
            "available_capital": round(self.capital, 2)
        }

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Returns consolidated portfolio overview."""
        total_unrealized = sum(p.get("unrealizedPnL", 0.0) for p in self.positions.values())
        total_margin_locked = sum(p.get("marginLocked", 0.0) for p in self.positions.values())
        total_realized = sum(t.get("realizedPnL", 0.0) for t in self.closed_trades)
        net_worth = self.capital + total_margin_locked + total_unrealized

        return {
            "available_capital": round(self.capital, 2),
            "margin_locked": round(total_margin_locked, 2),
            "net_worth": round(net_worth, 2),
            "total_unrealized_pnl": round(total_unrealized, 2),
            "total_realized_pnl": round(total_realized, 2),
            "open_positions_count": len(self.positions),
            "closed_trades_count": len(self.closed_trades),
            "positions": list(self.positions.values()),
            "closed_trades": self.closed_trades[-50:]
        }

    def reset_portfolio(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions.clear()
        self.closed_trades.clear()
        self.order_history.clear()
