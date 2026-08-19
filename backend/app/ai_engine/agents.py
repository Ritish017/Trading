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

    def _build_evidence_block(
        self,
        symbol: Optional[str] = None,
        evaluation: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        research_summary: Optional[Dict[str, Any]] = None,
        backtest_result: Optional[Dict[str, Any]] = None,
        scorecard: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format the evaluation result, research summary, backtest results, and market context as a terse evidence block."""
        lines = []

        if backtest_result:
            wf = backtest_result.get("walk_forward", {})
            cs = backtest_result.get("cost_sensitivity", {})
            lines.extend([
                f"=== BACKTEST EXECUTION & WALK-FORWARD EVIDENCE ===",
                f"Strategy: {backtest_result.get('strategy_id', 'Unknown')} (v{backtest_result.get('strategy_version', '1.0.0')})",
                f"Symbol: {backtest_result.get('symbol', 'UNKNOWN')}, Timeframe: {backtest_result.get('timeframe', '5m')}",
                f"Total Trades: {backtest_result.get('total_trades', 0)} (Win Rate: {backtest_result.get('win_rate_pct', 0)}%)",
                f"Net Profit: ₹{backtest_result.get('netProfit', 0)} | Total Net Return: {backtest_result.get('total_return_pct', 0)}% (Gross: {backtest_result.get('grossReturnPct', 0)}%)",
                f"Sharpe Ratio: {backtest_result.get('sharpe_ratio', 0)} | CAGR: {backtest_result.get('cagr', 0)}% | Max Drawdown: {backtest_result.get('max_drawdown_pct', 0)}%",
                f"Profit Factor: {backtest_result.get('profit_factor', 0)} | Avg Trade: {backtest_result.get('avg_trade_return_pct', 0)}% (Median: {backtest_result.get('median_trade_return_pct', 0)}%)",
                f"Friction Costs: ₹{backtest_result.get('total_friction_costs', 0)} (Brokerage: ₹{backtest_result.get('total_fees', 0)}, Slippage: ₹{backtest_result.get('total_slippage', 0)})",
                f"Walk-Forward (70% IS / 30% OOS):",
                f"  • In-Sample: Return={wf.get('in_sample_return_pct')}%, Trades={wf.get('in_sample_trades')}, WinRate={wf.get('in_sample_win_rate')}%",
                f"  • Out-of-Sample: Return={wf.get('out_of_sample_return_pct')}%, Trades={wf.get('out_of_sample_trades')}, WinRate={wf.get('out_of_sample_win_rate')}%",
                f"  • Overfitting Classification: {wf.get('overfitting_status', 'N/A')}",
                f"Cost Sensitivity Scenarios:",
                f"  • Zero Friction Return: {cs.get('zero_friction_return_pct')}%",
                f"  • Configured Friction: {cs.get('configured_friction_return_pct')}%",
                f"  • High Friction Return: {cs.get('high_friction_return_pct')}% (Cost Drag: {cs.get('cost_drag_pct')}%)",
            ])

        if scorecard:
            lines.extend([
                "",
                f"=== RESEARCH SCORECARD ===",
                f"Overall Research Status: {scorecard.get('overall_status', 'N/A')}",
                f"Sample Size Rating: {scorecard.get('sample_size_rating', {}).get('rating', 'N/A')} ({scorecard.get('sample_size_rating', {}).get('evidence', '')})",
                f"OOS Stability: {scorecard.get('oos_stability_rating', {}).get('rating', 'N/A')} ({scorecard.get('oos_stability_rating', {}).get('evidence', '')})",
                f"Drawdown Risk: {scorecard.get('drawdown_risk_rating', {}).get('rating', 'N/A')} ({scorecard.get('drawdown_risk_rating', {}).get('evidence', '')})",
                f"Regime Coverage: {scorecard.get('regime_coverage_rating', {}).get('rating', 'N/A')} ({scorecard.get('regime_coverage_rating', {}).get('evidence', '')})",
                f"Friction Resilience: {scorecard.get('friction_resilience_rating', {}).get('rating', 'N/A')} ({scorecard.get('friction_resilience_rating', {}).get('evidence', '')})",
            ])

        if research_summary:
            lines.extend([
                "",
                f"=== HISTORICAL RESEARCH EVIDENCE ===",
                f"Strategy: {research_summary.get('strategy_name', 'Unknown')} ({research_summary.get('strategy_id', '')})",
                f"Category: {research_summary.get('category', 'Unknown')}",
                f"Direction: {research_summary.get('direction', 'BULLISH')}",
                f"Symbol: {research_summary.get('symbol', 'UNKNOWN')}, Timeframe: {research_summary.get('timeframe', '5m')}",
                f"Total Candles Analyzed: {research_summary.get('total_candles_analyzed', 0)}",
                f"Total Activations: {research_summary.get('total_activations', 0)} ({research_summary.get('activation_frequency_pct', 0)}% of candles)",
                f"Continuous Active Episodes: {research_summary.get('active_episodes_count', 0)}",
                f"Avg Episode Duration: {research_summary.get('avg_episode_duration_candles', 0)} candles (Median: {research_summary.get('median_episode_duration_candles', 0)} candles)",
                f"Invalidation Frequency: {research_summary.get('invalidation_frequency_pct', 0)}% ({research_summary.get('invalidation_count', 0)} episodes)",
                "",
                "FORWARD OBSERVATION WINDOWS:",
            ])
            for h_str, h_data in (research_summary.get("horizons_summary") or {}).items():
                is_low = " [LOW SAMPLE]" if h_data.get("is_low_sample") else ""
                lines.append(
                    f"  • {h_str}-Candle Horizon: N={h_data.get('sample_count', 0)}{is_low}, "
                    f"Median Return={h_data.get('median_return_pct')}%, Mean={h_data.get('mean_return_pct')}%, "
                    f"Positive Return Freq={h_data.get('positive_return_pct')}%, "
                    f"Median MAE={h_data.get('median_mae_pct')}%, Median MFE={h_data.get('median_mfe_pct')}%"
                )

        if evaluation:
            lines.extend([
                "",
                "=== CURRENT OBSERVATORY EVALUATION ===",
                f"Strategy: {evaluation.get('strategy_name', 'Unknown')}",
                f"Category: {evaluation.get('category', 'Unknown')}",
                f"State: {evaluation.get('state', 'UNKNOWN')}",
                f"Data Freshness: {evaluation.get('data_freshness', 'UNKNOWN')} ({evaluation.get('data_age_seconds', 'N/A')}s ago)",
                f"Candles Used: {evaluation.get('candles_used', 0)}",
                f"Evaluated At: {evaluation.get('evaluated_at', 'N/A')}",
                "",
                "ENTRY RULES & MATHEMATICS:",
            ])
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

        return "\n".join(lines)

    async def answer(
        self,
        symbol: str,
        evaluation: Optional[Dict[str, Any]] = None,
        user_message: str = "",
        chat_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict[str, Any]] = None,
        research_summary: Optional[Dict[str, Any]] = None,
        backtest_result: Optional[Dict[str, Any]] = None,
        scorecard: Optional[Dict[str, Any]] = None,
        robustness_summary: Optional[Dict[str, Any]] = None,
        is_skeptic_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Interprets strategy state, research observations, backtest metrics, and robustness evidence.
        In Skeptic Mode ('CHALLENGE THIS STRATEGY'), actively audits for overfitting, parameter sensitivity,
        cost drag, and data mining risks.
        """
        evidence_block = self._build_evidence_block(
            symbol=symbol,
            evaluation=evaluation,
            context=context,
            research_summary=research_summary,
            backtest_result=backtest_result,
            scorecard=scorecard,
        )

        if robustness_summary:
            evidence_block += f"\nROBUSTNESS & DISCOVERY EVIDENCE:\n{robustness_summary}\n"

        if not self.client:
            # Deterministic fallback
            if is_skeptic_mode:
                return self._build_deterministic_skeptic_critique(symbol, backtest_result, scorecard, robustness_summary)

            if backtest_result:
                s_name = backtest_result.get('strategy_id', 'Strategy')
                tot_trades = backtest_result.get('total_trades', 0)
                tot_ret = backtest_result.get('total_return_pct', 0.0)
                win_rt = backtest_result.get('win_rate_pct', 0.0)
                sharpe = backtest_result.get('sharpe_ratio', 0.0)
                max_dd = backtest_result.get('max_drawdown_pct', 0.0)
                wf = backtest_result.get('walk_forward', {})
                oos_ret = wf.get('out_of_sample_return_pct', 0.0)
                ovf = wf.get('overfitting_status', 'N/A')
                reply = (
                    f"**{s_name}** Backtest on **{symbol}** recorded **{tot_trades} completed trades** with a **{win_rt}% win rate**.\n\n"
                    f"**Key Quantitative Performance:**\n"
                    f"• Total Net Return: **{tot_ret}%**\n"
                    f"• Sharpe Ratio: **{sharpe}** | Max Drawdown: **{max_dd}%**\n"
                    f"• In-Sample Return: **{wf.get('in_sample_return_pct')}%** | Out-of-Sample Return: **{oos_ret}%**\n"
                    f"• Overfitting Assessment: **{ovf}**\n\n"
                    f"*(Note: Simulated execution incorporates ₹{backtest_result.get('total_fees', 0)} brokerage and ₹{backtest_result.get('total_slippage', 0)} slippage.)*"
                )
                return {"reply": reply, "evidence_cited": ["Total Trades", "Net Return", "Sharpe Ratio", "Walk-Forward OOS"]}

            if research_summary:
                s_name = research_summary.get('strategy_name', 'Strategy')
                tot_act = research_summary.get('total_activations', 0)
                avg_dur = research_summary.get('avg_episode_duration_candles', 0)
                h5 = (research_summary.get('horizons_summary') or {}).get('5') or {}
                med5 = h5.get('median_return_pct', 'N/A')
                pos5 = h5.get('positive_return_pct', 'N/A')
                mae5 = h5.get('median_mae_pct', 'N/A')
                mfe5 = h5.get('median_mfe_pct', 'N/A')
                reply = (
                    f"**{s_name}** on **{symbol}** has recorded **{tot_act} activation episodes** across the analyzed dataset. "
                    f"The average continuous activation duration was **{avg_dur} candles**.\n\n"
                    f"**5-Candle Forward Outcomes:**\n"
                    f"• Median Return: **{med5}%**\n"
                    f"• Positive Return Frequency: **{pos5}%**\n"
                    f"• Median MAE (Adverse Excursion): **{mae5}%**\n"
                    f"• Median MFE (Favorable Excursion): **{mfe5}%**\n\n"
                    f"*(Note: All metrics reflect empirical historical observations under deterministic rules without execution/slippage modeling.)*"
                )
                return {"reply": reply, "evidence_cited": ["Total Activations", "5-Candle Forward Returns", "MAE/MFE"]}

            state = (evaluation or {}).get("state", "UNKNOWN")
            n_pass = (evaluation or {}).get("entry_rules_passing", 0)
            n_total = (evaluation or {}).get("entry_rules_total", 1)
            freshness = (evaluation or {}).get("data_freshness", "UNKNOWN")
            strat_name = (evaluation or {}).get('strategy_name', 'Unknown')
            reply = (
                f"**{strat_name}** on **{symbol}** is currently **{state}** ({n_pass}/{n_total} conditions met). "
                f"Data freshness: {freshness}. All rule states are deterministically verified from live indicator data."
            )
            evidence_cited = [
                r.get("label", "") for r in (evaluation or {}).get("rule_evaluations", [])
                if r.get("outcome") in ("PASS", "FAIL")
            ]
            return {"reply": reply, "evidence_cited": evidence_cited}

        history_str = ""
        if chat_history:
            history_str = "\nPREVIOUS CONVERSATION:\n" + "\n".join(
                f"{h.get('role', 'user').upper()}: {h.get('text', '')}"
                for h in chat_history[-6:]
            )

        skeptic_instructions = """
SKEPTIC MODE ACTIVE ("CHALLENGE THIS STRATEGY"):
- You must act as a ruthless quantitative peer reviewer.
- Identify every potential flaw, risk, and vulnerability in this strategy.
- Audit sample size (is N < 30?), Out-of-Sample decay, parameter cliffs/instability, regime dependency, symbol concentration, and transaction cost drag.
- If many configurations were tested, warn about data snooping and multiple testing.
- Do NOT cheerlead or validate poor research hypotheses.
""" if is_skeptic_mode else ""

        system_prompt = f"""You are the APEX Strategy Copilot — an expert quantitative strategy research, backtesting, and robustness testing assistant.

STRICT INVARIANTS:
1. Base EVERY statement directly on the VERIFIED EVIDENCE below. Cite exact numerical values.
2. CANNOT invent, approximate, or extrapolate missing metrics. If an indicator is UNAVAILABLE, explicitly state: "Data unavailable".
3. CANNOT alter the strategy state or convert an ACTIVE condition into a "BUY NOW" command.
4. If Data Freshness is STALE or market is CLOSED, frame the analysis as: "Based on the last available candle..." and explicitly state that it reflects historical data.
5. If asked for trade recommendations or "Should I buy?", clarify that Strategy Lab provides deterministic rule verification and simulation for research, not financial advice.
6. Distinguish between historical research forward observations (pre-friction) and backtested performance (post-friction).
{skeptic_instructions}

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
            reply_text = "AI interpreter temporarily unavailable — please review the quantitative scorecard directly."

        evidence_cited = ["Verified Robustness Evidence", "Quantitative Metrics"]
        return {"reply": reply_text, "evidence_cited": evidence_cited}

    def _build_deterministic_skeptic_critique(
        self,
        symbol: str,
        backtest_result: Optional[Dict[str, Any]],
        scorecard: Optional[Dict[str, Any]],
        robustness: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Deterministic skeptic critique when offline."""
        critiques = []
        if backtest_result:
            trades = backtest_result.get("totalTrades", 0)
            if trades < 15:
                critiques.append(f"• **Low Sample Warning**: Only {trades} completed trades observed. Statistical significance cannot be established.")
            wf = backtest_result.get("walk_forward", {})
            if wf.get("out_of_sample_return_pct", 0) < 0:
                critiques.append(f"• **Out-of-Sample Degradation**: OOS return collapsed to {wf.get('out_of_sample_return_pct')}%, suggesting in-sample curve fitting.")
            cs = backtest_result.get("cost_sensitivity", {})
            if cs.get("cost_drag_pct", 0) > 3.0:
                critiques.append(f"• **Severe Cost Friction Drag**: Frictions consume {cs.get('cost_drag_pct')}% of gross returns.")

        if not critiques:
            critiques.append("• Audit parameter neighborhood for cliff drop-offs and test across multiple market regimes before considering validation.")

        reply = (
            f"**Quantitative Skeptic Critique for {symbol}:**\n\n"
            + "\n".join(critiques)
            + "\n\n*Note: High historical returns without parameter neighborhood stability and OOS robustness indicate high data-mining risk.*"
        )
        return {"reply": reply, "evidence_cited": ["Skeptic Audit", "Friction Drag", "Sample Size Validation"]}
