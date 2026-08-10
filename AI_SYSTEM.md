# MULTI-AGENT AI SYSTEM SPECIFICATION

## 1. Overview
The APEX AI engine (`backend/app/ai_engine/agents.py`) employs specialized, domain-specific agents utilizing Google Gemini 2.5 Flash with structured JSON outputs.

## 2. Specialized Agents

1. **`MarketResearchAgent`**:
   - Analyzes real-time market snapshots, institutional flow (FII/DII), PCR, and technical levels.
   - Outputs structured JSON stance (`Bullish Accumulation`, support/resistance levels, catalysts, trade setup).

2. **`PersonalTradingCoach`**:
   - Analyzes actual paper trading journal entries.
   - Computes win rate, reward-to-risk ratio, expectancy, and highlights behavioral mistakes without fabricating psychological claims.

3. **`StrategyResearchAgent`**:
   - Converts natural language trader queries (e.g. "VWAP breakout with volume surge") into executable quantitative rule definitions.

## 3. Strict Data Integrity Principles
- The AI never fabricates stock prices, volume numbers, or institutional flows.
- If data is unavailable, the AI explicitly reports `DATA_UNAVAILABLE`.
- Basic financial indicators are calculated deterministically by Python code, not LLMs.
