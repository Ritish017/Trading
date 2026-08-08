import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig, Plugin} from 'vite';
import {GoogleGenAI} from '@google/genai';

function expressApiPlugin(): Plugin {
  return {
    name: 'express-api-plugin',
    configureServer(server) {
      server.middlewares.use('/api/indian-market-intelligence', async (req, res) => {
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end(JSON.stringify({ error: 'Method not allowed' }));
          return;
        }

        let body = '';
        req.on('data', (chunk) => { body += chunk; });
        req.on('end', async () => {
          try {
            const { symbol, name, sector, price, change24h, niftyPrice, fiiFlow, diiFlow, pcr } = JSON.parse(body || '{}');
            const apiKey = process.env.GEMINI_API_KEY;

            if (!apiKey) {
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ error: 'GEMINI_API_KEY_NOT_SET' }));
              return;
            }

            const ai = new GoogleGenAI({});
            const prompt = `You are a Senior Quantitative Data Engineer and Technical Analyst specializing in the Indian Stock Markets (NSE / BSE).
Provide a structured JSON response evaluating Indian stock "${name} (${symbol})" in the "${sector}" sector.
Context:
- Stock Price: ₹${price} (${change24h >= 0 ? '+' : ''}${change24h}%)
- NIFTY 50 Level: ${niftyPrice || 24500}
- FII Net Flow: ₹${fiiFlow || '+1,240'} Cr | DII Net Flow: ₹${diiFlow || '+890'} Cr
- Derivatives Put-Call Ratio (PCR): ${pcr || 1.15}

Return ONLY a valid JSON object matching this exact structure (no markdown, no backticks, no codeblocks):
{
  "symbol": "${symbol}",
  "name": "${name}",
  "sector": "${sector}",
  "marketStance": "Bullish Accumulation",
  "confidence": 88,
  "niftyCorrel": "0.82 High Positive",
  "fiiDiiSentiment": "FII Buying Acceleration",
  "executiveSummary": "Strong institutional order flow driven by quarterly earnings resilience and robust domestic inflows in ${sector}.",
  "supportLevels": [${(price * 0.975).toFixed(2)}, ${(price * 0.95).toFixed(2)}],
  "resistanceLevels": [${(price * 1.025).toFixed(2)}, ${(price * 1.05).toFixed(2)}],
  "technicalMetrics": {
    "rsi14": 58.4,
    "ema20": ${(price * 0.985).toFixed(2)},
    "ema50": ${(price * 0.96).toFixed(2)},
    "vwap": ${(price * 0.995).toFixed(2)},
    "pcrSignal": "Bullish Put Writing at ${price * 0.98}"
  },
  "catalysts": [
    "Q3 YoY Revenue Growth beat consensus estimates by 4.2%",
    "FII Net cash inflows reached 3-week peak in ${sector} basket",
    "Positive sectorial tailwinds from recent SEBI & RBI regulatory policy updates"
  ],
  "tacticalTradeSetup": {
    "action": "Buy / Delivery CNC",
    "entryZone": "₹${(price * 0.99).toFixed(2)} - ₹${price}",
    "target1": "₹${(price * 1.04).toFixed(2)}",
    "target2": "₹${(price * 1.08).toFixed(2)}",
    "stopLoss": "₹${(price * 0.965).toFixed(2)}",
    "riskReward": "1 : 2.8"
  }
}`;

            const response = await ai.models.generateContent({
              model: 'gemini-2.5-flash',
              contents: prompt,
            });

            const text = response.text || '';
            const cleanedText = text.replace(/```json/g, '').replace(/```/g, '').trim();
            const parsed = JSON.parse(cleanedText);

            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify(parsed));
          } catch (err) {
            console.error('Indian Market AI Intelligence API error:', err);
            res.setHeader('Content-Type', 'application/json');
            res.statusCode = 500;
            res.end(JSON.stringify({ error: 'AI Market Intelligence generation failed' }));
          }
        });
      });

      server.middlewares.use('/api/ai-analysis', async (req, res) => {
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end(JSON.stringify({ error: 'Method not allowed' }));
          return;
        }

        let body = '';
        req.on('data', (chunk) => { body += chunk; });
        req.on('end', async () => {
          try {
            const { symbol, price, change24h } = JSON.parse(body || '{}');
            const apiKey = process.env.GEMINI_API_KEY;

            if (!apiKey) {
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ error: 'GEMINI_API_KEY_NOT_SET' }));
              return;
            }

            const ai = new GoogleGenAI({});
            const prompt = `You are an expert technical analyst for Indian Equities. Provide a JSON response for NSE/BSE asset "${symbol}" currently at price ₹${price} (${change24h}%).
Return ONLY a valid JSON object matching this TypeScript format (no markdown formatting, no code blocks):
{
  "symbol": "${symbol}",
  "overallSignal": "Strong Buy",
  "confidence": 85,
  "summary": "Technical momentum on NSE suggests bullish continuation.",
  "supportLevels": [${(price * 0.97).toFixed(2)}, ${(price * 0.94).toFixed(2)}],
  "resistanceLevels": [${(price * 1.03).toFixed(2)}, ${(price * 1.06).toFixed(2)}],
  "indicators": {
    "rsi": { "value": 56, "signal": "Bullish" },
    "macd": { "signal": "Bullish Crossover", "histogram": 1.4 },
    "trend": "Bullish Trend"
  },
  "tradeSetup": {
    "recommendedSide": "Buy",
    "suggestedEntry": ${price},
    "takeProfit1": ${(price * 1.04).toFixed(2)},
    "takeProfit2": ${(price * 1.08).toFixed(2)},
    "stopLoss": ${(price * 0.97).toFixed(2)},
    "riskRewardRatio": "1 : 2.5"
  }
}`;

            const response = await ai.models.generateContent({
              model: 'gemini-2.5-flash',
              contents: prompt,
            });

            const text = response.text || '';
            const cleanedText = text.replace(/```json/g, '').replace(/```/g, '').trim();
            const parsed = JSON.parse(cleanedText);

            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify(parsed));
          } catch (err) {
            console.error('AI Analysis API error:', err);
            res.setHeader('Content-Type', 'application/json');
            res.statusCode = 500;
            res.end(JSON.stringify({ error: 'AI generation failed' }));
          }
        });
      });
    },
  };
}

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss(), expressApiPlugin()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modifyâfile watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
  };
});
