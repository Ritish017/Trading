import { NSEStock, IndianMarketAIReport } from '../types/indianMarket';

export interface IndianCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volumeLakhs: number;
}

export function generateInitialIndianCandles(
  currentPrice: number,
  count: number = 60,
  intervalSeconds: number = 300
): IndianCandle[] {
  const candles: IndianCandle[] = [];
  const now = Math.floor(Date.now() / 1000);
  let basePrice = currentPrice * 0.98; // start slightly lower for realistic intraday trend

  for (let i = count; i >= 0; i--) {
    const time = now - i * intervalSeconds;
    const volatility = basePrice * 0.0025;
    const open = basePrice + (Math.random() - 0.48) * volatility;
    const close = open + (Math.random() - 0.47) * volatility;
    const high = Math.max(open, close) + Math.random() * volatility * 0.8;
    const low = Math.min(open, close) - Math.random() * volatility * 0.8;
    const volumeLakhs = Number((Math.random() * 8.5 + 0.5).toFixed(2));

    candles.push({
      time,
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
      volumeLakhs,
    });

    basePrice = close;
  }

  // Adjust last candle close to match current live price
  if (candles.length > 0) {
    candles[candles.length - 1].close = currentPrice;
    candles[candles.length - 1].high = Math.max(candles[candles.length - 1].high, currentPrice);
    candles[candles.length - 1].low = Math.min(candles[candles.length - 1].low, currentPrice);
  }

  return candles;
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
    totalPV += typicalPrice * c.volumeLakhs;
    totalVolume += c.volumeLakhs;
  }

  return totalVolume > 0 ? Number((totalPV / totalVolume).toFixed(2)) : 0;
}

export function generateIndianMarketDepth(currentPrice: number, precision: number = 2) {
  const bids: { price: number; quantityLakhs: number; orders: number }[] = [];
  const asks: { price: number; quantityLakhs: number; orders: number }[] = [];

  for (let i = 1; i <= 5; i++) {
    const bidPrice = Number((currentPrice - i * (currentPrice * 0.0006)).toFixed(precision));
    const askPrice = Number((currentPrice + i * (currentPrice * 0.0006)).toFixed(precision));

    bids.push({
      price: bidPrice,
      quantityLakhs: Number((Math.random() * 2.2 + 0.3).toFixed(2)),
      orders: Math.floor(Math.random() * 85 + 15),
    });

    asks.push({
      price: askPrice,
      quantityLakhs: Number((Math.random() * 2.2 + 0.3).toFixed(2)),
      orders: Math.floor(Math.random() * 85 + 15),
    });
  }

  return { bids, asks };
}

export function generateLocalIndianAIReport(stock: NSEStock): IndianMarketAIReport {
  const p = stock.price;
  const hasVWAP = stock.vwap && stock.vwap > 0;
  const stance = (p > 0 && hasVWAP) ? (p >= stock.vwap ? 'Bullish Accumulation' : 'Distribution Pressure') : 'Consolidation Range';
  const conf = (p > 0 && hasVWAP) ? 50 : 25;

  return {
    symbol: stock.symbol,
    name: stock.name,
    sector: stock.sector,
    marketStance: stance,
    confidence: conf,
    niftyCorrel: 'Market Beta',
    fiiDiiSentiment: 'Settlement Neutral',
    executiveSummary: `Price action for ${stock.name} is trading at ₹${p.toLocaleString()} with active session benchmark at ₹${stock.vwap?.toLocaleString() || 'N/A'}.`,
    supportLevels: [],
    resistanceLevels: [],
    technicalMetrics: {
      rsi14: undefined,
      ema20: undefined,
      ema50: undefined,
      vwap: stock.vwap || undefined,
      pcrSignal: 'Unavailable',
    },
    catalysts: [
      'Active session price discovery relative to volume-weighted benchmark.',
    ],
    tacticalTradeSetup: {
      action: 'MONITOR',
      entryZone: p > 0 ? `₹${p.toFixed(2)}` : undefined,
      target1: undefined,
      target2: undefined,
      stopLoss: undefined,
      riskReward: undefined,
    },
  };
}
