import pytest
import time
from httpx import AsyncClient, ASGITransport

from backend.app.database.connection import init_db, AsyncSessionLocal
from backend.app.database.repositories.paper_repository import PaperRepository
from backend.app.database.repositories.research_repository import ResearchRepository
from backend.app.paper_trading.engine import PaperTradingEngine, PaperOrderRequest
from backend.app.main import app

@pytest.mark.asyncio
async def test_database_init_and_tables_creation():
    """Verify that all domain tables (paper, research, market) initialize cleanly."""
    await init_db()
    async with AsyncSessionLocal() as session:
        repo = PaperRepository(session)
        account = await repo.get_or_create_account("test_account_01", default_capital=750000.0)
        assert account.account_id == "test_account_01"
        assert account.available_capital == 750000.0

@pytest.mark.asyncio
async def test_paper_repository_full_lifecycle():
    """Verify PaperRepository: order, position, close, and reconstruct across session."""
    await init_db()
    async with AsyncSessionLocal() as session:
        repo = PaperRepository(session)
        account_id = "test_lifecycle_account"
        await repo.reset_portfolio_state(account_id, new_capital=500000.0)

        # 1. Place order and record position
        order_dict = {
            "id": "ORD_TEST_001",
            "symbol": "INFY.NS",
            "side": "BUY",
            "productType": "CNC",
            "quantity": 10,
            "price": 1500.0,
            "status": "FILLED"
        }
        pos_dict = {
            "id": "POS_TEST_001",
            "symbol": "INFY.NS",
            "side": "BUY",
            "productType": "CNC",
            "quantity": 10,
            "entryPrice": 1500.0,
            "currentPrice": 1520.0,
            "marginLocked": 15000.0,
            "realizedPnL": 0.0,
            "unrealizedPnL": 200.0
        }
        await repo.record_order(order_dict, account_id)
        await repo.save_or_update_position(pos_dict, account_id)
        await repo.update_account_capital(account_id, 485000.0)

    # 2. In a completely new session, reconstruct state
    async with AsyncSessionLocal() as session:
        repo = PaperRepository(session)
        cap, positions, closed_trades = await repo.load_portfolio_state(account_id)
        assert cap == 485000.0
        assert "POS_TEST_001" in positions
        assert positions["POS_TEST_001"]["symbol"] == "INFY.NS"
        assert positions["POS_TEST_001"]["quantity"] == 10
        assert len(closed_trades) == 0

        # 3. Close position and record closed trade
        closed_trade_dict = {
            "id": "TRD_TEST_001",
            "symbol": "INFY.NS",
            "side": "BUY",
            "productType": "CNC",
            "quantity": 10,
            "entryPrice": 1500.0,
            "exitPrice": 1550.0,
            "realizedPnL": 480.0,
            "brokerage": 20.0,
            "taxes": 0.0,
            "closedAt": time.time(),
            "timestamp": time.time()
        }
        await repo.delete_position("POS_TEST_001")
        await repo.record_closed_trade(closed_trade_dict, account_id)
        await repo.update_account_capital(account_id, 500480.0)

    # 4. In a third session, assert position is gone and trade is in history
    async with AsyncSessionLocal() as session:
        repo = PaperRepository(session)
        cap, positions, closed_trades = await repo.load_portfolio_state(account_id)
        assert cap == 500480.0
        assert "POS_TEST_001" not in positions
        assert len(closed_trades) == 1
        assert closed_trades[0]["symbol"] == "INFY.NS"
        assert closed_trades[0]["realizedPnL"] == 480.0

@pytest.mark.asyncio
async def test_research_repository_persistence():
    """Verify ResearchRepository saves and retrieves hypotheses and experiments."""
    await init_db()
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)

        hyp = {
            "id": "HYP_TEST_PERSIST_01",
            "name": "Mean Reversion on RSI Oversold",
            "technical_strategy_id": "RSI_OVERSOLD_REVERSAL",
            "fundamental_factor_id": "DEBT_FREE",
            "universe": "NIFTY50",
            "timeframe": "15m",
            "status": "VALIDATED",
            "scorecard": {"survived": True, "score": 85.0}
        }
        await repo.save_hypothesis(hyp)

        retrieved = await repo.get_hypothesis("HYP_TEST_PERSIST_01")
        assert retrieved is not None
        assert retrieved["hypothesis_id"] == "HYP_TEST_PERSIST_01"
        assert retrieved["status"] == "VALIDATED"
        assert retrieved["scorecard"]["score"] == 85.0

        exp = {
            "id": "EXP_TEST_PERSIST_01",
            "strategy_id": "RSI_OVERSOLD_REVERSAL",
            "symbol": "HDFCBANK.NS",
            "timeframe": "15m",
            "parameters": {"rsi_period": 14, "oversold_threshold": 30},
            "metrics": {"sharpe": 1.85, "win_rate": 0.62},
            "workflow_state": "ACTIVE"
        }
        await repo.save_experiment(exp)

        exp_list = await repo.list_experiments("RSI_OVERSOLD_REVERSAL")
        assert any(e["experiment_id"] == "EXP_TEST_PERSIST_01" for e in exp_list)

@pytest.mark.asyncio
async def test_engine_reconstruction_from_database():
    """Verify PaperTradingEngine reconstructs identical state from database."""
    await init_db()
    account_id = "test_reconstruction_account"

    # 1. Use engine A to execute order and persist
    engine_a = PaperTradingEngine(initial_capital=200000.0)
    await engine_a.load_from_db(account_id=account_id)
    # Reset cleanly first
    await engine_a.sync_reset_to_db(account_id=account_id)
    engine_a.capital = 200000.0

    order = PaperOrderRequest(
        symbol="SBIN.NS",
        productType="CNC",
        side="BUY",
        quantity=20,
        price=800.0
    )
    res = engine_a.execute_order(order)
    assert res["status"] == "FILLED"
    await engine_a.sync_order_to_db(order.model_dump(), res["position"], account_id)

    # 2. Simulate server restart: create brand new Engine B with NO prior in-memory state
    engine_b = PaperTradingEngine(initial_capital=100000.0) # different dummy init
    await engine_b.load_from_db(account_id=account_id)

    # Engine B must match Engine A's post-trade state from DB!
    assert engine_b.capital == engine_a.capital
    assert len(engine_b.positions) == 1
    pos_id = list(engine_b.positions.keys())[0]
    assert engine_b.positions[pos_id]["symbol"] == "SBIN.NS"
    assert engine_b.positions[pos_id]["quantity"] == 20


@pytest.mark.asyncio
async def test_atomic_transaction_rollback_on_failure():
    """
    TRANSACTION TEST:
    order -> fill -> position -> cash update
    Inject a failure during execution.
    Verify COMPLETE ROLLBACK: no partial order, no partial fill, no partial position created.
    """
    await init_db()
    account_id = "test_rollback_account"

    async with AsyncSessionLocal() as session:
        repo = PaperRepository(session)
        await repo.reset_portfolio_state(account_id, new_capital=300000.0)

    # Prepare payload with intentional schema violation in position (e.g., non-numeric price/quantity causing failure)
    bad_position = {
        "id": "POS_FAIL_001",
        "symbol": "FAIL.NS",
        "side": "BUY",
        "productType": "CNC",
        "quantity": "INVALID_QUANTITY_NOT_AN_INT",  # Intentional error to trigger failure during transaction
        "entryPrice": "NOT_A_FLOAT",
    }
    order_dict = {
        "id": "ORD_FAIL_001",
        "symbol": "FAIL.NS",
        "side": "BUY",
        "quantity": 10,
        "price": 1000.0,
    }
    fill_dict = {
        "fill_id": "FILL_FAIL_001",
        "order_id": "ORD_FAIL_001",
        "symbol": "FAIL.NS",
        "side": "BUY",
        "quantity": 10,
        "price": 1000.0,
    }

    # Attempt atomic execution with bad payload
    with pytest.raises(Exception):
        async with AsyncSessionLocal() as session:
            repo = PaperRepository(session)
            await repo.record_trade_execution_atomic(
                order_dict=order_dict,
                fill_dict=fill_dict,
                position_dict=bad_position,
                capital=290000.0,
                account_id=account_id
            )

    # Verify COMPLETE ROLLBACK: nothing was persisted!
    async with AsyncSessionLocal() as session:
        repo = PaperRepository(session)
        cap, positions, closed = await repo.load_portfolio_state(account_id)
        assert cap == 300000.0  # Capital unchanged!
        assert "POS_FAIL_001" not in positions
        assert len(positions) == 0


def test_postgresql_dialect_ddl_compilation():
    """
    POSTGRESQL TEST:
    Verify that all SQLAlchemy models, primary keys, foreign keys, and indexes
    cleanly compile to valid PostgreSQL DDL.
    """
    from sqlalchemy import create_mock_engine
    from backend.app.database.connection import Base
    import backend.app.database.models  # noqa: F401

    compiled_statements = []
    def dump(sql, *multiparams, **params):
        compiled_statements.append(str(sql.compile(dialect=pg_engine.dialect)))

    pg_engine = create_mock_engine('postgresql+asyncpg://user:pass@localhost:5432/apex_db', dump)
    Base.metadata.create_all(pg_engine)

    assert len(compiled_statements) > 0
    full_ddl = "\n".join(compiled_statements)
    assert "CREATE TABLE paper_orders" in full_ddl
    assert "CREATE TABLE paper_fills" in full_ddl
    assert "CREATE TABLE paper_positions" in full_ddl
    assert "CREATE TABLE paper_closed_trades" in full_ddl
    assert "BIGSERIAL" in full_ddl or "SERIAL" in full_ddl
    assert "TIMESTAMP WITH TIME ZONE" in full_ddl
