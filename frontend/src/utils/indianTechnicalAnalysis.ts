import { NSEStock, IndianMarketAIReport } from '../types/indianMarket';

export interface IndianCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  volumeLakhs?: number;
  vwap?: number;
  source?: string;
}

export function calculateEMA(prices: number[], period: number): number[] {
  if (prices.length < period) return prices;
  const k = 2 / (period + 1);
  const emaArray: number[] = [];
  
  // First value is simple moving average
  let sum = 0;
  for (let i = 0; i < period; i++) sum += prices[i];
  let currentEma = sum / period;
  emaArray.push(currentEma);

  for (let i = period; i < prices.length; i++) {
    currentEma = prices[i] * k + currentEma * (1 - k);
    emaArray.push(currentEma);
  }

  return emaArray;
}

export function calculateRSI(prices: number[], period: number = 14): number {
  if (prices.length < period + 1) return 50;

  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period; i++) {
    const diff = prices[i] - prices[i - 1];
    if (diff >= 0) gains += diff;
    else losses -= diff;
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  for (let i = period + 1; i < prices.length; i++) {
    const diff = prices[i] - prices[i - 1];
    if (diff >= 0) {
      avgGain = (avgGain * (period - 1) + diff) / period;
      avgLoss = (avgLoss * (period - 1)) / period;
    } else {
      avgGain = (avgGain * (period - 1)) / period;
      avgLoss = (avgLoss * (period - 1) - diff) / period;
    }
  }

  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return Number((100 - 100 / (1 + rs)).toFixed(1));
}

export function calculateVWAP(candles: IndianCandle[]): number {
  if (candles.length === 0) return 0;
  let totalPV = 0;
  let totalVolume = 0;

  for (const c of candles) {
    const typicalPrice = (c.high + c.low + c.close) / 3;
    const vol = c.volumeLakhs || (c.volume ? c.volume / 100000 : 0);
    totalPV += typicalPrice * vol;
    totalVolume += vol;
  }

  return totalVolume > 0 ? Number((totalPV / totalVolume).toFixed(2)) : 0;
}

export function generateLocalIndianAIReport(stock: NSEStock): IndianMarketAIReport {
  const p = stock.price;
  const hasPrice = p !== null && p !== undefined && p > 0;
  const hasVWAP = stock.vwap !== null && stock.vwap !== undefined && stock.vwap > 0;
  const stance = (hasPrice && hasVWAP) ? (p >= stock.vwap! ? 'Bullish Accumulation' : 'Distribution Pressure') : 'Neutral Consolidation';
  const conf = (hasPrice && hasVWAP) ? 50 : 20;

  return {
    symbol: stock.symbol,
    name: stock.name,
    sector: stock.sector,
    marketStance: stance,
    confidence: conf,
    niftyCorrel: 'Market Beta',
    fiiDiiSentiment: 'Settlement Neutral',
    executiveSummary: hasPrice 
      ? `Price action for ${stock.name} is currently at ₹${p.toLocaleString()} with reference VWAP at ₹${stock.vwap?.toLocaleString() || 'N/A'}.`
      : `Instrument ${stock.name} (${stock.symbol}) awaiting provider live price synchronization.`,
    supportLevels: [],
    resistanceLevels: [],
    technicalMetrics: {
      rsi14: 50,
      ema20: 0,
      ema50: 0,
      vwap: stock.vwap || 0,
      pcrSignal: 'Unavailable',
    },
    catalysts: [
      'Active session price discovery relative to volume-weighted benchmark.',
    ],
    tacticalTradeSetup: {
      action: 'MONITOR',
      entryZone: hasPrice ? `₹${p.toFixed(2)}` : 'Awaiting Quote',
      target1: undefined,
      target2: undefined,
      stopLoss: undefined,
      riskReward: undefined,
    },
  };
}
