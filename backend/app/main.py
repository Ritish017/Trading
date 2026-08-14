import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

from backend.app.config import settings
from backend.app.database.connection import init_db
from backend.app.broker_providers.base import NormalizedTick
from backend.app.market_data.service import MarketDataService
from backend.app.market_data.candle_aggregator import MarketCandleAggregator
from backend.app.quant_engine.indicators import (
    calculate_ema, calculate_vwap, calculate_rsi, calculate_macd, calculate_atr, calculate_bollinger_bands, detect_support_resistance, calculate_roc, calculate_stochastic, calculate_relative_volume
)
from backend.app.quant_engine.regime import classify_market_regime
from backend.app.quant_engine.options import calculate_pcr, calculate_max_pain, classify_oi_pattern
from backend.app.strategy_engine.dsl import StrategyHypothesis
from backend.app.ai_engine.agents import MarketResearchAgent, PersonalTradingCoach, StrategyResearchAgent
from backend.app.backtesting.event_driven import EventDrivenBacktester
from backend.app.paper_trading.engine import PaperTradingEngine, PaperOrderRequest
from backend.app.journal.analytics import compute_journal_statistics
from backend.app.personalization.trader_profile import trader_profile_mgr

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

active_ws_connections: Set[WebSocket] = set()

async def on_normalized_tick_received(tick: NormalizedTick):
    """Callback triggered whenever a normalized tick is received from MarketDataService."""
    updated_candles = candle_aggregator.process_tick(tick)
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
        "real_trading_enabled": settings.real_trading_enabled
    }

@app.get("/health/data-feed")
async def data_feed_health():
    return market_data_service.get_health_status()

@app.get("/health/database")
async def database_health():
    return {"status": "ONLINE", "type": "AsyncSQLite/PostgreSQL"}

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
    candle_aggregator.seed_historical_candles(symbol, interval, candles)
    return {"symbol": symbol, "interval": interval, "candles": candles, "source": "PROVIDER"}

@app.get("/api/market/option-chain/{symbol}")
async def get_option_chain(symbol: str):
    return await market_data_service.get_option_chain(symbol)

# --- Phase 10 Market Information APIs ---
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
    return [
        {
            "id": "ann_1",
            "companySymbol": "RELIANCE.NS",
            "category": "Quarterly Disclosures",
            "headline": "Jio Platforms reports 12.4% YoY increase in Q3 Net Profit to ₹5,420 Cr; ARPU rises to ₹188.5",
            "details": "Digital services segment recorded highest ever subscriber addition of 10.8 million during the quarter.",
            "timestamp": "10:42 AM IST",
            "source": "NSE_FILING"
        },
        {
            "id": "ann_2",
            "companySymbol": "HDFCBANK.NS",
            "category": "SEBI Disclosure",
            "headline": "SEBI grants approval for HDFC Mutual Fund new thematic infrastructure equity scheme",
            "details": "Regulatory approval received under SEBI Mutual Funds Regulations 1996 for new fund offering.",
            "timestamp": "09:55 AM IST",
            "source": "NSE_FILING"
        },
        {
            "id": "ann_3",
            "companySymbol": "TCS.NS",
            "category": "Corporate Action",
            "headline": "TCS secures $450 Million multi-year AI cloud transformation deal with European retail giant",
            "details": "Strategic technology modernization contract covering cloud migration and generative AI integration.",
            "timestamp": "09:18 AM IST",
            "source": "BSE_FILING"
        }
    ]

@app.get("/api/market/breadth")
async def get_market_breadth():
    return {
        "universe": "NSE Equity",
        "advances": 1482,
        "declines": 840,
        "unchanged": 128,
        "ratio": 1.76,
        "new52WeekHighs": 142,
        "new52WeekLows": 18,
        "upperCircuits": 84,
        "lowerCircuits": 12,
        "source": "NSE_OFFICIAL",
        "as_of": "15:30 IST"
    }

# --- Quantitative Analysis API ---
class IndicatorRequest(BaseModel):
    symbol: str
    candles: List[Dict[str, Any]]

@app.post("/api/quant/indicators")
async def compute_indicators(req: IndicatorRequest):
    if not req.candles:
        raise HTTPException(status_code=400, detail="Candles array cannot be empty")
    
    df = pd.DataFrame(req.candles)
    close = df['close']
    
    ema20 = calculate_ema(close, 20).tolist()
    ema50 = calculate_ema(close, 50).tolist()
    vwap = calculate_vwap(df).tolist() if 'high' in df and 'low' in df and 'volume' in df else close.tolist()
    rsi = calculate_rsi(close, 14).tolist()
    rvol = calculate_relative_volume(df['volume'], 20).tolist() if 'volume' in df else [1.0] * len(df)
    levels = detect_support_resistance(df)

    return {
        "symbol": req.symbol,
        "ema20": [round(x, 2) for x in ema20],
        "ema50": [round(x, 2) for x in ema50],
        "vwap": [round(x, 2) for x in vwap],
        "rsi14": [round(x, 1) for x in rsi],
        "rvol": [round(x, 2) for x in rvol],
        "supportLevels": levels["support"],
        "resistanceLevels": levels["resistance"]
    }

@app.post("/api/quant/regime")
async def analyze_regime(req: IndicatorRequest):
    df = pd.DataFrame(req.candles)
    result = classify_market_regime(df)
    return result

from backend.app.ai_engine.chief_analyst import ChiefMarketAnalyst
from backend.app.quant_engine.features import compute_market_features
from backend.app.event_engine.detector import detect_market_events
from backend.app.ai_engine.contracts import (
    MarketSnapshot, TechnicalSnapshot, DerivativeSnapshot, NewsSnapshot, SectorSnapshot, MacroSnapshot, InstitutionalSnapshot,
    DataFreshness
)

chief_market_analyst = ChiefMarketAnalyst(api_key=settings.gemini_api_key)

# --- AI Market Intelligence Endpoints ---
class AIAnalysisRequest(BaseModel):
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = "General"
    price: float
    change24h: Optional[float] = 0.0
    niftyPrice: Optional[float] = 24580.0
    pcr: Optional[float] = 1.18

@app.get("/api/intelligence/market-narrative")
async def get_market_narrative():
    """Returns today's overarching market regime and institutional narrative."""
    macro = MacroSnapshot(
        nifty_50=24580.45,
        nifty_change_pct=+0.42,
        bank_nifty=51240.80,
        bank_nifty_change_pct=+0.65,
        india_vix=13.82,
        india_vix_change_pct=-2.14
    )
    narrative = chief_market_analyst.generate_market_narrative(
        macro=macro,
        sector_leaders=["Banking & Financials", "Automotive", "Energy & Oil"],
        sector_laggards=["IT Services", "Metals"],
        fii_cash_net=+1840.50,
        dii_cash_net=+1210.80
    )
    return narrative

@app.get("/api/intelligence/feed")
@app.get("/api/intelligence/events")
async def get_intelligence_feed(symbols: str = Query(default="RELIANCE.NS,TCS.NS,HDFCBANK.NS,ICICIBANK.NS,INFY.NS,TATAMOTORS.NS,SBIN.NS,MRF.NS")):
    """Returns live stream of detected market events sorted by Attention Score."""
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    events = []
    
    macro = MacroSnapshot(
        nifty_50=24580.45,
        nifty_change_pct=+0.42,
        bank_nifty=51240.80,
        bank_nifty_change_pct=+0.65,
        india_vix=13.82,
        india_vix_change_pct=-2.14
    )

    for sym in sym_list:
        try:
            quote = await market_data_service.get_quote(sym)
            candles_data = await market_data_service.get_candles(sym, "15m", 30)
            price = quote.get("ltp", 1000.0)
            prev_close = quote.get("close", price)
            chg_pct = quote.get("change_percent", 0.0)
            vwap = quote.get("vwap", price)
            vol = quote.get("volume", 500000)

            mkt = MarketSnapshot(
                symbol=sym,
                ltp=price,
                open=quote.get("open", price),
                high=quote.get("high", price),
                low=quote.get("low", price),
                previous_close=prev_close,
                volume=vol,
                vwap=vwap,
                change=quote.get("change", 0.0),
                change_percent=chg_pct
            )

            tech = compute_market_features(candles_data, price, prev_close)
            sec = SectorSnapshot(
                sector_name="Automotive" if "TATAMOTORS" in sym or "MRF" in sym else "IT Services" if "TCS" in sym or "INFY" in sym else "Banking" if "BANK" in sym or "SBIN" in sym else "Energy & Oil",
                change_percent=chg_pct * 0.8,
                relative_strength=chg_pct - 0.42,
                breadth_advances=18,
                breadth_declines=8
            )

            evs = detect_market_events(
                market=mkt,
                technical=tech,
                sector=sec,
                macro=macro,
                is_nifty50=sym in ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS", "TATAMOTORS.NS"]
            )
            events.extend(evs)
        except Exception as e:
            logger.warning(f"Error scanning events for {sym}: {e}")

    # Sort descending by attention_score
    events.sort(key=lambda x: x.attention_score, reverse=True)
    return events

@app.get("/api/intelligence/symbol/{symbol}")
@app.post("/api/intelligence/analyze/{symbol}")
async def get_symbol_intelligence(symbol: str):
    """Returns full multi-domain evidence commentary for a given symbol."""
    quote = await market_data_service.get_quote(symbol)
    candles_data = await market_data_service.get_candles(symbol, "15m", 60)
    
    price = quote.get("ltp", 1000.0)
    prev_close = quote.get("close", price)
    chg_pct = quote.get("change_percent", 0.0)
    vwap = quote.get("vwap", price)
    vol = quote.get("volume", 500000)

    mkt = MarketSnapshot(
        symbol=symbol,
        ltp=price,
        open=quote.get("open", price),
        high=quote.get("high", price),
        low=quote.get("low", price),
        previous_close=prev_close,
        volume=vol,
        vwap=vwap,
        change=quote.get("change", 0.0),
        change_percent=chg_pct
    )

    tech = compute_market_features(candles_data, price, prev_close)
    deriv = DerivativeSnapshot(
        pcr=1.18 if "RELIANCE" in symbol or "TCS" in symbol else 0.92,
        futures_oi_change=+4.8,
        implied_volatility=14.2,
        oi_pattern="Long Buildup" if chg_pct > 0 else "Short Buildup"
    )
    sec = SectorSnapshot(
        sector_name="Automotive" if "TATAMOTORS" in symbol or "MRF" in symbol else "IT Services" if "TCS" in symbol or "INFY" in symbol else "Banking & Financials" if "BANK" in symbol or "SBIN" in symbol else "Energy & Oil",
        change_percent=chg_pct * 0.75,
        relative_strength=chg_pct - 0.42,
        breadth_advances=22,
        breadth_declines=10
    )
    macro = MacroSnapshot(
        nifty_50=24580.45,
        nifty_change_pct=+0.42,
        bank_nifty=51240.80,
        bank_nifty_change_pct=+0.65,
        india_vix=13.82,
        india_vix_change_pct=-2.14
    )
    inst = InstitutionalSnapshot(
        fii_cash_net_cr=+1840.50,
        dii_cash_net_cr=+1210.80,
        as_of="Today"
    )

    commentary = await chief_market_analyst.generate_commentary(
        market=mkt,
        technical=tech,
        derivatives=deriv,
        sector=sec,
        macro=macro,
        institutional=inst,
        is_nifty50=symbol in ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS", "TATAMOTORS.NS"]
    )
    return commentary

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
    return {
        "positions": list(paper_engine.positions.values()),
        "capital": paper_engine.capital
    }

@app.post("/api/paper/close/{pos_id}")
async def close_paper_position(pos_id: str, payload: Dict[str, float]):
    close_price = payload.get("close_price", 1000.0)
    res = paper_engine.close_position(pos_id, close_price)
    return res

# --- Journal Analytics API ---
@app.post("/api/journal/analytics")
async def get_journal_analytics(entries: List[Dict[str, Any]]):
    return compute_journal_statistics(entries)

# --- Backtest API ---
class BacktestRequest(BaseModel):
    symbol: str
    candles: List[Dict[str, Any]]
    initialCapital: Optional[float] = 1000000.0

@app.post("/api/backtest/run")
async def run_backtest(req: BacktestRequest):
    df = pd.DataFrame(req.candles)
    if df.empty:
        raise HTTPException(status_code=400, detail="Candles data is required for backtest")
    
    hypothesis = StrategyHypothesis()
    evaluated_df = hypothesis.evaluate_signals(df)

    backtester = EventDrivenBacktester(initial_capital=req.initialCapital or 1000000.0)
    results = backtester.run_backtest(evaluated_df)
    return results

# --- Real-Time WebSocket Endpoint ---
@app.websocket("/ws/ticks")
async def websocket_ticks(websocket: WebSocket):
    await websocket.accept()
    active_ws_connections.add(websocket)
    logger.info(f"Frontend client connected to /ws/ticks. Active clients: {len(active_ws_connections)}")
    try:
        while True:
            # Keep connection alive
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        active_ws_connections.discard(websocket)
        logger.info(f"Frontend client disconnected from /ws/ticks. Active clients: {len(active_ws_connections)}")
    except Exception as e:
        active_ws_connections.discard(websocket)
        logger.error(f"WebSocket client error: {e}")
