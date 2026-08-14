import pytest
from backend.app.ai_engine.contracts import (
    MarketSnapshot, TechnicalSnapshot, DerivativeSnapshot, NewsSnapshot, SectorSnapshot, MacroSnapshot, InstitutionalSnapshot,
    SignalStance, AttentionClassification, ImportanceLevel
)
from backend.app.quant_engine.features import compute_market_features, compute_z_score
from backend.app.event_engine.attention import compute_attention_score
from backend.app.event_engine.detector import detect_market_events
from backend.app.ai_engine.specialized_analysts import (
    TechnicalAnalyst, DerivativesAnalyst, NewsAnalyst, SectorAnalyst, InstitutionalAnalyst
)
from backend.app.ai_engine.contradiction import detect_contradictions
from backend.app.ai_engine.chief_analyst import ChiefMarketAnalyst

def test_feature_engine():
    candles = [
        {"open": 100 + i, "high": 105 + i, "low": 98 + i, "close": 102 + i, "volume": 10000 + i * 500}
        for i in range(30)
    ]
    tech = compute_market_features(candles, 132.0, 131.0)
    assert tech.rsi_14 is not None
    assert tech.ema_20 is not None
    assert tech.relative_volume is not None
    assert len(tech.support_levels) > 0

def test_attention_score_bounds():
    mkt = MarketSnapshot(
        symbol="RELIANCE.NS",
        ltp=2850.0,
        open=2820.0,
        high=2860.0,
        low=2810.0,
        previous_close=2800.0,
        volume=2500000,
        vwap=2840.0,
        change=50.0,
        change_percent=1.78
    )
    tech = TechnicalSnapshot(relative_volume=2.4, rsi_14=64.0)
    deriv = DerivativeSnapshot(pcr=1.35, futures_oi_change=12.5)
    
    score = compute_attention_score(mkt, tech, deriv, is_nifty50=True)
    assert 0 <= score.total_score <= 100
    assert score.classification in [
        AttentionClassification.MONITOR,
        AttentionClassification.INTERESTING,
        AttentionClassification.IMPORTANT,
        AttentionClassification.CRITICAL
    ]

def test_event_detection_unusual_selling():
    mkt = MarketSnapshot(
        symbol="TCS.NS",
        ltp=4200.0,
        open=4300.0,
        high=4310.0,
        low=4190.0,
        previous_close=4300.0,
        volume=3000000,
        vwap=4250.0,
        change=-100.0,
        change_percent=-2.32
    )
    tech = TechnicalSnapshot(relative_volume=2.8, rsi_14=32.0)
    events = detect_market_events(mkt, tech, is_nifty50=True)
    
    assert len(events) > 0
    selling_ev = next((e for e in events if e.event_type == "UNUSUAL_SELLING"), None)
    assert selling_ev is not None
    assert selling_ev.severity >= 60
    assert len(selling_ev.evidence) >= 2

def test_contradiction_engine():
    mkt = MarketSnapshot(
        symbol="INFY.NS",
        ltp=1850.0,
        open=1820.0,
        high=1860.0,
        low=1815.0,
        previous_close=1820.0,
        volume=1500000,
        vwap=1840.0,
        change=30.0,
        change_percent=+1.65
    )
    tech = TechnicalSnapshot(rsi_14=65.0, ema_20=1830.0, ema_50=1810.0)
    deriv = DerivativeSnapshot(pcr=0.62, futures_oi_change=0.0) # Bearish Call writing resistance

    ta_eval = TechnicalAnalyst.analyze(mkt, tech) # Bullish
    da_eval = DerivativesAnalyst.analyze(deriv, mkt.change_percent) # Bearish
    
    report = detect_contradictions([ta_eval, da_eval])
    assert report.has_contradiction is True
    assert report.consensus_stance == SignalStance.MIXED

@pytest.mark.asyncio
async def test_chief_market_analyst_commentary():
    analyst = ChiefMarketAnalyst()
    mkt = MarketSnapshot(
        symbol="MRF.NS",
        ltp=132235.0,
        open=131000.0,
        high=132800.0,
        low=130900.0,
        previous_close=130985.0,
        volume=45000,
        vwap=132100.0,
        change=+1250.0,
        change_percent=+0.95
    )
    tech = TechnicalSnapshot(rsi_14=58.0, relative_volume=1.4, ema_20=131500.0, ema_50=130800.0)
    sec = SectorSnapshot(sector_name="Automotive", change_percent=+1.2, relative_strength=+0.8, breadth_advances=15, breadth_declines=5)
    
    commentary = await analyst.generate_commentary(market=mkt, technical=tech, sector=sec)
    
    assert commentary.symbol == "MRF.NS"
    assert commentary.what_changed != ""
    assert commentary.why_it_matters != ""
    assert len(commentary.what_to_watch) > 0
    assert len(commentary.confirming_evidence) > 0
