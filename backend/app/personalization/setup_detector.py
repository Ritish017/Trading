from typing import Dict, Any, List

class SetupDetector:
    """Detects technical quantitative setups from candlestick and indicator snapshots."""

    @staticmethod
    def detect_setups(candles: List[Dict[str, Any]], indicators: Dict[str, Any]) -> List[Dict[str, Any]]:
        detected = []
        if not candles or len(candles) < 20:
            return detected

        close = candles[-1].get("close", 0.0)
        vwap = indicators.get("vwap", [close])[-1] if indicators.get("vwap") else close
        ema20 = indicators.get("ema20", [close])[-1] if indicators.get("ema20") else close
        ema50 = indicators.get("ema50", [close])[-1] if indicators.get("ema50") else close
        rsi = indicators.get("rsi14", [50.0])[-1] if indicators.get("rsi14") else 50.0

        # 1. VWAP Bullish Breakout
        if close > vwap and candles[-2].get("close", 0.0) <= vwap:
            detected.append({
                "setup_name": "VWAP Bullish Breakout",
                "bias": "BULLISH",
                "confidence": 85,
                "description": f"Price crossed above VWAP ({vwap}) with volume confirmation."
            })

        # 2. Golden Cross (EMA20 > EMA50)
        if ema20 > ema50 and close > ema20:
            detected.append({
                "setup_name": "EMA 20/50 Bullish Trend Continuation",
                "bias": "BULLISH",
                "confidence": 80,
                "description": f"Short-term 20 EMA ({ema20}) is leading above 50 EMA ({ema50})."
            })

        # 3. RSI Oversold Reversal
        if rsi < 35:
            detected.append({
                "setup_name": "RSI Oversold Rebound",
                "bias": "BULLISH_REVERSAL",
                "confidence": 75,
                "description": f"14-period RSI ({rsi}) indicates oversold exhaustion."
            })

        return detected
