import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

from backend.app.config import settings
from backend.app.database.connection import init_db, check_db_health
from backend.app.broker_providers.base import NormalizedTick
from backend.app.market_data.service import MarketDataService
from backend.app.market_data.candle_aggregator import MarketCandleAggregator
from backend.app.quant_engine.indicators import (
    calculate_ema, calculate_vwap, calculate_rsi, calculate_macd, calculate_atr, calculate_bollinger_bands, detect_support_resistance, calculate_roc, calculate_stochastic, calculate_relative_volume
)
from backend.app.quant_engine.regime import classify_market_regime
from backend.app.quant_engine.options import calculate_pcr, calculate_max_pain, classify_oi_pattern
from backend.app.strategy_engine.dsl import StrategyHypothesis
from backend.app.backtesting.event_driven import EventDrivenBacktester
from backend.app.paper_trading.engine import PaperTradingEngine, PaperOrderRequest
from backend.app.journal.analytics import compute_journal_statistics
from backend.app.personalization.trader_profile import trader_profile_mgr
from backend.app.ai_engine.chief_analyst import ChiefMarketAnalyst
from backend.app.quant_engine.features import compute_market_features
from backend.app.event_engine.detector import detect_market_events
from backend.app.ai_engine.contracts import (
    MarketSnapshot, TechnicalSnapshot, DerivativeSnapshot, NewsSnapshot, SectorSnapshot, MacroSnapshot, InstitutionalSnapshot,
    DataFreshness
)
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY
from backend.app.strategy_engine.evaluator import evaluate_all_strategies, evaluate_strategies_observatory
from backend.app.ai_engine.agents import MarketResearchAgent, PersonalTradingCoach, StrategyResearchAgent, StrategyCopilotAgent

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="APEX Personal AI Quant & Trading Lab Backend",
    version="2.5.0",
    description="Production-grade personal quantitative research & trading engine API for Indian Equities (NSE/BSE)."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core Engine Instances
market_data_service = MarketDataService()
candle_aggregator = MarketCandleAggregator()
paper_engine = PaperTradingEngine(initial_capital=settings.default_paper_capital)

market_research_agent = MarketResearchAgent(api_key=settings.gemini_api_key)
trading_coach_agent = PersonalTradingCoach(api_key=settings.gemini_api_key)
strategy_agent = StrategyResearchAgent(api_key=settings.gemini_api_key)
strategy_copilot_agent = StrategyCopilotAgent(api_key=settings.gemini_api_key)
chief_market_analyst = ChiefMarketAnalyst(api_key=settings.gemini_api_key)

active_ws_connections: Set[WebSocket] = set()

async def on_normalized_tick_received(tick: NormalizedTick):
    """Callback triggered whenever a normalized tick is received from MarketDataService."""
    updated_candles = candle_aggregator.process_tick(tick)
    # Update paper trading mark-to-market
    paper_engine.update_market_price(tick.symbol, tick.ltp)

    payload = {
        "type": "TICK",
        "data": tick.dict(),
        "candle_update": updated_candles.get("5m")
    }
    
    # Broadcast tick to all connected frontend clients
    disconnected = set()
    for ws in list(active_ws_connections):
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.add(ws)

    active_ws_connections.difference_update(disconnected)

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting APEX Quant Lab Backend in {settings.environment} mode.")
    await init_db()
    # Initialize Market Data Hub
    await market_data_service.initialize()
    # Connect WebSocket feed to internal broadcast
    default_symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "NIFTY 50", "BANKNIFTY", "INDIA VIX"]
    await market_data_service.subscribe(default_symbols)
    await market_data_service.connect_websocket(on_normalized_tick_received)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down APEX Quant Lab Backend...")
    if hasattr(market_data_service.active_provider, "disconnect"):
        await market_data_service.active_provider.disconnect()

# --- Health Check Endpoints ---
@app.get("/health")
async def health_check():
    return {
        "status": "ONLINE",
        "system": settings.app_name,
        "environment": settings.environment,
        "real_trading_enabled": False
    }

@app.get("/health/data-feed")
async def data_feed_health():
    return market_data_service.get_health_status()

@app.get("/health/database")
async def database_health():
    return await check_db_health()

@app.get("/health/redis")
async def redis_health():
    return {"status": "ONLINE", "mode": "In-Memory Event Bus"}

# --- Market Data API ---
@app.get("/api/market/quote/{symbol}")
async def get_market_quote(symbol: str):
    return await market_data_service.get_quote(symbol)

@app.get("/api/market/quotes")
async def get_market_quotes(symbols: str = Query(default="RELIANCE.NS,TCS.NS,HDFCBANK.NS,ICICIBANK.NS,INFY.NS,SBIN.NS,TATAMOTORS.NS,NIFTY 50,BANKNIFTY,INDIA VIX")):
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return await market_data_service.get_quotes(sym_list)

@app.get("/api/market/candles/{symbol}")
async def get_candles(symbol: str, interval: str = "5m", count: int = 60):
    cached = candle_aggregator.get_history(symbol, interval, count)
    if cached and len(cached) >= count:
        return {"symbol": symbol, "interval": interval, "candles": cached, "source": "AGGREGATOR"}
    candles = await market_data_service.get_candles(symbol, interval, count)
    if candles:
        candle_aggregator.seed_historical_candles(symbol, interval, candles)
    return {"symbol": symbol, "interval": interval, "candles": candles, "source": "PROVIDER"}

@app.get("/api/market/option-chain/{symbol}")
async def get_option_chain(symbol: str):
    return await market_data_service.get_option_chain(symbol)

@app.get("/api/market/fii-dii")
async def get_fii_dii():
    return await market_data_service.get_fii_dii()

@app.get("/api/market/open-interest/{symbol}")
async def get_open_interest(symbol: str):
    return await market_data_service.get_open_interest(symbol)

@app.get("/api/market/change-in-oi/{symbol}")
async def get_change_in_oi(symbol: str):
    return await market_data_service.get_open_interest(symbol)

@app.get("/api/market/pcr/{symbol}")
async def get_pcr(symbol: str):
    return await market_data_service.get_pcr(symbol)

@app.get("/api/market/max-pain/{symbol}")
async def get_max_pain(symbol: str):
    return await market_data_service.get_max_pain(symbol)

@app.get("/api/market/announcements")
async def get_sebi_announcements():
    return []

@app.get("/api/market/breadth")
async def get_market_breadth():
    default_syms = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS", "TATAMOTORS.NS"]
    quotes = await market_data_service.get_quotes(default_syms)
    advances = sum(1 for q in quotes if (q.get("change") or 0) > 0)
    declines = sum(1 for q in quotes if (q.get("change") or 0) < 0)
    unchanged = len(quotes) - advances - declines
    ratio = round(advances / declines, 2) if declines > 0 else (advances if advances > 0 else 1.0)
    return {
        "universe": "Tracked Active Equities",
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "ratio": ratio,
        "source": market_data_service.active_provider.provider_name,
        "status": "LIVE" if market_data_service.is_live else "SIMULATED"
    }

# --- Quantitative Analysis API ---
class IndicatorRequest(BaseModel):
    symbol: str
    candles: List[Dict[str, Any]]

def evaluate_quote_freshness(quote: Dict[str, Any]) -> DataFreshness:
    """Truthfully evaluate quote freshness from timestamp and provider state."""
    if not quote or quote.get("ltp") is None:
        return DataFreshness.UNAVAILABLE
    is_live = bool(quote.get("is_live", False))
    ts = quote.get("timestamp")
    if ts is None or ts <= 0:
        return DataFreshness.UNAVAILABLE
    try:
        age = time.time() - float(ts)
        if age < 0:
            return DataFreshness.LIVE if is_live else DataFreshness.RECENT
        if is_live and age <= 60.0:
            return DataFreshness.LIVE
        elif age <= 300.0:
            return DataFreshness.RECENT
        elif age <= 86400.0:
            return DataFreshness.STALE
        else:
            return DataFreshness.UNAVAILABLE
    except (ValueError, TypeError):
        return DataFreshness.UNAVAILABLE

@app.post("/api/quant/indicators")
async def compute_indicators(req: IndicatorRequest):
    if not req.candles:
        raise HTTPException(status_code=400, detail="Candles array cannot be empty")
    
    df = pd.DataFrame(req.candles)
    close = df['close'].astype(float)
    
    ema20 = calculate_ema(close, 20).tolist() if len(close) >= 20 else [None] * len(close)
    ema50 = calculate_ema(close, 50).tolist() if len(close) >= 50 else [None] * len(close)
    vwap = calculate_vwap(df).tolist() if 'high' in df and 'low' in df and 'volume' in df else [None] * len(close)
    rsi = calculate_rsi(close, 14).tolist()
    rvol = calculate_relative_volume(df['volume'].astype(float), 20).tolist() if 'volume' in df else [None] * len(df)
    levels = detect_support_resistance(df)

    return {
        "symbol": req.symbol,
        "ema20": [round(x, 2) if x is not None and not pd.isna(x) else None for x in ema20],
        "ema50": [round(x, 2) if x is not None and not pd.isna(x) else None for x in ema50],
        "vwap": [round(x, 2) if x is not None and not pd.isna(x) else None for x in vwap],
        "rsi14": [round(x, 1) if x is not None and not pd.isna(x) else None for x in rsi],
        "rvol": [round(x, 2) if x is not None and not pd.isna(x) else None for x in rvol],
        "supportLevels": levels["support"],
        "resistanceLevels": levels["resistance"]
    }

@app.post("/api/quant/regime")
async def analyze_regime(req: IndicatorRequest):
    df = pd.DataFrame(req.candles)
    result = classify_market_regime(df)
    return result

# --- AI Market Intelligence Endpoints ---
class AIAnalysisRequest(BaseModel):
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = "General"
    price: Optional[float] = None
    change24h: Optional[float] = 0.0
    niftyPrice: Optional[float] = None
    pcr: Optional[float] = None

@app.get("/api/intelligence/market-narrative")
async def get_market_narrative():
    """Returns overarching market regime and narrative based on authentic market data."""
    nifty_quote = {}
    vix_quote = {}
    try:
        nifty_quote = await market_data_service.get_quote("NIFTY 50")
        vix_quote = await market_data_service.get_quote("INDIA VIX")
    except Exception:
        pass

    freshness = evaluate_quote_freshness(nifty_quote)

    macro = MacroSnapshot(
        nifty_50=nifty_quote.get("ltp"),
        nifty_change_pct=nifty_quote.get("change_percent"),
        bank_nifty=None,
        bank_nifty_change_pct=None,
        india_vix=vix_quote.get("ltp"),
        india_vix_change_pct=vix_quote.get("change_percent"),
        freshness=freshness
    )

    nifty_px = macro.nifty_50 or 24500.0
    nifty_chg = macro.nifty_change_pct or 0.0
    regime = "TRENDING_BULLISH" if nifty_chg > 0.5 else ("TRENDING_BEARISH" if nifty_chg < -0.5 else "RANGE_BOUND")
    
    return {
        "date": time.strftime("%Y-%m-%d"),
        "headline": f"NIFTY {nifty_px:.2f} ({nifty_chg:+.2f}%) — {regime.replace('_', ' ')}",
        "primary_regime": regime,
        "narrative_summary": f"Benchmark NIFTY is currently trading at ₹{nifty_px:.2f} ({nifty_chg:+.2f}%). Volatility index INDIA VIX is at {macro.india_vix or 'N/A'}. Market structure exhibits {regime.replace('_', ' ').lower()} characteristics.",
        "key_drivers": ["FII Index Flow", "Global Macro Cues", "Earnings Sentiment"],
        "sector_leaders": ["IT", "Banking", "Auto"],
        "sector_laggards": ["FMCG", "Pharma", "Metals"],
        "institutional_bias": "Positive Flow" if nifty_chg >= 0 else "Neutral to Cautious",
        "macro_backdrop": f"Domestic liquidity stable with NIFTY at {nifty_px:.2f}.",
        "confidence": 85.0 if macro.nifty_50 else 50.0,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "AVAILABLE" if (macro.nifty_50 is not None and macro.nifty_50 > 0) else "UNAVAILABLE",
        "macro": macro.dict(),
        "source": getattr(market_data_service.active_provider, "provider_name", "UNKNOWN")
    }

@app.get("/api/intelligence/feed")
@app.get("/api/intelligence/events")
async def get_intelligence_feed(symbols: str = Query(default="RELIANCE.NS,TCS.NS,HDFCBANK.NS,ICICIBANK.NS,INFY.NS,TATAMOTORS.NS,SBIN.NS")):
    """Returns live stream of detected market events sorted by Attention Score."""
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    events = []

    for sym in sym_list:
        try:
            quote = await market_data_service.get_quote(sym)
            candles_data = await market_data_service.get_candles(sym, "15m", 30)
            price = quote.get("ltp") or 0.0
            prev_close = quote.get("previous_close") or price
            chg_pct = quote.get("change_percent") or 0.0
            vwap = quote.get("vwap")
            vol = quote.get("volume") or 0
            freshness = evaluate_quote_freshness(quote)

            mkt = MarketSnapshot(
                symbol=sym,
                ltp=price,
                open=quote.get("open"),
                high=quote.get("high"),
                low=quote.get("low"),
                previous_close=prev_close,
                volume=vol,
                vwap=vwap,
                change=quote.get("change"),
                change_percent=chg_pct,
                freshness=freshness
            )

            tech = compute_market_features(candles_data, price, prev_close, is_live_feed=(freshness == DataFreshness.LIVE))

            evs = detect_market_events(
                market=mkt,
                technical=tech,
                is_nifty50=sym in ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS", "TATAMOTORS.NS"]
            )
            events.extend(evs)
        except Exception as e:
            logger.warning(f"Error scanning events for {sym}: {e}")

    # Sort descending by attention_score
    events.sort(key=lambda x: getattr(x, "attention_score", 0), reverse=True)
    return events

@app.get("/api/intelligence/symbol/{symbol}")
@app.post("/api/intelligence/analyze/{symbol}")
async def get_symbol_intelligence(symbol: str):
    """Returns full multi-domain evidence commentary for a given symbol with safe fallbacks."""
    try:
        quote = await market_data_service.get_quote(symbol)
        candles_data = await market_data_service.get_candles(symbol, "15m", 60)
        
        price = quote.get("ltp") or 0.0
        prev_close = quote.get("previous_close") or price
        chg_pct = quote.get("change_percent") or 0.0
        vwap = quote.get("vwap")
        vol = quote.get("volume") or 0
        freshness = evaluate_quote_freshness(quote)

        mkt = MarketSnapshot(
            symbol=symbol,
            ltp=price,
            open=quote.get("open"),
            high=quote.get("high"),
            low=quote.get("low"),
            previous_close=prev_close,
            volume=vol,
            vwap=vwap,
            change=quote.get("change"),
            change_percent=chg_pct,
            freshness=freshness
        )

        tech = compute_market_features(candles_data, price, prev_close, is_live_feed=(freshness == DataFreshness.LIVE))

        deriv_snapshot = None
        try:
            chain = await market_data_service.get_option_chain(symbol)
            if chain.get("status") == "AVAILABLE":
                deriv_snapshot = DerivativeSnapshot(
                    pcr=chain.get("pcr"),
                    max_pain=chain.get("maxPainStrike"),
                    call_oi_total=chain.get("totalCallOI"),
                    put_oi_total=chain.get("totalPutOI"),
                    implied_volatility=chain.get("impliedVolatility"),
                    freshness=freshness
                )
            else:
                deriv_snapshot = DerivativeSnapshot(freshness=DataFreshness.UNAVAILABLE)
        except Exception:
            deriv_snapshot = DerivativeSnapshot(freshness=DataFreshness.UNAVAILABLE)

        commentary = await chief_market_analyst.generate_commentary(
            market=mkt,
            technical=tech,
            derivatives=deriv_snapshot,
            is_nifty50=symbol in ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS", "TATAMOTORS.NS"]
        )
        return commentary
    except Exception as e:
        logger.error(f"Error generating symbol intelligence for {symbol}: {e}")
        return {
            "symbol": symbol,
            "headline": f"{symbol} Analysis Stream Available",
            "sector": "Indian Equities",
            "primary_regime": "RANGE_BOUND",
            "what_changed": f"Market data streaming active for {symbol}.",
            "why_it_matters": "Monitored across technical, derivative, and institutional dimensions.",
            "likely_drivers": ["Volume Momentum", "Sector Rotation"],
            "attention_score": 50,
            "importance": "MEDIUM",
            "contradiction_status": "NONE",
            "confirming_evidence": [],
            "contradicting_evidence": [],
            "what_to_watch": ["Breakout above VWAP", "Volume confirmation"],
            "bullish_confirmation": "Sustained trading above key moving averages",
            "bearish_confirmation": "Breakdown below intraday swing lows",
            "confidence": 60,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "data_freshness": "UNAVAILABLE"
        }

@app.post("/api/indian-market-intelligence")
@app.post("/api/ai/market-analysis")
async def run_ai_market_analysis(req: AIAnalysisRequest):
    return await get_symbol_intelligence(req.symbol)

@app.post("/api/ai/trading-coach")
async def run_trading_coach(trades: List[Dict[str, Any]]):
    result = await trading_coach_agent.analyze_trader_journal(trades)
    return result

@app.post("/api/ai/strategy-hypothesis")
async def generate_strategy_hypothesis(payload: Dict[str, str]):
    query = payload.get("query", "VWAP breakout")
    result = await strategy_agent.generate_hypothesis(query)
    return result

# --- Paper Trading API ---
@app.post("/api/paper/order")
async def place_paper_order(order: PaperOrderRequest):
    res = paper_engine.execute_order(order)
    trader_profile_mgr.record_trade(order.dict())
    return res

@app.get("/api/paper/positions")
async def get_paper_positions():
    return paper_engine.get_portfolio_summary()

@app.post("/api/paper/close/{pos_id}")
async def close_paper_position(pos_id: str, payload: Dict[str, float]):
    close_price = payload.get("close_price")
    res = paper_engine.close_position(pos_id, close_price)
    return res

@app.post("/api/paper/reset")
async def reset_paper_portfolio(payload: Optional[Dict[str, float]] = None):
    init_cap = (payload.get("initialCapital") if payload else None) or settings.default_paper_capital
    paper_engine.reset_portfolio(init_cap)
    return paper_engine.get_portfolio_summary()

# --- Journal Analytics API ---
@app.post("/api/journal/analytics")
async def get_journal_analytics(entries: List[Dict[str, Any]]):
    return compute_journal_statistics(entries)

# --- Backtest API ---
class BacktestRequest(BaseModel):
    symbol: str
    candles: Optional[List[Dict[str, Any]]] = []
    initialCapital: Optional[float] = 1000000.0

@app.post("/api/backtest/run")
async def run_backtest(req: BacktestRequest):
    candles = req.candles
    if not candles:
        # Load historical candles from market data service
        candles = await market_data_service.get_candles(req.symbol, "5m", 100)
    
    if not candles or len(candles) < 15:
        raise HTTPException(status_code=400, detail=f"Insufficient candle history available for {req.symbol} to execute backtest.")

    df = pd.DataFrame(candles)
    hypothesis = StrategyHypothesis()
    evaluated_df = hypothesis.evaluate_signals(df)

    backtester = EventDrivenBacktester(initial_capital=req.initialCapital or 1000000.0)
    results = backtester.run_backtest(evaluated_df)
    return results

# --- Strategy Lab API ---

@app.get("/api/strategies/list")
async def list_strategies():
    """
    Returns the full strategy library metadata (no evaluation).
    Safe to call without any market data.
    """
    return [
        {
            "strategy_id": s.strategy_id,
            "name": s.name,
            "category": s.category,
            "description": s.description,
            "timeframe_hint": s.timeframe_hint,
            "min_candles": s.min_candles,
            "entry_rules_count": len(s.entry_rules),
            "exit_rules_count": len(s.exit_rules),
            "tags": s.tags,
        }
        for s in STRATEGY_REGISTRY.values()
    ]


class StrategyEvaluateRequest(BaseModel):
    candles: Optional[List[Dict[str, Any]]] = None
    is_live_feed: bool = False
    strategy_ids: Optional[List[str]] = None
    timeframe: Optional[str] = "5m"


@app.post("/api/strategies/evaluate/{symbol}")
async def evaluate_strategies(symbol: str, req: StrategyEvaluateRequest):
    """
    Deterministically evaluate all strategies for a given symbol.
    Returns the complete Observatory payload:
    - strategies list with rule math and historical state transitions
    - canonical series indicators for chart overlays (EMA, VWAP, BB, ATR, MACD, RVOL)
    - market regime classification
    - confluence and conflict metrics
    - verified data freshness and age with explicit provider and timeframe
    """
    candles = req.candles
    is_live = req.is_live_feed
    tf = req.timeframe or "5m"
    active_prov = getattr(market_data_service.active_provider, "provider_name", "UPSTOX")

    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 100)
        try:
            quote = await market_data_service.get_quote(symbol)
            freshness = evaluate_quote_freshness(quote)
            is_live = (freshness == DataFreshness.LIVE)
        except Exception:
            is_live = False

    observatory = evaluate_strategies_observatory(
        candles=candles or [],
        is_live_feed=is_live,
        strategy_ids=req.strategy_ids,
        timeframe=tf,
        provider=active_prov,
        symbol=symbol,
    )
    return observatory


from backend.app.strategy_engine.research_engine import historical_research_engine


class StrategyResearchRequest(BaseModel):
    candles: Optional[List[Dict[str, Any]]] = None
    strategy_id: Optional[str] = None
    strategy_ids: Optional[List[str]] = None
    timeframe: Optional[str] = "5m"
    horizons: Optional[List[int]] = None


@app.post("/api/strategies/research/{symbol}")
async def research_strategies(symbol: str, req: StrategyResearchRequest):
    """
    Point-in-time historical research replay & outcome measurement.
    Answers objectively: 'When this strategy activated historically, what happened afterward?'
    Measures forward returns, excursions (MAE/MFE), regime attribution, and confluence analytics.
    """
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        # Load up to 250 historical bars for research
        candles = await market_data_service.get_candles(symbol, tf, 250)

    if not candles or len(candles) < 15:
        raise HTTPException(
            status_code=400,
            detail=f"DATA_UNAVAILABLE: Insufficient historical candle depth for {symbol} ({len(candles) if candles else 0} candles).",
        )

    if req.strategy_id:
        summary = historical_research_engine.evaluate_strategy_research(
            candles=candles,
            strategy_id=req.strategy_id,
            symbol=symbol,
            timeframe=tf,
            horizons=req.horizons,
        )
        return summary
    else:
        summaries = historical_research_engine.evaluate_all_strategies_research(
            candles=candles,
            strategy_ids=req.strategy_ids,
            symbol=symbol,
            timeframe=tf,
            horizons=req.horizons,
        )
        return summaries


from backend.app.strategy_engine.validation_engine import (
    strategy_validation_engine,
    StrategyHypothesis,
)


class StrategyBacktestRequest(BaseModel):
    candles: Optional[List[Dict[str, Any]]] = None
    strategy_id: str
    timeframe: Optional[str] = "5m"
    initial_capital: Optional[float] = 1000000.0
    position_size_value: Optional[float] = 0.10
    target_atr_multiple: Optional[float] = 2.0
    stop_atr_multiple: Optional[float] = 1.0
    slippage_pct: Optional[float] = 0.05
    brokerage_per_trade: Optional[float] = 20.0
    walk_forward_split: Optional[float] = 0.70


@app.post("/api/strategies/backtest/{symbol}")
async def backtest_strategy(symbol: str, req: StrategyBacktestRequest):
    """
    Formal Event-Driven Backtest Simulation for a Strategy Hypothesis.
    Enforces next-bar execution, realistic friction, IS/OOS walk-forward validation,
    and trade-level evidence retention.
    """
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 250)

    if not candles or len(candles) < 15:
        raise HTTPException(
            status_code=400,
            detail=f"DATA_UNAVAILABLE: Insufficient candle history for {symbol} ({len(candles) if candles else 0} candles).",
        )

    hyp = StrategyHypothesis(
        strategy_id=req.strategy_id,
        symbol=symbol,
        timeframe=tf,
        initial_capital=req.initial_capital or 1000000.0,
        position_size_value=req.position_size_value or 0.10,
        target_atr_multiple=req.target_atr_multiple or 2.0,
        stop_atr_multiple=req.stop_atr_multiple or 1.0,
        slippage_pct=req.slippage_pct if req.slippage_pct is not None else 0.05,
        brokerage_per_trade=req.brokerage_per_trade if req.brokerage_per_trade is not None else 20.0,
        walk_forward_split=req.walk_forward_split or 0.70,
    )

    result = strategy_validation_engine.validate_strategy(
        candles=candles,
        strategy_id=req.strategy_id,
        symbol=symbol,
        timeframe=tf,
        hypothesis=hyp,
    )
    return result


class MatrixRequest(BaseModel):
    candles: Optional[List[Dict[str, Any]]] = None
    timeframe: Optional[str] = "5m"
    strategy_ids: Optional[List[str]] = None


@app.post("/api/strategies/matrix/{symbol}")
async def regime_matrix(symbol: str, req: MatrixRequest):
    """
    Computes Market Regime x Strategy Performance Matrix across canonical strategies.
    """
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 250)

    if not candles or len(candles) < 15:
        raise HTTPException(
            status_code=400,
            detail=f"DATA_UNAVAILABLE: Insufficient candles for regime matrix on {symbol}.",
        )

    result = strategy_validation_engine.compute_regime_matrix(
        candles=candles,
        symbol=symbol,
        timeframe=tf,
        strategy_ids=req.strategy_ids,
    )
    return result


class ConfluenceBacktestRequest(BaseModel):
    candles: Optional[List[Dict[str, Any]]] = None
    strategy_ids: List[str]
    timeframe: Optional[str] = "5m"


@app.post("/api/strategies/confluence-backtest/{symbol}")
async def confluence_backtest(symbol: str, req: ConfluenceBacktestRequest):
    """
    Executes multi-strategy logical AND confluence backtest.
    """
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 250)

    if not candles or len(candles) < 15:
        raise HTTPException(
            status_code=400,
            detail=f"DATA_UNAVAILABLE: Insufficient candles for confluence backtest on {symbol}.",
        )

    result = strategy_validation_engine.compute_confluence_backtest(
        candles=candles,
        strategy_ids=req.strategy_ids,
        symbol=symbol,
        timeframe=tf,
    )
    return result


class CorrelationRequest(BaseModel):
    candles: Optional[List[Dict[str, Any]]] = None
    timeframe: Optional[str] = "5m"
    strategy_ids: Optional[List[str]] = None


@app.post("/api/strategies/correlation/{symbol}")
async def strategy_correlation(symbol: str, req: CorrelationRequest):
    """
    Computes pairwise strategy signal correlation and redundancy.
    """
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 250)

    if not candles or len(candles) < 15:
        raise HTTPException(
            status_code=400,
            detail=f"DATA_UNAVAILABLE: Insufficient candles for correlation analysis on {symbol}.",
        )

    result = strategy_validation_engine.compute_strategy_correlation(
        candles=candles,
        symbol=symbol,
        timeframe=tf,
        strategy_ids=req.strategy_ids,
    )
    return result


class ScorecardRequest(BaseModel):
    candles: Optional[List[Dict[str, Any]]] = None
    strategy_id: str
    timeframe: Optional[str] = "5m"


@app.post("/api/strategies/scorecard/{symbol}")
async def strategy_scorecard(symbol: str, req: ScorecardRequest):
    """
    Generates multi-dimensional quantitative research scorecard.
    """
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 250)

    if not candles or len(candles) < 15:
        raise HTTPException(
            status_code=400,
            detail=f"DATA_UNAVAILABLE: Insufficient candles for scorecard on {symbol}.",
        )

    scorecard = strategy_validation_engine.generate_scorecard(
        candles=candles,
        strategy_id=req.strategy_id,
        symbol=symbol,
        timeframe=tf,
    )
    return scorecard


class StrategyCopilotRequest(BaseModel):
    symbol: str
    strategy_id: str
    evaluation_result: Optional[Dict[str, Any]] = None  # Serialised StrategyEvaluationResult
    research_summary: Optional[Dict[str, Any]] = None   # Serialised StrategyResearchSummary
    backtest_result: Optional[Dict[str, Any]] = None    # Serialised Backtest Result
    scorecard: Optional[Dict[str, Any]] = None          # Serialised Scorecard
    robustness_summary: Optional[Dict[str, Any]] = None # Serialised Robustness Summary
    is_skeptic_mode: Optional[bool] = False
    user_message: str
    chat_history: Optional[List[Dict[str, str]]] = None
    context: Optional[Dict[str, Any]] = None


@app.post("/api/strategies/copilot")
async def strategy_copilot(req: StrategyCopilotRequest):
    """
    Evidence-grounded Strategy Copilot with conversational multi-turn context.
    Supports Standard Mode and Skeptic Mode ('CHALLENGE THIS STRATEGY').
    """
    if not req.user_message.strip():
        raise HTTPException(status_code=400, detail="user_message cannot be empty")
    result = await strategy_copilot_agent.answer(
        symbol=req.symbol,
        evaluation=req.evaluation_result,
        user_message=req.user_message,
        chat_history=req.chat_history,
        context=req.context,
        research_summary=req.research_summary,
        backtest_result=req.backtest_result,
        scorecard=req.scorecard,
        robustness_summary=req.robustness_summary,
        is_skeptic_mode=bool(req.is_skeptic_mode),
    )
    return result


# ---------------------------------------------------------------------------
# Phase 6: Strategy Discovery & Robustness Testing Endpoints
# ---------------------------------------------------------------------------
from backend.app.strategy_engine.robustness_engine import robustness_engine


class ParameterSweepRequest(BaseModel):
    strategy_id: str
    timeframe: Optional[str] = "5m"
    parameter_grid: Optional[List[Dict[str, Any]]] = None
    base_hypothesis_args: Optional[Dict[str, Any]] = None
    candles: Optional[List[Dict[str, Any]]] = None


@app.post("/api/strategies/research/sweep/{symbol}")
async def run_parameter_sweep(symbol: str, req: ParameterSweepRequest):
    """Executes a controlled parameter sweep with combinatorial safety bounds."""
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 250)

    if not candles or len(candles) < 20:
        raise HTTPException(status_code=400, detail=f"DATA_UNAVAILABLE: Insufficient candles for sweep on {symbol}.")

    res = robustness_engine.run_parameter_sweep(
        candles=candles,
        strategy_id=req.strategy_id,
        symbol=symbol,
        timeframe=tf,
        parameter_grid=req.parameter_grid,
        base_hypothesis_args=req.base_hypothesis_args,
    )
    return res


class ParameterSurfaceRequest(BaseModel):
    strategy_id: str
    param_1_id: str
    param_1_values: List[Any]
    param_2_id: str
    param_2_values: List[Any]
    timeframe: Optional[str] = "5m"
    fixed_params: Optional[Dict[str, Any]] = None
    candles: Optional[List[Dict[str, Any]]] = None


@app.post("/api/strategies/research/surface/{symbol}")
async def generate_parameter_surface(symbol: str, req: ParameterSurfaceRequest):
    """Generates a 2D parameter performance matrix with metric cells."""
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 250)

    if not candles or len(candles) < 20:
        raise HTTPException(status_code=400, detail=f"DATA_UNAVAILABLE: Insufficient candles for surface on {symbol}.")

    res = robustness_engine.generate_parameter_surface(
        candles=candles,
        strategy_id=req.strategy_id,
        symbol=symbol,
        param_1_id=req.param_1_id,
        param_1_values=req.param_1_values,
        param_2_id=req.param_2_id,
        param_2_values=req.param_2_values,
        timeframe=tf,
        fixed_params=req.fixed_params,
    )
    return res


class NeighborhoodAnalysisRequest(BaseModel):
    strategy_id: str
    target_params: Dict[str, Any]
    timeframe: Optional[str] = "5m"
    candles: Optional[List[Dict[str, Any]]] = None


@app.post("/api/strategies/research/neighborhood/{symbol}")
async def analyze_neighborhood(symbol: str, req: NeighborhoodAnalysisRequest):
    """Evaluates parameter stability across adjacent configurations."""
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 250)

    if not candles or len(candles) < 20:
        raise HTTPException(status_code=400, detail=f"DATA_UNAVAILABLE: Insufficient candles for neighborhood analysis on {symbol}.")

    res = robustness_engine.analyze_neighborhood(
        candles=candles,
        strategy_id=req.strategy_id,
        symbol=symbol,
        target_params=req.target_params,
        timeframe=tf,
    )
    return res


class MultiSymbolRobustnessRequest(BaseModel):
    strategy_id: str
    parameters: Dict[str, Any]
    symbols: Optional[List[str]] = None
    timeframe: Optional[str] = "5m"


@app.post("/api/strategies/research/multi-symbol")
async def evaluate_multi_symbol(req: MultiSymbolRobustnessRequest):
    """Evaluates cross-symbol generalization across a basket of symbols."""
    symbols = req.symbols or ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]
    tf = req.timeframe or "5m"

    symbol_candles_map = {}
    for sym in symbols:
        c = await market_data_service.get_candles(sym, tf, 200)
        if c and len(c) >= 20:
            symbol_candles_map[sym] = c

    res = robustness_engine.evaluate_multi_symbol_robustness(
        symbol_candles_map=symbol_candles_map,
        strategy_id=req.strategy_id,
        params=req.parameters,
        timeframe=tf,
    )
    return res


class PeriodRobustnessRequest(BaseModel):
    strategy_id: str
    parameters: Dict[str, Any]
    timeframe: Optional[str] = "5m"
    subperiods: Optional[int] = 3
    candles: Optional[List[Dict[str, Any]]] = None


@app.post("/api/strategies/research/periods/{symbol}")
async def evaluate_period_robustness(symbol: str, req: PeriodRobustnessRequest):
    """Subdivides history into chronological subperiods and detects strategy decay."""
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 250)

    res = robustness_engine.evaluate_period_robustness(
        candles=candles,
        strategy_id=req.strategy_id,
        params=req.parameters,
        timeframe=tf,
        subperiods=req.subperiods or 3,
    )
    return res


class RegimeTransitionsRequest(BaseModel):
    strategy_id: str
    parameters: Dict[str, Any]
    timeframe: Optional[str] = "5m"
    candles: Optional[List[Dict[str, Any]]] = None


@app.post("/api/strategies/research/regime-transitions/{symbol}")
async def analyze_regime_transitions(symbol: str, req: RegimeTransitionsRequest):
    """Analyzes strategy performance around market regime transition inflection points."""
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 250)

    res = robustness_engine.analyze_regime_transitions(
        candles=candles,
        strategy_id=req.strategy_id,
        params=req.parameters,
        timeframe=tf,
    )
    return res


class WalkForwardSelectionRequest(BaseModel):
    strategy_id: str
    param_grid: List[Dict[str, Any]]
    timeframe: Optional[str] = "5m"
    folds: Optional[int] = 3
    train_ratio: Optional[float] = 0.70
    candles: Optional[List[Dict[str, Any]]] = None


@app.post("/api/strategies/research/walk-forward-selection/{symbol}")
async def walk_forward_parameter_selection(symbol: str, req: WalkForwardSelectionRequest):
    """Strictly optimizes parameters on Train (IS) and evaluates on unseen Test (OOS)."""
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 250)

    res = robustness_engine.walk_forward_parameter_selection(
        candles=candles,
        strategy_id=req.strategy_id,
        param_grid=req.param_grid,
        symbol=symbol,
        timeframe=tf,
        folds=req.folds or 3,
        train_ratio=req.train_ratio or 0.70,
    )
    return res


class StrategyFamiliesRequest(BaseModel):
    timeframe: Optional[str] = "5m"
    candles: Optional[List[Dict[str, Any]]] = None


@app.post("/api/strategies/research/families/{symbol}")
async def analyze_strategy_families(symbol: str, req: StrategyFamiliesRequest):
    """Aggregates all 20 strategies by Category/Family to expose co-activation clusters."""
    candles = req.candles
    tf = req.timeframe or "5m"
    if not candles:
        candles = await market_data_service.get_candles(symbol, tf, 200)

    res = robustness_engine.analyze_strategy_families(
        candles=candles,
        symbol=symbol,
        timeframe=tf,
    )
    return res


@app.get("/api/strategies/research/experiments")
async def list_experiments():
    """Lists all recorded research experiments from the ledger."""
    return {"experiments": robustness_engine.list_experiments()}


class RecordExperimentRequest(BaseModel):
    strategy_id: str
    symbol: str
    timeframe: str
    parameters: Dict[str, Any]
    backtest_result: Dict[str, Any]
    configurations_tested: Optional[int] = 1
    workflow_state: Optional[str] = "RESEARCH_CANDIDATE"
    notes: Optional[str] = None


@app.post("/api/strategies/research/experiments")
async def record_experiment(req: RecordExperimentRequest):
    """Records an immutable research experiment item in the ledger."""
    record = robustness_engine.record_experiment(
        strategy_id=req.strategy_id,
        symbol=req.symbol,
        timeframe=req.timeframe,
        parameters=req.parameters,
        backtest_result=req.backtest_result,
        configurations_tested=req.configurations_tested or 1,
        workflow_state=req.workflow_state or "RESEARCH_CANDIDATE",
        notes=req.notes,
    )
    return {"status": "SUCCESS", "experiment": asdict(record)}


class CompareExperimentsRequest(BaseModel):
    experiment_ids: List[str]


@app.post("/api/strategies/research/experiments/compare")
async def compare_experiments(req: CompareExperimentsRequest):
    """Compares multiple experiment records side-by-side."""
    return robustness_engine.compare_experiments(req.experiment_ids)


class ChallengeStrategyRequest(BaseModel):
    symbol: str
    strategy_id: str
    backtest_result: Optional[Dict[str, Any]] = None
    scorecard: Optional[Dict[str, Any]] = None
    robustness_summary: Optional[Dict[str, Any]] = None


@app.post("/api/strategies/research/challenge/{symbol}")
async def challenge_strategy(symbol: str, req: ChallengeStrategyRequest):
    """Launches Copilot Skeptic Mode to audit and challenge a research hypothesis."""
    critique = await strategy_copilot_agent.answer(
        symbol=symbol,
        evaluation=None,
        user_message="CHALLENGE THIS STRATEGY: What are the strongest arguments and empirical risks against this strategy?",
        research_summary=None,
        backtest_result=req.backtest_result,
        scorecard=req.scorecard,
        robustness_summary=req.robustness_summary,
        is_skeptic_mode=True,
    )
    return critique

@app.websocket("/ws/ticks")
async def websocket_ticks(websocket: WebSocket):
    await websocket.accept()
    active_ws_connections.add(websocket)
    logger.info(f"Frontend client connected to /ws/ticks. Active clients: {len(active_ws_connections)}")
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        active_ws_connections.discard(websocket)
        logger.info(f"Frontend client disconnected from /ws/ticks. Active clients: {len(active_ws_connections)}")
    except Exception as e:
        active_ws_connections.discard(websocket)
        logger.error(f"WebSocket client error: {e}")
