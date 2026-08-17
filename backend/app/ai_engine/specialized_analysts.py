from typing import List, Dict, Any, Optional
from backend.app.ai_engine.contracts import (
    DomainAssessment, SignalStance, EvidenceItem, DataFreshness,
    MarketSnapshot, TechnicalSnapshot, DerivativeSnapshot, NewsSnapshot, SectorSnapshot, MacroSnapshot, InstitutionalSnapshot
)

class TechnicalAnalyst:
    @staticmethod
    def analyze(market: MarketSnapshot, tech: TechnicalSnapshot) -> DomainAssessment:
        if tech.freshness == DataFreshness.UNAVAILABLE and market.freshness == DataFreshness.UNAVAILABLE:
            return DomainAssessment(
                domain="Technical Analysis",
                stance=SignalStance.UNAVAILABLE,
                confidence=0.0,
                key_findings=["Technical and market data unavailable"],
                bullish_evidence=[],
                bearish_evidence=[]
            )

        bullish_ev: List[EvidenceItem] = []
        bearish_ev: List[EvidenceItem] = []
        findings: List[str] = []

        # 1. VWAP position
        if market.vwap > 0:
            if market.ltp >= market.vwap:
                bullish_ev.append(EvidenceItem(
                    type="TECHNICAL", statement=f"Price above VWAP (₹{market.vwap:,.2f})", value=market.vwap, source="QUANT", timestamp="LIVE"
                ))
                findings.append("Trading above intraday VWAP")
            else:
                bearish_ev.append(EvidenceItem(
                    type="TECHNICAL", statement=f"Price below VWAP (₹{market.vwap:,.2f})", value=market.vwap, source="QUANT", timestamp="LIVE"
                ))
                findings.append("Trading below intraday VWAP")

        # 2. RSI Zone
        if tech.rsi_14 is not None:
            if tech.rsi_14 >= 60:
                bullish_ev.append(EvidenceItem(type="TECHNICAL", statement=f"RSI bullish momentum ({tech.rsi_14:.1f})", value=tech.rsi_14, source="QUANT", timestamp="LIVE"))
            elif tech.rsi_14 <= 40:
                bearish_ev.append(EvidenceItem(type="TECHNICAL", statement=f"RSI bearish pressure ({tech.rsi_14:.1f})", value=tech.rsi_14, source="QUANT", timestamp="LIVE"))

        # 3. EMA Trend
        if tech.ema_20 and tech.ema_50:
            if tech.ema_20 > tech.ema_50:
                bullish_ev.append(EvidenceItem(type="TECHNICAL", statement="EMA 20 > EMA 50 bullish alignment", value=tech.ema_20, source="QUANT", timestamp="LIVE"))
            else:
                bearish_ev.append(EvidenceItem(type="TECHNICAL", statement="EMA 20 < EMA 50 bearish alignment", value=tech.ema_20, source="QUANT", timestamp="LIVE"))

        if len(bullish_ev) > len(bearish_ev):
            stance = SignalStance.BULLISH
        elif len(bearish_ev) > len(bullish_ev):
            stance = SignalStance.BEARISH
        else:
            stance = SignalStance.NEUTRAL

        return DomainAssessment(
            domain="Technical Analysis",
            stance=stance,
            confidence=0.85,
            key_findings=findings,
            bullish_evidence=bullish_ev,
            bearish_evidence=bearish_ev
        )

class DerivativesAnalyst:
    @staticmethod
    def analyze(deriv: Optional[DerivativeSnapshot], market_chg: float) -> DomainAssessment:
        if not deriv or deriv.freshness == DataFreshness.UNAVAILABLE or deriv.pcr is None:
            return DomainAssessment(
                domain="Derivatives Analysis",
                stance=SignalStance.UNAVAILABLE,
                confidence=0.0,
                key_findings=["F&O derivatives data unavailable for this instrument"],
                bullish_evidence=[],
                bearish_evidence=[]
            )

        bullish_ev: List[EvidenceItem] = []
        bearish_ev: List[EvidenceItem] = []
        findings: List[str] = []

        # PCR Analysis
        if deriv.pcr >= 1.20:
            bullish_ev.append(EvidenceItem(type="DERIVATIVES", statement=f"PCR elevated at {deriv.pcr:.2f} (Put Writing Support)", value=deriv.pcr, source="F&O", timestamp="LIVE"))
            findings.append("Option writers aggressive on Put side")
        elif deriv.pcr <= 0.75:
            bearish_ev.append(EvidenceItem(type="DERIVATIVES", statement=f"PCR depressed at {deriv.pcr:.2f} (Call Writing Resistance)", value=deriv.pcr, source="F&O", timestamp="LIVE"))
            findings.append("Option writers aggressive on Call side")

        # OI Buildup
        if deriv.futures_oi_change and abs(deriv.futures_oi_change) > 2.0:
            if deriv.futures_oi_change > 0 and market_chg > 0:
                bullish_ev.append(EvidenceItem(type="DERIVATIVES", statement="Long Buildup detected in active futures contract", value=deriv.futures_oi_change, source="F&O", timestamp="LIVE"))
            elif deriv.futures_oi_change > 0 and market_chg < 0:
                bearish_ev.append(EvidenceItem(type="DERIVATIVES", statement="Short Buildup detected in active futures contract", value=deriv.futures_oi_change, source="F&O", timestamp="LIVE"))

        if len(bullish_ev) > len(bearish_ev):
            stance = SignalStance.BULLISH
        elif len(bearish_ev) > len(bullish_ev):
            stance = SignalStance.BEARISH
        else:
            stance = SignalStance.NEUTRAL

        return DomainAssessment(
            domain="Derivatives Analysis",
            stance=stance,
            confidence=0.88,
            key_findings=findings,
            bullish_evidence=bullish_ev,
            bearish_evidence=bearish_ev
        )

class NewsAnalyst:
    @staticmethod
    def analyze(news: Optional[NewsSnapshot]) -> DomainAssessment:
        if not news or not news.headline or news.freshness == DataFreshness.UNAVAILABLE:
            return DomainAssessment(
                domain="News & Announcements",
                stance=SignalStance.UNAVAILABLE,
                confidence=0.0,
                key_findings=["No breaking high-impact corporate announcement in current session"],
                bullish_evidence=[],
                bearish_evidence=[]
            )

        ev = EvidenceItem(type="NEWS", statement=news.headline, value=news.sentiment, source=news.source, timestamp=news.published_at)
        if news.sentiment == "Positive":
            return DomainAssessment(
                domain="News & Announcements",
                stance=SignalStance.BULLISH,
                confidence=news.sentiment_confidence,
                key_findings=[f"Positive corporate catalyst: {news.headline}"],
                bullish_evidence=[ev],
                bearish_evidence=[]
            )
        elif news.sentiment == "Negative":
            return DomainAssessment(
                domain="News & Announcements",
                stance=SignalStance.BEARISH,
                confidence=news.sentiment_confidence,
                key_findings=[f"Negative headline pressure: {news.headline}"],
                bullish_evidence=[],
                bearish_evidence=[ev]
            )
        return DomainAssessment(
            domain="News & Announcements",
            stance=SignalStance.NEUTRAL,
            confidence=0.7,
            key_findings=[f"Neutral disclosure: {news.headline}"],
            bullish_evidence=[],
            bearish_evidence=[]
        )

class SectorAnalyst:
    @staticmethod
    def analyze(sector: Optional[SectorSnapshot], stock_chg: float, nifty_chg: float) -> DomainAssessment:
        if not sector or sector.freshness == DataFreshness.UNAVAILABLE:
            return DomainAssessment(
                domain="Sector Analysis",
                stance=SignalStance.UNAVAILABLE,
                confidence=0.0,
                key_findings=["Sector index benchmark data unavailable"],
                bullish_evidence=[],
                bearish_evidence=[]
            )

        bullish_ev: List[EvidenceItem] = []
        bearish_ev: List[EvidenceItem] = []
        findings: List[str] = []

        rel_strength = sector.change_percent - nifty_chg
        if rel_strength >= 0.7:
            bullish_ev.append(EvidenceItem(type="SECTOR", statement=f"{sector.sector_name} leading market (+{rel_strength:.2f}% vs NIFTY)", value=rel_strength, source="SECTOR", timestamp="LIVE"))
            findings.append(f"Sector tailwinds in {sector.sector_name}")
        elif rel_strength <= -0.7:
            bearish_ev.append(EvidenceItem(type="SECTOR", statement=f"{sector.sector_name} lagging market ({rel_strength:.2f}% vs NIFTY)", value=rel_strength, source="SECTOR", timestamp="LIVE"))
            findings.append(f"Sector headwinds in {sector.sector_name}")

        # Company vs Sector Attribution
        comp_vs_sec = stock_chg - sector.change_percent
        if abs(comp_vs_sec) >= 1.5:
            findings.append(f"Stock move is company-specific ({comp_vs_sec:+.2f}% divergence from sector)")
        else:
            findings.append("Stock move is largely in tandem with broader sector")

        stance = SignalStance.BULLISH if len(bullish_ev) > len(bearish_ev) else SignalStance.BEARISH if len(bearish_ev) > len(bullish_ev) else SignalStance.NEUTRAL
        return DomainAssessment(
            domain="Sector Analysis",
            stance=stance,
            confidence=0.82,
            key_findings=findings,
            bullish_evidence=bullish_ev,
            bearish_evidence=bearish_ev
        )

class InstitutionalAnalyst:
    @staticmethod
    def analyze(inst: Optional[InstitutionalSnapshot]) -> DomainAssessment:
        if not inst or inst.freshness == DataFreshness.UNAVAILABLE:
            return DomainAssessment(
                domain="Institutional Flow",
                stance=SignalStance.UNAVAILABLE,
                confidence=0.0,
                key_findings=["Institutional flow data unavailable"],
                bullish_evidence=[],
                bearish_evidence=[]
            )

        fii = inst.fii_cash_net_cr
        dii = inst.dii_cash_net_cr
        net_inst = fii + dii
        ev = EvidenceItem(type="INSTITUTIONAL", statement=f"FII Net: {fii:+,g} Cr | DII Net: {dii:+,g} Cr", value=net_inst, source="SETTLEMENT", timestamp=inst.as_of)

        if net_inst > 500:
            return DomainAssessment(
                domain="Institutional Flow",
                stance=SignalStance.BULLISH,
                confidence=0.85,
                key_findings=["Combined FII + DII institutional accumulation"],
                bullish_evidence=[ev],
                bearish_evidence=[]
            )
        elif net_inst < -500:
            return DomainAssessment(
                domain="Institutional Flow",
                stance=SignalStance.BEARISH,
                confidence=0.85,
                key_findings=["Combined FII + DII institutional distribution"],
                bullish_evidence=[],
                bearish_evidence=[ev]
            )
        return DomainAssessment(
            domain="Institutional Flow",
            stance=SignalStance.NEUTRAL,
            confidence=0.7,
            key_findings=["Institutional flows balanced"],
            bullish_evidence=[],
            bearish_evidence=[]
        )

class MacroAnalyst:
    @staticmethod
    def analyze(macro: Optional[MacroSnapshot]) -> DomainAssessment:
        if not macro or macro.freshness == DataFreshness.UNAVAILABLE:
            return DomainAssessment(domain="Macro Context", stance=SignalStance.UNAVAILABLE, confidence=0.0, key_findings=["Macro context data unavailable"], bullish_evidence=[], bearish_evidence=[])

        vix = macro.india_vix
        nifty_chg = macro.nifty_change_pct
        findings: List[str] = []

        if vix > 16.0 or nifty_chg <= -1.2:
            stance = SignalStance.BEARISH
            findings.append(f"Risk-off macro regime (India VIX at {vix:.1f})")
        elif vix < 13.0 and nifty_chg >= 0.5:
            stance = SignalStance.BULLISH
            findings.append("Risk-on macro regime with subdued volatility")
        else:
            stance = SignalStance.NEUTRAL
            findings.append("Macro environment in balanced consolidation")

        return DomainAssessment(
            domain="Macro Context",
            stance=stance,
            confidence=0.80,
            key_findings=findings,
            bullish_evidence=[],
            bearish_evidence=[]
        )
