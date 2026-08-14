export type MarketStatusCode = 
  | 'LIVE'
  | 'MARKET_CLOSED'
  | 'PRE_MARKET'
  | 'DISCONNECTED'
  | 'STALE'
  | 'SIMULATED';

export type MarketProvenance = 
  | 'UPSTOX'
  | 'FYERS'
  | 'DEV_MOCK'
  | 'DERIVED'
  | 'GEMINI_AI';

export interface MarketQuote {
  symbol: string;               // e.g. 'RELIANCE.NS', 'NIFTY 50'
  displayName: string;          // e.g. 'Reliance Industries Ltd'
  exchange: 'NSE' | 'BSE' | 'MCX';
  instrumentKey: string;        // e.g. 'NSE_EQ|INE002A01018'
  instrumentType: 'EQUITY' | 'INDEX' | 'FUTURES' | 'OPTION';
  sector?: string;
  bseCode?: string;

  ltp: number;
  previousClose: number;
  open: number;
  high: number;
  low: number;
  close: number;

  change: number;              // Exact ltp - previousClose
  changePercent: number;       // Exact ((ltp - previousClose) / previousClose) * 100

  volume: number;              // Raw volume
  volumeLakhs?: number;        // Derived for UI
  turnoverCr?: number;         // Derived for UI
  openInterest?: number;
  vwap?: number;
  
  peRatio?: number;
  week52High?: number;
  week52Low?: number;
  isNifty50?: boolean;
  isFavorite?: boolean;

  timestamp: number;           // Exchange timestamp (epoch seconds)
  receivedAt: number;          // Local client received timestamp (epoch ms)
  dataAgeMs: number;           // Date.now() - receivedAt

  source: MarketProvenance;
  marketStatus: MarketStatusCode;
}
