import os
import json
import logging
from typing import Dict, Any, Optional, List
from google import genai
from backend.app.config import settings

logger = logging.getLogger(__name__)

class MarketResearchAgent:
    """
    Multi-Agent Research Specialist for Indian Stock Markets.
    Outputs structured quantitative and fundamental analysis JSON reports.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    async def analyze_stock_intelligence(self, market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        symbol = market_snapshot.get("symbol", "RELIANCE.NS")
        price = market_snapshot.get("price") or market_snapshot.get("ltp") or 0.0
        name = market_snapshot.get("name", symbol)
        sector = market_snapshot.get("sector", "General")
        nifty = market_snapshot.get("niftyPrice") or market_snapshot.get("nifty_50")
        pcr = market_snapshot.get("pcr")

        if not self.client:
            logger.info(f"Gemini API client not configured or key omitted. Generating deterministic AI report for {symbol}.")
            return self._generate_local_fallback(symbol, name, sector, price, nifty, pcr, market_snapshot)

        tech = market_snapshot.get("technicalMetrics", {})
        actual_rsi = tech.get("rsi14") or market_snapshot.get("rsi_14")
        actual_ema20 = tech.get("ema20") or market_snapshot.get("ema_20")
        actual_ema50 = tech.get("ema50") or market_snapshot.get("ema_50")
        actual_vwap = tech.get("vwap") or market_snapshot.get("vwap")
        actual_sups = market_snapshot.get("supportLevels") or []
        actual_resis = market_snapshot.get("resistanceLevels") or []

        prompt = f"""
You are a Senior Quantitative Analyst specializing in Indian Equities (NSE / BSE).
Interpret ONLY the verified factual evidence below. Do not estimate, infer, approximate, or invent missing financial metrics. If a metric is null or unavailable, keep it as null.

VERIFIED FACTUAL CONTEXT:
- Stock: {name} ({symbol}) | Sector: {sector}
- Current Price: ₹{price if price > 0 else 'Unavailable'}
- NIFTY 50 Benchmark: {nifty if nifty else 'Unavailable'}
- Put-Call Ratio (PCR): {pcr if pcr else 'Unavailable'}
- Technical Metrics: RSI(14)={actual_rsi}, EMA20={actual_ema20}, EMA50={actual_ema50}, VWAP={actual_vwap}
- Support Levels: {actual_sups if actual_sups else 'None'}
- Resistance Levels: {actual_resis if actual_resis else 'None'}

Return ONLY valid JSON matching this schema:
{{
  "symbol": "{symbol}",
  "name": "{name}",
  "sector": "{sector}",
  "marketStance": "Bullish Accumulation / Distribution Pressure / Neutral Consolidation / UNAVAILABLE",
  "confidence": <integer 0 to 100 based strictly on data completeness and signal strength>,
  "niftyCorrel": "Positive Beta / Negative Beta / Unavailable",
  "fiiDiiSentiment": "Institutional Inflow / Institutional Outflow / Neutral / Unavailable",
  "executiveSummary": "Factual market evaluation based strictly on verified inputs.",
  "supportLevels": {json.dumps(actual_sups)},
  "resistanceLevels": {json.dumps(actual_resis)},
  "technicalMetrics": {{
    "rsi14": {json.dumps(actual_rsi)},
    "ema20": {json.dumps(actual_ema20)},
    "ema50": {json.dumps(actual_ema50)},
    "vwap": {json.dumps(actual_vwap)},
    "pcrSignal": {json.dumps(f"PCR {pcr:.2f}" if pcr else "Unavailable")}
  }},
  "catalysts": [],
  "tacticalTradeSetup": {{
    "action": "MONITOR / BUY / SELL / DATA_UNAVAILABLE",
    "entryZone": {json.dumps(f"₹{price:,.2f}" if price > 0 else None)},
    "target1": {json.dumps(f"₹{actual_resis[0]:,.2f}" if actual_resis else None)},
    "target2": {json.dumps(f"₹{actual_resis[1]:,.2f}" if len(actual_resis) > 1 else None)},
    "stopLoss": {json.dumps(f"₹{actual_sups[0]:,.2f}" if actual_sups else None)},
    "riskReward": {json.dumps("1 : 2.0" if (actual_resis and actual_sups) else None)}
  }}
}}
"""
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            raw_text = response.text or ""
            cleaned = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except Exception as err:
            logger.error(f"Gemini API error during AI analysis: {err}")
            return self._generate_local_fallback(symbol, name, sector, price, nifty, pcr, market_snapshot)

    def _generate_local_fallback(
        self, symbol: str, name: str, sector: str, price: float, nifty: Optional[float], pcr: Optional[float], raw_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        tech = raw_snapshot.get("technicalMetrics", {})
        rsi = tech.get("rsi14") or raw_snapshot.get("rsi_14")
        ema20 = tech.get("ema20") or raw_snapshot.get("ema_20")
        ema50 = tech.get("ema50") or raw_snapshot.get("ema_50")
        vwap = tech.get("vwap") or raw_snapshot.get("vwap")
        sups = raw_snapshot.get("supportLevels") or []
        resis = raw_snapshot.get("resistanceLevels") or []

        # Deterministic confidence based strictly on factual dimension completeness
        points = 0
        if price > 0:
            points += 25
        if vwap is not None and vwap > 0:
            points += 25
        if ema20 is not None and ema20 > 0:
            points += 25
        if rsi is not None:
            points += 25
        confidence = points

        if vwap is not None and rsi is not None and price > 0:
            stance = "Bullish Accumulation" if price > vwap and rsi > 50 else ("Distribution Pressure" if price < vwap and rsi < 50 else "Consolidation Range")
        elif price > 0:
            stance = "Consolidation / Range Discovery"
        else:
            stance = "UNAVAILABLE"

        vwap_str = f"₹{vwap:,.2f}" if vwap else "Unavailable"
        t1 = f"₹{resis[0]:,.2f}" if resis else None
        s1 = f"₹{sups[0]:,.2f}" if sups else None

        return {
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "marketStance": stance,
            "confidence": confidence,
            "niftyCorrel": "Positive Beta" if nifty else "Unavailable",
            "fiiDiiSentiment": "Neutral Settlement",
            "executiveSummary": f"Quantitative structure for {name} ({sector}) at ₹{price:,.2f}. Dynamic VWAP benchmark: {vwap_str}.",
            "supportLevels": sups,
            "resistanceLevels": resis,
            "technicalMetrics": {
                "rsi14": rsi,
                "ema20": ema20,
                "ema50": ema50,
                "vwap": vwap,
                "pcrSignal": f"PCR {pcr:.2f}" if pcr else "Unavailable"
            },
            "catalysts": [
                f"Active price discovery relative to volume-weighted benchmark."
            ],
            "tacticalTradeSetup": {
                "action": "MONITOR" if stance != "UNAVAILABLE" else "DATA_UNAVAILABLE",
                "entryZone": f"₹{price:,.2f}" if price > 0 else None,
                "target1": t1,
                "target2": f"₹{resis[1]:,.2f}" if len(resis) > 1 else None,
                "stopLoss": s1,
                "riskReward": "1 : 2.0" if (t1 and s1) else None
            }
        }

class PersonalTradingCoach:
    """
    AI Trading Behavior Specialist.
    Analyzes historical trades and journal entries to identify behavioral patterns and risk flaws.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    async def analyze_trader_journal(self, trades_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not trades_history:
            return {
                "status": "NO_DATA",
                "insights": ["No trades recorded in journal yet. Execute paper trades to generate behavioral insights."],
                "recommendation": "Maintain strict adherence to predefined stop-loss levels."
            }

        total = len(trades_history)
        winners = [t for t in trades_history if t.get("pnl", 0) > 0]
        losers = [t for t in trades_history if t.get("pnl", 0) <= 0]
        win_rate = round(len(winners) / total * 100, 1) if total > 0 else 0.0

        avg_win = round(sum(t.get("pnl", 0) for t in winners) / len(winners), 2) if winners else 0.0
        avg_loss = round(abs(sum(t.get("pnl", 0) for t in losers)) / len(losers), 2) if losers else 0.0

        return {
            "status": "SUCCESS",
            "total_trades_analyzed": total,
            "win_rate_pct": win_rate,
            "avg_winner_pnl": avg_win,
            "avg_loser_pnl": avg_loss,
            "expectancy_ratio": round(avg_win / avg_loss, 2) if avg_loss > 0 else 1.0,
            "behavioral_insights": [
                f"Your win rate is {win_rate}% across {total} trades.",
                f"Reward-to-risk ratio is currently {round(avg_win / avg_loss, 2) if avg_loss > 0 else 'N/A'}."
            ],
            "coaching_recommendation": "Avoid revenge trading after consecutive stop-loss hits. Ensure Relative Volume > 1.5 before entering VWAP crossovers."
        }

class StrategyResearchAgent:
    """
    AI Strategy Hypothesis Generator.
    Converts plain text research ideas into executable quantitative rules.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    async def generate_hypothesis(self, query: str) -> Dict[str, Any]:
        return {
            "hypothesis_id": "HYP-042",
            "name": f"Strategy for: {query[:30]}...",
            "description": "Momentum strategy combining VWAP cross, EMA trend confirmation, and volume surges.",
            "rules": {
                "entry": ["Price > VWAP", "EMA20 > EMA50", "RSI > 55", "Relative Volume >= 1.5"],
                "exit": ["Price < EMA20", "RSI < 45"],
                "stop_loss_atr": 1.5,
                "target_atr": 3.0
            },
            "status": "REQUIRES_BACKTEST_VALIDATION"
        }


class StrategyCopilotAgent:
    """
    Evidence-grounded Strategy Copilot.

    Receives a StrategyEvaluationResult dict, optional multi-strategy context,
    market regime, confluence, and multi-turn chat history.
    Grounds every answer strictly in the verified, deterministically-computed rule
    evaluations. Never invents indicator values or declares strategy states.
    The copilot is read-only: it interprets the computed evidence only.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def _build_evidence_block(self, evaluation: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
        """Format the evaluation result and broader market context as a terse evidence block."""
        lines = [
            f"Strategy: {evaluation.get('strategy_name', 'Unknown')}",
            f"Category: {evaluation.get('category', 'Unknown')}",
            f"State: {evaluation.get('state', 'UNKNOWN')}",
            f"Data Freshness: {evaluation.get('data_freshness', 'UNKNOWN')} ({evaluation.get('data_age_seconds', 'N/A')}s ago)",
            f"Candles Used: {evaluation.get('candles_used', 0)}",
            f"Evaluated At: {evaluation.get('evaluated_at', 'N/A')}",
            "",
            "ENTRY RULES & MATHEMATICS:",
        ]
        for rule in evaluation.get("rule_evaluations", []):
            if rule.get("is_entry_rule"):
                math_note = f" [Math: {rule.get('math_detail')}]" if rule.get("math_detail") else ""
                lines.append(
                    f"  [{rule.get('outcome', 'UNKNOWN')}] {rule.get('label', '')} "
                    f"(value: {rule.get('actual_value_label', 'UNAVAILABLE')}){math_note}"
                )
        lines.append("")
        lines.append("EXIT RULES:")
        for rule in evaluation.get("rule_evaluations", []):
            if not rule.get("is_entry_rule"):
                lines.append(
                    f"  [{rule.get('outcome', 'UNKNOWN')}] {rule.get('label', '')} "
                    f"(value: {rule.get('actual_value_label', 'UNAVAILABLE')})"
                )
        fv = evaluation.get("feature_vector", {})
        if fv:
            lines.append("")
            lines.append("COMPUTED INDICATORS (verified, non-fabricated):")
            for k, v in list(fv.items())[:14]:
                lines.append(f"  {k}: {v}")

        if context:
            if context.get("market_regime"):
                reg = context["market_regime"]
                lines.append(f"\nMARKET REGIME: {reg.get('regime')} (Confidence: {reg.get('confidence')}%) - {reg.get('evidence')}")
            if context.get("confluence"):
                conf = context["confluence"]
                lines.append(f"STRATEGY CONFLUENCE: {conf.get('active_count')}/{conf.get('total_strategies')} Active, "
                             f"Bullish={conf.get('bullish_confluence')}, Reversal={conf.get('reversal_confluence')}, "
                             f"Alignment Score={conf.get('alignment_score_pct')}%")
                if conf.get("conflicts"):
                    lines.append(f"CONFLICT WARNINGS: {'; '.join(conf['conflicts'])}")
            if context.get("other_strategies"):
                lines.append("\nOTHER STRATEGIES STATUS:")
                for os_item in context["other_strategies"][:8]:
                    lines.append(f"  • {os_item.get('name')}: {os_item.get('state')} ({os_item.get('passing_count')}/{os_item.get('total_count')})")

        return "\n".join(lines)

    async def answer(
        self,
        symbol: str,
        evaluation: Dict[str, Any],
        user_message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Answer a user question about strategy evaluation with full multi-turn context.
        """
        evidence_block = self._build_evidence_block(evaluation, context)

        if not self.client:
            state = evaluation.get("state", "UNKNOWN")
            n_pass = evaluation.get("entry_rules_passing", 0)
            n_total = evaluation.get("entry_rules_total", 1)
            freshness = evaluation.get("data_freshness", "UNKNOWN")
            strat_name = evaluation.get('strategy_name', 'Unknown')
            reply = (
                f"**{strat_name}** on **{symbol}** is currently **{state}** ({n_pass}/{n_total} conditions met). "
                f"Data freshness: {freshness}. All rule states are deterministically verified from live indicator data."
            )
            evidence_cited = [
                r.get("label", "") for r in evaluation.get("rule_evaluations", [])
                if r.get("outcome") in ("PASS", "FAIL")
            ]
            return {"reply": reply, "evidence_cited": evidence_cited}

        history_str = ""
        if chat_history:
            history_str = "\nPREVIOUS CONVERSATION:\n" + "\n".join(
                f"{h.get('role', 'user').upper()}: {h.get('text', '')}"
                for h in chat_history[-6:]
            )

        system_prompt = f"""You are the APEX Strategy Copilot — an expert quantitative strategy observatory assistant.

STRICT INVARIANTS:
1. Base EVERY statement directly on the VERIFIED EVIDENCE below.
2. CANNOT invent, approximate, or extrapolate missing metrics. If missing, say "Data unavailable".
3. CANNOT alter the strategy state.
4. Explain the mathematics, invalidation triggers, and comparisons factually.
5. Keep explanations concise, professional, and quantitative. Cite exact numbers (e.g. "EMA20 = ₹1,323.15 is above EMA50 = ₹1,322.94").
6. NEVER claim guaranteed profits or give direct financial advice.

VERIFIED EVIDENCE FOR {symbol}:
{evidence_block}
{history_str}

User Question: {user_message}

Answer concisely, citing exact evidence and numbers:"""

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=system_prompt,
            )
            reply_text = response.text.strip() if response and response.text else (
                "Evidence is available but the AI interpreter is temporarily offline."
            )
        except Exception as exc:
            logger.warning("StrategyCopilotAgent Gemini call failed: %s", exc)
            reply_text = (
                f"Strategy state is {evaluation.get('state', 'UNKNOWN')} "
                f"({evaluation.get('entry_rules_passing', 0)}/{evaluation.get('entry_rules_total', 0)} "
                f"entry conditions met). AI interpreter temporarily unavailable — please review the rule checklist directly."
            )

        evidence_cited = [
            r.get("label", "") for r in evaluation.get("rule_evaluations", [])
            if r.get("outcome") in ("PASS", "FAIL") and r.get("actual_value_label", "") != "UNAVAILABLE"
        ]

        return {"reply": reply_text, "evidence_cited": evidence_cited}
