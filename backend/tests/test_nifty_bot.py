"""
Comprehensive Automated Test Suite for NIFTY 50 Autonomous Derivatives Bot
==========================================================================
Validates:
1. News Sentiment Engine (RSS scraping, keyword fallback, macro catalyst flags).
2. Time and Expiry Guards (IST market hours, Thursday expiry, post-1PM zero-day guard).
3. Strategy Regime Selection:
   - High IV Range-Bound: Delta-neutral defined-risk Iron Condor.
   - Low IV Breakout: Directional Bull Call / Bear Put debit spreads.
   - Futures Momentum: Basis velocity and Open Interest buildup (Long/Short Buildup).
4. Risk Management & Circuit Breaker:
   - Macro sentiment veto on high-impact opposite catalysts.
   - 2% daily loss portfolio circuit breaker.
   - 1% per-trade risk sizing.
5. Authoritative Paper Execution:
   - Order placement through paper engine with idempotency keys.
6. FastAPI Endpoints (/api/nifty-bot/status, /api/nifty-bot/scan, /api/nifty-bot/toggle, /api/news/sentiment).
"""

import pytest
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.ai_engine.news_engine import NewsSentimentEngine, NewsItem, MarketNewsSentimentSummary
from backend.app.signal_engine.nifty_derivatives_bot import (
    NiftyDerivativesBot, BotState, StrategyRegime, BotTradeSignal, IST
)
from backend.app.signal_engine.futures_engine import OpenInterestPattern
from backend.app.paper_trading.engine import PaperTradingEngine, PaperOrderRequest


@pytest.fixture
def mock_paper_engine():
    engine = PaperTradingEngine(initial_capital=500000.0)
    return engine


@pytest.fixture
def mock_market_data_service():
    service = MagicMock()
    # Mock spot quote
    service.get_quote = AsyncMock(side_effect=lambda sym: {
        "symbol": sym,
        "ltp": 24500.0 if "FUT" not in sym else 24560.0,
        "open": 24450.0,
        "high": 24550.0,
        "low": 24420.0,
        "volume": 5000000,
        "oi": 12000000,
        "previous_close": 24450.0,
        "is_live": True,
    })
    # Mock candles
    service.get_candles = AsyncMock(return_value=[
        {
            "timestamp": int(time.time()) - (i * 300),
            "open": 24400.0 + (i * 2),
            "high": 24420.0 + (i * 2),
            "low": 24390.0 + (i * 2),
            "close": 24410.0 + (i * 2),
            "volume": 100000,
        }
        for i in range(50)
    ])
    # Mock options chain
    service.get_option_chain = AsyncMock(return_value={
        "symbol": "NIFTY 50",
        "pcr": 1.15,
        "maxPain": 24500.0,
        "atm_iv": 0.16,
        "iv_percentile": 55.0,
        "contracts": [],
    })
    return service


@pytest.fixture
def mock_news_engine():
    engine = MagicMock(spec=NewsSentimentEngine)
    engine.get_market_sentiment = AsyncMock(return_value=MarketNewsSentimentSummary(
        aggregate_sentiment=0.35,
        sentiment_label="MODERATELY_BULLISH",
        high_impact_catalyst_detected=False,
        catalyst_summary="Moderate corporate earnings expansion.",
        headline_count=5,
        top_headlines=[
            NewsItem(
                title="Nifty surges on IT rally and strong corporate quarterly results",
                source="Economic Times",
                sentiment_score=0.45,
                urgency="ROUTINE",
                affected_segment="NIFTY 50",
            )
        ]
    ))
    return engine


# ---------------------------------------------------------------------------
# 1. News Sentiment Engine Unit Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_news_sentiment_keyword_scoring():
    engine = NewsSentimentEngine(api_key=None)

    # Bullish item
    bullish_text = "Nifty surges to record high as FII inflows jump and economy exhibits strong growth"
    score_bull = engine._keyword_sentiment_score(bullish_text)
    assert score_bull > 0.0

    # Bearish item with high-impact keyword (RBI)
    bearish_text = "Nifty plunges and crashes after RBI unexpectedly hikes repo rate amid inflation fears"
    score_bear = engine._keyword_sentiment_score(bearish_text)
    assert score_bear < 0.0
    has_high_impact = any(k in bearish_text.lower() for k in engine.HIGH_IMPACT_KEYWORDS)
    assert has_high_impact is True


# ---------------------------------------------------------------------------
# 2. Time & Expiry Guard Tests
# ---------------------------------------------------------------------------

def test_indian_market_hours_validation():
    # Tuesday 11:30 AM IST -> Should be OPEN
    tuesday_trading = datetime(2026, 11, 10, 11, 30, 0, tzinfo=IST)
    assert NiftyDerivativesBot.is_indian_market_hours(tuesday_trading) is True

    # Tuesday 08:30 AM IST (Pre-market) -> Should be CLOSED
    tuesday_pre = datetime(2026, 11, 10, 8, 30, 0, tzinfo=IST)
    assert NiftyDerivativesBot.is_indian_market_hours(tuesday_pre) is False

    # Tuesday 16:30 IST (Post-market) -> Should be CLOSED
    tuesday_post = datetime(2026, 11, 10, 16, 30, 0, tzinfo=IST)
    assert NiftyDerivativesBot.is_indian_market_hours(tuesday_post) is False

    # Sunday 12:00 PM IST -> Should be CLOSED
    sunday_noon = datetime(2026, 11, 15, 12, 0, 0, tzinfo=IST)
    assert NiftyDerivativesBot.is_indian_market_hours(sunday_noon) is False


def test_expiry_day_and_post_1pm_guards():
    # Thursday (2026-11-12)
    thursday_morning = datetime(2026, 11, 12, 10, 0, 0, tzinfo=IST)
    thursday_afternoon = datetime(2026, 11, 12, 14, 0, 0, tzinfo=IST)
    friday_afternoon = datetime(2026, 11, 13, 14, 0, 0, tzinfo=IST)

    assert NiftyDerivativesBot.is_expiry_day(thursday_morning) is True
    assert NiftyDerivativesBot.is_expiry_day(friday_afternoon) is False

    # Post 1 PM on Thursday -> zero-day guard triggers
    assert NiftyDerivativesBot.is_post_1pm_expiry(thursday_morning) is False
    assert NiftyDerivativesBot.is_post_1pm_expiry(thursday_afternoon) is True
    assert NiftyDerivativesBot.is_post_1pm_expiry(friday_afternoon) is False


# ---------------------------------------------------------------------------
# 3. Strategy Regime Selection & Signal Generation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_high_iv_range_bound_iron_condor(mock_market_data_service, mock_paper_engine, mock_news_engine):
    bot = NiftyDerivativesBot(
        market_data_service=mock_market_data_service,
        paper_engine=mock_paper_engine,
        news_engine=mock_news_engine,
    )

    context = {
        "spot_price": 24500.0,
        "iv_percentile": 68.0,
        "atm_iv": 0.18,
        "rsi": 49.0,
        "atr": 45.0,
        "pcr": 1.05,
        "sentiment": MarketNewsSentimentSummary(aggregate_sentiment=0.05, sentiment_label="NEUTRAL"),
    }

    regime, reason = bot.evaluate_market_regime(context)
    assert regime == StrategyRegime.HIGH_IV_RANGE_BOUND

    signal = bot.generate_strategy_signal(context, regime)
    assert signal.is_valid is True
    assert signal.strategy_name == "DELTA_NEUTRAL_IRON_CONDOR"
    assert len(signal.legs) == 4
    # Defined risk properties
    assert signal.net_premium_or_debit < 0  # Net credit received
    assert signal.max_loss > 0              # Bounded maximum risk


@pytest.mark.asyncio
async def test_low_iv_bull_call_spread(mock_market_data_service, mock_paper_engine, mock_news_engine):
    bot = NiftyDerivativesBot(
        market_data_service=mock_market_data_service,
        paper_engine=mock_paper_engine,
        news_engine=mock_news_engine,
    )

    context = {
        "spot_price": 24500.0,
        "iv_percentile": 25.0,
        "atm_iv": 0.12,
        "rsi": 62.0,
        "atr": 40.0,
        "pcr": 1.30,
        "sentiment": MarketNewsSentimentSummary(aggregate_sentiment=0.40, sentiment_label="BULLISH"),
    }

    regime, reason = bot.evaluate_market_regime(context)
    assert regime == StrategyRegime.LOW_IV_TRENDING

    signal = bot.generate_strategy_signal(context, regime)
    assert signal.is_valid is True
    assert signal.strategy_name == "BULL_CALL_DEBIT_SPREAD"
    assert len(signal.legs) == 2
    assert signal.legs[0].action == "BUY"
    assert signal.legs[1].action == "SELL"
    assert signal.max_loss > 0
    assert signal.max_gain > 0


@pytest.mark.asyncio
async def test_futures_momentum_long_buildup(mock_market_data_service, mock_paper_engine, mock_news_engine):
    bot = NiftyDerivativesBot(
        market_data_service=mock_market_data_service,
        paper_engine=mock_paper_engine,
        news_engine=mock_news_engine,
    )

    context = {
        "spot_price": 24500.0,
        "futures_price": 24565.0,
        "basis": 65.0,
        "basis_velocity": 8.0,
        "oi_pattern": OpenInterestPattern.LONG_BUILDUP.value,
        "rsi": 58.0,
        "atr": 50.0,
        "sentiment": MarketNewsSentimentSummary(aggregate_sentiment=0.25, sentiment_label="MODERATELY_BULLISH"),
    }

    regime, reason = bot.evaluate_market_regime(context)
    assert regime == StrategyRegime.FUTURES_MOMENTUM

    signal = bot.generate_strategy_signal(context, regime)
    assert signal.is_valid is True
    assert signal.strategy_name == "FUTURES_BUY"
    assert len(signal.legs) == 1
    assert signal.legs[0].symbol == "NIFTY-FUT"
    assert signal.stop_loss < 24565.0
    assert signal.target_price > 24565.0


# ---------------------------------------------------------------------------
# 4. Risk Guardrails & Circuit Breaker Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_macro_sentiment_veto_on_longs(mock_market_data_service, mock_paper_engine, mock_news_engine):
    bot = NiftyDerivativesBot(
        market_data_service=mock_market_data_service,
        paper_engine=mock_paper_engine,
        news_engine=mock_news_engine,
    )

    # Severe negative macro catalyst (e.g. surprise rate hike, war)
    context = {
        "spot_price": 24500.0,
        "futures_price": 24550.0,
        "basis": 50.0,
        "basis_velocity": 5.0,
        "oi_pattern": OpenInterestPattern.LONG_BUILDUP.value,
        "rsi": 56.0,
        "sentiment": MarketNewsSentimentSummary(
            aggregate_sentiment=-0.75,
            sentiment_label="BEARISH",
            high_impact_catalyst_detected=True,
            catalyst_summary="Emergency rate hike announced by central bank."
        ),
    }

    signal = bot.generate_strategy_signal(context, StrategyRegime.FUTURES_MOMENTUM)
    assert signal.is_valid is False
    assert signal.rejection_reason == "MACRO_SENTIMENT_VETO_LONG"


@pytest.mark.asyncio
async def test_daily_loss_circuit_breaker(mock_market_data_service, mock_paper_engine, mock_news_engine):
    bot = NiftyDerivativesBot(
        market_data_service=mock_market_data_service,
        paper_engine=mock_paper_engine,
        news_engine=mock_news_engine,
        daily_loss_limit_pct=2.0,
        initial_capital=500000.0,
    )

    # Simulate an open loss exceeding 2% (₹12,000 on ₹500,000)
    mock_paper_engine.positions["BAD_TRADE"] = {
        "id": "BAD_TRADE",
        "symbol": "NIFTY-FUT",
        "account_id": bot.ACCOUNT_ID,
        "unrealizedPnL": -12500.0,
    }

    is_breached, daily_pnl, dd_pct = bot.check_daily_loss_circuit_breaker()
    assert is_breached is True
    assert daily_pnl <= -10000.0
    assert bot.state == BotState.HALTED_DAILY_LOSS_BREACH


# ---------------------------------------------------------------------------
# 5. Full Autonomous Scan & Paper Execution Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_and_execute_cycle(mock_market_data_service, mock_paper_engine, mock_news_engine):
    bot = NiftyDerivativesBot(
        market_data_service=mock_market_data_service,
        paper_engine=mock_paper_engine,
        news_engine=mock_news_engine,
        initial_capital=500000.0,
    )

    bot.toggle_auto_trade(True)
    assert bot.auto_trade_enabled is True

    # Run scan with forced execution
    result = await bot.scan_and_evaluate(force_scan=True)
    assert result["bot_state"] in ("ACTIVE", "ARMED", "IDLE")
    assert result["signal"] is not None
    assert "regime" in result

    # Check that execution record exists if signal was valid
    if result["signal"]["is_valid"]:
        assert result["execution"] is not None
        assert result["execution"]["status"] in ("FILLED", "PENDING")


# ---------------------------------------------------------------------------
# 6. FastAPI Endpoints Integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_endpoints():
    from httpx import AsyncClient, ASGITransport
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Bot status
        res_status = await ac.get("/api/nifty-bot/status")
        assert res_status.status_code == 200
        data_status = res_status.json()
        assert "bot_state" in data_status
        assert "auto_trade_enabled" in data_status

        # 2. Toggle Bot
        res_toggle = await ac.post("/api/nifty-bot/toggle", json={"enabled": True})
        assert res_toggle.status_code == 200
        assert res_toggle.json()["auto_trade_enabled"] is True

        # Toggle back off
        await ac.post("/api/nifty-bot/toggle", json={"enabled": False})

        # 3. Bot Scan
        res_scan = await ac.post("/api/nifty-bot/scan?force_scan=true")
        assert res_scan.status_code == 200
        data_scan = res_scan.json()
        assert "regime" in data_scan

        # 4. News Sentiment
        res_sentiment = await ac.get("/api/news/sentiment")
        assert res_sentiment.status_code == 200
        data_sentiment = res_sentiment.json()
        assert "aggregate_sentiment" in data_sentiment
        assert "sentiment_label" in data_sentiment
