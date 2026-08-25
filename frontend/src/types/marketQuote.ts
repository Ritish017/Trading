export type MarketStatusCode = 
  | 'LIVE'
  | 'RECENT'
  | 'MARKET_CLOSED'
  | 'PRE_MARKET'
  | 'DISCONNECTED'
  | 'STALE'
  | 'SIMULATED'
  | 'UNAVAILABLE';

export type ProviderMode = 
  | 'AUTHENTIC_LIVE'
  | 'SIMULATED'
  | 'HISTORICAL'
  | 'UNAVAILABLE';

export type MarketProvenance = 
  | 'UPSTOX'
  | 'DHAN'
  | 'MOCK'
  | 'DEV_MOCK'
  | 'DERIVED'
  | 'GEMINI_AI'
  | 'YAHOO_FINANCE';

export interface CanonicalQuote {
  symbol: string;
  instrument_key: string;
  exchange: string;

  ltp: number | null;
  previous_close: number | null;
  change: number | null;
  change_percent: number | null;

  open?: number | null;
  high?: number | null;
  low?: number | null;
  volume?: number | null;
  bid?: number | null;
  ask?: number | null;

  provider: string;
  provider_mode: ProviderMode;
  provider_timestamp: number;    // Exact exchange/provider epoch seconds
  received_timestamp: number;    // Server epoch seconds
  data_age_seconds: number;

  market_data_status: MarketStatusCode;
  canonical_source?: 'REST' | 'WS';
  quote_sequence_id?: number;

  is_live: boolean;
  is_stale: boolean;

  last_rest_ltp?: number | null;
  last_rest_ts?: number | null;
  last_ws_ltp?: number | null;
  last_ws_ts?: number | null;
}

export interface MarketQuote {
  symbol: string;
  displayName: string;
  exchange: 'NSE' | 'BSE' | 'MCX';
  instrumentKey: string;
  instrumentType: 'EQUITY' | 'INDEX' | 'FUTURES' | 'OPTION';
  sector?: string;
  bseCode?: string;

  ltp: number | null;
  previousClose: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;

  change: number | null;
  changePercent: number | null;

  volume?: number | null;
  volumeLakhs?: number;
  turnoverCr?: number;
  openInterest?: number;
  vwap?: number | null;
  
  peRatio?: number;
  week52High?: number;
  week52Low?: number;
  isNifty50?: boolean;
  isFavorite?: boolean;

  timestamp: number;           // Exchange timestamp (epoch seconds)
  receivedAt: number;          // Local client received timestamp (epoch ms)
  dataAgeMs: number;           // Milliseconds since provider timestamp

  source: MarketProvenance;
  providerMode?: ProviderMode;
  marketStatus: MarketStatusCode;
  isLive?: boolean;
  isStale?: boolean;
}
