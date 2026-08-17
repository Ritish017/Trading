from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.app.ai_engine.contracts import (
    EvidenceItem, DataFreshness,
    MarketSnapshot, TechnicalSnapshot, DerivativeSnapshot, NewsSnapshot, SectorSnapshot, MacroSnapshot, InstitutionalSnapshot
)

def aggregate_market_evidence(
    market: MarketSnapshot,
    technical: TechnicalSnapshot,
    derivatives: Optional[DerivativeSnapshot] = None,
    news: Optional[NewsSnapshot] = None,
    sector: Optional[SectorSnapshot] = None,
    macro: Optional[MacroSnapshot] = None,
    institutional: Optional[InstitutionalSnapshot] = None
) -> List[EvidenceItem]:
    """
    Collects, normalizes, and stamps verified factual evidence items across all market pillars.
    Excludes UNAVAILABLE snapshots so AI synthesis only reasons over authentic evidence.
    """
    evidence: List[EvidenceItem] = []
    now_str = datetime.now().strftime("%H:%M IST")

    # 1. Price Evidence
    if market.freshness != DataFreshness.UNAVAILABLE and market.ltp is not None:
        sign = "+" if market.change_percent >= 0 else ""
        evidence.append(EvidenceItem(
            type="PRICE",
            statement=f"Price is ₹{market.ltp:,.2f} ({sign}{market.change_percent:.2f}% intraday)",
            value=market.change_percent,
            source=market.source or "NSE_FEED",
            timestamp=now_str,
            freshness=market.freshness
        ))

    # 2. Volume Evidence
    if technical.freshness != DataFreshness.UNAVAILABLE and technical.relative_volume is not None:
        evidence.append(EvidenceItem(
            type="VOLUME",
            statement=f"Relative volume (RVOL) is {technical.relative_volume:.2f}x of 20-period baseline",
            value=technical.relative_volume,
            source="QUANT_ENGINE",
            timestamp=now_str,
            freshness=technical.freshness
        ))

    # 3. Technical Indicator Evidence
    if technical.freshness != DataFreshness.UNAVAILABLE:
        if technical.rsi_14 is not None:
            rsi_zone = "Overbought (>70)" if technical.rsi_14 >= 70 else "Oversold (<30)" if technical.rsi_14 <= 30 else "Neutral range"
            evidence.append(EvidenceItem(
                type="TECHNICAL",
                statement=f"RSI 14 at {technical.rsi_14:.1f} ({rsi_zone})",
                value=technical.rsi_14,
                source="QUANT_ENGINE",
                timestamp=now_str,
                freshness=technical.freshness
            ))
        if market.vwap > 0:
            vwap_pos = "above" if market.ltp >= market.vwap else "below"
            vwap_gap = abs(market.ltp - market.vwap) / market.vwap * 100
            evidence.append(EvidenceItem(
                type="TECHNICAL",
                statement=f"Trading {vwap_gap:.2f}% {vwap_pos} intraday VWAP of ₹{market.vwap:,.2f}",
                value=round(market.vwap, 2),
                source="QUANT_ENGINE",
                timestamp=now_str,
                freshness=technical.freshness
            ))
        if technical.ema_20 and technical.ema_50:
            trend = "Bullish (EMA20 > EMA50)" if technical.ema_20 > technical.ema_50 else "Bearish (EMA20 < EMA50)"
            evidence.append(EvidenceItem(
                type="TECHNICAL",
                statement=f"Short-term moving average structure is {trend}",
                value=round(technical.ema_20, 2),
                source="QUANT_ENGINE",
                timestamp=now_str,
                freshness=technical.freshness
            ))

    # 4. Derivatives Evidence
    if derivatives and derivatives.freshness != DataFreshness.UNAVAILABLE:
        if derivatives.pcr is not None:
            pcr_sentiment = "Heavy Put Writing (Bullish)" if derivatives.pcr >= 1.25 else "Call Writing Pressure (Bearish)" if derivatives.pcr <= 0.75 else "Balanced"
            evidence.append(EvidenceItem(
                type="DERIVATIVES",
                statement=f"Put-Call Ratio (PCR) at {derivatives.pcr:.2f} ({pcr_sentiment})",
                value=derivatives.pcr,
                source="F&O_NSE",
                timestamp=now_str,
                freshness=derivatives.freshness
            ))
        if derivatives.futures_oi_change is not None and abs(derivatives.futures_oi_change) > 0.5:
            pattern = derivatives.oi_pattern or ("Long Buildup" if derivatives.futures_oi_change > 0 and market.change_percent > 0 else "Short Buildup")
            evidence.append(EvidenceItem(
                type="DERIVATIVES",
                statement=f"Futures OI changed by {derivatives.futures_oi_change:+.1f}% indicating {pattern}",
                value=derivatives.futures_oi_change,
                source="F&O_NSE",
                timestamp=now_str,
                freshness=derivatives.freshness
            ))

    # 5. News & SEBI Announcement Evidence
    if news and news.headline and news.freshness != DataFreshness.UNAVAILABLE:
        evidence.append(EvidenceItem(
            type="NEWS",
            statement=f"{news.headline}",
            value=news.sentiment,
            source=news.source,
            timestamp=news.published_at,
            freshness=news.freshness
        ))

    # 6. Sector Evidence
    if sector and sector.freshness != DataFreshness.UNAVAILABLE:
        nifty_ref_chg = (macro.nifty_change_pct if macro and macro.freshness != DataFreshness.UNAVAILABLE else 0.0)
        rel = sector.change_percent - nifty_ref_chg
        outperformance = "outperforming" if rel > 0 else "underperforming"
        evidence.append(EvidenceItem(
            type="SECTOR",
            statement=f"{sector.sector_name} sector is {sector.change_percent:+.2f}% ({outperformance} NIFTY by {abs(rel):.2f}%)",
            value=sector.change_percent,
            source="SECTOR_INDEX",
            timestamp=now_str,
            freshness=sector.freshness
        ))

    # 7. Institutional FII/DII Evidence
    if institutional and institutional.freshness != DataFreshness.UNAVAILABLE:
        fii_flow = f"FII Net Cash: {institutional.fii_cash_net_cr:+,g} Cr | DII Net Cash: {institutional.dii_cash_net_cr:+,g} Cr"
        evidence.append(EvidenceItem(
            type="INSTITUTIONAL",
            statement=f"Institutional Net Flows: {fii_flow}",
            value=institutional.fii_cash_net_cr,
            source="NSE_SETTLEMENT",
            timestamp=institutional.as_of,
            freshness=institutional.freshness
        ))

    # 8. Macro Evidence
    if macro and macro.freshness != DataFreshness.UNAVAILABLE:
        vix_status = "Elevated (>15)" if macro.india_vix >= 15 else "Calm (<13)"
        evidence.append(EvidenceItem(
            type="MACRO",
            statement=f"India VIX at {macro.india_vix:.2f} ({vix_status}) | NIFTY 50: {macro.nifty_50:,.2f} ({macro.nifty_change_pct:+.2f}%)",
            value=macro.india_vix,
            source="BENCHMARK_INDEX",
            timestamp=now_str,
            freshness=macro.freshness
        ))

    return evidence
