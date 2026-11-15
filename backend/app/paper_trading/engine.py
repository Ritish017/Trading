import time
import uuid
import logging
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
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


class PaperExitType(str, Enum):
    EXIT_STOP = "EXIT_STOP"
    EXIT_TARGET = "EXIT_TARGET"
    MANUAL_CLOSE = "MANUAL_CLOSE"
    STRATEGY_INVALIDATION = "STRATEGY_INVALIDATION"
    TIME_EXPIRY = "TIME_EXPIRY"


class PaperExitEvent(BaseModel):
    pos_id: str
    order_id: Optional[str] = None
    account_id: str = "primary_personal_account"
    symbol: str
    side: str  # "BUY" or "SELL"
    exit_type: str  # "EXIT_STOP" or "EXIT_TARGET"
    exit_reason: str  # "STOP_LOSS", "TAKE_PROFIT"
    trigger_price: float
    exit_price: float
    effective_exit_price: float
    quantity: int
    gross_pnl: float
    realized_pnl: float
    same_bar_conflict: bool = False
    timestamp: float = Field(default_factory=time.time)
    trade: Dict[str, Any]


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
        self.trade_audits: List[Any] = []

    def get_trade_audits(self, strategy_id: Optional[str] = None) -> List[Any]:
        """Returns trade audits, optionally filtered by strategy_id."""
        if strategy_id:
            return [a for a in self.trade_audits if getattr(a, "strategy_id", None) == strategy_id]
        return list(self.trade_audits)

    @property
    def available_capital(self) -> float:
        return round(self.capital, 2)

    def validate_order_pre_submission(
        self,
        order_req: Optional[Union[PaperOrderRequest, Dict[str, Any]]] = None,
        account_id: str = "primary_personal_account",
        max_positions: int = 20,
        **kwargs,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates order pre-submission invariants:
        1. Basic quantity, price, and symbol validity.
        2. Directional geometry (BUY: stopLoss < price < targetPrice; SELL: targetPrice < price < stopLoss).
        3. Signal qualification and freshness/expiry (via signal_id or direct parameters).
        4. Portfolio capacity limits (max open positions).
        5. Margin and available capital requirements for both BUY and SELL.
        """
        # Resolve parameters flexibly from order_req or kwargs
        if order_req is None:
            symbol = kwargs.get("symbol")
            side = kwargs.get("side", "BUY")
            quantity = kwargs.get("quantity", 0)
            price = kwargs.get("price", 0.0)
            sl = kwargs.get("stop_loss", kwargs.get("stopLoss"))
            tp = kwargs.get("take_profit", kwargs.get("targetPrice"))
            signal_id = kwargs.get("signal_id")
            signal_status = kwargs.get("signal_status")
            signal_timestamp = kwargs.get("signal_timestamp")
            signal_expiry_seconds = kwargs.get("signal_expiry_seconds")
            product_type = kwargs.get("product_type", kwargs.get("productType", "CNC"))
        elif isinstance(order_req, dict):
            symbol = order_req.get("symbol", kwargs.get("symbol"))
            side = order_req.get("side", kwargs.get("side", "BUY"))
            quantity = order_req.get("quantity", kwargs.get("quantity", 0))
            price = order_req.get("price", kwargs.get("price", 0.0))
            sl = order_req.get("stop_loss", order_req.get("stopLoss", kwargs.get("stop_loss", kwargs.get("stopLoss"))))
            tp = order_req.get("take_profit", order_req.get("targetPrice", kwargs.get("take_profit", kwargs.get("targetPrice"))))
            signal_id = order_req.get("signal_id", kwargs.get("signal_id"))
            signal_status = kwargs.get("signal_status", order_req.get("signal_status"))
            signal_timestamp = kwargs.get("signal_timestamp", order_req.get("signal_timestamp"))
            signal_expiry_seconds = kwargs.get("signal_expiry_seconds", order_req.get("signal_expiry_seconds"))
            product_type = order_req.get("product_type", order_req.get("productType", kwargs.get("productType", "CNC")))
        else:
            symbol = order_req.symbol
            side = order_req.side
            quantity = order_req.quantity
            price = order_req.price
            sl = order_req.stopLoss
            tp = order_req.targetPrice
            signal_id = order_req.signal_id
            signal_status = kwargs.get("signal_status")
            signal_timestamp = kwargs.get("signal_timestamp")
            signal_expiry_seconds = kwargs.get("signal_expiry_seconds")
            product_type = order_req.productType

        # 1. Basic Checks
        if quantity <= 0 or price <= 0 or not symbol:
            return False, "Invalid quantity, price, or symbol."

        is_buy = side.upper() == "BUY"

        # 2. Directional Geometry Validation (Feature 13 / R2 Contract)
        if is_buy:
            if sl is not None and sl >= price:
                return False, f"Invalid LONG trade geometry: stop loss / stopLoss (₹{sl}) must be strictly below price (₹{price})"
            if tp is not None and tp <= price:
                return False, f"Invalid LONG trade geometry: target price / targetPrice (₹{tp}) must be strictly above price (₹{price})"
        else:  # SELL (SHORT)
            if sl is not None and sl <= price:
                return False, f"Invalid SHORT trade geometry: stop loss / stopLoss (₹{sl}) must be strictly above price (₹{price})"
            if tp is not None and tp >= price:
                return False, f"Invalid SHORT trade geometry: target price / targetPrice (₹{tp}) must be strictly below price (₹{price})"

        # 3. Direct Signal Status & Expiry Check
        if signal_status:
            st = str(signal_status).upper()
            if st in ["DISQUALIFIED", "REJECTED", "NO_TRADE", "EXPIRED"]:
                return False, f"Cannot execute signal: status is '{signal_status}', not actionable"

        if signal_timestamp is not None and signal_expiry_seconds is not None:
            if (float(signal_timestamp) + float(signal_expiry_seconds)) < time.time():
                return False, "Cannot execute signal: signal has expired"

        # 4. Signal Qualification & Freshness from SignalStore if signal_id is present
        if signal_id:
            try:
                from backend.app.signal_engine.signal_store import apex_signal_store
                sig = apex_signal_store.get_signal_by_id(signal_id)
                if sig:
                    sig_state = getattr(sig.state, "value", str(sig.state)).upper()
                    if sig_state != "QUALIFIED":
                        return False, f"Cannot execute signal '{signal_id}': status is '{sig_state}', expected 'QUALIFIED'"
                    qg = str(getattr(sig, "quality_grade", "")).upper()
                    if qg in ["NO_TRADE", "NO TRADE", "REJECTED"]:
                        return False, f"Cannot execute signal with quality grade '{qg}'"
                    expiry = getattr(sig, "expiry", None)
                    if expiry:
                        from datetime import datetime, timezone
                        if isinstance(expiry, (int, float)):
                            if time.time() > float(expiry):
                                sig.state = "EXPIRED"
                                return False, "Invalid or expired signal timestamp"
                        elif isinstance(expiry, str):
                            try:
                                exp_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                                if datetime.now(timezone.utc) > exp_dt:
                                    sig.state = "EXPIRED"
                                    return False, "Invalid or expired signal timestamp"
                            except Exception:
                                pass
            except Exception:
                pass

        # 5. Portfolio Risk Limits & Capacity Saturation
        existing_symbols = [p.get("symbol") for p in self.positions.values() if p.get("account_id") == account_id]
        if len(self.positions) >= max_positions and symbol not in existing_symbols:
            return False, f"Maximum open positions ({len(self.positions)}) reached (limit {max_positions})"

        # 6. Margin & Cash Requirements (both BUY and SELL / SHORT)
        total_val = quantity * price
        frictions = calculate_indian_equity_frictions(
            price=price,
            quantity=quantity,
            is_buy=is_buy,
            slippage_pct=self.slippage_pct,
        )
        margin_required = total_val * 0.20 if "MIS" in str(product_type).upper() else total_val
        total_cash_needed = margin_required + frictions["total_fees"]

        if total_cash_needed > self.capital:
            return False, f"Insufficient margin. Required ₹{total_cash_needed:,.2f}, Available ₹{self.capital:,.2f}"

        return True, "VALID"

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

        # 2. Comprehensive Pre-Submission Validation (F16)
        valid, reason = self.validate_order_pre_submission(order_req, account_id)
        if not valid:
            canonical_order.transition_to(OrderState.REJECTED, reason=reason or "Validation failed.")
            return {
                "status": "REJECTED",
                "order_id": order_id,
                "reason": canonical_order.rejection_reason,
            }

        canonical_order.transition_to(OrderState.VALIDATED)
        canonical_order.transition_to(OrderState.ACCEPTED)

        # 3. Cost & Margin Calculation
        total_val = canonical_order.quantity * canonical_order.requested_price
        frictions = calculate_indian_equity_frictions(
            price=canonical_order.requested_price,
            quantity=canonical_order.quantity,
            is_buy=is_buy,
            slippage_pct=self.slippage_pct,
        )
        margin_required = total_val * 0.20 if "MIS" in canonical_order.product_type else total_val
        total_cash_needed = margin_required + frictions["total_fees"]

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
        self.capital = round(self.capital - total_cash_needed, 2)
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
            # Retain signal metadata (Feature 20)
            "signal_id": canonical_order.signal_id,
            "candidate_id": canonical_order.candidate_id,
            "strategy_version": canonical_order.strategy_version,
            "signal_engine_version": canonical_order.signal_engine_version,
            "configuration_hash": canonical_order.configuration_hash,
            "decision_reason": canonical_order.decision_reason,
            "idempotency_key": order_req.idempotency_key,
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

    def process_market_tick(
        self,
        symbol: str,
        ltp: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
        open_price: Optional[float] = None,
        timestamp: Optional[float] = None,
        account_id: Optional[str] = None,
    ) -> List[PaperExitEvent]:
        """
        Processes market tick or candle update for symbol:
        1. Validates tick prices.
        2. Updates mark-to-market prices & unrealized P&L.
        3. Evaluates side-correct automated exits (SL/TP) with same-bar conservative resolution.
        """
        if ltp <= 0:
            return []

        # Update MTM first
        self.update_market_price(symbol, ltp)

        # Normalize bar ranges
        eff_high = high if (high is not None and high > 0) else ltp
        eff_low = low if (low is not None and low > 0) else ltp
        if eff_high < eff_low:
            eff_high, eff_low = eff_low, eff_high
        eff_open = open_price if (open_price is not None and open_price > 0) else ltp

        return self.evaluate_exits(
            symbol=symbol,
            high=eff_high,
            low=eff_low,
            open_price=eff_open,
            ltp=ltp,
            timestamp=timestamp,
            account_id=account_id,
        )

    def evaluate_exits(
        self,
        symbol: str,
        high: float,
        low: float,
        open_price: Optional[float] = None,
        ltp: Optional[float] = None,
        timestamp: Optional[float] = None,
        account_id: Optional[str] = None,
    ) -> List[PaperExitEvent]:
        """
        Evaluates open positions on symbol against bar range [low, high].
        Enforces:
        - LONG: low <= SL -> EXIT_STOP; high >= TP -> EXIT_TARGET
        - SHORT: high >= SL -> EXIT_STOP; low <= TP -> EXIT_TARGET
        - Same-Bar Conflict: Stop-Loss takes absolute precedence.
        - Conservative Gap Defense: Fills at open_price if bar opened past stop level.
        """
        exit_events: List[PaperExitEvent] = []
        eff_open = open_price or ltp or high

        for pos_id, pos in list(self.positions.items()):
            if pos.get("symbol") != symbol:
                continue
            if account_id and pos.get("account_id") != account_id:
                continue

            side = pos.get("side", "BUY").upper()
            is_long = (side == "BUY")
            sl = pos.get("stopLoss")
            tp = pos.get("targetPrice")

            stop_triggered = False
            target_triggered = False

            if is_long:
                if sl is not None and sl > 0 and low <= sl:
                    stop_triggered = True
                if tp is not None and tp > 0 and high >= tp:
                    target_triggered = True
            else:  # SHORT
                if sl is not None and sl > 0 and high >= sl:
                    stop_triggered = True
                if tp is not None and tp > 0 and low <= tp:
                    target_triggered = True

            if not (stop_triggered or target_triggered):
                continue

            # Same-Bar Conflict Resolution (Feature 19)
            same_bar_conflict = (stop_triggered and target_triggered)

            if same_bar_conflict or stop_triggered:
                exit_type = "EXIT_STOP"
                exit_reason = "STOP_LOSS"
                trigger_price = sl

                # Conservative Gap Defense
                if is_long:
                    exec_price = eff_open if (eff_open <= sl) else sl
                else:
                    exec_price = eff_open if (eff_open >= sl) else sl
            else:
                exit_type = "EXIT_TARGET"
                exit_reason = "TAKE_PROFIT"
                trigger_price = tp

                # Favorable Gap Fill
                if is_long:
                    exec_price = eff_open if (eff_open >= tp) else tp
                else:
                    exec_price = eff_open if (eff_open <= tp) else tp

            close_res = self.close_position(
                pos_id=pos_id,
                close_price=exec_price,
                account_id=pos.get("account_id"),
                exit_reason=exit_reason,
                exit_type=exit_type,
            )

            if close_res.get("status") in ["CLOSED", "PARTIALLY_CLOSED"]:
                trade = close_res.get("trade", {})
                trade["same_bar_conflict"] = same_bar_conflict
                event = PaperExitEvent(
                    pos_id=pos_id,
                    order_id=pos.get("order_id"),
                    account_id=pos.get("account_id", "primary_personal_account"),
                    symbol=symbol,
                    side=side,
                    exit_type=exit_type,
                    exit_reason=exit_reason,
                    trigger_price=trigger_price,
                    exit_price=exec_price,
                    effective_exit_price=trade.get("exitPrice", exec_price),
                    quantity=trade.get("quantity", pos.get("quantity", 0)),
                    gross_pnl=trade.get("grossPnL", 0.0),
                    realized_pnl=trade.get("realizedPnL", 0.0),
                    same_bar_conflict=same_bar_conflict,
                    timestamp=timestamp or time.time(),
                    trade=trade,
                )
                exit_events.append(event)

        return exit_events

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
        exit_reason: str = "MANUAL",
        exit_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        pos = self.positions.get(pos_id)
        if not pos:
            return {"status": "ERROR", "reason": "Position not found"}

        # IDOR Tenant Isolation: verify ownership
        if account_id and pos.get("account_id") and pos.get("account_id") != account_id:
            return {"status": "FORBIDDEN", "reason": "IDOR violation: position belongs to another account"}

        total_qty = pos["quantity"]
        if close_quantity is not None:
            if close_quantity <= 0:
                return {"status": "ERROR", "reason": "Invalid close quantity: must be positive"}
            qty_to_close = close_quantity
        else:
            qty_to_close = total_qty

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
        self.capital = round(self.capital + margin_portion + realized_pnl, 2)

        effective_exit_type = exit_type or (
            "EXIT_STOP" if exit_reason == "STOP_LOSS" else (
                "EXIT_TARGET" if exit_reason == "TAKE_PROFIT" else "MANUAL"
            )
        )

        # Calculation evidence (Feature 20)
        r_multiple = None
        if pos.get("stopLoss") and pos["stopLoss"] != pos["entryPrice"]:
            risk_per_share = abs(pos["entryPrice"] - pos["stopLoss"])
            if risk_per_share > 0:
                r_multiple = round(gross_pnl / (risk_per_share * qty_to_close), 2)

        evidence = {
            "entry_price": pos["entryPrice"],
            "exit_price": effective_exit_price,
            "stop_loss": pos.get("stopLoss"),
            "target_price": pos.get("targetPrice"),
            "r_multiple_realized": r_multiple,
            "decision_reason": pos.get("decision_reason"),
            "frictions": exit_frictions,
        }

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
            "exit_reason": exit_reason,
            "exit_type": effective_exit_type,
            "signal_id": pos.get("signal_id"),
            "candidate_id": pos.get("candidate_id"),
            "strategy_version": pos.get("strategy_version"),
            "configuration_hash": pos.get("configuration_hash"),
            "calculation_evidence_json": evidence,
            "timestamp": pos.get("timestamp", time.time()),
            "closedAt": time.time(),
        }
        self.closed_trades.append(closed_record)

        # Append to unified trade_audits (Feature 15)
        try:
            from backend.app.paper_engine.models import PaperTradeAudit, OrderSide, ExitReason
            side_enum = OrderSide.BUY if pos.get("side") == "BUY" else OrderSide.SELL
            audit_exit_reason = ExitReason.STOP_LOSS if exit_reason == "STOP_LOSS" else (
                ExitReason.TAKE_PROFIT if exit_reason == "TAKE_PROFIT" else ExitReason.MANUAL_CLOSE
            )
            audit = PaperTradeAudit(
                trade_id=closed_record["id"],
                signal_id=pos.get("signal_id") or "MANUAL",
                symbol=pos["symbol"],
                strategy_id=pos.get("strategy_version") or "DISCRETIONARY",
                strategy_version=pos.get("strategy_version") or "1.0.0",
                side=side_enum,
                quantity=qty_to_close,
                entry_timestamp=int(pos.get("timestamp", time.time())),
                entry_price=pos["entryPrice"],
                exit_timestamp=int(closed_record["closedAt"]),
                exit_price=effective_exit_price,
                exit_reason=audit_exit_reason,
                gross_pnl=round(gross_pnl, 2),
                net_pnl=round(realized_pnl, 2),
                fees_paid=round(total_exit_fees, 2),
                slippage_paid=round(exit_frictions["slippage"], 2),
                return_pct=round((realized_pnl / (pos["entryPrice"] * qty_to_close)) * 100.0, 2) if pos["entryPrice"] > 0 else 0.0,
                holding_period_bars=max(1, int((closed_record["closedAt"] - pos.get("timestamp", closed_record["closedAt"])) / 3600)),
                entry_evidence=[pos.get("decision_reason")] if pos.get("decision_reason") else [],
                exit_evidence=[f"Exit triggered by: {exit_reason}"],
                r_multiple=round(float(r_multiple), 2) if r_multiple is not None else 0.0,
            )
            self.trade_audits.append(audit)
        except Exception as e:
            logger.debug(f"[PAPER] Could not append PaperTradeAudit: {e}")

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
        self.trade_audits.clear()

    async def load_from_db(self, session: Optional[AsyncSession] = None, account_id: str = "primary_personal_account"):
        """Loads authoritative state from database into engine memory cache."""
        try:
            from backend.app.database.connection import AsyncSessionLocal
            from backend.app.database.repositories.paper_repository import PaperRepository

            async def _do_load(s: AsyncSession):
                repo = PaperRepository(s)
                cap, pos, trades = await repo.load_portfolio_state(account_id, self.initial_capital)
                idem_cache = await repo.load_idempotency_cache(account_id)
                self.capital = cap
                self.positions = pos
                self.closed_trades = trades
                self.idempotency_cache.update(idem_cache)

                # Reconstitute trade_audits for in-memory queries
                from backend.app.paper_engine.models import PaperTradeAudit, OrderSide, ExitReason
                self.trade_audits = []
                for t in trades:
                    side_enum = OrderSide.BUY if t.get("side") == "BUY" else OrderSide.SELL
                    er_val = t.get("exit_reason", "MANUAL")
                    audit_exit_reason = ExitReason.STOP_LOSS if er_val == "STOP_LOSS" else (
                        ExitReason.TAKE_PROFIT if er_val == "TAKE_PROFIT" else ExitReason.MANUAL_CLOSE
                    )
                    qty = t.get("quantity", 1)
                    entry_p = t.get("entryPrice", 0.0)
                    ret_pct = round((t.get("realizedPnL", 0.0) / (entry_p * qty)) * 100.0, 2) if entry_p > 0 else 0.0
                    self.trade_audits.append(PaperTradeAudit(
                        trade_id=t.get("id", ""),
                        signal_id=t.get("signal_id") or "MANUAL",
                        symbol=t.get("symbol", ""),
                        strategy_id=t.get("strategy_version") or "DISCRETIONARY",
                        strategy_version=t.get("strategy_version") or "1.0.0",
                        side=side_enum,
                        quantity=qty,
                        entry_timestamp=int(t.get("timestamp", 0)),
                        entry_price=entry_p,
                        exit_timestamp=int(t.get("closedAt", 0)),
                        exit_price=t.get("exitPrice", 0.0),
                        exit_reason=audit_exit_reason,
                        gross_pnl=round(t.get("grossPnL", t.get("realizedPnL", 0.0)), 2),
                        net_pnl=round(t.get("realizedPnL", 0.0), 2),
                        fees_paid=round(t.get("total_frictions", t.get("brokerage", 0.0) + t.get("taxes", 0.0)), 2),
                        slippage_paid=round(t.get("slippage", 0.0), 2),
                        return_pct=ret_pct,
                        holding_period_bars=max(1, int((t.get("closedAt", 0) - t.get("timestamp", 0)) / 3600)) if t.get("closedAt") and t.get("timestamp") else 1,
                    ))

                logger.info(f"[DB PAPER] Loaded portfolio from DB: Capital ₹{cap:,.2f}, Positions {len(pos)}, Closed Trades {len(trades)}, Idempotency Keys {len(idem_cache)}")

            if session:
                await _do_load(session)
            else:
                async with AsyncSessionLocal() as s:
                    await _do_load(s)
        except Exception as e:
            logger.warning(f"[DB PAPER] Failed to load portfolio state from database: {e}")

    async def sync_order_to_db(self, order_dict: Dict[str, Any], position_dict: Dict[str, Any], account_id: str = "primary_personal_account", order_result: Optional[Dict[str, Any]] = None):
        """Persists order, fill, new position, idempotency key, and updated capital to database atomically."""
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
                if position_dict.get("strategy_version"):
                    order_to_save["strategy_version"] = position_dict["strategy_version"]
                if position_dict.get("configuration_hash"):
                    order_to_save["configuration_hash"] = position_dict["configuration_hash"]
                if position_dict.get("decision_reason"):
                    order_to_save["decision_reason"] = position_dict["decision_reason"]
                if position_dict.get("idempotency_key"):
                    order_to_save["idempotency_key"] = position_dict["idempotency_key"]
                
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
                    account_id=account_id,
                    idempotency_key=order_dict.get("idempotency_key") or position_dict.get("idempotency_key"),
                    order_result=order_result,
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


# Canonical Authoritative Engine Singleton
paper_engine = PaperTradingEngine()

def get_paper_engine() -> PaperTradingEngine:
    return paper_engine
