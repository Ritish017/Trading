export type SectorCategory = 
  | 'IT Services'
  | 'Banking & Financials'
  | 'Energy & Oil'
  | 'Automotive'
  | 'FMCG'
  | 'Metals & Mining'
  | 'Pharmaceuticals'
  | 'Infrastructure & Capital Goods';

export interface NSEStockMetadata {
  symbol: string;               // e.g. 'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS'
  bseCode: string;              // e.g. '500325', '532540'
  name: string;                 // e.g. 'Reliance Industries Ltd'
  sector: SectorCategory;
  marketCapCr?: number;         // Market Capitalization in ₹ Crores (Quarterly/Annual)
  peRatio?: number;             // Price to Earnings ratio (Fundamental)
  pbRatio?: number;             // Price to Book ratio (Fundamental)
  week52High?: number;          // 52-Week High in ₹ (Statistical)
  week52Low?: number;           // 52-Week Low in ₹ (Statistical)
  isNifty50: boolean;
  isFavorite?: boolean;
}

export interface NSEStock extends NSEStockMetadata {
  // Live market price fields (Populated ONLY by provider; null/undefined on init)
  price?: number | null;        // Current LTP in ₹ INR
  change?: number | null;       // Absolute change in ₹
  changePercent?: number | null;// Percentage change %
  open?: number | null;
  high?: number | null;
  low?: number | null;
  prevClose?: number | null;
  volumeLakhs?: number | null;  // Trading volume in Lakhs
  turnoverCr?: number | null;   // Total Turnover in ₹ Crores
  vwap?: number | null;         // Volume Weighted Average Price in ₹
  upperCircuit?: number | null;
  lowerCircuit?: number | null;
  sparkline?: number[];
  source?: string;
  providerTimestamp?: number;
  dataAgeSeconds?: number;
  marketStatus?: string;
  isLive?: boolean;
}

export interface MarketIndexMetadata {
  symbol: string;               // 'NIFTY 50', 'SENSEX', 'BANKNIFTY', 'NIFTY IT', 'INDIA VIX'
  name: string;
}

export interface MarketIndex extends MarketIndexMetadata {
  // Live index levels (Populated ONLY by provider; null/undefined on init)
  value?: number | null;        // Index level
  change?: number | null;
  changePercent?: number | null;
  high?: number | null;
  low?: number | null;
  sparkline?: number[];
  providerTimestamp?: number;
  isLive?: boolean;
}

export interface FIIDIINetFlow {
  date: string;
  fiiCashNetCr: number;         // Net FII Buy/Sell in Cash Market (₹ Cr)
  diiCashNetCr: number;         // Net DII Buy/Sell in Cash Market (₹ Cr)
  fiiIndexFuturesCr: number;    // FII Index Futures Net Position
  fiiIndexOptionsCr: number;    // FII Index Options Net Position
  fiiStockFuturesCr: number;    // FII Stock Futures Net Position
}

export interface MarketBreadth {
  advances: number;
  declines: number;
  unchanged: number;
  ratio: number;
  new52WeekHighs: number;
  new52WeekLows: number;
  upperCircuits: number;
  lowerCircuits: number;
}

export interface OptionChainSummary {
  symbol: 'NIFTY' | 'BANKNIFTY' | 'FINNIFTY';
  spotPrice?: number | null;
  atmStrike?: number | null;
  pcr?: number | null;          // Put-Call Ratio
  maxPainStrike?: number | null;// Strike price with maximum pain
  totalCallOI?: number | null;  // In Lakhs
  totalPutOI?: number | null;   // In Lakhs
  impliedVolatility?: number | null;
  expiryDate?: string;
}

export interface SEBIAnnouncement {
  id: string;
  companySymbol: string;
  companyName: string;
  headline: string;
  category: 'Quarterly Results' | 'Dividend' | 'Board Meeting' | 'SEBI Disclosure' | 'Bulk / Block Deal' | 'Corporate Action';
  timestamp: string;
  impact: 'Positive' | 'Neutral' | 'Negative';
  details: string;
  sourceUrl?: string;
}

export interface IndianMarketAIReport {
  symbol: string;
  name: string;
  sector: SectorCategory;
  marketStance: 'Strong Bullish' | 'Bullish Accumulation' | 'Neutral Consolidation' | 'Bearish Distribution' | 'Strong Bearish';
  confidence: number;           // 0 - 100
  niftyCorrel: string;
  fiiDiiSentiment: string;
  executiveSummary: string;
  supportLevels: number[];
  resistanceLevels: number[];
  technicalMetrics: {
    rsi14: number;
    ema20: number;
    ema50: number;
    vwap: number;
    pcrSignal: string;
  };
  catalysts: string[];
  tacticalTradeSetup: {
    action: string;
    entryZone: string;
    target1: string;
    target2: string;
    stopLoss: string;
    riskReward: string;
  };
}

export interface PaperPosition {
  id: string;
  symbol: string;
  companyName: string;
  productType: 'CNC (Delivery)' | 'MIS (Intraday)';
  side: 'BUY' | 'SELL';
  quantity: number;
  entryPrice: number;
  currentPrice: number;
  unrealizedPnL: number;
  unrealizedPnLPercent: number;
  targetPrice?: number;
  stopLoss?: number;
  timestamp: number;
}
