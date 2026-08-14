export type DataFreshness = 'LIVE' | 'RECENT' | 'STALE' | 'UNAVAILABLE';

export type MarketRegime = 
  | 'BULLISH_TREND'
  | 'BEARISH_TREND'
  | 'HIGH_VOLATILITY'
  | 'COMPRESSION'
  | 'RISK_ON'
  | 'RISK_OFF'
  | 'SECTOR_ROTATION'
  | 'NEUTRAL_CONSOLIDATION';

export type AttentionClassification = 
  | 'NOISE'          // 0 - 30
  | 'MONITOR'        // 30 - 50
  | 'INTERESTING'    // 50 - 70
  | 'IMPORTANT'      // 70 - 85
  | 'CRITICAL';      // 85 - 100

export type ImportanceLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type SignalStance = 'BULLISH' | 'BEARISH' | 'NEUTRAL' | 'MIXED' | 'UNAVAILABLE';

export interface EvidenceItem {
  type: string; // PRICE, VOLUME, DERIVATIVES, TECHNICAL, NEWS, SECTOR, MACRO, INSTITUTIONAL
  statement: string;
  value: any;
  source: string;
  timestamp: string;
  freshness?: DataFreshness;
}

export interface MarketEvent {
  event_id: string;
  event_type: string;
  symbol: string;
  company_name?: string;
  sector?: string;
  timestamp: string;
  severity: number; // 0 - 100
  confidence: number; // 0 - 1
  attention_score: number; // 0 - 100
  classification: AttentionClassification;
  evidence: EvidenceItem[];
  affected_sector?: string;
  affected_assets?: string[];
  affected_indices?: string[];
}

export interface AICommentary {
  id: string;
  symbol: string;
  company_name: string;
  sector: string;
  headline: string;
  event_type: string;
  importance: ImportanceLevel;
  attention_score: number;
  classification: AttentionClassification;
  market_regime: MarketRegime;
  
  // 7 Core Questions Answered
  what_changed: string;
  why_it_matters: string;
  likely_drivers: string[];
  confirming_evidence: EvidenceItem[];
  contradicting_evidence: EvidenceItem[];
  company_context: string;
  sector_context: string;
  macro_context: string;
  why_should_i_care: string;
  what_to_watch: string[];
  
  bullish_confirmation: string[];
  bearish_confirmation: string[];
  uncertainties: string[];
  
  confidence: number;
  timestamp: string;
  data_freshness: DataFreshness;
  sources: string[];
}

export interface MarketNarrative {
  date: string;
  headline: string;
  primary_regime: MarketRegime;
  narrative_summary: string;
  key_drivers: string[];
  sector_leaders: string[];
  sector_laggards: string[];
  institutional_bias: string;
  macro_backdrop: string;
  confidence: number;
  timestamp: string;
}

export interface SnapshotMetricDiff {
  metric: string;
  previous_value: string | number;
  current_value: string | number;
  direction: 'UP' | 'DOWN' | 'NEUTRAL';
  significance: 'LOW' | 'MEDIUM' | 'HIGH';
}
