export type SectorCategory = 
  | 'IT Services'
  | 'Banking & Financials'
  | 'Energy & Oil'
  | 'Automotive'
  | 'FMCG'
  | 'Metals & Mining'
  | 'Pharmaceuticals'
  | 'Infrastructure & Capital Goods';

export interface NSEStock {
  symbol: string;               // e.g. 'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS'
  bseCode: string;              // e.g. '500325', '532540'
  name: string;                 // e.g. 'Reliance Industries Ltd'
  sector: SectorCategory;
  price: number;                // Current price in ₹ INR
  change: number;               // Absolute change in ₹
  changePercent: number;        // Percentage change %
  open: number;
  high: number;
  low: number;
  prevClose: number;
  volumeLakhs: number;          // Trading volume in Lakhs (1 Lakh = 100,000)
  turnoverCr: number;           // Total Turnover in ₹ Crores (1 Crore = 10,000,000)
  marketCapCr: number;          // Market Capitalization in ₹ Crores
  peRatio: number;              // Price to Earnings ratio
  pbRatio: number;              // Price to Book ratio
  week52High: number;           // 52-Week High in ₹
  week52Low: number;            // 52-Week Low in ₹
  vwap: number;                 // Volume Weighted Average Price in ₹
  upperCircuit: number;         // NSE Upper Price Band (10% or 20%)
  lowerCircuit: number;         // NSE Lower Price Band
  isNifty50: boolean;
  isFavorite?: boolean;
  sparkline: number[];
}

export interface MarketIndex {
  symbol: string;               // 'NIFTY 50', 'SENSEX', 'BANKNIFTY', 'NIFTY IT', 'INDIA VIX'
  name: string;
  value: number;                // Index level
  change: number;
  changePercent: number;
  high: number;
  low: number;
  sparkline: number[];
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
  spotPrice: number;
  atmStrike: number;
  pcr: number;                  // Put-Call Ratio (Put OI / Call OI)
  maxPainStrike: number;        // Strike price with maximum pain for option buyers
  totalCallOI: number;          // In Lakhs
  totalPutOI: number;           // In Lakhs
  impliedVolatility: number;    // % IV
  expiryDate: string;
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
