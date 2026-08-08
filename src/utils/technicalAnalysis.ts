import { Candle, OrderBook, AIAnalysis, TradeSide, Position } from '../types/trading';

/**
 * Generates realistic candlestick data for a given asset base price and count.
 */
export function generateInitialCandles(
  basePrice: number,
  count: number = 60,
  timeframeSeconds: number = 300 // default 5m
): Candle[] {
  const candles: Candle[] = [];
  let currentPrice = basePrice * 0.96; // start slightly lower for trend
  const now = Math.floor(Date.now() / 1000);
  const startTime = now - count * timeframeSeconds;

  for (let i = 0; i < count; i++) {
    const time = startTime + i * timeframeSeconds;
    const volatility = basePrice * 0.008; // 0.8% volatility per bar
    const change = (Math.random() - 0.48) * volatility; // slight upward drift
    const open = currentPrice;
    const close = Math.max(open + change, basePrice * 0.1);
    const high = Math.max(open, close) + Math.random() * volatility * 0.6;
    const low = Math.min(open, close) - Math.random() * volatility * 0.6;
    const volume = Math.floor(Math.random() * 5000 + 1000) * (basePrice > 1000 ? 0.1 : 10);

    candles.push({
      time,
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
      volume: Number(volume.toFixed(2)),
    });

    currentPrice = close;
  }

  return candles;
}

/**
 * Calculates Simple Moving Average (SMA)
 */
export function calculateSMA(candles: Candle[], period: number): (number | null)[] {
  const smas: (number | null)[] = [];
  for (let i = 0; i < candles.length; i++) {
    if (i < period - 1) {
      smas.push(null);
    } else {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) {
        sum += candles[j].close;
      }
      smas.push(Number((sum / period).toFixed(2)));
    }
  }
  return smas;
}

/**
 * Calculates Relative Strength Index (RSI - 14)
 */
export function calculateRSI(candles: Candle[], period: number = 14): (number | null)[] {
  const rsis: (number | null)[] = [];
  if (candles.length < period + 1) return new Array(candles.length).fill(null);

  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period; i++) {
    const change = candles[i].close - candles[i - 1].close;
    if (change >= 0) gains += change;
    else losses += Math.abs(change);
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  rsis.push(...new Array(period).fill(null));

  let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  let rsi = 100 - 100 / (1 + rs);
  rsis.push(Number(rsi.toFixed(2)));

  for (let i = period + 1; i < candles.length; i++) {
    const change = candles[i].close - candles[i - 1].close;
    const currentGain = change >= 0 ? change : 0;
    const currentLoss = change < 0 ? Math.abs(change) : 0;

    avgGain = (avgGain * (period - 1) + currentGain) / period;
    avgLoss = (avgLoss * (period - 1) + currentLoss) / period;

    rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi = 100 - 100 / (1 + rs);
    rsis.push(Number(rsi.toFixed(2)));
  }

  return rsis;
}

/**
 * Calculates Bollinger Bands (20, 2)
 */
export function calculateBollingerBands(candles: Candle[], period: number = 20, multiplier: number = 2) {
  const sma = calculateSMA(candles, period);
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];

  for (let i = 0; i < candles.length; i++) {
    const currentSma = sma[i];
    if (currentSma === null || i < period - 1) {
      upper.push(null);
      lower.push(null);
    } else {
      let sumSquareDiff = 0;
      for (let j = i - period + 1; j <= i; j++) {
        const diff = candles[j].close - currentSma;
        sumSquareDiff += diff * diff;
      }
      const stdDev = Math.sqrt(sumSquareDiff / period);
      upper.push(Number((currentSma + multiplier * stdDev).toFixed(2)));
      lower.push(Number((currentSma - multiplier * stdDev).toFixed(2)));
    }
  }

  return { upper, middle: sma, lower };
}

/**
 * Generates dynamic order book for a symbol price
 */
export function generateOrderBook(currentPrice: number, precision: number = 2): OrderBook {
  const bids = [];
  const asks = [];
  const step = currentPrice * 0.0008;

  let totalBidVol = 0;
  for (let i = 1; i <= 8; i++) {
    const price = Number((currentPrice - i * step).toFixed(precision));
    const amount = Number((Math.random() * 2.5 + 0.1).toFixed(3));
    totalBidVol += amount;
    bids.push({ price, amount, total: Number(totalBidVol.toFixed(3)) });
  }

  let totalAskVol = 0;
  for (let i = 1; i <= 8; i++) {
    const price = Number((currentPrice + i * step).toFixed(precision));
    const amount = Number((Math.random() * 2.5 + 0.1).toFixed(3));
    totalAskVol += amount;
    asks.push({ price, amount, total: Number(totalAskVol.toFixed(3)) });
  }

  const bestBid = bids[0].price;
  const bestAsk = asks[0].price;
  const spread = Number((bestAsk - bestBid).toFixed(precision));
  const spreadPercent = Number(((spread / currentPrice) * 100).toFixed(3));

  return { bids, asks, spread, spreadPercent };
}

/**
 * Calculates position liquidation price and unrealized PnL
 */
export function calculatePositionMetrics(
  side: TradeSide,
  entryPrice: number,
  markPrice: number,
  amount: number,
  leverage: number,
  margin: number
) {
  const priceDiff = side === 'Buy' ? markPrice - entryPrice : entryPrice - markPrice;
  const rawPnL = priceDiff * amount;
  const unrealizedPnL = Number(rawPnL.toFixed(2));
  const unrealizedPnLPercent = Number(((rawPnL / margin) * 100).toFixed(2));

  // Liquidation threshold approx 90% loss of initial margin
  const maxLossPercent = 0.90;
  let liquidationPrice = 0;
  if (side === 'Buy') {
    liquidationPrice = entryPrice * (1 - maxLossPercent / leverage);
  } else {
    liquidationPrice = entryPrice * (1 + maxLossPercent / leverage);
  }

  return {
    unrealizedPnL,
    unrealizedPnLPercent,
    liquidationPrice: Number(Math.max(liquidationPrice, 0.01).toFixed(2)),
  };
}

/**
 * Generates local algorithmic technical analysis signal
 */
export function generateLocalAIAnalysis(symbol: string, currentPrice: number, candles: Candle[]): AIAnalysis {
  const rsiValues = calculateRSI(candles);
  const latestRSI = rsiValues[rsiValues.length - 1] ?? 50;
  const sma20Values = calculateSMA(candles, 20);
  const latestSMA20 = sma20Values[sma20Values.length - 1] ?? currentPrice;

  let overallSignal: 'Strong Buy' | 'Buy' | 'Neutral' | 'Sell' | 'Strong Sell' = 'Neutral';
  let confidence = 75;

  if (latestRSI < 30 && currentPrice > latestSMA20) {
    overallSignal = 'Strong Buy';
    confidence = 88;
  } else if (latestRSI < 40) {
    overallSignal = 'Buy';
    confidence = 80;
  } else if (latestRSI > 70) {
    overallSignal = 'Strong Sell';
    confidence = 86;
  } else if (latestRSI > 60) {
    overallSignal = 'Sell';
    confidence = 78;
  }

  const support1 = Number((currentPrice * 0.975).toFixed(2));
  const support2 = Number((currentPrice * 0.95).toFixed(2));
  const resistance1 = Number((currentPrice * 1.025).toFixed(2));
  const resistance2 = Number((currentPrice * 1.05).toFixed(2));

  const recommendedSide: TradeSide = overallSignal.includes('Buy') ? 'Buy' : 'Sell';
  const targetMultiplier = recommendedSide === 'Buy' ? 1.04 : 0.96;
  const stopMultiplier = recommendedSide === 'Buy' ? 0.98 : 1.02;

  return {
    symbol,
    overallSignal,
    confidence,
    summary: `Technical analysis for ${symbol} indicates a ${overallSignal} bias. RSI is currently at ${latestRSI.toFixed(
      1
    )}, with the 20-period moving average holding at $${latestSMA20.toLocaleString()}. Trend momentum suggests strategic entry near current key price zones.`,
    supportLevels: [support1, support2],
    resistanceLevels: [resistance1, resistance2],
    indicators: {
      rsi: {
        value: latestRSI,
        signal: latestRSI < 30 ? 'Oversold (Bullish)' : latestRSI > 70 ? 'Overbought (Bearish)' : 'Neutral Zone',
      },
      macd: {
        signal: recommendedSide === 'Buy' ? 'Bullish Crossover' : 'Bearish Divergence',
        histogram: recommendedSide === 'Buy' ? 1.45 : -1.22,
      },
      trend: currentPrice >= latestSMA20 ? 'Uptrend Above SMA20' : 'Downtrend Below SMA20',
    },
    tradeSetup: {
      recommendedSide,
      suggestedEntry: currentPrice,
      takeProfit1: Number((currentPrice * targetMultiplier).toFixed(2)),
      takeProfit2: Number((currentPrice * (targetMultiplier + (recommendedSide === 'Buy' ? 0.03 : -0.03))).toFixed(2)),
      stopLoss: Number((currentPrice * stopMultiplier).toFixed(2)),
      riskRewardRatio: '1 : 2.5',
    },
  };
}
