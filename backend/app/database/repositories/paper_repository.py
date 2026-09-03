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
            )
            self.session.add(pos)
        await self.session.commit()

    async def delete_position(self, position_id: str) -> None:
        stmt = delete(PaperPositionModel).where(PaperPositionModel.position_id == position_id)
        await self.session.execute(stmt)
        await self.session.commit()

    async def record_closed_trade(self, trade_dict: Dict[str, Any], account_id: str = "primary_personal_account") -> None:
        trade = PaperClosedTradeModel(
            trade_id=trade_dict.get("id") or f"TRD_{int(time.time()*1000)}",
            account_id=account_id,
            symbol=trade_dict.get("symbol", ""),
            side=trade_dict.get("side", "BUY"),
            product_type=trade_dict.get("productType", "CNC"),
            quantity=int(trade_dict.get("quantity", 1)),
            entry_price=float(trade_dict.get("entryPrice", 0.0)),
            exit_price=float(trade_dict.get("exitPrice", 0.0)),
            gross_pnl=float(trade_dict.get("realizedPnL", 0.0)),
            brokerage=float(trade_dict.get("brokerage", 20.0)),
            taxes=float(trade_dict.get("taxes", 0.0)),
            realized_pnl=float(trade_dict.get("realizedPnL", 0.0)),
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
    ) -> None:
        """
        Executes order, fill, position, and capital update within a single atomic ACID transaction.
        If ANY step fails, the entire transaction is rolled back: COMPLETE SUCCESS OR COMPLETE ROLLBACK.
        """
        try:
            # 1. Record / Update Order
            order_id = order_dict.get("id") or order_dict.get("order_id") or f"ORD_{int(time.time()*1000)}"
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
        Closes position, logs closed trade, and updates capital inside a single atomic transaction.
        """
        try:
            # 1. Remove open position
            del_stmt = delete(PaperPositionModel).where(PaperPositionModel.position_id == pos_id)
            await self.session.execute(del_stmt)

            # 2. Record closed trade
            trade = PaperClosedTradeModel(
                trade_id=closed_trade_dict.get("id") or f"TRD_{int(time.time()*1000)}",
                account_id=account_id,
                symbol=closed_trade_dict.get("symbol", ""),
                side=closed_trade_dict.get("side", "BUY"),
                product_type=closed_trade_dict.get("productType", "CNC"),
                quantity=int(closed_trade_dict.get("quantity", 1)),
                entry_price=float(closed_trade_dict.get("entryPrice", 0.0)),
                exit_price=float(closed_trade_dict.get("exitPrice", 0.0)),
                gross_pnl=float(closed_trade_dict.get("realizedPnL", 0.0)),
                brokerage=float(closed_trade_dict.get("brokerage", 20.0)),
                taxes=float(closed_trade_dict.get("taxes", 0.0)),
                realized_pnl=float(closed_trade_dict.get("realizedPnL", 0.0)),
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
                "realizedPnL": t.realized_pnl,
                "brokerage": t.brokerage,
                "taxes": t.taxes,
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
        await self.session.commit()
        logger.info(f"[DB PAPER] Reset account {account_id} to capital ₹{new_capital} in database.")
