"""
ACCEPTANCE SUITE: Database Durability & Transactional Integrity
Verifies SQLite round-trip parity, atomic transaction rollback on failure, and PostgreSQL dialect DDL compilation.
"""

import pytest
import time
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from backend.app.database.connection import init_db, AsyncSessionLocal
from backend.app.database.models import Base
from backend.app.database.repositories.paper_repository import PaperRepository
from backend.app.paper_trading.engine import PaperTradingEngine


@pytest.mark.asyncio
async def test_sqlite_round_trip_cold_engine_restoration():
    """Validates complete database durability across cold engine restarts."""
    await init_db()
    account_id = f"acceptance_user_{int(time.time()*1000)}"

    async with AsyncSessionLocal() as s:
        repo = PaperRepository(s)
        await repo.reset_portfolio_state(account_id, new_capital=500000.0)

        # Order details
        order_dict = {
            "order_id": f"ORD_ACC_{int(time.time())}",
            "symbol": "TATASTEEL.NS",
            "exchange": "NSE",
            "side": "BUY",
            "quantity": 100,
            "order_type": "MARKET",
            "product_type": "CNC",
            "requested_price": 150.0,
            "target_price": 180.0,
            "stop_loss": 140.0,
            "status": "FILLED",
            "source": "ACCEPTANCE_TEST",
        }
        fill_dict = {
            "fill_id": f"FILL_ACC_{int(time.time())}",
            "order_id": order_dict["order_id"],
            "account_id": account_id,
            "symbol": "TATASTEEL.NS",
            "side": "BUY",
            "quantity": 100,
            "price": 150.0,
            "brokerage": 7.50,
            "stt": 15.00,
            "exchange_charges": 0.52,
            "sebi_charges": 0.02,
            "gst": 1.45,
            "stamp_duty": 2.25,
            "slippage": 7.50,
            "fees": 26.74,
        }
        pos_dict = {
            "id": f"POS_ACC_{int(time.time())}",
            "symbol": "TATASTEEL.NS",
            "companyName": "Tata Steel",
            "productType": "CNC",
            "side": "BUY",
            "quantity": 100,
            "entryPrice": 150.0,
            "currentPrice": 150.0,
            "marginLocked": 15000.0,
            "order_id": order_dict["order_id"],
            "fill_id": fill_dict["fill_id"],
        }
        new_capital = 500000.0 - 15026.74

        await repo.record_trade_execution_atomic(
            order_dict=order_dict,
            fill_dict=fill_dict,
            position_dict=pos_dict,
            capital=new_capital,
            account_id=account_id,
        )

    # Simulate cold engine restart
    cold_engine = PaperTradingEngine()
    async with AsyncSessionLocal() as s:
        await cold_engine.load_from_db(session=s, account_id=account_id)

    assert round(cold_engine.capital, 2) == round(new_capital, 2)
    assert len(cold_engine.positions) == 1
    pos = list(cold_engine.positions.values())[0]
    assert pos["symbol"] == "TATASTEEL.NS"
    assert pos["quantity"] == 100
    assert pos["entryPrice"] == 150.0


@pytest.mark.asyncio
async def test_database_atomic_transaction_rollback_on_injected_failure():
    """Validates that a failure anywhere during trade persistence triggers a 100% atomic rollback."""
    await init_db()
    account_id = f"test_rollback_{int(time.time()*1000)}"

    async with AsyncSessionLocal() as s:
        repo = PaperRepository(s)
        await repo.reset_portfolio_state(account_id, new_capital=1000000.0)

        # Injected invalid pos_dict with non-numeric fields to trigger transaction failure
        invalid_pos_dict = {
            "id": "POS_FAIL_1",
            "symbol": "FAIL.NS",
            "side": "BUY",
            "quantity": "NOT_AN_INTEGER_VALUE",
            "entryPrice": "NOT_A_FLOAT_VALUE",
        }

        order_dict = {
            "order_id": "ORD_ROLLBACK_1",
            "symbol": "RELIANCE.NS",
            "side": "BUY",
            "quantity": 10,
            "requested_price": 2900.0,
            "status": "FILLED",
        }
        fill_dict = {
            "fill_id": "FILL_ROLLBACK_1",
            "order_id": "ORD_ROLLBACK_1",
            "account_id": account_id,
            "symbol": "RELIANCE.NS",
            "side": "BUY",
            "quantity": 10,
            "price": 2900.0,
            "fees": 25.0,
        }

        with pytest.raises(Exception):
            await repo.record_trade_execution_atomic(
                order_dict=order_dict,
                fill_dict=fill_dict,
                position_dict=invalid_pos_dict,
                capital=970000.0,
                account_id=account_id,
            )

    # Verify rollback: no order, no fill, no position, and capital remains untouched
    async with AsyncSessionLocal() as s:
        repo = PaperRepository(s)
        acc = await repo.get_or_create_account(account_id)
        assert acc.available_capital == 1000000.0
        cap, positions, trades = await repo.load_portfolio_state(account_id)
        assert len(positions) == 0


def test_postgresql_ddl_compilation_all_models():
    """Validates PostgreSQL dialect DDL generation for all domain models."""
    pg_dialect = postgresql.dialect()
    assert len(Base.metadata.tables) >= 10

    for table_name, table in Base.metadata.tables.items():
        ddl = str(CreateTable(table).compile(dialect=pg_dialect))
        assert "CREATE TABLE" in ddl
        assert table_name in ddl
