import time
import uuid
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.paper_trading.canonical_order import (
    CanonicalOrder,
    CanonicalFill,
    OrderState,
    validate_order_transition,
)
from backend.app.paper_engine.bridge import calculate_indian_equity_frictions

logger = logging.getLogger(__name__)


class PaperOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=50)
    companyName: Optional[str] = None
    productType: str = "CNC"  # CNC (Delivery) or MIS (Intraday)
    side: str = "BUY"  # BUY or SELL
    quantity: int = Field(gt=0, description="Order quantity must be strictly positive")
    price: float = Field(gt=0, description="Order price must be strictly positive")
    targetPrice: Optional[float] = None
    stopLoss: Optional[float] = None
    order_type: str = "MARKET"
    exchange: str = "NSE"
    source: str = "MANUAL"
    account_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    signal_id: Optional[str] = None
    candidate_id: Optional[str] = None
    strategy_version: Optional[str] = None
    signal_engine_version: Optional[str] = None
    configuration_hash: Optional[str] = None
    decision_reason: Optional[str] = None


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
    Unified Authoritative Backend Paper Trading Simulator & Ledger.
    Enforces canonical order lifecycle: CREATED -> VALIDATED -> ACCEPTED -> FILLED.
    Applies realistic Indian equity statutory friction (STT, Brokerage, Exchange, SEBI, GST, Stamp Duty, Slippage).
    Drives authoritative persistence to PostgreSQL/SQLite.
    """

    def __init__(self, initial_capital: float = 1000000.0, brokerage: float = 20.0, slippage_pct: float = 0.05):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.brokerage = brokerage
        self.slippage_pct = slippage_pct
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: List[Dict[str, Any]] = []
        self.order_history: List[Dict[str, Any]] = []
        self.fill_history: List[Dict[str, Any]] = []
        self.idempotency_cache: Dict[str, Dict[str, Any]] = {}

    @property
    def available_capital(self) -> float:
        return round(self.capital, 2)

    def execute_order(self, order_req: PaperOrderRequest, account_id: str = "primary_personal_account") -> Dict[str, Any]:
        # Check idempotency cache first to prevent duplicate execution on retries
        if order_req.idempotency_key and order_req.idempotency_key in self.idempotency_cache:
            cached = dict(self.idempotency_cache[order_req.idempotency_key])
            cached["is_idempotent_replay"] = True
            return cached

        order_id = f"ORD_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        is_buy = order_req.side.upper() == "BUY"

        # 1. Order Creation
        canonical_order = CanonicalOrder(
            order_id=order_id,
            account_id=account_id,
            symbol=order_req.symbol,
            exchange=order_req.exchange,
            side=order_req.side.upper(),
            quantity=order_req.quantity,
            order_type=order_req.order_type,
            requested_price=order_req.price,
            product_type=order_req.productType.upper(),
            target_price=order_req.targetPrice,
            stop_loss=order_req.stopLoss,
            source=order_req.source,
            signal_id=order_req.signal_id,
            candidate_id=order_req.candidate_id,
            strategy_version=order_req.strategy_version,
            signal_engine_version=order_req.signal_engine_version,
            configuration_hash=order_req.configuration_hash,
            decision_reason=order_req.decision_reason,
        )

        # 2. Validation
        if canonical_order.quantity <= 0 or canonical_order.requested_price <= 0 or not canonical_order.symbol:
            canonical_order.transition_to(OrderState.REJECTED, reason="Invalid quantity, price, or symbol.")
            return {
                "status": "REJECTED",
                "order_id": order_id,
                "reason": canonical_order.rejection_reason,
            }
        canonical_order.transition_to(OrderState.VALIDATED)

        # 3. Risk Gate & Margin Check
        total_val = canonical_order.quantity * canonical_order.requested_price
        frictions = calculate_indian_equity_frictions(
            price=canonical_order.requested_price,
            quantity=canonical_order.quantity,
            is_buy=is_buy,
            slippage_pct=self.slippage_pct,
        )

        margin_required = total_val * 0.20 if "MIS" in canonical_order.product_type else total_val
        total_cash_needed = margin_required + frictions["total_fees"]

        if is_buy and total_cash_needed > self.capital:
            canonical_order.transition_to(
                OrderState.REJECTED,
                reason=f"Insufficient margin. Required ₹{total_cash_needed:,.2f}, Available ₹{self.capital:,.2f}"
            )
            return {
                "status": "REJECTED",
                "order_id": order_id,
                "reason": canonical_order.rejection_reason,
            }

        canonical_order.transition_to(OrderState.ACCEPTED)

        # 4. Fill Execution Simulation
        slippage_amount = frictions["slippage"]
        filled_price = round(
            canonical_order.requested_price + (slippage_amount / canonical_order.quantity if is_buy else -slippage_amount / canonical_order.quantity),
            2
        )
        canonical_order.transition_to(OrderState.FILLED)

        fill_id = f"FILL_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        fill = CanonicalFill(
            fill_id=fill_id,
            order_id=order_id,
            account_id=account_id,
            symbol=canonical_order.symbol,
            side=canonical_order.side,
            quantity=canonical_order.quantity,
            price=filled_price,
            brokerage=frictions["brokerage"],
            stt=frictions["stt"],
            exchange_charges=frictions["exchange_charges"],
            sebi_charges=frictions["sebi_charges"],
            gst=frictions["gst"],
            stamp_duty=frictions["stamp_duty"],
            slippage=frictions["slippage"],
            fees=frictions["total_fees"],
            timestamp=time.time(),
        )

        # 5. Ledger & Balance Update
        self.capital -= total_cash_needed
        pos_id = f"POS_{canonical_order.symbol}_{int(time.time() * 1000)}"

        pos = {
            "id": pos_id,
            "account_id": account_id,
            "symbol": canonical_order.symbol,
            "companyName": order_req.companyName or canonical_order.symbol.split(".")[0],
            "productType": canonical_order.product_type,
            "side": canonical_order.side,
            "quantity": canonical_order.quantity,
            "entryPrice": filled_price,
            "currentPrice": filled_price,
            "unrealizedPnL": 0.0,
            "unrealizedPnLPercent": 0.0,
            "marginLocked": margin_required,
            "targetPrice": canonical_order.target_price,
            "stopLoss": canonical_order.stop_loss,
            "timestamp": time.time(),
            "frictions": frictions,
            "order_id": order_id,
            "fill_id": fill_id,
        }

        self.positions[pos_id] = pos
        self.order_history.append(canonical_order.model_dump())
        self.fill_history.append(fill.model_dump())

        res = {
            "status": "FILLED",
            "order_id": order_id,
            "fill_id": fill_id,
            "position": pos,
            "fill": fill.model_dump(),
            "available_capital": round(self.capital, 2),
        }
        if order_req.idempotency_key:
            self.idempotency_cache[order_req.idempotency_key] = res

        return res

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

    def get_position(self, symbol_or_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve active position by pos_id or symbol."""
        if symbol_or_id in self.positions:
            return self.positions[symbol_or_id]
        for pos in self.positions.values():
            if pos.get("symbol") == symbol_or_id:
                return pos
        return None

    def close_position(
        self,
        pos_id: str,
        close_price: Optional[float] = None,
        account_id: Optional[str] = None,
        close_quantity: Optional[int] = None,
    ) -> Dict[str, Any]:
        pos = self.positions.get(pos_id)
        if not pos:
            return {"status": "ERROR", "reason": "Position not found"}

        # IDOR Tenant Isolation: verify ownership
        if account_id and pos.get("account_id") and pos.get("account_id") != account_id:
            return {"status": "FORBIDDEN", "reason": "IDOR violation: position belongs to another account"}

        total_qty = pos["quantity"]
        qty_to_close = close_quantity if (close_quantity is not None and close_quantity > 0) else total_qty

        if qty_to_close <= 0:
            return {"status": "ERROR", "reason": "Invalid close quantity"}
        if qty_to_close > total_qty:
            return {"status": "ERROR", "reason": f"Close quantity {qty_to_close} exceeds open quantity {total_qty}"}

        is_partial = qty_to_close < total_qty
        price_to_use = close_price if close_price and close_price > 0 else pos.get("currentPrice", pos["entryPrice"])
        is_buy = pos["side"] == "BUY"

        # Calculate authentic exit friction
        exit_frictions = calculate_indian_equity_frictions(
            price=price_to_use,
            quantity=qty_to_close,
            is_buy=not is_buy,
            slippage_pct=self.slippage_pct,
        )
        effective_exit_price = round(
            price_to_use - (exit_frictions["slippage"] / qty_to_close if is_buy else -exit_frictions["slippage"] / qty_to_close),
            2
        )

        gross_pnl = (effective_exit_price - pos["entryPrice"]) * qty_to_close if is_buy else (pos["entryPrice"] - effective_exit_price) * qty_to_close
        total_exit_fees = exit_frictions["total_fees"]
        realized_pnl = gross_pnl - total_exit_fees

        # Proportional returned margin
        margin_portion = (pos.get("marginLocked", 0.0) / total_qty) * qty_to_close
        self.capital += (margin_portion + realized_pnl)

        closed_record = {
            "id": f"TRD_{pos['symbol']}_{int(time.time() * 1000)}",
            "account_id": pos.get("account_id", "primary_personal_account"),
            "pos_id": pos_id,
            "symbol": pos["symbol"],
            "companyName": pos.get("companyName"),
            "productType": pos.get("productType"),
            "side": pos.get("side"),
            "quantity": qty_to_close,
            "entryPrice": pos["entryPrice"],
            "exitPrice": effective_exit_price,
            "grossPnL": round(gross_pnl, 2),
            "realizedPnL": round(realized_pnl, 2),
            "brokerage": exit_frictions["brokerage"],
            "taxes": total_exit_fees - exit_frictions["brokerage"],
            "exit_frictions": exit_frictions,
            "timestamp": pos.get("timestamp", time.time()),
            "closedAt": time.time(),
        }
        self.closed_trades.append(closed_record)

        if is_partial:
            pos["quantity"] = total_qty - qty_to_close
            pos["marginLocked"] = round(pos.get("marginLocked", 0.0) - margin_portion, 2)
            return {
                "status": "PARTIALLY_CLOSED",
                "pos_id": pos_id,
                "closed_quantity": qty_to_close,
                "remaining_quantity": pos["quantity"],
                "realized_pnl": round(realized_pnl, 2),
                "available_capital": round(self.capital, 2),
                "trade": closed_record,
                "position": pos,
            }
        else:
            del self.positions[pos_id]
            return {
                "status": "CLOSED",
                "pos_id": pos_id,
                "closed_quantity": qty_to_close,
                "remaining_quantity": 0,
                "realized_pnl": round(realized_pnl, 2),
                "available_capital": round(self.capital, 2),
                "trade": closed_record,
            }

    def get_performance_summary(self) -> Dict[str, Any]:
        """Calculates performance analytics from closed trades and equity curve."""
        total_trades = len(self.closed_trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "total_realized_pnl": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "avg_trade_pnl": 0.0,
            }

        wins = [t for t in self.closed_trades if t.get("realizedPnL", 0.0) > 0]
        losses = [t for t in self.closed_trades if t.get("realizedPnL", 0.0) <= 0]
        gross_profit = sum(t.get("realizedPnL", 0.0) for t in wins)
        gross_loss = abs(sum(t.get("realizedPnL", 0.0) for t in losses))
        total_realized = round(sum(t.get("realizedPnL", 0.0) for t in self.closed_trades), 2)

        win_rate = round((len(wins) / total_trades) * 100.0, 2)
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        avg_trade = round(total_realized / total_trades, 2)

        return {
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "total_realized_pnl": total_realized,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "avg_trade_pnl": avg_trade,
        }

    def get_portfolio_summary(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns unified authoritative portfolio overview, optionally scoped by account_id."""
        relevant_positions = [
            p for p in self.positions.values()
            if not account_id or p.get("account_id", "primary_personal_account") == account_id
        ]
        relevant_trades = [
            t for t in self.closed_trades
            if not account_id or t.get("account_id", "primary_personal_account") == account_id
        ]
        total_unrealized = sum(p.get("unrealizedPnL", 0.0) for p in relevant_positions)
        total_margin_locked = sum(p.get("marginLocked", 0.0) for p in relevant_positions)
        total_realized = sum(t.get("realizedPnL", 0.0) for t in relevant_trades)
        net_worth = self.capital + total_margin_locked + total_unrealized

        return {
            "capital": round(self.capital, 2),
            "available_capital": round(self.capital, 2),
            "initial_capital": round(self.initial_capital, 2),
            "margin_locked": round(total_margin_locked, 2),
            "net_worth": round(net_worth, 2),
            "total_unrealized_pnl": round(total_unrealized, 2),
            "total_realized_pnl": round(total_realized, 2),
            "open_positions_count": len(relevant_positions),
            "closed_trades_count": len(relevant_trades),
            "positions": relevant_positions,
            "closed_trades": relevant_trades[-50:],
            "performance": self.get_performance_summary(),
        }

    def reset_portfolio(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions.clear()
        self.closed_trades.clear()
        self.order_history.clear()
        self.fill_history.clear()
        self.idempotency_cache.clear()

    async def load_from_db(self, session: Optional[AsyncSession] = None, account_id: str = "primary_personal_account"):
        """Loads authoritative state from database into engine memory cache."""
        try:
            from backend.app.database.connection import AsyncSessionLocal
            from backend.app.database.repositories.paper_repository import PaperRepository

            async def _do_load(s: AsyncSession):
                repo = PaperRepository(s)
                cap, pos, trades = await repo.load_portfolio_state(account_id, self.initial_capital)
                self.capital = cap
                self.positions = pos
                self.closed_trades = trades
                logger.info(f"[DB PAPER] Loaded portfolio from DB: Capital ₹{cap:,.2f}, Positions {len(pos)}, Closed Trades {len(trades)}")

            if session:
                await _do_load(session)
            else:
                async with AsyncSessionLocal() as s:
                    await _do_load(s)
        except Exception as e:
            logger.warning(f"[DB PAPER] Failed to load portfolio state from database: {e}")

    async def sync_order_to_db(self, order_dict: Dict[str, Any], position_dict: Dict[str, Any], account_id: str = "primary_personal_account"):
        """Persists order, fill, new position, and updated capital to database atomically."""
        try:
            from backend.app.database.connection import AsyncSessionLocal
            from backend.app.database.repositories.paper_repository import PaperRepository
            async with AsyncSessionLocal() as s:
                repo = PaperRepository(s)
                oid = order_dict.get("order_id") or order_dict.get("id") or position_dict.get("order_id") or f"ORD_{int(time.time()*1000)}"
                order_to_save = dict(order_dict)
                order_to_save["order_id"] = oid
                order_to_save["id"] = oid
                if position_dict.get("signal_id"):
                    order_to_save["signal_id"] = position_dict["signal_id"]
                if position_dict.get("candidate_id"):
                    order_to_save["candidate_id"] = position_dict["candidate_id"]
                
                fill_dict = None
                if position_dict.get("fill_id"):
                    frictions = position_dict.get("frictions", {})
                    fill_dict = {
                        "fill_id": position_dict["fill_id"],
                        "order_id": oid,
                        "symbol": order_dict.get("symbol"),
                        "side": order_dict.get("side", "BUY"),
                        "quantity": order_dict.get("quantity", 1),
                        "price": position_dict.get("entryPrice", order_dict.get("price")),
                        "brokerage": frictions.get("brokerage", 20.0),
                        "stt": frictions.get("stt", 0.0),
                        "exchange_charges": frictions.get("exchange_charges", 0.0),
                        "sebi_charges": frictions.get("sebi_charges", 0.0),
                        "gst": frictions.get("gst", 0.0),
                        "stamp_duty": frictions.get("stamp_duty", 0.0),
                        "taxes": frictions.get("total_fees", 0.0) - frictions.get("brokerage", 20.0),
                        "slippage": frictions.get("slippage", 0.0),
                        "timestamp": position_dict.get("timestamp", time.time()),
                    }
                await repo.record_trade_execution_atomic(
                    order_dict=order_to_save,
                    fill_dict=fill_dict,
                    position_dict=position_dict,
                    capital=self.capital,
                    account_id=account_id
                )
        except Exception as e:
            logger.warning(f"[DB PAPER] Failed to persist order to database: {e}")

    async def sync_close_to_db(self, pos_id: str, closed_trade_dict: Dict[str, Any], account_id: str = "primary_personal_account"):
        """Persists closed trade, removes position, and updates capital in database atomically."""
        try:
            from backend.app.database.connection import AsyncSessionLocal
            from backend.app.database.repositories.paper_repository import PaperRepository
            async with AsyncSessionLocal() as s:
                repo = PaperRepository(s)
                await repo.record_trade_closure_atomic(
                    pos_id=pos_id,
                    closed_trade_dict=closed_trade_dict,
                    capital=self.capital,
                    account_id=account_id
                )
        except Exception as e:
            logger.warning(f"[DB PAPER] Failed to persist position close to database: {e}")

    async def sync_reset_to_db(self, account_id: str = "primary_personal_account"):
        """Resets the account state in the database."""
        try:
            from backend.app.database.connection import AsyncSessionLocal
            from backend.app.database.repositories.paper_repository import PaperRepository
            async with AsyncSessionLocal() as s:
                repo = PaperRepository(s)
                await repo.reset_portfolio_state(account_id, self.capital)
        except Exception as e:
            logger.warning(f"[DB PAPER] Failed to reset portfolio in database: {e}")
