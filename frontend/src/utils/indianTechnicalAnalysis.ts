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
}

export function generateInitialIndianCandles(
  currentPrice: number,
  count: number = 60,
  intervalSeconds: number = 300
): IndianCandle[] {
  const now = Math.floor(Date.now() / 1000);
  let walkPrice = currentPrice;
  const rawCandles: IndianCandle[] = [];

  for (let i = 0; i < count; i++) {
    const time = now - i * intervalSeconds;
    // Controlled ~0.10% to 0.15% candle volatility
    const volatility = Math.max(walkPrice * 0.0015, 0.25);
    
    // Close of this candle is walkPrice
    const close = walkPrice;
    // Step backwards to open with slight drift
    const openDrift = (Math.random() - 0.49) * volatility;
    const open = Math.max(close - openDrift, 1.0);
    
    const wickHigh = Math.random() * volatility * 0.5;
    const wickLow = Math.random() * volatility * 0.5;
    const high = Math.max(open, close) + wickHigh;
    const low = Math.max(Math.min(open, close) - wickLow, 0.5);

    const volumeShares = Math.floor(Math.random() * 25000 + 4000);
    const volumeLakhs = Number((volumeShares / 100000).toFixed(2));
    const vwap = Number(((high + low + close) / 3).toFixed(2));

    rawCandles.push({
      time,
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
      volume: volumeShares,
      volumeLakhs,
      vwap,
    });

    // Next step backward
    walkPrice = open;
  }

  // Reverse so chronological order (oldest to newest)
  rawCandles.reverse();

  // Ensure the latest candle close is exactly the current live price
  if (rawCandles.length > 0) {
    const last = rawCandles[rawCandles.length - 1];
    last.close = currentPrice;
    last.high = Math.max(last.high, currentPrice);
    last.low = Math.min(last.low, currentPrice);
  }

  return rawCandles;
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
