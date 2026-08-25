import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.app.ai_engine.gemini_client import genai

from backend.app.config import settings
from backend.app.ai_engine.contracts import (
    AICommentary, MarketNarrative, MarketRegime, ImportanceLevel, AttentionClassification,
    SignalStance, DataFreshness, EvidenceItem,
    MarketSnapshot, TechnicalSnapshot, DerivativeSnapshot, NewsSnapshot, SectorSnapshot, MacroSnapshot, InstitutionalSnapshot
)
from backend.app.event_engine.attention import compute_attention_score
from backend.app.ai_engine.evidence import aggregate_market_evidence
from backend.app.ai_engine.specialized_analysts import (
    TechnicalAnalyst, DerivativesAnalyst, NewsAnalyst, SectorAnalyst, InstitutionalAnalyst, MacroAnalyst
)
from backend.app.ai_engine.contradiction import detect_contradictions

logger = logging.getLogger(__name__)

class ChiefMarketAnalyst:
    """
    Synthesizes multi-domain evidence into institutional-grade, evidence-backed market commentary.
    Answers the 7 fundamental questions:
    1. What changed?
    2. Why did it change?
    3. Is it significant?
    4. What confirms it?
    5. What contradicts it?
    6. Why should I care?
    7. What to watch next?
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    async def generate_commentary(
        self,
        market: MarketSnapshot,
        technical: TechnicalSnapshot,
        derivatives: Optional[DerivativeSnapshot] = None,
        news: Optional[NewsSnapshot] = None,
        sector: Optional[SectorSnapshot] = None,
        macro: Optional[MacroSnapshot] = None,
        institutional: Optional[InstitutionalSnapshot] = None,
        is_nifty50: bool = False
    ) -> AICommentary:
        now_str = datetime.now().strftime("%H:%M IST")
        
        # 1. Deterministic Attention Score
        attention = compute_attention_score(
            market=market,
            technical=technical,
            derivatives=derivatives,
            news=news,
            sector=sector,
            macro=macro,
            is_nifty50=is_nifty50
        )

        # 2. Run Specialized Domain Analysts
        ta_eval = TechnicalAnalyst.analyze(market, technical)
        da_eval = DerivativesAnalyst.analyze(derivatives, market.change_percent)
        na_eval = NewsAnalyst.analyze(news)
        sa_eval = SectorAnalyst.analyze(sector, market.change_percent, macro.nifty_change_pct if macro else 0.0)
        ia_eval = InstitutionalAnalyst.analyze(institutional)
        ma_eval = MacroAnalyst.analyze(macro)

        assessments = [ta_eval, da_eval, na_eval, sa_eval, ia_eval, ma_eval]

        # 3. Contradiction Detection
        contradiction_report = detect_contradictions(assessments)

        # 4. Evidence Aggregation
        all_evidence = aggregate_market_evidence(
            market=market,
            technical=technical,
            derivatives=derivatives,
            news=news,
            sector=sector,
            macro=macro,
            institutional=institutional
        )

        # 5. Classify Importance
        if attention.total_score >= 80:
            importance = ImportanceLevel.CRITICAL
        elif attention.total_score >= 65:
            importance = ImportanceLevel.HIGH
        elif attention.total_score >= 45:
            importance = ImportanceLevel.MEDIUM
        else:
            importance = ImportanceLevel.LOW

        # 6. If Gemini API key is available, run LLM synthesis over structured evidence
        if self.client and attention.total_score >= 35:
            try:
                llm_res = await self._synthesize_with_llm(
                    market, technical, derivatives, news, sector, macro,
                    attention, contradiction_report, all_evidence, importance
                )
                if llm_res:
                    return llm_res
            except Exception as e:
                logger.warning(f"Chief Analyst LLM call failed ({e}), falling back to deterministic synthesis.")

        # 7. High-Fidelity Deterministic Fallback Synthesis
        return self._synthesize_deterministic(
            market, technical, derivatives, news, sector, macro, institutional,
            attention, contradiction_report, all_evidence, importance, now_str
        )

    def _synthesize_deterministic(
        self,
        market: MarketSnapshot,
        technical: TechnicalSnapshot,
        derivatives: Optional[DerivativeSnapshot],
        news: Optional[NewsSnapshot],
        sector: Optional[SectorSnapshot],
        macro: Optional[MacroSnapshot],
        institutional: Optional[InstitutionalSnapshot],
        attention: Any,
        contradiction_report: Any,
        all_evidence: List[EvidenceItem],
        importance: ImportanceLevel,
        now_str: str
    ) -> AICommentary:
        chg = market.change_percent
        sign = "+" if chg >= 0 else ""
        price = market.ltp
        sec_name = sector.sector_name if sector else "Equities"
        rvol = technical.relative_volume or 1.0

        # Headline
        if chg <= -2.0 and rvol >= 1.5:
            headline = f"Persistent Selling Pressure in {market.symbol.split('.')[0]} with Volume Expansion"
            event_type = "UNUSUAL_SELLING"
        elif chg >= 2.0 and rvol >= 1.5:
            headline = f"Strong Bullish Inflows & Volume Breakout in {market.symbol.split('.')[0]}"
            event_type = "UNUSUAL_BUYING"
        elif news and news.headline:
            headline = f"Corporate Catalyst: {news.headline[:60]}..."
            event_type = f"NEWS_{news.event_type}"
        else:
            headline = f"{market.symbol.split('.')[0]} Consolidates at ₹{price:,.2f} in {sec_name}"
            event_type = "CONSOLIDATION"

        # What Changed
        vol_str = f"while volume expanded to {rvol:.1f}x average" if rvol > 1.2 else "on routine turnover"
        what_changed = f"{market.symbol.split('.')[0]} moved {sign}{chg:.2f}% to ₹{price:,.2f} {vol_str} during the active trading window."

        # Why it Matters
        if sector and abs(sector.change_percent) > 1.0:
            why_it_matters = f"The price action is occurring alongside a {sector.change_percent:+.2f}% move in the {sec_name} sector basket."
        else:
            why_it_matters = f"Key moving averages ({technical.ema_20 or price:.2f}) and intraday VWAP are acting as critical dynamic boundaries."

        # Drivers
        drivers = []
        if rvol >= 1.5:
            drivers.append(f"Elevated volume participation ({rvol:.1f}x 20-period average)")
        if sector and abs(sector.change_percent) >= 1.0:
            drivers.append(f"Sector-wide momentum in {sec_name} ({sector.change_percent:+.2f}%)")
        if derivatives and derivatives.pcr:
            drivers.append(f"Derivatives positioning with Put-Call Ratio at {derivatives.pcr:.2f}")
        if not drivers:
            drivers.append("Normal intraday liquidity provisioning and range consolidation")

        # Why Should I Care?
        if importance in [ImportanceLevel.CRITICAL, ImportanceLevel.HIGH]:
            why_care = "High index relevance and elevated volume anomaly indicate institutional participation rather than retail noise."
        else:
            why_care = "Move is within expected intraday volatility bands with limited systemic contagion to broader NIFTY indices."

        # What to Watch Next
        watch = []
        if technical.support_levels:
            watch.append(f"Immediate support zone around ₹{technical.support_levels[0]:,.2f}")
        if technical.resistance_levels:
            watch.append(f"Key overhead resistance near ₹{technical.resistance_levels[0]:,.2f}")
        if market.vwap > 0:
            watch.append(f"Intraday VWAP pivot at ₹{market.vwap:,.2f}")

        # Regime
        if macro and macro.india_vix > 15:
            regime = MarketRegime.HIGH_VOLATILITY
        elif chg > 1.0:
            regime = MarketRegime.BULLISH_TREND
        elif chg < -1.0:
            regime = MarketRegime.BEARISH_TREND
        else:
            regime = MarketRegime.NEUTRAL_CONSOLIDATION

        # Partition Confirming vs Contradicting Evidence
        confirming = [e for e in all_evidence if (chg >= 0 and e.type in ["PRICE", "VOLUME"]) or (chg < 0 and e.type in ["PRICE", "VOLUME"])]
        contradicting = [e for e in all_evidence if "EMA20 > EMA50" in e.statement and chg < 0]

        # Compute factual evidence-based confidence
        if market.freshness == DataFreshness.UNAVAILABLE or price <= 0:
            computed_confidence = 0.0
        else:
            valid_count = len(all_evidence)
            base_conf = min(1.0, valid_count / 5.0)
            if contradiction_report.has_contradiction:
                base_conf *= 0.75
            computed_confidence = round(base_conf, 2)

        bullish_triggers = [f"Sustained volume above ₹{technical.resistance_levels[0]:,.2f}"] if technical.resistance_levels else ["Price discovery above session highs"]
        bearish_triggers = [f"Break below support at ₹{technical.support_levels[0]:,.2f}"] if technical.support_levels else ["Price discovery below session lows"]

        return AICommentary(
            id=f"COM_{uuid.uuid4().hex[:8].upper()}",
            symbol=market.symbol,
            company_name=market.symbol.split('.')[0],
            sector=sec_name,
            headline=headline,
            event_type=event_type,
            importance=importance,
            attention_score=attention.total_score,
            classification=attention.classification,
            market_regime=regime,
            what_changed=what_changed,
            why_it_matters=why_it_matters,
            likely_drivers=drivers,
            confirming_evidence=confirming,
            contradicting_evidence=contradicting,
            company_context=f"{market.symbol.split('.')[0]} is trading at ₹{price:,.2f} in the {sec_name} segment.",
            sector_context=f"{sec_name} sector is {'gaining' if (sector and sector.change_percent >= 0) else 'losing'} momentum.",
            macro_context=f"NIFTY 50 is {macro.nifty_change_pct:+.2f}% with India VIX at {macro.india_vix:.1f}." if macro else "Broader macro indices stable.",
            why_should_i_care=why_care,
            what_to_watch=watch,
            bullish_confirmation=bullish_triggers,
            bearish_confirmation=bearish_triggers,
            uncertainties=[contradiction_report.synthesis_note] if contradiction_report.has_contradiction else [],
            confidence=computed_confidence,
            timestamp=now_str,
            data_freshness=market.freshness,
            sources=["NSE_FEED", "QUANT_ENGINE", "F&O_NSE", "SECTOR_INDEX"]
        )

    async def _synthesize_with_llm(self, market, technical, derivatives, news, sector, macro, attention, contradiction, evidence, importance) -> Optional[AICommentary]:
        prompt = f"""
You are the Chief Market Analyst for APEX Trading Lab (Indian Markets - NSE/BSE).
Interpret ONLY the verified factual evidence below. Do NOT invent numbers or guess unprovided metrics.

FACTUAL EVIDENCE:
- Symbol: {market.symbol} ({sector.sector_name if sector else 'NSE'})
- Current Price: ₹{market.ltp} ({market.change_percent:+.2f}%)
- Relative Volume (RVOL): {technical.relative_volume}x
- VWAP: ₹{market.vwap} | RSI: {technical.rsi_14}
- Attention Score: {attention.total_score}/100 ({attention.classification.value})
- Sector Move: {sector.change_percent if sector else 0.0:+.2f}%
- Derivatives PCR: {derivatives.pcr if derivatives else 'N/A'}
- Contradiction Note: {contradiction.synthesis_note}

Return ONLY valid JSON matching this schema:
{{
  "headline": "Brief analytical headline",
  "what_changed": "1-2 sentences on what changed with price & volume",
  "why_it_matters": "Why this price/volume move is significant in sector context",
  "likely_drivers": ["driver 1", "driver 2"],
  "why_should_i_care": "Systemic/portfolio impact statement",
  "what_to_watch": ["Specific level 1", "Specific trigger 2"]
}}
"""
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        raw = response.text or ""
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)

        now_str = datetime.now().strftime("%H:%M IST")
        return AICommentary(
            id=f"COM_{uuid.uuid4().hex[:8].upper()}",
            symbol=market.symbol,
            company_name=market.symbol.split('.')[0],
            sector=sector.sector_name if sector else "NSE Equities",
            headline=data.get("headline", f"Market Update for {market.symbol}"),
            event_type="ANALYST_SYNTHESIS",
            importance=importance,
            attention_score=attention.total_score,
            classification=attention.classification,
            market_regime=MarketRegime.BULLISH_TREND if market.change_percent > 0 else MarketRegime.BEARISH_TREND,
            what_changed=data.get("what_changed", f"Price at ₹{market.ltp:,.2f}" if market.ltp > 0 else "Price action unavailable"),
            why_it_matters=data.get("why_it_matters", "Contextual move around key technical levels."),
            likely_drivers=data.get("likely_drivers", ["Technical momentum"]),
            confirming_evidence=evidence[:4],
            contradicting_evidence=[],
            company_context=f"{market.symbol} trading at ₹{market.ltp:,.2f}" if market.ltp > 0 else f"{market.symbol} market structure",
            sector_context=f"{sector.sector_name if sector else 'Sector'} basket active",
            macro_context=f"NIFTY {macro.nifty_change_pct:+.2f}%" if (macro and macro.nifty_change_pct is not None) else "Broader macro indices unavailable",
            why_should_i_care=data.get("why_should_i_care", "Standard liquidity event."),
            what_to_watch=data.get("what_to_watch", []),
            bullish_confirmation=[],
            bearish_confirmation=[],
            uncertainties=[],
            confidence=round(min(0.95, max(0.20, len(evidence) / 5.0)), 2),
            timestamp=now_str,
            data_freshness=market.freshness,
            sources=["NSE_FEED", "QUANT_ENGINE", "GEMINI_ANALYST"]
        )

    def generate_market_narrative(
        self,
        macro: Optional[MacroSnapshot] = None,
        sector_leaders: Optional[List[str]] = None,
        sector_laggards: Optional[List[str]] = None,
        fii_cash_net: Optional[float] = None,
        dii_cash_net: Optional[float] = None
    ) -> MarketNarrative:
        now_str = datetime.now().strftime("%H:%M IST")
        nifty_chg = macro.nifty_change_pct if (macro and macro.nifty_change_pct is not None) else None
        vix = macro.india_vix if (macro and macro.india_vix is not None) else None

        if nifty_chg is None:
            headline = "Macro Overview Pending Live Session Feeds"
            regime = MarketRegime.NEUTRAL_CONSOLIDATION
            summary = "Broad market indices and institutional cash flow data are currently unavailable or disconnected."
            confidence = 0.0
        elif nifty_chg >= 0.5:
            headline = "Broad-Based Accumulation Led by Financials & Heavyweights"
            regime = MarketRegime.BULLISH_TREND
            fii_str = f" Institutional FIIs recorded net cash flows of ₹{fii_cash_net:+,g} Cr." if fii_cash_net is not None else ""
            summary = f"Indian equities are experiencing broad risk-on momentum with NIFTY up +{nifty_chg:.2f}%.{fii_str}"
            confidence = 0.85 if vix is not None else 0.60
        elif nifty_chg <= -0.5:
            headline = "Risk-Off Consolidation Amid Elevated Volatility"
            regime = MarketRegime.RISK_OFF
            vix_str = f" India VIX is at {vix:.1f}." if vix is not None else ""
            summary = f"Markets under distribution pressure with NIFTY declining {nifty_chg:.2f}%.{vix_str}"
            confidence = 0.85 if vix is not None else 0.60
        else:
            headline = "Range-Bound Compression Across Major Indices"
            regime = MarketRegime.NEUTRAL_CONSOLIDATION
            vix_str = f" with India VIX at {vix:.1f}" if vix is not None else ""
            summary = f"NIFTY is trading in a tight consolidation range ({nifty_chg:+.2f}%){vix_str}."
            confidence = 0.75 if vix is not None else 0.50

        inst_bias = f"FII: ₹{fii_cash_net:+,g} Cr | DII: ₹{dii_cash_net:+,g} Cr" if (fii_cash_net is not None and dii_cash_net is not None) else "Institutional Flow: Unavailable"
        macro_str = f"India VIX: {vix:.1f}" if vix is not None else "Macro Volatility: Unavailable"

        return MarketNarrative(
            date=datetime.now().strftime("%d %b %Y"),
            headline=headline,
            primary_regime=regime,
            narrative_summary=summary,
            key_drivers=["FII/DII Net Cash Flow Dynamics", "Domestic Liquidity", "Quarterly Earnings Rotation"],
            sector_leaders=sector_leaders or [],
            sector_laggards=sector_laggards or [],
            institutional_bias=inst_bias,
            macro_backdrop=macro_str,
            confidence=confidence,
            timestamp=now_str
        )
