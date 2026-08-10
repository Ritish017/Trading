export type AssetCategory = 'Crypto' | 'Stocks' | 'Forex' | 'Commodities';

export interface Asset {
  symbol: string;
  name: string;
  category: AssetCategory;
  price: number;
  change24h: number;
  high24h: number;
  low24h: number;
  volume24h: number;
  precision: number;
  sparkline: number[];
  isFavorite?: boolean;
}

export interface Candle {
  time: number; // Unix timestamp in seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type OrderType = 'Market' | 'Limit' | 'Stop';
export type TradeSide = 'Buy' | 'Sell'; // Buy = Long, Sell = Short

export interface OrderBookEntry {
  price: number;
  amount: number;
  total: number;
}

export interface OrderBook {
  bids: OrderBookEntry[]; // Buy orders
  asks: OrderBookEntry[]; // Sell orders
  spread: number;
  spreadPercent: number;
}

export interface ExecutedTrade {
  id: string;
  price: number;
  amount: number;
  side: TradeSide;
  time: string;
}

export interface Position {
  id: string;
  symbol: string;
  side: TradeSide;
  entryPrice: number;
  markPrice: number;
  amount: number; // Quantity in base asset
  leverage: number;
  margin: number;
  unrealizedPnL: number;
  unrealizedPnLPercent: number;
  liquidationPrice: number;
  stopLoss?: number;
  takeProfit?: number;
  timestamp: number;
}

export interface PendingOrder {
  id: string;
  symbol: string;
  side: TradeSide;
  type: OrderType;
  price: number;
  amount: number;
  triggerPrice?: number;
  timestamp: number;
}

export interface ClosedTrade {
  id: string;
  symbol: string;
  side: TradeSide;
  entryPrice: number;
  exitPrice: number;
  amount: number;
  leverage: number;
  realizedPnL: number;
  realizedPnLPercent: number;
  fee: number;
  closeTimestamp: number;
  reason: 'Manual' | 'Take Profit' | 'Stop Loss' | 'Liquidation';
}

export interface NewsItem {
  id: string;
  title: string;
  source: string;
  timeAgo: string;
  sentiment: 'Bullish' | 'Bearish' | 'Neutral';
  relatedSymbol: string;
  impact: 'High' | 'Medium' | 'Low';
  summary: string;
}

export interface AIAnalysis {
  symbol: string;
  overallSignal: 'Strong Buy' | 'Buy' | 'Neutral' | 'Sell' | 'Strong Sell';
  confidence: number; // 0 - 100
  summary: string;
  supportLevels: number[];
  resistanceLevels: number[];
  indicators: {
    rsi: { value: number; signal: string };
    macd: { signal: string; histogram: number };
    trend: string;
  };
  tradeSetup?: {
    recommendedSide: TradeSide;
    suggestedEntry: number;
    takeProfit1: number;
    takeProfit2: number;
    stopLoss: number;
    riskRewardRatio: string;
  };
}

export type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1D' | '1W';

export interface ChartIndicatorConfig {
  sma20: boolean;
  sma50: boolean;
  bollingerBands: boolean;
  rsi: boolean;
  macd: boolean;
  volume: boolean;
}
