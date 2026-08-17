from typing import Dict, Any, Optional
from backend.app.ai_engine.contracts import (
    AttentionScore, AttentionClassification,
    MarketSnapshot, TechnicalSnapshot, DerivativeSnapshot, NewsSnapshot, SectorSnapshot, MacroSnapshot
)

def compute_attention_score(
    market: MarketSnapshot,
    technical: TechnicalSnapshot,
    derivatives: Optional[DerivativeSnapshot] = None,
    news: Optional[NewsSnapshot] = None,
    sector: Optional[SectorSnapshot] = None,
    macro: Optional[MacroSnapshot] = None,
    is_nifty50: bool = False
) -> AttentionScore:
    """
    Computes a deterministic, transparent 0-100 attention score based on real market anomaly weights.
    Does not assign baseline points to unavailable or unconfigured domains.
    """
    # 1. Price Anomaly (0 - 20 pts)
    abs_chg = abs(market.change_percent) if market.change_percent is not None else 0.0
    if abs_chg >= 5.0:
        tech_score = 20.0
    elif abs_chg >= 3.0:
        tech_score = 16.0
    elif abs_chg >= 1.8:
        tech_score = 12.0
    elif abs_chg >= 0.8:
        tech_score = 7.0
    else:
        tech_score = 3.0

    # Add technical breakout / breakdown bonus
    if technical.relative_volume and technical.relative_volume > 1.8:
        tech_score = min(20.0, tech_score + 3.0)

    # 2. Volume Anomaly (0 - 20 pts)
    rvol = technical.relative_volume or 1.0
    if rvol >= 3.5:
        vol_score = 20.0
    elif rvol >= 2.5:
        vol_score = 16.0
    elif rvol >= 1.8:
        vol_score = 12.0
    elif rvol >= 1.2:
        vol_score = 6.0
    else:
        vol_score = 2.0

    # 3. Derivatives Anomaly (0 - 20 pts)
    deriv_score = 0.0
    if derivatives and derivatives.freshness != "UNAVAILABLE":
        oi_chg = abs(derivatives.futures_oi_change or 0.0)
        pcr = derivatives.pcr
        if oi_chg >= 15.0 or (pcr is not None and (pcr <= 0.6 or pcr >= 1.6)):
            deriv_score = 20.0
        elif oi_chg >= 10.0 or (pcr is not None and (pcr <= 0.75 or pcr >= 1.4)):
            deriv_score = 15.0
        elif oi_chg >= 5.0:
            deriv_score = 10.0
        elif pcr is not None or oi_chg > 0:
            deriv_score = 5.0

    # 4. News & Corporate Catalyst Impact (0 - 15 pts)
    news_score = 0.0
    if news and news.freshness != "UNAVAILABLE":
        if news.event_type in ["EARNINGS", "REGULATORY", "ACQUISITION"]:
            news_score = 15.0
        elif news.event_type in ["ORDER_WIN", "CORPORATE_ACTION"]:
            news_score = 11.0
        elif news.sentiment in ["Positive", "Negative"]:
            news_score = 8.0
        else:
            news_score = 4.0

    # 5. Sector & Market Relevance (0 - 15 pts)
    sec_score = 4.0 if is_nifty50 else 0.0
    if sector and sector.freshness != "UNAVAILABLE":
        sec_chg = abs(sector.change_percent) if sector.change_percent is not None else 0.0
        if sec_chg >= 2.5:
            sec_score = min(15.0, sec_score + 9.0)
        elif sec_chg >= 1.5:
            sec_score = min(15.0, sec_score + 6.0)
        else:
            sec_score = min(15.0, sec_score + 3.0)

    # 6. Macro Shock Impact (0 - 10 pts)
    macro_score = 0.0
    if macro and macro.freshness != "UNAVAILABLE":
        vix_chg = abs(macro.india_vix_change_pct) if macro.india_vix_change_pct is not None else 0.0
        nifty_chg = abs(macro.nifty_change_pct) if macro.nifty_change_pct is not None else 0.0
        if vix_chg >= 10.0 or nifty_chg >= 2.0:
            macro_score = 10.0
        elif vix_chg >= 5.0 or nifty_chg >= 1.0:
            macro_score = 7.0
        else:
            macro_score = 3.0

    total = int(round(tech_score + vol_score + deriv_score + news_score + sec_score + macro_score))
    total = max(0, min(100, total))

    if total >= 85:
        classification = AttentionClassification.CRITICAL
    elif total >= 70:
        classification = AttentionClassification.IMPORTANT
    elif total >= 50:
        classification = AttentionClassification.INTERESTING
    elif total >= 30:
        classification = AttentionClassification.MONITOR
    else:
        classification = AttentionClassification.NOISE

    return AttentionScore(
        total_score=total,
        classification=classification,
        breakdown={
            "price_anomaly": round(tech_score, 1),
            "volume_anomaly": round(vol_score, 1),
            "derivatives_anomaly": round(deriv_score, 1),
            "news_impact": round(news_score, 1),
            "sector_relevance": round(sec_score, 1),
            "macro_impact": round(macro_score, 1)
        }
    )
