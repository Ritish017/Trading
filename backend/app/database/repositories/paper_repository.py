import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.models import (
    PaperAccountModel,
    PaperOrderModel,
    PaperPositionModel,
    PaperFillModel,
    PaperClosedTradeModel,
    PaperIdempotencyModel,
)

logger = logging.getLogger(__name__)

class PaperRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_account(self, account_id: str, default_capital: float = 1000000.0) -> PaperAccountModel:
        stmt = select(PaperAccountModel).where(PaperAccountModel.account_id == account_id)
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            account = PaperAccountModel(
                account_id=account_id,
                available_capital=default_capital,
                initial_capital=default_capital,
            )
            self.session.add(account)
            await self.session.commit()
            await self.session.refresh(account)
            logger.info(f"[DB PAPER] Created paper account {account_id} with capital ₹{default_capital}")
        return account

    async def update_account_capital(self, account_id: str, available_capital: float) -> None:
        account = await self.get_or_create_account(account_id)
        account.available_capital = available_capital
        await self.session.commit()

    async def record_order(self, order_dict: Dict[str, Any], account_id: str = "primary_personal_account") -> None:
        order_id = order_dict.get("id") or f"ORD_{int(time.time()*1000)}"
        stmt = select(PaperOrderModel).where(PaperOrderModel.order_id == order_id)
        result = await self.session.execute(stmt)
        order = result.scalar_one_or_none()

        if order:
            order.account_id = account_id
            order.symbol = order_dict.get("symbol", order.symbol)
            order.exchange = order_dict.get("exchange", getattr(order, "exchange", "NSE"))
            order.side = order_dict.get("side", order.side)
            order.order_type = order_dict.get("order_type", getattr(order, "order_type", "MARKET"))
            order.product_type = order_dict.get("productType", order.product_type)
            order.quantity = int(order_dict.get("quantity", order.quantity))
            order.price = float(order_dict.get("price", order.price))
            order.requested_price = float(order_dict["requested_price"]) if order_dict.get("requested_price") is not None else order.requested_price
            order.target_price = float(order_dict["targetPrice"]) if order_dict.get("targetPrice") else order.target_price
            order.stop_loss = float(order_dict["stopLoss"]) if order_dict.get("stopLoss") else order.stop_loss
            order.status = order_dict.get("status", order.status)
            order.source = order_dict.get("source", order.source)
            order.rejection_reason = order_dict.get("rejection_reason", order.rejection_reason)
            order.signal_id = order_dict.get("signal_id", getattr(order, "signal_id", None))
            order.candidate_id = order_dict.get("candidate_id", getattr(order, "candidate_id", None))
            order.strategy_version = order_dict.get("strategy_version", getattr(order, "strategy_version", None))
            order.signal_engine_version = order_dict.get("signal_engine_version", getattr(order, "signal_engine_version", None))
            order.configuration_hash = order_dict.get("configuration_hash", getattr(order, "configuration_hash", None))
            order.decision_reason = order_dict.get("decision_reason", getattr(order, "decision_reason", None))
            order.idempotency_key = order_dict.get("idempotency_key", getattr(order, "idempotency_key", None))
        else:
            order = PaperOrderModel(
                order_id=order_id,
                account_id=account_id,
                symbol=order_dict.get("symbol", ""),
                exchange=order_dict.get("exchange", "NSE"),
                side=order_dict.get("side", "BUY"),
                order_type=order_dict.get("order_type", "MARKET"),
                product_type=order_dict.get("productType", "CNC"),
                quantity=int(order_dict.get("quantity", 1)),
                price=float(order_dict.get("price", 0.0)),
                requested_price=float(order_dict["requested_price"]) if order_dict.get("requested_price") is not None else float(order_dict.get("price", 0.0)),
                target_price=float(order_dict["targetPrice"]) if order_dict.get("targetPrice") else None,
                stop_loss=float(order_dict["stopLoss"]) if order_dict.get("stopLoss") else None,
                status=order_dict.get("status", "FILLED"),
                source=order_dict.get("source", "MANUAL"),
                rejection_reason=order_dict.get("rejection_reason"),
                signal_id=order_dict.get("signal_id"),
                candidate_id=order_dict.get("candidate_id"),
                strategy_version=order_dict.get("strategy_version"),
                signal_engine_version=order_dict.get("signal_engine_version"),
                configuration_hash=order_dict.get("configuration_hash"),
                decision_reason=order_dict.get("decision_reason"),
                idempotency_key=order_dict.get("idempotency_key"),
            )
            self.session.add(order)
        await self.session.commit()

    async def record_fill(self, fill_dict: Dict[str, Any], account_id: str = "primary_personal_account") -> None:
        fill_id = fill_dict.get("id") or fill_dict.get("fill_id") or f"FILL_{int(time.time()*1000)}"
        fill = PaperFillModel(
            fill_id=fill_id,
            order_id=fill_dict.get("order_id", ""),
            account_id=account_id,
            symbol=fill_dict.get("symbol", ""),
            side=fill_dict.get("side", "BUY"),
            quantity=int(fill_dict.get("quantity", 1)),
            price=float(fill_dict.get("price", 0.0)),
            brokerage=float(fill_dict.get("brokerage", 20.0)),
            stt=float(fill_dict.get("stt", 0.0)),
            exchange_charges=float(fill_dict.get("exchange_charges", 0.0)),
            sebi_charges=float(fill_dict.get("sebi_charges", 0.0)),
            gst=float(fill_dict.get("gst", 0.0)),
            stamp_duty=float(fill_dict.get("stamp_duty", 0.0)),
            taxes=float(fill_dict.get("taxes", 0.0)),
            slippage=float(fill_dict.get("slippage", 0.0)),
            timestamp=float(fill_dict.get("timestamp", time.time())),
        )
        self.session.add(fill)
        await self.session.commit()

    async def save_or_update_position(self, pos_dict: Dict[str, Any], account_id: str = "primary_personal_account") -> None:
        pos_id = pos_dict.get("id")
        stmt = select(PaperPositionModel).where(PaperPositionModel.position_id == pos_id)
        result = await self.session.execute(stmt)
        pos = result.scalar_one_or_none()

        if pos:
            pos.quantity = int(pos_dict.get("quantity", pos.quantity))
            pos.entry_price = float(pos_dict.get("entryPrice", pos.entry_price))
            pos.current_price = float(pos_dict.get("currentPrice", pos.current_price))
            pos.margin_locked = float(pos_dict.get("marginLocked", pos.margin_locked))
            pos.realized_pnl = float(pos_dict.get("realizedPnL", pos.realized_pnl))
            pos.unrealized_pnl = float(pos_dict.get("unrealizedPnL", pos.unrealized_pnl))
            pos.signal_id = pos_dict.get("signal_id", getattr(pos, "signal_id", None))
            pos.candidate_id = pos_dict.get("candidate_id", getattr(pos, "candidate_id", None))
            pos.strategy_version = pos_dict.get("strategy_version", getattr(pos, "strategy_version", None))
            pos.configuration_hash = pos_dict.get("configuration_hash", getattr(pos, "configuration_hash", None))
            pos.decision_reason = pos_dict.get("decision_reason", getattr(pos, "decision_reason", None))
        else:
            pos = PaperPositionModel(
                position_id=pos_id,
                account_id=account_id,
                symbol=pos_dict.get("symbol", ""),
                side=pos_dict.get("side", "BUY"),
                product_type=pos_dict.get("productType", "CNC"),
                quantity=int(pos_dict.get("quantity", 1)),
                entry_price=float(pos_dict.get("entryPrice", 0.0)),
                current_price=float(pos_dict.get("currentPrice", pos_dict.get("entryPrice", 0.0))),
                target_price=float(pos_dict["targetPrice"]) if pos_dict.get("targetPrice") else None,
                stop_loss=float(pos_dict["stopLoss"]) if pos_dict.get("stopLoss") else None,
                margin_locked=float(pos_dict.get("marginLocked", 0.0)),
                realized_pnl=float(pos_dict.get("realizedPnL", 0.0)),
                unrealized_pnl=float(pos_dict.get("unrealizedPnL", 0.0)),
                signal_id=pos_dict.get("signal_id"),
                candidate_id=pos_dict.get("candidate_id"),
                strategy_version=pos_dict.get("strategy_version"),
                configuration_hash=pos_dict.get("configuration_hash"),
                decision_reason=pos_dict.get("decision_reason"),
            )
            self.session.add(pos)
        await self.session.commit()

    async def delete_position(self, position_id: str) -> None:
        stmt = delete(PaperPositionModel).where(PaperPositionModel.position_id == position_id)
        await self.session.execute(stmt)
        await self.session.commit()

    async def record_closed_trade(self, trade_dict: Dict[str, Any], account_id: str = "primary_personal_account") -> None:
        frictions = trade_dict.get("exit_frictions", {})
        trade = PaperClosedTradeModel(
            trade_id=trade_dict.get("id") or f"TRD_{int(time.time()*1000)}",
            account_id=account_id,
            symbol=trade_dict.get("symbol", ""),
            side=trade_dict.get("side", "BUY"),
            product_type=trade_dict.get("productType", "CNC"),
            quantity=int(trade_dict.get("quantity", 1)),
            entry_price=float(trade_dict.get("entryPrice", 0.0)),
            exit_price=float(trade_dict.get("exitPrice", 0.0)),
            gross_pnl=float(trade_dict.get("grossPnL", trade_dict.get("realizedPnL", 0.0))),
            brokerage=float(trade_dict.get("brokerage", 20.0)),
            taxes=float(trade_dict.get("taxes", 0.0)),
            realized_pnl=float(trade_dict.get("realizedPnL", 0.0)),
            signal_id=trade_dict.get("signal_id"),
            candidate_id=trade_dict.get("candidate_id"),
            strategy_version=trade_dict.get("strategy_version"),
            configuration_hash=trade_dict.get("configuration_hash"),
            exit_reason=trade_dict.get("exit_reason", "MANUAL"),
            exit_type=trade_dict.get("exit_type", "MANUAL"),
            stt=float(frictions.get("stt", trade_dict.get("stt", 0.0))),
            exchange_charges=float(frictions.get("exchange_charges", trade_dict.get("exchange_charges", 0.0))),
            sebi_charges=float(frictions.get("sebi_charges", trade_dict.get("sebi_charges", 0.0))),
            gst=float(frictions.get("gst", trade_dict.get("gst", 0.0))),
            stamp_duty=float(frictions.get("stamp_duty", trade_dict.get("stamp_duty", 0.0))),
            slippage=float(frictions.get("slippage", trade_dict.get("slippage", 0.0))),
            total_frictions=float(frictions.get("total_friction", trade_dict.get("total_frictions", 0.0))),
            calculation_evidence_json=trade_dict.get("calculation_evidence_json"),
            entry_time=float(trade_dict.get("timestamp", time.time())),
            closed_at=float(trade_dict.get("closedAt", time.time())),
        )
        self.session.add(trade)
        await self.session.commit()

    async def record_trade_execution_atomic(
        self,
        order_dict: Dict[str, Any],
        fill_dict: Optional[Dict[str, Any]],
        position_dict: Optional[Dict[str, Any]],
        capital: float,
        account_id: str = "primary_personal_account",
        idempotency_key: Optional[str] = None,
        order_result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Executes order, fill, position, and capital update within a single atomic ACID transaction.
        Also persists idempotency key if provided.
        If ANY step fails, the entire transaction is rolled back: COMPLETE SUCCESS OR COMPLETE ROLLBACK.
        """
        try:
            # 1. Record / Update Order
            order_id = order_dict.get("id") or order_dict.get("order_id") or f"ORD_{int(time.time()*1000)}"
            effective_idem_key = idempotency_key or order_dict.get("idempotency_key")
            stmt = select(PaperOrderModel).where(PaperOrderModel.order_id == order_id)
            result = await self.session.execute(stmt)
            order = result.scalar_one_or_none()

            if order:
                order.account_id = account_id
                order.symbol = order_dict.get("symbol", order.symbol)
                order.exchange = order_dict.get("exchange", getattr(order, "exchange", "NSE"))
                order.side = order_dict.get("side", order.side)
                order.order_type = order_dict.get("order_type", getattr(order, "order_type", "MARKET"))
                order.product_type = order_dict.get("productType", order.product_type)
                order.quantity = int(order_dict.get("quantity", order.quantity))
                order.price = float(order_dict.get("price", order.price))
                order.requested_price = float(order_dict["requested_price"]) if order_dict.get("requested_price") is not None else order.requested_price
                order.target_price = float(order_dict["targetPrice"]) if order_dict.get("targetPrice") else order.target_price
                order.stop_loss = float(order_dict["stopLoss"]) if order_dict.get("stopLoss") else order.stop_loss
                order.status = order_dict.get("status", order.status)
                order.source = order_dict.get("source", order.source)
                order.rejection_reason = order_dict.get("rejection_reason", order.rejection_reason)
                order.signal_id = order_dict.get("signal_id", getattr(order, "signal_id", None))
                order.candidate_id = order_dict.get("candidate_id", getattr(order, "candidate_id", None))
                order.strategy_version = order_dict.get("strategy_version", getattr(order, "strategy_version", None))
                order.signal_engine_version = order_dict.get("signal_engine_version", getattr(order, "signal_engine_version", None))
                order.configuration_hash = order_dict.get("configuration_hash", getattr(order, "configuration_hash", None))
                order.decision_reason = order_dict.get("decision_reason", getattr(order, "decision_reason", None))
                if effective_idem_key:
                    order.idempotency_key = effective_idem_key
            else:
                order = PaperOrderModel(
                    order_id=order_id,
                    account_id=account_id,
                    symbol=order_dict.get("symbol", ""),
                    exchange=order_dict.get("exchange", "NSE"),
                    side=order_dict.get("side", "BUY"),
                    order_type=order_dict.get("order_type", "MARKET"),
                    product_type=order_dict.get("productType", "CNC"),
                    quantity=int(order_dict.get("quantity", 1)),
                    price=float(order_dict.get("price", 0.0)),
                    requested_price=float(order_dict["requested_price"]) if order_dict.get("requested_price") is not None else float(order_dict.get("price", 0.0)),
                    target_price=float(order_dict["targetPrice"]) if order_dict.get("targetPrice") else None,
                    stop_loss=float(order_dict["stopLoss"]) if order_dict.get("stopLoss") else None,
                    status=order_dict.get("status", "FILLED"),
                    source=order_dict.get("source", "MANUAL"),
                    rejection_reason=order_dict.get("rejection_reason"),
                    signal_id=order_dict.get("signal_id"),
                    candidate_id=order_dict.get("candidate_id"),
                    strategy_version=order_dict.get("strategy_version"),
                    signal_engine_version=order_dict.get("signal_engine_version"),
                    configuration_hash=order_dict.get("configuration_hash"),
                    decision_reason=order_dict.get("decision_reason"),
                    idempotency_key=effective_idem_key,
                )
                self.session.add(order)

            # 2. Record Fill (if executed)
            if fill_dict:
                fill_id = fill_dict.get("id") or fill_dict.get("fill_id") or f"FILL_{int(time.time()*1000)}"
                fill = PaperFillModel(
                    fill_id=fill_id,
                    order_id=order_id,
                    account_id=account_id,
                    symbol=fill_dict.get("symbol", ""),
                    side=fill_dict.get("side", "BUY"),
                    quantity=int(fill_dict.get("quantity", 1)),
                    price=float(fill_dict.get("price", 0.0)),
                    brokerage=float(fill_dict.get("brokerage", 20.0)),
                    stt=float(fill_dict.get("stt", 0.0)),
                    exchange_charges=float(fill_dict.get("exchange_charges", 0.0)),
                    sebi_charges=float(fill_dict.get("sebi_charges", 0.0)),
                    gst=float(fill_dict.get("gst", 0.0)),
                    stamp_duty=float(fill_dict.get("stamp_duty", 0.0)),
                    taxes=float(fill_dict.get("taxes", 0.0)),
                    slippage=float(fill_dict.get("slippage", 0.0)),
                    timestamp=float(fill_dict.get("timestamp", time.time())),
                )
                self.session.add(fill)

            # 3. Save or Update Position
            if position_dict:
                pos_id = position_dict.get("id")
                pos_stmt = select(PaperPositionModel).where(PaperPositionModel.position_id == pos_id)
                pos_result = await self.session.execute(pos_stmt)
                pos = pos_result.scalar_one_or_none()

                if pos:
                    pos.quantity = int(position_dict.get("quantity", pos.quantity))
                    pos.entry_price = float(position_dict.get("entryPrice", pos.entry_price))
                    pos.current_price = float(position_dict.get("currentPrice", pos.current_price))
                    pos.margin_locked = float(position_dict.get("marginLocked", pos.margin_locked))
                    pos.realized_pnl = float(position_dict.get("realizedPnL", pos.realized_pnl))
                    pos.unrealized_pnl = float(position_dict.get("unrealizedPnL", pos.unrealized_pnl))
                    pos.signal_id = position_dict.get("signal_id", getattr(pos, "signal_id", None))
                    pos.candidate_id = position_dict.get("candidate_id", getattr(pos, "candidate_id", None))
                    pos.strategy_version = position_dict.get("strategy_version", getattr(pos, "strategy_version", None))
                    pos.configuration_hash = position_dict.get("configuration_hash", getattr(pos, "configuration_hash", None))
                    pos.decision_reason = position_dict.get("decision_reason", getattr(pos, "decision_reason", None))
                else:
                    pos = PaperPositionModel(
                        position_id=pos_id,
                        account_id=account_id,
                        symbol=position_dict.get("symbol", ""),
                        side=position_dict.get("side", "BUY"),
                        product_type=position_dict.get("productType", "CNC"),
                        quantity=int(position_dict.get("quantity", 1)),
                        entry_price=float(position_dict.get("entryPrice", 0.0)),
                        current_price=float(position_dict.get("currentPrice", position_dict.get("entryPrice", 0.0))),
                        target_price=float(position_dict["targetPrice"]) if position_dict.get("targetPrice") else None,
                        stop_loss=float(position_dict["stopLoss"]) if position_dict.get("stopLoss") else None,
                        margin_locked=float(position_dict.get("marginLocked", 0.0)),
                        realized_pnl=float(position_dict.get("realizedPnL", 0.0)),
                        unrealized_pnl=float(position_dict.get("unrealizedPnL", 0.0)),
                        signal_id=position_dict.get("signal_id"),
                        candidate_id=position_dict.get("candidate_id"),
                        strategy_version=position_dict.get("strategy_version"),
                        configuration_hash=position_dict.get("configuration_hash"),
                        decision_reason=position_dict.get("decision_reason"),
                    )
                    self.session.add(pos)

            # 4. Update Account Capital
            acc_stmt = select(PaperAccountModel).where(PaperAccountModel.account_id == account_id)
            acc_result = await self.session.execute(acc_stmt)
            account = acc_result.scalar_one_or_none()
            if account:
                account.available_capital = capital
            else:
                account = PaperAccountModel(
                    account_id=account_id,
                    available_capital=capital,
                    initial_capital=capital,
                )
                self.session.add(account)

            # 5. Save Idempotency Key (Feature 17)
            if effective_idem_key:
                idem_payload = order_result or {
                    "status": order.status,
                    "order_id": order_id,
                    "position": position_dict,
                    "fill": fill_dict,
                    "available_capital": capital,
                }
                idem_stmt = select(PaperIdempotencyModel).where(PaperIdempotencyModel.idempotency_key == effective_idem_key)
                idem_res = await self.session.execute(idem_stmt)
                existing_idem = idem_res.scalar_one_or_none()
                if existing_idem:
                    existing_idem.response_json = idem_payload
                    existing_idem.status = idem_payload.get("status", "FILLED")
                else:
                    idem_rec = PaperIdempotencyModel(
                        idempotency_key=effective_idem_key,
                        account_id=account_id,
                        order_id=order_id,
                        status=idem_payload.get("status", "FILLED"),
                        response_json=idem_payload,
                    )
                    self.session.add(idem_rec)

            # Commit all operations atomically
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def record_trade_closure_atomic(
        self,
        pos_id: str,
        closed_trade_dict: Dict[str, Any],
        capital: float,
        account_id: str = "primary_personal_account",
    ) -> None:
        """
        Closes position, logs closed trade with full forensic evidence, and updates capital inside a single atomic transaction.
        """
        try:
            # 1. Remove open position
            del_stmt = delete(PaperPositionModel).where(PaperPositionModel.position_id == pos_id)
            await self.session.execute(del_stmt)

            # 2. Record closed trade with enriched forensic evidence
            frictions = closed_trade_dict.get("exit_frictions", {})
            trade = PaperClosedTradeModel(
                trade_id=closed_trade_dict.get("id") or f"TRD_{int(time.time()*1000)}",
                account_id=account_id,
                symbol=closed_trade_dict.get("symbol", ""),
                side=closed_trade_dict.get("side", "BUY"),
                product_type=closed_trade_dict.get("productType", "CNC"),
                quantity=int(closed_trade_dict.get("quantity", 1)),
                entry_price=float(closed_trade_dict.get("entryPrice", 0.0)),
                exit_price=float(closed_trade_dict.get("exitPrice", 0.0)),
                gross_pnl=float(closed_trade_dict.get("grossPnL", closed_trade_dict.get("realizedPnL", 0.0))),
                brokerage=float(closed_trade_dict.get("brokerage", 20.0)),
                taxes=float(closed_trade_dict.get("taxes", 0.0)),
                realized_pnl=float(closed_trade_dict.get("realizedPnL", 0.0)),
                signal_id=closed_trade_dict.get("signal_id"),
                candidate_id=closed_trade_dict.get("candidate_id"),
                strategy_version=closed_trade_dict.get("strategy_version"),
                configuration_hash=closed_trade_dict.get("configuration_hash"),
                exit_reason=closed_trade_dict.get("exit_reason", "MANUAL"),
                exit_type=closed_trade_dict.get("exit_type", "MANUAL"),
                stt=float(frictions.get("stt", closed_trade_dict.get("stt", 0.0))),
                exchange_charges=float(frictions.get("exchange_charges", closed_trade_dict.get("exchange_charges", 0.0))),
                sebi_charges=float(frictions.get("sebi_charges", closed_trade_dict.get("sebi_charges", 0.0))),
                gst=float(frictions.get("gst", closed_trade_dict.get("gst", 0.0))),
                stamp_duty=float(frictions.get("stamp_duty", closed_trade_dict.get("stamp_duty", 0.0))),
                slippage=float(frictions.get("slippage", closed_trade_dict.get("slippage", 0.0))),
                total_frictions=float(frictions.get("total_friction", closed_trade_dict.get("total_frictions", 0.0))),
                calculation_evidence_json=closed_trade_dict.get("calculation_evidence_json"),
                entry_time=float(closed_trade_dict.get("timestamp", time.time())),
                closed_at=float(closed_trade_dict.get("closedAt", time.time())),
            )
            self.session.add(trade)

            # 3. Update capital
            acc_stmt = select(PaperAccountModel).where(PaperAccountModel.account_id == account_id)
            acc_result = await self.session.execute(acc_stmt)
            account = acc_result.scalar_one_or_none()
            if account:
                account.available_capital = capital

            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def load_idempotency_cache(self, account_id: str = "primary_personal_account") -> Dict[str, Dict[str, Any]]:
        """Loads all persisted idempotency keys and cached response payloads for an account."""
        stmt = select(PaperIdempotencyModel).where(PaperIdempotencyModel.account_id == account_id)
        res = await self.session.execute(stmt)
        records = res.scalars().all()
        return {r.idempotency_key: r.response_json for r in records}

    async def load_portfolio_state(self, account_id: str = "primary_personal_account", default_capital: float = 1000000.0) -> Tuple[float, Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
        """Loads persistent portfolio state from relational database."""
        account = await self.get_or_create_account(account_id, default_capital)
        capital = account.available_capital

        # Load open positions
        pos_stmt = select(PaperPositionModel).where(PaperPositionModel.account_id == account_id)
        pos_res = await self.session.execute(pos_stmt)
        db_positions = pos_res.scalars().all()

        positions: Dict[str, Dict[str, Any]] = {}
        for p in db_positions:
            positions[p.position_id] = {
                "id": p.position_id,
                "symbol": p.symbol,
                "companyName": p.symbol.split(".")[0],
                "productType": p.product_type,
                "side": p.side,
                "quantity": p.quantity,
                "entryPrice": p.entry_price,
                "currentPrice": p.current_price,
                "targetPrice": p.target_price,
                "stopLoss": p.stop_loss,
                "marginLocked": p.margin_locked,
                "unrealizedPnL": p.unrealized_pnl,
                "realizedPnL": p.realized_pnl,
                "unrealizedPnLPercent": round((p.current_price - p.entry_price) / p.entry_price * 100.0, 2) if p.entry_price > 0 else 0.0,
                "signal_id": p.signal_id,
                "candidate_id": p.candidate_id,
                "strategy_version": p.strategy_version,
                "configuration_hash": p.configuration_hash,
                "decision_reason": p.decision_reason,
                "timestamp": p.updated_at.timestamp() if p.updated_at else time.time()
            }

        # Load closed trades
        trade_stmt = select(PaperClosedTradeModel).where(PaperClosedTradeModel.account_id == account_id).order_by(PaperClosedTradeModel.closed_at.desc()).limit(100)
        trade_res = await self.session.execute(trade_stmt)
        db_trades = trade_res.scalars().all()

        closed_trades: List[Dict[str, Any]] = []
        for t in reversed(db_trades):
            closed_trades.append({
                "id": t.trade_id,
                "symbol": t.symbol,
                "companyName": t.symbol.split(".")[0],
                "productType": t.product_type,
                "side": t.side,
                "quantity": t.quantity,
                "entryPrice": t.entry_price,
                "exitPrice": t.exit_price,
                "grossPnL": t.gross_pnl,
                "realizedPnL": t.realized_pnl,
                "brokerage": t.brokerage,
                "taxes": t.taxes,
                "signal_id": t.signal_id,
                "candidate_id": t.candidate_id,
                "strategy_version": t.strategy_version,
                "configuration_hash": t.configuration_hash,
                "exit_reason": t.exit_reason,
                "exit_type": t.exit_type,
                "stt": t.stt,
                "exchange_charges": t.exchange_charges,
                "sebi_charges": t.sebi_charges,
                "gst": t.gst,
                "stamp_duty": t.stamp_duty,
                "slippage": t.slippage,
                "total_frictions": t.total_frictions,
                "calculation_evidence_json": t.calculation_evidence_json,
                "closedAt": t.closed_at,
                "timestamp": t.entry_time or t.closed_at
            })

        return capital, positions, closed_trades

    async def reset_portfolio_state(self, account_id: str = "primary_personal_account", new_capital: float = 1000000.0) -> None:
        """Resets the persistent database state for the given account."""
        account = await self.get_or_create_account(account_id, new_capital)
        account.available_capital = new_capital
        account.initial_capital = new_capital
        # Delete open positions
        await self.session.execute(
            delete(PaperPositionModel).where(PaperPositionModel.account_id == account_id)
        )
        # Delete closed trades
        await self.session.execute(
            delete(PaperClosedTradeModel).where(PaperClosedTradeModel.account_id == account_id)
        )
        # Delete orders
        await self.session.execute(
            delete(PaperOrderModel).where(PaperOrderModel.account_id == account_id)
        )
        # Delete fills
        await self.session.execute(
            delete(PaperFillModel).where(PaperFillModel.account_id == account_id)
        )
        # Delete idempotency keys
        await self.session.execute(
            delete(PaperIdempotencyModel).where(PaperIdempotencyModel.account_id == account_id)
        )
        await self.session.commit()
        logger.info(f"[DB PAPER] Reset account {account_id} to capital ₹{new_capital} in database.")
