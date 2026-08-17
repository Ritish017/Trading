import uuid
import time
from datetime import datetime
from typing import List, Optional, Dict, Any

from backend.app.ai_engine.contracts import (
    MarketEvent, EvidenceItem, DataFreshness,
    MarketSnapshot, TechnicalSnapshot, DerivativeSnapshot, NewsSnapshot, SectorSnapshot, MacroSnapshot
)
from backend.app.event_engine.attention import compute_attention_score

def detect_market_events(
    market: MarketSnapshot,
    technical: TechnicalSnapshot,
    derivatives: Optional[DerivativeSnapshot] = None,
    news: Optional[NewsSnapshot] = None,
    sector: Optional[SectorSnapshot] = None,
    macro: Optional[MacroSnapshot] = None,
    is_nifty50: bool = False
) -> List[MarketEvent]:
    """
    Scans factual snapshots and deterministically generates structured MarketEvents with traceable evidence.
    """
    events: List[MarketEvent] = []
    now_str = datetime.now().strftime("%H:%M IST")
    
    attention = compute_attention_score(
        market=market,
        technical=technical,
        derivatives=derivatives,
        news=news,
        sector=sector,
        macro=macro,
        is_nifty50=is_nifty50
    )

    rvol = technical.relative_volume or 1.0
    price = market.ltp
    chg_pct = market.change_percent

    # 1. Detect UNUSUAL SELLING or BUYING
    if chg_pct <= -1.8 and rvol >= 1.5:
        evidence = [
            EvidenceItem(
                type="PRICE",
                statement=f"Price declined {abs(chg_pct):.2f}% to ₹{price:,.2f}",
                value=chg_pct,
                source="NSE_FEED",
                timestamp=now_str
            ),
            EvidenceItem(
                type="VOLUME",
                statement=f"Volume is {rvol:.1f}x the 20-period average",
                value=rvol,
                source="QUANT_ENGINE",
                timestamp=now_str
            )
        ]
        if derivatives and derivatives.futures_oi_change and derivatives.futures_oi_change > 5.0:
            evidence.append(EvidenceItem(
                type="DERIVATIVES",
                statement=f"Futures Open Interest expanded by +{derivatives.futures_oi_change:.1f}% (Short Buildup)",
                value=derivatives.futures_oi_change,
                source="F&O_FEED",
                timestamp=now_str
            ))
        if sector:
            evidence.append(EvidenceItem(
                type="SECTOR",
                statement=f"{sector.sector_name} sector is {'down' if sector.change_percent < 0 else 'up'} {abs(sector.change_percent):.2f}%",
                value=sector.change_percent,
                source="SECTOR_INDEX",
                timestamp=now_str
            ))

        events.append(MarketEvent(
            event_id=f"EV_{uuid.uuid4().hex[:8].upper()}",
            event_type="UNUSUAL_SELLING",
            symbol=market.symbol,
            company_name=market.symbol.split('.')[0],
            sector=sector.sector_name if sector else "NSE Equities",
            timestamp=now_str,
            severity=min(95, int(abs(chg_pct) * 15 + rvol * 10)),
            confidence=0.92,
            attention_score=attention.total_score,
            classification=attention.classification,
            evidence=evidence,
            affected_sector=sector.sector_name if sector else None,
            affected_assets=[market.symbol],
            affected_indices=["NIFTY 50"] if is_nifty50 else []
        ))

    elif chg_pct >= 1.8 and rvol >= 1.5:
        evidence = [
            EvidenceItem(
                type="PRICE",
                statement=f"Price advanced +{chg_pct:.2f}% to ₹{price:,.2f}",
                value=chg_pct,
                source="NSE_FEED",
                timestamp=now_str
            ),
            EvidenceItem(
                type="VOLUME",
                statement=f"Volume is {rvol:.1f}x the 20-period average",
                value=rvol,
                source="QUANT_ENGINE",
                timestamp=now_str
            )
        ]
        if derivatives and derivatives.futures_oi_change and derivatives.futures_oi_change > 5.0:
            evidence.append(EvidenceItem(
                type="DERIVATIVES",
                statement=f"Futures Open Interest expanded by +{derivatives.futures_oi_change:.1f}% (Long Buildup)",
                value=derivatives.futures_oi_change,
                source="F&O_FEED",
                timestamp=now_str
            ))
        events.append(MarketEvent(
            event_id=f"EV_{uuid.uuid4().hex[:8].upper()}",
            event_type="UNUSUAL_BUYING",
            symbol=market.symbol,
            company_name=market.symbol.split('.')[0],
            sector=sector.sector_name if sector else "NSE Equities",
            timestamp=now_str,
            severity=min(95, int(chg_pct * 15 + rvol * 10)),
            confidence=0.91,
            attention_score=attention.total_score,
            classification=attention.classification,
            evidence=evidence,
            affected_sector=sector.sector_name if sector else None,
            affected_assets=[market.symbol],
            affected_indices=["NIFTY 50"] if is_nifty50 else []
        ))

    # 2. Detect VWAP Cross or Rejection
    if market.vwap > 0:
        vwap_diff_pct = (price - market.vwap) / market.vwap * 100
        if abs(vwap_diff_pct) >= 1.2:
            direction = "ABOVE" if vwap_diff_pct > 0 else "BELOW"
            events.append(MarketEvent(
                event_id=f"EV_{uuid.uuid4().hex[:8].upper()}",
                event_type="VWAP_DEVIATION",
                symbol=market.symbol,
                company_name=market.symbol.split('.')[0],
                timestamp=now_str,
                severity=60,
                confidence=0.88,
                attention_score=attention.total_score,
                classification=attention.classification,
                evidence=[
                    EvidenceItem(
                        type="TECHNICAL",
                        statement=f"Price trading {abs(vwap_diff_pct):.2f}% {direction} intraday VWAP (₹{market.vwap:,.2f})",
                        value=round(vwap_diff_pct, 2),
                        source="QUANT_ENGINE",
                        timestamp=now_str
                    )
                ],
                affected_assets=[market.symbol]
            ))

    # 3. News Catalyst Event
    if news and news.headline:
        events.append(MarketEvent(
            event_id=f"EV_{uuid.uuid4().hex[:8].upper()}",
            event_type=f"NEWS_{news.event_type}",
            symbol=market.symbol,
            company_name=market.symbol.split('.')[0],
            sector=sector.sector_name if sector else "NSE Equities",
            timestamp=news.published_at or now_str,
            severity=78,
            confidence=news.sentiment_confidence,
            attention_score=attention.total_score,
            classification=attention.classification,
            evidence=[
                EvidenceItem(
                    type="NEWS",
                    statement=f"{news.headline} ({news.source})",
                    value=news.sentiment,
                    source=news.source,
                    timestamp=news.published_at
                )
            ],
            affected_assets=[market.symbol]
        ))

    # If no specific extreme event, provide a baseline MONITOR or CONSOLIDATION event if data is present
    if not events:
        if market.freshness == DataFreshness.UNAVAILABLE:
            events.append(MarketEvent(
                event_id=f"EV_{uuid.uuid4().hex[:8].upper()}",
                event_type="DATA_UNAVAILABLE",
                symbol=market.symbol,
                company_name=market.symbol.split('.')[0],
                sector=sector.sector_name if sector else "NSE Equities",
                timestamp=now_str,
                severity=20,
                confidence=1.0,
                attention_score=0,
                classification=attention.classification,
                evidence=[
                    EvidenceItem(
                        type="SYSTEM",
                        statement=f"Market data feed for {market.symbol} is currently unavailable or initializing.",
                        value=0.0,
                        source="MARKET_DATA_HUB",
                        timestamp=now_str
                    )
                ],
                affected_assets=[market.symbol]
            ))
        else:
            evidence_items = [
                EvidenceItem(
                    type="PRICE",
                    statement=f"Price at ₹{price:,.2f} ({chg_pct:+.2f}%)",
                    value=chg_pct,
                    source=market.source or "NSE_FEED",
                    timestamp=now_str
                )
            ]
            if technical.rsi_14 is not None:
                evidence_items.append(
                    EvidenceItem(
                        type="TECHNICAL",
                        statement=f"RSI 14 at {technical.rsi_14:.1f}",
                        value=technical.rsi_14,
                        source="QUANT_ENGINE",
                        timestamp=now_str
                    )
                )

            events.append(MarketEvent(
                event_id=f"EV_{uuid.uuid4().hex[:8].upper()}",
                event_type="ORDERLY_CONSOLIDATION",
                symbol=market.symbol,
                company_name=market.symbol.split('.')[0],
                sector=sector.sector_name if sector else "NSE Equities",
                timestamp=now_str,
                severity=30,
                confidence=0.85,
                attention_score=attention.total_score,
                classification=attention.classification,
                evidence=evidence_items,
                affected_assets=[market.symbol]
            ))

    return events
