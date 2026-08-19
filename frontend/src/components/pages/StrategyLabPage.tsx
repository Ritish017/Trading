import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  FlaskConical, Search, Zap, CheckCircle2, XCircle, AlertTriangle,
  MinusCircle, Clock, Database, ChevronDown, ChevronUp, ChevronRight,
  TrendingUp, TrendingDown, Info, Send, Loader2, Shield, Activity,
  Sliders, Eye, EyeOff, BarChart2, Layers, Sparkles, MessageSquare,
  HelpCircle, RefreshCw, CheckSquare, Square, History, ShieldAlert,
  BarChart, ArrowUpRight, ArrowDownRight, Compass, Filter, Tag, BookOpen,
  Calendar, Award, Crosshair, Target, Percent, DollarSign, PieChart,
  Grid, Cpu, CheckCheck, GitMerge, FileText, ChevronLeft, ShieldCheck,
  Flame, Copy, Bookmark, AlertOctagon, CornerDownRight, BarChart3, Split
} from 'lucide-react';
import { NSEStock } from '../../types/indianMarket';

// ---------------------------------------------------------------------------
// Types & Extensible Contracts (V3, V4, V5, V6)
// ---------------------------------------------------------------------------
export type RuleOutcome = 'PASS' | 'FAIL' | 'UNAVAILABLE';
export type StrategyState = 'ACTIVE' | 'PARTIAL' | 'INACTIVE' | 'CONFLICTED' | 'UNAVAILABLE';
export type DataFreshness = 'LIVE' | 'RECENT' | 'STALE' | 'UNAVAILABLE';
export type StrategyDirection = 'BULLISH' | 'BEARISH' | 'BOTH';

export interface ResearchParameterMeta {
  parameter_id: string;
  name: string;
  param_type: string;
  default_value: any;
  allowed_values?: any[] | null;
  minimum?: number | null;
  maximum?: number | null;
  step?: number | null;
  description: string;
}

export interface RuleEvaluation {
  rule_id: string;
  label: string;
  dependency_keys: string[];
  outcome: RuleOutcome;
  actual_value: number | null;
  actual_value_label: string;
  is_entry_rule: boolean;
  math_detail?: string | null;
}

export interface ActivationEvent {
  candle_index: number;
  timestamp: number;
  event_type: 'ACTIVATED' | 'INVALIDATED' | 'CONFLICT' | 'PARTIAL';
  price: number;
  strategy_id: string;
  label: string;
}

export interface HistoricalState {
  candle_index: number;
  timestamp: number;
  state: StrategyState;
  passing_count: number;
  total_count: number;
  price: number;
}

export interface StrategyVisualizationMeta {
  overlays: string[];
  subpanels: string[];
  markers: string[];
  highlight_active_regions: boolean;
  color: string;
}

export interface StrategyRequirementsMeta {
  min_candles: number;
  requires_volume: boolean;
  requires_vwap: boolean;
  requires_intraday: boolean;
  supported_timeframes: string[];
}

export interface StrategyResult {
  strategy_id: string;
  strategy_name: string;
  short_name?: string;
  category: string;
  description: string;
  direction?: StrategyDirection | string;
  version?: string;
  enabled?: boolean;
  experimental?: boolean;
  state: StrategyState;
  entry_rules_total: number;
  entry_rules_passing: number;
  entry_rules_unavailable: number;
  exit_rules_triggered: number;
  exit_rules_total: number;
  rule_evaluations: RuleEvaluation[];
  feature_vector: Record<string, number>;
  data_freshness: string;
  data_age_seconds?: number | null;
  evaluated_at: string;
  candles_used: number;
  tags: string[];
  requirements?: StrategyRequirementsMeta;
  visualization?: StrategyVisualizationMeta;
  research_parameters?: ResearchParameterMeta[];
  historical_states: HistoricalState[];
  activation_events: ActivationEvent[];
}

export interface ChartCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number;
}

export interface SeriesIndicators {
  ema20?: (number | null)[];
  ema50?: (number | null)[];
  ema200?: (number | null)[];
  vwap?: (number | null)[];
  vwap_distance_pct?: (number | null)[];
  rsi14?: (number | null)[];
  roc12?: (number | null)[];
  macd?: (number | null)[];
  macd_signal?: (number | null)[];
  macd_histogram?: (number | null)[];
  adx?: (number | null)[];
  plus_di?: (number | null)[];
  minus_di?: (number | null)[];
  bb_upper?: (number | null)[];
  bb_middle?: (number | null)[];
  bb_lower?: (number | null)[];
  donchian_high?: (number | null)[];
  donchian_mid?: (number | null)[];
  donchian_low?: (number | null)[];
  prev_day_high?: (number | null)[];
  prev_day_low?: (number | null)[];
  highest_high_20?: (number | null)[];
  atr14?: (number | null)[];
  atr_sma20?: (number | null)[];
  rvol?: (number | null)[];
  cmf20?: (number | null)[];
  obv?: (number | null)[];
  supertrend_band?: (number | null)[];
  orb_high?: (number | null)[];
  orb_low?: (number | null)[];
}

export interface MarketRegimeData {
  regime: string;
  confidence: number;
  trend_strength: number;
  volatility_status: string;
  evidence: string;
  metrics: Record<string, number>;
}

export interface ConfluenceData {
  active_count: number;
  partial_count: number;
  inactive_count: number;
  unavailable_count: number;
  conflicted_count: number;
  total_strategies: number;
  alignment_score_pct: number;
  passing_rules_count: number;
  total_rules_count: number;
  bullish_confluence: number;
  reversal_confluence: number;
  has_conflicts: boolean;
  conflict_reasons: string[];
}

export interface ObservatoryData {
  symbol?: string;
  market_status?: 'OPEN' | 'CLOSED' | 'PRE_OPEN' | 'SIMULATED';
  market_regime: MarketRegimeData;
  confluence: ConfluenceData;
  data_freshness: string;
  data_age_seconds?: number | null;
  evaluated_at: string;
  timeframe?: string;
  provider?: string;
  strategies: StrategyResult[];
  chart_indicators: SeriesIndicators;
  candles: ChartCandle[];
}

export interface ForwardObservationData {
  horizon_candles: number;
  forward_return_pct?: number | null;
  direction_adjusted_return_pct?: number | null;
  mae_pct?: number | null;
  mfe_pct?: number | null;
  is_complete: boolean;
  end_price?: number | null;
  min_price?: number | null;
  max_price?: number | null;
}

export interface ResearchObservationData {
  observation_id: string;
  strategy_id: string;
  strategy_version: string;
  symbol: string;
  timeframe: string;
  direction: string;
  activation_index: number;
  activation_timestamp: number;
  activation_price: number;
  invalidation_index?: number | null;
  invalidation_timestamp?: number | null;
  invalidation_price?: number | null;
  candles_to_invalidation?: number | null;
  time_to_invalidation_seconds?: number | null;
  regime_at_activation: string;
  regime_evidence: string;
  confluence_count: number;
  confluent_strategies: string[];
  conflicting_strategies: string[];
  rule_snapshot: any[];
  indicator_snapshot: Record<string, number>;
  forward_observations: Record<string, ForwardObservationData>;
  observation_status: string;
}

export interface HorizonSummaryData {
  horizon: number;
  sample_count: number;
  mean_return_pct?: number | null;
  median_return_pct?: number | null;
  std_dev_pct?: number | null;
  min_return_pct?: number | null;
  max_return_pct?: number | null;
  positive_return_pct?: number | null;
  negative_return_pct?: number | null;
  p10?: number | null;
  p25?: number | null;
  p50?: number | null;
  p75?: number | null;
  p90?: number | null;
  mean_mae_pct?: number | null;
  median_mae_pct?: number | null;
  mean_mfe_pct?: number | null;
  median_mfe_pct?: number | null;
  is_low_sample: boolean;
}

export interface StrategyResearchSummaryData {
  strategy_id: string;
  strategy_name: string;
  category: string;
  direction: string;
  symbol: string;
  timeframe: string;
  total_candles_analyzed: number;
  total_activations: number;
  active_episodes_count: number;
  total_active_candles: number;
  activation_frequency_pct: number;
  avg_episode_duration_candles: number;
  median_episode_duration_candles: number;
  invalidation_count: number;
  invalidation_frequency_pct: number;
  horizons_summary: Record<string, HorizonSummaryData>;
  regime_breakdown: Record<string, { activations: number; median_5candle_return: number; positive_frequency_pct: number; is_low_sample: boolean }>;
  confluence_breakdown: Record<string, { activations: number; median_5candle_return: number; positive_frequency_pct: number; is_low_sample: boolean }>;
  observations: ResearchObservationData[];
}

export interface BacktestTradeData {
  trade_id: string;
  strategy_id: string;
  strategy_version: string;
  symbol: string;
  timeframe: string;
  direction: string;
  entry_index: number;
  entry_time: any;
  entry_price: number;
  exit_index: number;
  exit_time: any;
  exit_price: number;
  quantity: number;
  gross_pnl: number;
  gross_return_pct: number;
  slippage_cost: number;
  brokerage_cost: number;
  total_costs: number;
  net_pnl: number;
  net_return_pct: number;
  exit_reason: string;
  duration_bars: number;
  regime_at_entry: string;
  confluence_state: Record<string, any>;
  entry_rule_evidence: Array<{ rule_id: string; label: string; outcome: string; value: string }>;
  exit_rule_evidence: Array<{ rule_id: string; label: string; outcome: string; value: string }>;
  is_in_sample: boolean;
}

export interface BacktestResultData {
  status: string;
  strategy_id: string;
  strategy_version: string;
  symbol: string;
  timeframe: string;
  initialCapital: number;
  finalCapital: number;
  netProfit: number;
  totalReturnPct: number;
  total_return_pct: number;
  grossReturnPct: number;
  winRate: number;
  win_rate_pct: number;
  profitFactor: number;
  profit_factor: number;
  maxDrawdown: number;
  max_drawdown_pct: number;
  totalTrades: number;
  total_trades: number;
  winningTrades: number;
  losingTrades: number;
  sharpeRatio: number;
  sharpe_ratio: number;
  cagr: number;
  avg_trade_return_pct: number;
  median_trade_return_pct: number;
  avg_trade_duration_bars: number;
  median_trade_duration_bars: number;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
  total_fees: number;
  total_slippage: number;
  total_friction_costs: number;
  walk_forward: {
    split_ratio: number;
    in_sample_bars: number;
    out_of_sample_bars: number;
    in_sample_trades: number;
    out_of_sample_trades: number;
    in_sample_return_pct: number;
    out_of_sample_return_pct: number;
    in_sample_win_rate: number;
    out_of_sample_win_rate: number;
    overfitting_status: string;
  };
  cost_sensitivity: {
    zero_friction_return_pct: number;
    configured_friction_return_pct: number;
    high_friction_return_pct: number;
    cost_drag_pct: number;
  };
  equity_curve: number[];
  drawdown_curve: number[];
  trades: BacktestTradeData[];
}

export interface ParameterSweepItemData {
  configuration_id: string;
  parameters: Record<string, any>;
  total_trades: number;
  gross_return_pct: number;
  net_return_pct: number;
  cagr: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  profit_factor: number;
  win_rate_pct: number;
  is_return_pct: number;
  oos_return_pct: number;
  is_win_rate_pct: number;
  oos_win_rate_pct: number;
  overfitting_status: string;
  cost_drag_pct: number;
  high_friction_return_pct: number;
  triple_friction_return_pct: number;
  robustness_classification: string;
}

export interface ParameterSurfaceData {
  param_1_id: string;
  param_1_name: string;
  param_1_values: any[];
  param_2_id: string;
  param_2_name: string;
  param_2_values: any[];
  cells: Array<{
    param_1_val: any;
    param_2_val: any;
    net_return_pct: number;
    sharpe_ratio: number;
    max_drawdown_pct: number;
    profit_factor: number;
    total_trades: number;
    oos_return_pct: number;
    overfitting_status: string;
    is_low_sample: boolean;
  }>;
}

export interface NeighborhoodAnalysisData {
  candidate_params: Record<string, any>;
  candidate_net_return_pct: number;
  candidate_sharpe: number;
  neighbor_count: number;
  mean_neighbor_return_pct: number;
  median_neighbor_return_pct: number;
  return_standard_deviation: number;
  plateau_score: number;
  stability_classification: string;
  neighbors: Array<{
    parameters: Record<string, any>;
    net_return_pct: number;
    sharpe_ratio: number;
    total_trades: number;
  }>;
}

export interface MultiSymbolSummaryData {
  strategy_id: string;
  parameters: Record<string, any>;
  symbols_tested: string[];
  symbol_count: number;
  total_trades_all_symbols: number;
  median_net_return_pct: number;
  mean_net_return_pct: number;
  min_return_pct: number;
  max_return_pct: number;
  dispersion_iqr_pct: number;
  best_symbol: string;
  worst_symbol: string;
  profitable_symbols_count: number;
  generalization_classification: string;
  symbol_breakdown: Record<string, {
    net_return_pct: number;
    total_trades: number;
    sharpe_ratio: number;
    win_rate_pct: number;
    profit_factor: number;
  }>;
}

export interface PeriodRobustnessData {
  strategy_id: string;
  parameters: Record<string, any>;
  subperiod_count: number;
  subperiod_results: Array<{
    period_index: number;
    period_name: string;
    start_time: number;
    end_time: number;
    bars_count: number;
    total_trades: number;
    net_return_pct: number;
    win_rate_pct: number;
    sharpe_ratio: number;
    max_drawdown_pct: number;
  }>;
  early_period_return_pct: number;
  recent_period_return_pct: number;
  decay_ratio: number;
  decay_status: string;
}

export interface WalkForwardSelectionData {
  strategy_id: string;
  fold_count: number;
  train_split_ratio: number;
  selected_parameters_per_fold: Record<string, any>[];
  is_returns_per_fold: number[];
  oos_returns_per_fold: number[];
  cumulative_oos_return_pct: number;
  cumulative_oos_sharpe: number;
  cumulative_oos_drawdown_pct: number;
  parameter_stability_pct: number;
  walk_forward_classification: string;
}

export interface ResearchExperimentData {
  experiment_id: string;
  created_at: string;
  strategy_id: string;
  strategy_version: string;
  symbol: string;
  timeframe: string;
  parameters: Record<string, any>;
  configurations_tested_count: number;
  data_snooping_risk: string;
  sample_size_bars: number;
  total_trades: number;
  net_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  is_return_pct: number;
  oos_return_pct: number;
  robustness_status: string;
  cost_drag_pct: number;
  workflow_state: string;
  notes?: string;
}

export interface CopilotMessage {
  role: 'user' | 'assistant';
  text: string;
  evidence_cited?: string[];
}

export interface StrategyLabPageProps {
  stocks: NSEStock[];
  selectedSymbol: string;
  onSelectSymbol?: (symbol: string) => void;
}

// ---------------------------------------------------------------------------
// Quick Symbols for Fast Switching
// ---------------------------------------------------------------------------
const QUICK_SYMBOLS = [
  'RELIANCE.NS',
  'TCS.NS',
  'HDFCBANK.NS',
  'INFY.NS',
  'ICICIBANK.NS',
  'TATAMOTORS.NS',
  'SBIN.NS',
  'NIFTY 50',
  'BANKNIFTY'
];

// ---------------------------------------------------------------------------
// State Badge Component
// ---------------------------------------------------------------------------
const STATE_STYLES: Record<StrategyState, { label: string; bg: string; border: string; text: string; dot: string; icon: React.FC<any> }> = {
  ACTIVE:      { label: 'ACTIVE',      bg: 'bg-emerald-500/15', border: 'border-emerald-500/40', text: 'text-emerald-400', dot: 'bg-emerald-400', icon: CheckCircle2 },
  PARTIAL:     { label: 'PARTIAL',     bg: 'bg-amber-500/15',   border: 'border-amber-500/40',   text: 'text-amber-400',   dot: 'bg-amber-400',   icon: AlertTriangle },
  INACTIVE:    { label: 'INACTIVE',    bg: 'bg-rose-500/10',    border: 'border-rose-500/30',    text: 'text-rose-400',    dot: 'bg-rose-500',    icon: XCircle },
  CONFLICTED:  { label: 'CONFLICTED',  bg: 'bg-purple-500/15',  border: 'border-purple-500/40',  text: 'text-purple-400',  dot: 'bg-purple-400',  icon: AlertTriangle },
  UNAVAILABLE: { label: 'UNAVAILABLE', bg: 'bg-stone-800/40',   border: 'border-stone-700/40',   text: 'text-stone-400',   dot: 'bg-stone-500',   icon: MinusCircle },
};

function StateBadge({ state, size = 'md' }: { state: StrategyState; size?: 'sm' | 'md' }) {
  const cfg = STATE_STYLES[state] || STATE_STYLES.UNAVAILABLE;
  const sizeClass = size === 'sm' ? 'px-1.5 py-0.5 text-[9px]' : 'px-2.5 py-1 text-xs';
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border font-bold font-mono ${sizeClass} ${cfg.bg} ${cfg.border} ${cfg.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

function formatDuration(seconds?: number | null): string {
  if (seconds === undefined || seconds === null) return 'N/A';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

// ---------------------------------------------------------------------------
// Dynamic Strategy Keypad Tile (Metadata-Driven)
// ---------------------------------------------------------------------------
function StrategyKeypadButton({
  strategy,
  isSelected,
  onClick,
}: {
  strategy: StrategyResult;
  isSelected: boolean;
  onClick: () => void;
}) {
  const displayName = strategy.short_name || strategy.strategy_name;

  return (
    <button
      onClick={onClick}
      className={`p-2.5 rounded-xl border text-left flex flex-col justify-between transition-all cursor-pointer relative overflow-hidden ${
        isSelected
          ? 'bg-violet-950/40 border-violet-500/80 ring-1 ring-violet-500/60 shadow-lg shadow-violet-500/10'
          : 'bg-[#151720] border-stone-800/80 hover:border-stone-700 hover:bg-[#1c1e29]'
      }`}
    >
      <div className="flex items-start justify-between gap-1 w-full mb-1">
        <div className="flex-1 min-w-0">
          <div className="font-extrabold text-xs text-stone-100 truncate tracking-tight">{displayName}</div>
          <div className="text-[9px] font-mono text-stone-500 uppercase">{strategy.category}</div>
        </div>
        <StateBadge state={strategy.state} size="sm" />
      </div>

      <div className="flex items-center justify-between text-[10px] font-mono text-stone-400 mt-1 border-t border-stone-800/40 pt-1.5 w-full">
        <span className="text-stone-500">Coverage</span>
        <span className="font-bold text-stone-300">
          {strategy.entry_rules_passing}/{strategy.entry_rules_total}
        </span>
      </div>

      {isSelected && (
        <div className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-violet-400 animate-ping" />
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Strategy Alignment & Confluence Gauge
// ---------------------------------------------------------------------------
function StrategyAlignmentBar({ confluence }: { confluence: ConfluenceData }) {
  const total = confluence.total_strategies || 20;
  const actPct = (confluence.active_count / total) * 100;
  const partPct = (confluence.partial_count / total) * 100;
  const inactPct = (confluence.inactive_count / total) * 100;
  const unavailPct = (confluence.unavailable_count / total) * 100;

  return (
    <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Layers className="w-3.5 h-3.5 text-violet-400" />
          <span className="text-xs font-bold text-stone-200 uppercase tracking-wide font-mono">Strategy Alignment & Confluence</span>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-emerald-400 font-bold">{confluence.active_count} Active</span>
          <span className="text-stone-600">·</span>
          <span className="text-amber-400 font-bold">{confluence.partial_count} Partial</span>
          <span className="text-stone-600">·</span>
          <span className="text-rose-400 font-bold">{confluence.inactive_count} Inactive</span>
          {confluence.unavailable_count > 0 && (
            <>
              <span className="text-stone-600">·</span>
              <span className="text-stone-400 font-bold">{confluence.unavailable_count} N/A</span>
            </>
          )}
        </div>
      </div>

      <div className="h-2 w-full bg-stone-900 rounded-full overflow-hidden flex border border-stone-800">
        <div style={{ width: `${actPct}%` }} className="bg-emerald-500 transition-all duration-500" title={`Active: ${confluence.active_count}`} />
        <div style={{ width: `${partPct}%` }} className="bg-amber-500 transition-all duration-500" title={`Partial: ${confluence.partial_count}`} />
        <div style={{ width: `${inactPct}%` }} className="bg-rose-500/80 transition-all duration-500" title={`Inactive: ${confluence.inactive_count}`} />
        <div style={{ width: `${unavailPct}%` }} className="bg-stone-700 transition-all duration-500" title={`Unavailable: ${confluence.unavailable_count}`} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono">
        <div className="flex items-center gap-4 flex-wrap">
          <span className="text-stone-400">
            Rule Satisfaction: <strong className="text-stone-200">{confluence.passing_rules_count}/{confluence.total_rules_count}</strong> ({confluence.alignment_score_pct}%)
          </span>
          <span className="text-stone-400">
            Bullish Confluence: <strong className="text-emerald-400">{confluence.bullish_confluence} strategies</strong>
          </span>
          {confluence.reversal_confluence > 0 && (
            <span className="text-stone-400">
              Reversal / Exhaustion: <strong className="text-amber-400">{confluence.reversal_confluence} strategy</strong>
            </span>
          )}
        </div>
      </div>

      {confluence.has_conflicts && (
        <div className="p-2.5 rounded-lg bg-orange-950/40 border border-orange-700/50 text-orange-300 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-orange-400" />
          <div>
            <strong className="text-orange-200 font-mono">STRATEGY CONFLICT:</strong>{' '}
            <span>{confluence.conflict_reasons.join(' ')}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dynamic Metadata-Driven Observatory Trading Chart
// ---------------------------------------------------------------------------
interface ObservatoryChartProps {
  candles: ChartCandle[];
  indicators: SeriesIndicators;
  selectedStrategy: StrategyResult | null;
  allStrategies: StrategyResult[];
  timeframe: string;
  onTimeframeChange: (tf: string) => void;
  highlightIndex?: number | null;
}

function ObservatoryChart({
  candles,
  indicators,
  selectedStrategy,
  allStrategies,
  timeframe,
  onTimeframeChange,
  highlightIndex,
}: ObservatoryChartProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [overlayMode, setOverlayMode] = useState<'SELECTED' | 'ALL'>('SELECTED');
  const [showLayerMenu, setShowLayerMenu] = useState(false);

  const [layers, setLayers] = useState({
    candles: true,
    volume: true,
    regions: true,
    events: true,
    ema20: false,
    ema50: false,
    ema200: false,
    vwap: false,
    bollinger: false,
    supertrend: false,
    orb: false,
  });

  const n = candles.length;
  const chartWidth = 840;
  const priceChartHeight = 250;
  const volumeHeight = 50;
  const subpanelHeight = 65;
  const subpanelGap = 16;

  const strategyOverlays = selectedStrategy?.visualization?.overlays || [];
  const isEMA20Active = layers.ema20 || strategyOverlays.includes('ema20');
  const isEMA50Active = layers.ema50 || strategyOverlays.includes('ema50');
  const isEMA200Active = layers.ema200 || strategyOverlays.includes('ema200');
  const isVWAPActive = layers.vwap || strategyOverlays.includes('vwap');
  const isBollingerActive = layers.bollinger || strategyOverlays.includes('bb_upper') || strategyOverlays.includes('bb_middle');
  const isSupertrendActive = layers.supertrend || strategyOverlays.includes('supertrend_band');
  const isORBActive = layers.orb || strategyOverlays.includes('orb_high') || strategyOverlays.includes('orb_low');
  const isDonchianActive = strategyOverlays.includes('donchian_high') || strategyOverlays.includes('donchian_low');
  const isPDHActive = strategyOverlays.includes('prev_day_high') || strategyOverlays.includes('prev_day_low');
  const isHH20Active = strategyOverlays.includes('highest_high_20');

  const strategySubpanels = selectedStrategy?.visualization?.subpanels || [];
  const isRSISubpanel = strategySubpanels.includes('rsi14');
  const isMACDSubpanel = strategySubpanels.includes('macd');
  const isADXSubpanel = strategySubpanels.includes('adx');
  const isROCSubpanel = strategySubpanels.includes('roc12');
  const isATRSubpanel = strategySubpanels.includes('atr14');
  const isCMFSubpanel = strategySubpanels.includes('cmf20');
  const hasSubpanel = isRSISubpanel || isMACDSubpanel || isADXSubpanel || isROCSubpanel || isATRSubpanel || isCMFSubpanel;

  const totalHeight = priceChartHeight + volumeHeight + (hasSubpanel ? subpanelHeight + subpanelGap : 0) + 20;

  if (n === 0) {
    return (
      <div className="h-80 flex items-center justify-center text-stone-500 font-mono text-xs bg-[#11131a] rounded-2xl border border-stone-800">
        No candle history available for chart rendering
      </div>
    );
  }

  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);
  const minPrice = Math.min(...lows) * 0.998;
  const maxPrice = Math.max(...highs) * 1.002;
  const priceRange = maxPrice - minPrice || 1;
  const maxVolume = Math.max(...candles.map(c => c.volume), 1);

  const candleStep = chartWidth / n;
  const candleWidth = Math.max(1, candleStep * 0.7);

  const getY = (val: number) => priceChartHeight - ((val - minPrice) / priceRange) * priceChartHeight;
  const getVolY = (vol: number) => priceChartHeight + volumeHeight - (vol / maxVolume) * volumeHeight;
  const getSubY = (val: number, minV: number, maxV: number) => {
    const range = maxV - minV || 1;
    return priceChartHeight + volumeHeight + subpanelGap + subpanelHeight - ((val - minV) / range) * subpanelHeight;
  };

  const makeLinePath = (series?: (number | null)[]) => {
    if (!series || series.length === 0) return '';
    let path = '';
    let started = false;
    for (let i = 0; i < Math.min(n, series.length); i++) {
      const v = series[i];
      if (v !== null && v !== undefined && !isNaN(v)) {
        const x = i * candleStep + candleStep / 2;
        const y = getY(v);
        if (!started) {
          path += `M ${x} ${y}`;
          started = true;
        } else {
          path += ` L ${x} ${y}`;
        }
      }
    }
    return path;
  };

  const makeSubpanelPath = (series?: (number | null)[], minV = 0, maxV = 100) => {
    if (!series || series.length === 0) return '';
    let path = '';
    let started = false;
    for (let i = 0; i < Math.min(n, series.length); i++) {
      const v = series[i];
      if (v !== null && v !== undefined && !isNaN(v)) {
        const x = i * candleStep + candleStep / 2;
        const y = getSubY(v, minV, maxV);
        if (!started) {
          path += `M ${x} ${y}`;
          started = true;
        } else {
          path += ` L ${x} ${y}`;
        }
      }
    }
    return path;
  };

  const activeIdx = hoverIndex !== null && hoverIndex >= 0 && hoverIndex < n
    ? hoverIndex
    : (highlightIndex !== undefined && highlightIndex !== null && highlightIndex >= 0 && highlightIndex < n ? highlightIndex : n - 1);
  const activeCandle = candles[activeIdx];

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * chartWidth;
    const idx = Math.min(Math.max(Math.floor(x / candleStep), 0), n - 1);
    setHoverIndex(idx);
  };

  return (
    <div className="bg-[#12131b] border border-stone-800/80 rounded-2xl p-3 flex flex-col gap-2 shadow-2xl">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-stone-800/60 text-xs">
        <div className="flex items-center gap-3">
          <span className="font-mono font-black text-white text-sm">₹{activeCandle.close.toFixed(2)}</span>
          <div className="flex items-center gap-2 text-[10px] font-mono text-stone-400">
            <span>O: ₹{activeCandle.open.toFixed(2)}</span>
            <span>H: ₹{activeCandle.high.toFixed(2)}</span>
            <span>L: ₹{activeCandle.low.toFixed(2)}</span>
            <span>C: ₹{activeCandle.close.toFixed(2)}</span>
            <span>Vol: {activeCandle.volume.toLocaleString()}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-stone-900/80 p-0.5 rounded-lg border border-stone-800 text-[10px] font-mono">
            <button
              onClick={() => setOverlayMode('SELECTED')}
              className={`px-2 py-0.5 rounded transition-all cursor-pointer font-bold ${
                overlayMode === 'SELECTED' ? 'bg-violet-600 text-white' : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              Selected Strategy
            </button>
            <button
              onClick={() => setOverlayMode('ALL')}
              className={`px-2 py-0.5 rounded transition-all cursor-pointer font-bold ${
                overlayMode === 'ALL' ? 'bg-violet-600 text-white' : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              All Strategies
            </button>
          </div>

          <div className="flex items-center gap-1 bg-stone-900/80 p-0.5 rounded-lg border border-stone-800">
            {(['1m', '5m', '15m', '1h', '1D'] as const).map(tf => (
              <button
                key={tf}
                onClick={() => onTimeframeChange(tf)}
                className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded transition-all cursor-pointer ${
                  timeframe === tf ? 'bg-violet-600 text-white shadow-sm' : 'text-stone-400 hover:text-stone-200'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          <div className="relative">
            <button
              onClick={() => setShowLayerMenu(!showLayerMenu)}
              className="p-1 px-2 rounded-lg bg-stone-900 hover:bg-stone-800 border border-stone-700 text-stone-300 text-[10px] font-mono flex items-center gap-1 cursor-pointer"
            >
              <Sliders className="w-3 h-3" />
              <span>Layers</span>
            </button>

            {showLayerMenu && (
              <div className="absolute right-0 top-7 w-48 bg-[#181a24] border border-stone-700 rounded-xl p-2.5 shadow-2xl z-30 space-y-1.5 text-xs font-mono">
                <div className="font-bold text-stone-200 border-b border-stone-700/60 pb-1 text-[11px]">Chart Layers</div>
                {[
                  { key: 'candles', label: 'Candlesticks' },
                  { key: 'volume', label: 'Volume Bars' },
                  { key: 'regions', label: 'Strategy Regions' },
                  { key: 'events', label: 'Activation Markers' },
                  { key: 'ema20', label: 'EMA20 (Cyan)' },
                  { key: 'ema50', label: 'EMA50 (Amber)' },
                  { key: 'ema200', label: 'EMA200 (Purple)' },
                  { key: 'vwap', label: 'VWAP (Magenta)' },
                  { key: 'bollinger', label: 'Bollinger Bands' },
                  { key: 'supertrend', label: 'Supertrend Proxy' },
                  { key: 'orb', label: 'ORB High/Low' },
                ].map(l => (
                  <label key={l.key} className="flex items-center gap-2 text-stone-300 hover:text-white cursor-pointer">
                    <input
                      type="checkbox"
                      checked={(layers as any)[l.key]}
                      onChange={e => setLayers({ ...layers, [l.key]: e.target.checked })}
                      className="rounded border-stone-700 text-violet-600 focus:ring-0"
                    />
                    <span className="text-[10px]">{l.label}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 text-[10px] font-mono text-stone-400 flex-wrap">
        <span className="text-stone-500 font-bold">Active Overlays:</span>
        {isEMA20Active && <span className="flex items-center gap-1 text-cyan-400"><span className="w-2 h-0.5 bg-cyan-400 inline-block" /> EMA20</span>}
        {isEMA50Active && <span className="flex items-center gap-1 text-amber-400"><span className="w-2 h-0.5 bg-amber-400 inline-block" /> EMA50</span>}
        {isEMA200Active && <span className="flex items-center gap-1 text-purple-400"><span className="w-2 h-0.5 bg-purple-400 inline-block" /> EMA200</span>}
        {isVWAPActive && <span className="flex items-center gap-1 text-fuchsia-400"><span className="w-2 h-0.5 bg-fuchsia-400 inline-block" /> VWAP</span>}
        {isBollingerActive && <span className="flex items-center gap-1 text-emerald-400"><span className="w-2 h-0.5 bg-emerald-400 inline-block" /> Bollinger (20, 2σ)</span>}
        {isSupertrendActive && <span className="flex items-center gap-1 text-lime-400"><span className="w-2 h-0.5 bg-lime-400 inline-block" /> Dynamic Support</span>}
        {isORBActive && <span className="flex items-center gap-1 text-yellow-400"><span className="w-2 h-0.5 bg-yellow-400 inline-block" /> ORB Range</span>}
        {isDonchianActive && <span className="flex items-center gap-1 text-yellow-300"><span className="w-2 h-0.5 bg-yellow-300 inline-block" /> Donchian (20)</span>}
        {isPDHActive && <span className="flex items-center gap-1 text-orange-400"><span className="w-2 h-0.5 bg-orange-400 inline-block" /> Prev Day H/L</span>}
        {isHH20Active && <span className="flex items-center gap-1 text-emerald-300"><span className="w-2 h-0.5 bg-emerald-300 inline-block" /> 20-Bar High</span>}
      </div>

      <div className="relative overflow-hidden w-full select-none">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${chartWidth} ${totalHeight}`}
          className="w-full h-auto cursor-crosshair"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="activeZoneGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.02" />
            </linearGradient>
          </defs>

          {[0.2, 0.4, 0.6, 0.8].map(ratio => {
            const y = ratio * priceChartHeight;
            const px = maxPrice - ratio * priceRange;
            return (
              <g key={ratio}>
                <line x1={0} y1={y} x2={chartWidth} y2={y} stroke="#27272a" strokeWidth={0.8} strokeDasharray="3,3" />
                <text x={chartWidth - 4} y={y - 3} fill="#71717a" fontSize={9} textAnchor="end" fontFamily="monospace">
                  ₹{px.toFixed(2)}
                </text>
              </g>
            );
          })}

          {layers.regions && overlayMode === 'SELECTED' && selectedStrategy?.historical_states?.map((hs, i) => {
            if (hs.state !== 'ACTIVE') return null;
            const x = hs.candle_index * candleStep;
            return (
              <rect key={i} x={x} y={0} width={candleStep} height={priceChartHeight} fill="url(#activeZoneGrad)" />
            );
          })}

          {layers.candles && candles.map((c, i) => {
            const x = i * candleStep + candleStep / 2;
            const openY = getY(c.open);
            const closeY = getY(c.close);
            const highY = getY(c.high);
            const lowY = getY(c.low);
            const isBull = c.close >= c.open;
            const bodyTop = Math.min(openY, closeY);
            const bodyHeight = Math.max(1.5, Math.abs(openY - closeY));

            return (
              <g key={i}>
                <line x1={x} y1={highY} x2={x} y2={lowY} stroke={isBull ? '#10b981' : '#f43f5e'} strokeWidth={1} />
                <rect x={x - candleWidth / 2} y={bodyTop} width={candleWidth} height={bodyHeight} fill={isBull ? '#10b981' : '#f43f5e'} rx={0.5} />
              </g>
            );
          })}

          {layers.volume && candles.map((c, i) => {
            const x = i * candleStep + candleStep / 2;
            const vy = getVolY(c.volume);
            const vHeight = priceChartHeight + volumeHeight - vy;
            const isBull = c.close >= c.open;
            return (
              <rect key={`vol-${i}`} x={x - candleWidth / 2} y={vy} width={candleWidth} height={Math.max(1, vHeight)} fill={isBull ? '#10b981' : '#f43f5e'} opacity={0.35} />
            );
          })}

          {isBollingerActive && (
            <>
              <path d={makeLinePath(indicators.bb_upper)} stroke="#10b981" strokeWidth={1} fill="none" strokeDasharray="2,2" />
              <path d={makeLinePath(indicators.bb_middle)} stroke="#34d399" strokeWidth={0.8} fill="none" />
              <path d={makeLinePath(indicators.bb_lower)} stroke="#10b981" strokeWidth={1} fill="none" strokeDasharray="2,2" />
            </>
          )}

          {isDonchianActive && (
            <>
              <path d={makeLinePath(indicators.donchian_high)} stroke="#eab308" strokeWidth={1.2} fill="none" strokeDasharray="3,2" />
              <path d={makeLinePath(indicators.donchian_mid)} stroke="#ca8a04" strokeWidth={0.8} fill="none" strokeDasharray="2,2" />
              <path d={makeLinePath(indicators.donchian_low)} stroke="#eab308" strokeWidth={1.2} fill="none" strokeDasharray="3,2" />
            </>
          )}

          {isPDHActive && (
            <>
              <path d={makeLinePath(indicators.prev_day_high)} stroke="#f59e0b" strokeWidth={1.2} strokeDasharray="4,2" fill="none" />
              <path d={makeLinePath(indicators.prev_day_low)} stroke="#f59e0b" strokeWidth={1.2} strokeDasharray="4,2" fill="none" />
            </>
          )}

          {isHH20Active && indicators.highest_high_20 && (
            <path d={makeLinePath(indicators.highest_high_20)} stroke="#10b981" strokeWidth={1} strokeDasharray="2,2" fill="none" />
          )}

          {isSupertrendActive && indicators.supertrend_band && (
            <path d={makeLinePath(indicators.supertrend_band)} stroke="#a3e635" strokeWidth={1.5} fill="none" strokeDasharray="4,2" />
          )}

          {isORBActive && indicators.orb_high && indicators.orb_low && (
            <>
              <path d={makeLinePath(indicators.orb_high)} stroke="#fbbf24" strokeWidth={1} strokeDasharray="3,3" fill="none" />
              <path d={makeLinePath(indicators.orb_low)} stroke="#fbbf24" strokeWidth={1} strokeDasharray="3,3" fill="none" />
            </>
          )}

          {isEMA20Active && <path d={makeLinePath(indicators.ema20)} stroke="#22d3ee" strokeWidth={1.2} fill="none" />}
          {isEMA50Active && <path d={makeLinePath(indicators.ema50)} stroke="#f59e0b" strokeWidth={1.2} fill="none" />}
          {isEMA200Active && <path d={makeLinePath(indicators.ema200)} stroke="#a855f7" strokeWidth={1.5} fill="none" />}
          {isVWAPActive && <path d={makeLinePath(indicators.vwap)} stroke="#e879f9" strokeWidth={1.4} fill="none" />}

          {layers.events && (overlayMode === 'SELECTED' ? selectedStrategy?.activation_events || [] : allStrategies.flatMap(s => s.activation_events || [])).map((ev, i) => {
            const cx = ev.candle_index * candleStep + candleStep / 2;
            const cy = getY(ev.price);
            if (cx < 0 || cx > chartWidth) return null;
            const markerColor = selectedStrategy?.visualization?.color || '#10b981';

            if (ev.event_type === 'ACTIVATED') {
              return (
                <g key={i} transform={`translate(${cx}, ${cy - 12})`}>
                  <polygon points="0,-4 4,3 -4,3" fill={markerColor} />
                  <circle cx={0} cy={0} r={5} stroke={markerColor} strokeWidth={1.5} fill="none" />
                </g>
              );
            } else if (ev.event_type === 'INVALIDATED') {
              return (
                <g key={i} transform={`translate(${cx}, ${cy + 12})`}>
                  <polygon points="0,4 4,-3 -4,-3" fill="#f43f5e" />
                </g>
              );
            } else {
              return (
                <g key={i} transform={`translate(${cx}, ${cy - 14})`}>
                  <circle cx={0} cy={0} r={4} fill="#f97316" />
                </g>
              );
            }
          })}

          {activeIdx !== null && activeIdx >= 0 && activeIdx < n && (
            <g>
              <line x1={activeIdx * candleStep + candleStep / 2} y1={0} x2={activeIdx * candleStep + candleStep / 2} y2={priceChartHeight + volumeHeight} stroke="#a1a1aa" strokeWidth={0.8} strokeDasharray="2,2" />
              <line x1={0} y1={getY(candles[activeIdx].close)} x2={chartWidth} y2={getY(candles[activeIdx].close)} stroke="#a1a1aa" strokeWidth={0.8} strokeDasharray="2,2" />
            </g>
          )}

          {isRSISubpanel && indicators.rsi14 && (
            <g transform={`translate(0, ${priceChartHeight + volumeHeight + subpanelGap})`}>
              <rect x={0} y={0} width={chartWidth} height={subpanelHeight} fill="#0d0e14" rx={4} stroke="#27272a" strokeWidth={0.8} />
              <line x1={0} y1={getSubY(70, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} x2={chartWidth} y2={getSubY(70, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} stroke="#f43f5e" strokeWidth={0.8} strokeDasharray="2,2" opacity={0.6} />
              <line x1={0} y1={getSubY(50, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} x2={chartWidth} y2={getSubY(50, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} stroke="#71717a" strokeWidth={0.8} strokeDasharray="2,2" opacity={0.4} />
              <line x1={0} y1={getSubY(35, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} x2={chartWidth} y2={getSubY(35, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} stroke="#10b981" strokeWidth={0.8} strokeDasharray="2,2" opacity={0.6} />
              <text x={chartWidth - 4} y={12} fill="#71717a" fontSize={9} textAnchor="end" fontFamily="monospace">RSI(14): {indicators.rsi14[activeIdx]?.toFixed(1) || 'N/A'}</text>
              <path d={makeSubpanelPath(indicators.rsi14, 0, 100)} stroke="#ec4899" strokeWidth={1.5} fill="none" />
            </g>
          )}

          {isADXSubpanel && indicators.adx && (
            <g transform={`translate(0, ${priceChartHeight + volumeHeight + subpanelGap})`}>
              <rect x={0} y={0} width={chartWidth} height={subpanelHeight} fill="#0d0e14" rx={4} stroke="#27272a" strokeWidth={0.8} />
              <line x1={0} y1={getSubY(25, 0, 60) - (priceChartHeight + volumeHeight + subpanelGap)} x2={chartWidth} y2={getSubY(25, 0, 60) - (priceChartHeight + volumeHeight + subpanelGap)} stroke="#06b6d4" strokeWidth={0.8} strokeDasharray="2,2" opacity={0.6} />
              <text x={chartWidth - 4} y={12} fill="#71717a" fontSize={9} textAnchor="end" fontFamily="monospace">ADX(14): {indicators.adx[activeIdx]?.toFixed(1) || 'N/A'}</text>
              <path d={makeSubpanelPath(indicators.adx, 0, 60)} stroke="#06b6d4" strokeWidth={1.5} fill="none" />
              <path d={makeSubpanelPath(indicators.plus_di, 0, 60)} stroke="#10b981" strokeWidth={1} fill="none" />
              <path d={makeSubpanelPath(indicators.minus_di, 0, 60)} stroke="#f43f5e" strokeWidth={1} fill="none" />
            </g>
          )}
        </svg>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Selected Strategy Rule Inspector with Mathematical Basis
// ---------------------------------------------------------------------------
function StrategyRuleInspector({ strategy }: { strategy: StrategyResult }) {
  const [expandedRule, setExpandedRule] = useState<string | null>(null);

  const entryRules = strategy.rule_evaluations.filter(r => r.is_entry_rule);
  const exitRules = strategy.rule_evaluations.filter(r => !r.is_entry_rule);

  return (
    <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-800/60 pb-2">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-black text-sm text-stone-100">{strategy.strategy_name}</span>
            {strategy.version && (
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-stone-900 border border-stone-800 text-stone-400">
                v{strategy.version}
              </span>
            )}
            <StateBadge state={strategy.state} />
          </div>
          <p className="text-xs text-stone-400 mt-1 leading-relaxed">{strategy.description}</p>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between text-xs font-bold text-stone-300 uppercase mb-2">
          <span className="flex items-center gap-1.5 text-emerald-400">
            <TrendingUp className="w-3.5 h-3.5" /> Entry Conditions ({strategy.entry_rules_passing}/{strategy.entry_rules_total} Pass)
          </span>
        </div>
        <div className="space-y-1.5">
          {entryRules.map(rule => {
            const isPass = rule.outcome === 'PASS';
            const isUnavail = rule.outcome === 'UNAVAILABLE';
            const isExpanded = expandedRule === rule.rule_id;

            return (
              <div
                key={rule.rule_id}
                onClick={() => setExpandedRule(isExpanded ? null : rule.rule_id)}
                className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                  isPass
                    ? 'bg-emerald-950/20 border-emerald-800/40 hover:bg-emerald-950/30'
                    : isUnavail
                    ? 'bg-stone-900/40 border-stone-800 hover:bg-stone-900/60'
                    : 'bg-rose-950/20 border-rose-900/30 hover:bg-rose-950/30'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {isPass ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" /> :
                     isUnavail ? <MinusCircle className="w-3.5 h-3.5 text-stone-500 shrink-0" /> :
                     <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />}
                    <span className="font-semibold text-stone-200">{rule.label}</span>
                  </div>
                  <div className="flex items-center gap-2 font-mono text-[11px]">
                    <span className={isPass ? 'text-emerald-400' : isUnavail ? 'text-stone-500' : 'text-rose-400'}>
                      {rule.actual_value_label}
                    </span>
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5 text-stone-500" /> : <ChevronDown className="w-3.5 h-3.5 text-stone-500" />}
                  </div>
                </div>

                {isExpanded && (
                  <div className="mt-2 pt-2 border-t border-stone-800/60 text-[11px] font-mono space-y-1 text-stone-400 bg-stone-950/40 p-2 rounded">
                    <div><strong>Rule ID:</strong> {rule.rule_id}</div>
                    <div><strong>Outcome:</strong> <span className={isPass ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>{rule.outcome}</span></div>
                    {rule.math_detail && (
                      <div><strong>Mathematical Calculation:</strong> <span className="text-violet-300 font-bold">{rule.math_detail}</span></div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase 6: Robustness & Discovery Workstation View
// ---------------------------------------------------------------------------
interface RobustnessWorkstationProps {
  symbol: string;
  strategyId: string;
  timeframe: string;
  onSelectCandidate: (params: Record<string, any>) => void;
  onLaunchChallenge: (backtestData: any) => void;
}

function RobustnessWorkstation({
  symbol,
  strategyId,
  timeframe,
  onSelectCandidate,
  onLaunchChallenge,
}: RobustnessWorkstationProps) {
  const [subTab, setSubTab] = useState<'SWEEP' | 'NEIGHBORHOOD' | 'MULTI_SYMBOL' | 'PERIODS' | 'WALK_FORWARD' | 'LEDGER'>('SWEEP');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Robustness States
  const [sweepResults, setSweepResults] = useState<ParameterSweepItemData[]>([]);
  const [snoopingWarning, setSnoopingWarning] = useState<boolean>(false);
  const [snoopingMessage, setSnoopingMessage] = useState<string>('');
  const [surfaceData, setSurfaceData] = useState<ParameterSurfaceData | null>(null);
  const [neighborhoodData, setNeighborhoodData] = useState<NeighborhoodAnalysisData | null>(null);
  const [multiSymbolData, setMultiSymbolData] = useState<MultiSymbolSummaryData | null>(null);
  const [periodData, setPeriodData] = useState<PeriodRobustnessData | null>(null);
  const [walkForwardData, setWalkForwardData] = useState<WalkForwardSelectionData | null>(null);
  const [experimentRecords, setExperimentRecords] = useState<ResearchExperimentData[]>([]);

  // Selected candidate configuration
  const [candidateParams, setCandidateParams] = useState<Record<string, any>>({ fast_period: 20, slow_period: 50, max_rsi: 70.0 });

  // Run Parameter Sweep & Surface
  const runSweep = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const sweepRes = await fetch(`/api/strategies/research/sweep/${encodeURIComponent(symbol)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy_id: strategyId, timeframe }),
      });
      if (!sweepRes.ok) throw new Error("Parameter sweep execution failed");
      const sweepJson = await sweepRes.json();
      setSweepResults(sweepJson.results || []);
      setSnoopingWarning(Boolean(sweepJson.data_snooping_warning));
      setSnoopingMessage(sweepJson.data_snooping_message || '');

      // Load 2D Surface
      const surfRes = await fetch(`/api/strategies/research/surface/${encodeURIComponent(symbol)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: strategyId,
          param_1_id: 'fast_period',
          param_1_values: [15, 20, 25],
          param_2_id: 'slow_period',
          param_2_values: [40, 50, 60],
          timeframe,
        }),
      });
      if (surfRes.ok) {
        const surfJson = await surfRes.json();
        setSurfaceData(surfJson.surface || null);
      }
    } catch (e: any) {
      setError(e.message || "Failed to execute parameter sweep");
    } finally {
      setIsLoading(false);
    }
  }, [symbol, strategyId, timeframe]);

  // Run Neighborhood Stability
  const runNeighborhood = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/strategies/research/neighborhood/${encodeURIComponent(symbol)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy_id: strategyId, target_params: candidateParams, timeframe }),
      });
      if (!res.ok) throw new Error("Neighborhood analysis failed");
      const data = await res.json();
      setNeighborhoodData(data.analysis || null);
    } catch (e: any) {
      setError(e.message || "Failed to analyze neighborhood");
    } finally {
      setIsLoading(false);
    }
  }, [symbol, strategyId, candidateParams, timeframe]);

  // Run Multi-Symbol Generalization
  const runMultiSymbol = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/strategies/research/multi-symbol`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: strategyId,
          parameters: candidateParams,
          timeframe,
          symbols: ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS', 'TATAMOTORS.NS', 'SBIN.NS'],
        }),
      });
      if (!res.ok) throw new Error("Multi-symbol evaluation failed");
      const data = await res.json();
      setMultiSymbolData(data.summary || null);
    } catch (e: any) {
      setError(e.message || "Failed to evaluate multi-symbol generalization");
    } finally {
      setIsLoading(false);
    }
  }, [strategyId, candidateParams, timeframe]);

  // Run Period Decay
  const runPeriods = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/strategies/research/periods/${encodeURIComponent(symbol)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy_id: strategyId, parameters: candidateParams, timeframe, subperiods: 3 }),
      });
      if (!res.ok) throw new Error("Period analysis failed");
      const data = await res.json();
      setPeriodData(data.summary || null);
    } catch (e: any) {
      setError(e.message || "Failed to evaluate period decay");
    } finally {
      setIsLoading(false);
    }
  }, [symbol, strategyId, candidateParams, timeframe]);

  // Run Purged Walk-Forward Selection
  const runWalkForward = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const grid = [
        { fast_period: 15, slow_period: 40 },
        { fast_period: 20, slow_period: 50 },
        { fast_period: 25, slow_period: 60 },
      ];
      const res = await fetch(`/api/strategies/research/walk-forward-selection/${encodeURIComponent(symbol)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy_id: strategyId, param_grid: grid, timeframe, folds: 3 }),
      });
      if (!res.ok) throw new Error("Walk-forward selection failed");
      const data = await res.json();
      setWalkForwardData(data.result || null);
    } catch (e: any) {
      setError(e.message || "Failed to execute walk-forward selection");
    } finally {
      setIsLoading(false);
    }
  }, [symbol, strategyId, timeframe]);

  // Load Experiments Ledger
  const loadLedger = useCallback(async () => {
    try {
      const res = await fetch('/api/strategies/research/experiments');
      if (res.ok) {
        const data = await res.json();
        setExperimentRecords(data.experiments || []);
      }
    } catch (e) {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (subTab === 'SWEEP') runSweep();
    else if (subTab === 'NEIGHBORHOOD') runNeighborhood();
    else if (subTab === 'MULTI_SYMBOL') runMultiSymbol();
    else if (subTab === 'PERIODS') runPeriods();
    else if (subTab === 'WALK_FORWARD') runWalkForward();
    else if (subTab === 'LEDGER') loadLedger();
  }, [subTab, runSweep, runNeighborhood, runMultiSymbol, runPeriods, runWalkForward, loadLedger]);

  return (
    <div className="space-y-3 font-mono">
      {/* ── Sub-Workstation Navigation & Skeptic Mode Trigger ── */}
      <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-1 overflow-x-auto custom-scrollbar">
          {[
            { id: 'SWEEP', label: 'Parameter Sweep & Surface', icon: Grid },
            { id: 'NEIGHBORHOOD', label: 'Neighborhood Plateaus', icon: Target },
            { id: 'MULTI_SYMBOL', label: 'Multi-Symbol Generalization', icon: Compass },
            { id: 'PERIODS', label: 'Period Decay Diagnostics', icon: History },
            { id: 'WALK_FORWARD', label: 'Purged Walk-Forward', icon: Split },
            { id: 'LEDGER', label: 'Experiment Ledger', icon: Bookmark },
          ].map(t => {
            const Icon = t.icon;
            const isActive = subTab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setSubTab(t.id as any)}
                className={`px-2.5 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all cursor-pointer text-[11px] shrink-0 ${
                  isActive ? 'bg-violet-600 text-white shadow-md' : 'bg-stone-900 text-stone-400 hover:text-stone-200 border border-stone-800'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        {/* Challenge This Strategy (Copilot Skeptic Mode) */}
        <button
          onClick={() => onLaunchChallenge({ strategy_id: strategyId, candidate_params: candidateParams })}
          className="px-3 py-1.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded-lg font-bold flex items-center gap-1.5 text-xs transition-all cursor-pointer shadow-inner"
        >
          <Flame className="w-3.5 h-3.5 text-rose-400" />
          <span>Challenge This Strategy</span>
        </button>
      </div>

      {/* Multiple Testing & Data Snooping Disclosure Banner */}
      {snoopingWarning && (
        <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-600/40 text-amber-300 text-xs flex items-center gap-2.5">
          <AlertOctagon className="w-4 h-4 shrink-0 text-amber-400" />
          <div>
            <strong className="text-amber-200 uppercase">Data Snooping Notice:</strong>{' '}
            <span>{snoopingMessage}</span>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="p-12 bg-[#12131b] border border-stone-800 rounded-2xl flex flex-col items-center justify-center text-stone-400 space-y-3 font-mono">
          <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
          <span className="text-xs">Computing Multi-Dimensional Robustness Analytics…</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-rose-950/30 border border-rose-800/40 rounded-xl text-rose-300 text-xs">
          <AlertTriangle className="w-4 h-4 inline-block mr-2 text-rose-400" />
          {error}
        </div>
      )}

      {/* ── SubTab 1: PARAMETER SWEEP & 2D SURFACE ── */}
      {subTab === 'SWEEP' && !isLoading && (
        <div className="space-y-3">
          {/* 2D Parameter Surface Grid */}
          {surfaceData && (
            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
              <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
                <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
                  <Grid className="w-4 h-4 text-violet-400" /> Parameter Stability Surface ({surfaceData.param_1_name} × {surfaceData.param_2_name})
                </span>
                <span className="text-[10px] text-stone-500">Exposes Net Return % | Sharpe | Drawdown | OOS Return</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 text-xs">
                {surfaceData.cells.map((cell, idx) => (
                  <div
                    key={idx}
                    onClick={() => {
                      const p: Record<string, any> = {};
                      p[surfaceData.param_1_id] = cell.param_1_val;
                      p[surfaceData.param_2_id] = cell.param_2_val;
                      setCandidateParams(p);
                      onSelectCandidate(p);
                    }}
                    className="p-2.5 rounded-lg bg-stone-900/50 border border-stone-800/80 hover:border-violet-500/60 hover:bg-stone-900 cursor-pointer transition-all space-y-1"
                  >
                    <div className="flex items-center justify-between font-bold text-stone-300 text-[10px]">
                      <span>{surfaceData.param_1_id}={cell.param_1_val} | {surfaceData.param_2_id}={cell.param_2_val}</span>
                      <span className={`px-1 rounded text-[9px] ${cell.net_return_pct >= 0 ? 'bg-emerald-950 text-emerald-400' : 'bg-rose-950 text-rose-400'}`}>
                        {cell.overfitting_status}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs font-black">
                      <span className="text-stone-400 font-normal">Net Return:</span>
                      <span className={cell.net_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                        {cell.net_return_pct > 0 ? '+' : ''}{cell.net_return_pct.toFixed(2)}%
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-stone-500">
                      <span>Sharpe: {cell.sharpe_ratio}</span>
                      <span>OOS: {cell.oos_return_pct}%</span>
                      <span>Trades: {cell.total_trades}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Detailed Parameter Sweep Ledger Table */}
          <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
            <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
              <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
                <BarChart3 className="w-4 h-4 text-emerald-400" /> Bounded Parameter Sweep Ledger ({sweepResults.length} Configurations)
              </span>
            </div>

            <div className="overflow-x-auto custom-scrollbar">
              <table className="w-full text-left text-[11px]">
                <thead>
                  <tr className="border-b border-stone-800 text-stone-500 text-[10px] uppercase">
                    <th className="pb-2 font-bold">Parameters</th>
                    <th className="pb-2 font-bold">Trades</th>
                    <th className="pb-2 font-bold">Net Return</th>
                    <th className="pb-2 font-bold">Gross Return</th>
                    <th className="pb-2 font-bold">Sharpe</th>
                    <th className="pb-2 font-bold">Max DD</th>
                    <th className="pb-2 font-bold">IS / OOS Return</th>
                    <th className="pb-2 font-bold">3x Friction</th>
                    <th className="pb-2 font-bold">Classification</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-800/60">
                  {sweepResults.map(item => (
                    <tr
                      key={item.configuration_id}
                      onClick={() => {
                        setCandidateParams(item.parameters);
                        onSelectCandidate(item.parameters);
                      }}
                      className="hover:bg-stone-900/50 cursor-pointer transition-all"
                    >
                      <td className="py-2.5 font-bold text-stone-200">
                        {Object.entries(item.parameters).map(([k, v]) => `${k}=${v}`).join(', ')}
                      </td>
                      <td className="py-2.5 text-stone-400">{item.total_trades}</td>
                      <td className={`py-2.5 font-bold ${item.net_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {item.net_return_pct > 0 ? '+' : ''}{item.net_return_pct.toFixed(2)}%
                      </td>
                      <td className="py-2.5 text-stone-400">{item.gross_return_pct.toFixed(2)}%</td>
                      <td className="py-2.5 text-stone-300 font-bold">{item.sharpe_ratio}</td>
                      <td className="py-2.5 text-rose-400">{item.max_drawdown_pct}%</td>
                      <td className="py-2.5 text-stone-400 text-[10px]">
                        IS: {item.is_return_pct}% | OOS: {item.oos_return_pct}%
                      </td>
                      <td className="py-2.5 text-stone-400">{item.triple_friction_return_pct}%</td>
                      <td className="py-2.5">
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                          item.robustness_classification === 'ROBUST_CANDIDATE' ? 'bg-emerald-950 text-emerald-300 border border-emerald-600/40' :
                          item.robustness_classification === 'OVERFIT' ? 'bg-rose-950 text-rose-300 border border-rose-600/40' :
                          'bg-amber-950 text-amber-300 border border-amber-600/40'
                        }`}>
                          {item.robustness_classification}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── SubTab 2: NEIGHBORHOOD PLATEAUS ── */}
      {subTab === 'NEIGHBORHOOD' && neighborhoodData && !isLoading && (
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
          <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
            <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
              <Target className="w-4 h-4 text-amber-400" /> Neighborhood Perturbation Analysis (Plateau vs Cliff)
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
              neighborhoodData.stability_classification === 'STABLE_PLATEAU' ? 'bg-emerald-950 text-emerald-300 border border-emerald-600/50' :
              'bg-rose-950 text-rose-300 border border-rose-600/50'
            }`}>
              {neighborhoodData.stability_classification} (Plateau Score: {neighborhoodData.plateau_score}%)
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Candidate Return</div>
              <div className="text-lg font-black text-white mt-0.5">{neighborhoodData.candidate_net_return_pct}%</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Mean Neighbor Return</div>
              <div className="text-lg font-black text-amber-400 mt-0.5">{neighborhoodData.mean_neighbor_return_pct}%</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Return Std Deviation</div>
              <div className="text-lg font-black text-stone-300 mt-0.5">{neighborhoodData.return_standard_deviation}%</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Neighbors Tested</div>
              <div className="text-lg font-black text-violet-400 mt-0.5">{neighborhoodData.neighbor_count}</div>
            </div>
          </div>

          <div className="space-y-1.5 pt-2">
            <div className="text-[11px] font-bold text-stone-400">Adjacent Perturbations (+/- 1 Parameter Step):</div>
            {neighborhoodData.neighbors.map((n, idx) => (
              <div key={idx} className="p-2 rounded bg-stone-900/30 border border-stone-800/60 flex items-center justify-between text-xs">
                <span className="text-stone-300">{Object.entries(n.parameters).map(([k, v]) => `${k}=${v}`).join(', ')}</span>
                <div className="flex items-center gap-3">
                  <span className={n.net_return_pct >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                    {n.net_return_pct > 0 ? '+' : ''}{n.net_return_pct}%
                  </span>
                  <span className="text-stone-500 text-[10px]">{n.total_trades} trades</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── SubTab 3: MULTI-SYMBOL GENERALIZATION ── */}
      {subTab === 'MULTI_SYMBOL' && multiSymbolData && !isLoading && (
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
          <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
            <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
              <Compass className="w-4 h-4 text-cyan-400" /> Multi-Symbol Generalization ({multiSymbolData.symbol_count} Symbols)
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-violet-950 border border-violet-600/50 text-violet-300">
              {multiSymbolData.generalization_classification}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Median Symbol Return</div>
              <div className="text-lg font-black text-white mt-0.5">{multiSymbolData.median_net_return_pct}%</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Dispersion (IQR)</div>
              <div className="text-lg font-black text-amber-400 mt-0.5">{multiSymbolData.dispersion_iqr_pct}%</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Best Symbol</div>
              <div className="text-sm font-black text-emerald-400 mt-0.5 truncate">{multiSymbolData.best_symbol}</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Profitable Symbols</div>
              <div className="text-lg font-black text-violet-400 mt-0.5">{multiSymbolData.profitable_symbols_count}/{multiSymbolData.symbol_count}</div>
            </div>
          </div>

          <div className="space-y-1.5 pt-2">
            {Object.entries(multiSymbolData.symbol_breakdown).map(([sym, item]) => (
              <div key={sym} className="p-2 rounded bg-stone-900/40 border border-stone-800/60 flex items-center justify-between text-xs">
                <span className="font-bold text-stone-200">{sym}</span>
                <div className="flex items-center gap-4">
                  <span className={item.net_return_pct >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                    {item.net_return_pct > 0 ? '+' : ''}{item.net_return_pct}%
                  </span>
                  <span className="text-stone-400 text-[10px]">Sharpe: {item.sharpe_ratio}</span>
                  <span className="text-stone-500 text-[10px]">{item.total_trades} trades</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── SubTab 4: PERIOD DECAY ── */}
      {subTab === 'PERIODS' && periodData && !isLoading && (
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
          <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
            <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
              <History className="w-4 h-4 text-emerald-400" /> Chronological Subperiod Performance & Decay
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
              periodData.decay_status === 'STABLE' ? 'bg-emerald-950 text-emerald-300 border border-emerald-600/50' :
              periodData.decay_status === 'IMPROVING' ? 'bg-sky-950 text-sky-300 border border-sky-600/50' :
              'bg-rose-950 text-rose-300 border border-rose-600/50'
            }`}>
              DECAY STATUS: {periodData.decay_status}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
            {periodData.subperiod_results.map(sub => (
              <div key={sub.period_index} className="p-3 rounded-lg bg-stone-900/40 border border-stone-800 space-y-1">
                <div className="font-bold text-stone-300 flex items-center justify-between text-xs">
                  <span>{sub.period_name}</span>
                  <span className={sub.net_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                    {sub.net_return_pct > 0 ? '+' : ''}{sub.net_return_pct}%
                  </span>
                </div>
                <div className="text-[10px] text-stone-500 flex items-center justify-between pt-1">
                  <span>Trades: {sub.total_trades}</span>
                  <span>Win Rate: {sub.win_rate_pct}%</span>
                  <span>Sharpe: {sub.sharpe_ratio}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── SubTab 5: PURGED WALK-FORWARD ── */}
      {subTab === 'WALK_FORWARD' && walkForwardData && !isLoading && (
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
          <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
            <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
              <Split className="w-4 h-4 text-violet-400" /> Purged Walk-Forward Parameter Optimization
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-violet-950 border border-violet-600/50 text-violet-300">
              {walkForwardData.walk_forward_classification}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Cumulative OOS Return</div>
              <div className="text-lg font-black text-emerald-400 mt-0.5">{walkForwardData.cumulative_oos_return_pct}%</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">OOS Sharpe Ratio</div>
              <div className="text-lg font-black text-cyan-400 mt-0.5">{walkForwardData.cumulative_oos_sharpe}</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Parameter Stability</div>
              <div className="text-lg font-black text-white mt-0.5">{walkForwardData.parameter_stability_pct}%</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Folds Completed</div>
              <div className="text-lg font-black text-violet-400 mt-0.5">{walkForwardData.fold_count} Folds</div>
            </div>
          </div>
        </div>
      )}

      {/* ── SubTab 6: EXPERIMENT LEDGER ── */}
      {subTab === 'LEDGER' && (
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
          <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
            <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
              <Bookmark className="w-4 h-4 text-amber-400" /> Immutable Research Experiment Ledger ({experimentRecords.length} Records)
            </span>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto custom-scrollbar">
            {experimentRecords.length > 0 ? (
              experimentRecords.map(rec => (
                <div key={rec.experiment_id} className="p-2.5 rounded-lg bg-stone-900/40 border border-stone-800 flex items-center justify-between text-xs">
                  <div>
                    <div className="font-bold text-stone-200">{rec.experiment_id} ({rec.strategy_id})</div>
                    <div className="text-[10px] text-stone-500">
                      {Object.entries(rec.parameters).map(([k, v]) => `${k}=${v}`).join(', ')} · {rec.created_at.slice(0, 10)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={rec.net_return_pct >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                      {rec.net_return_pct > 0 ? '+' : ''}{rec.net_return_pct}%
                    </div>
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-stone-800 text-stone-400">
                      {rec.workflow_state}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-6 text-center text-stone-500 text-xs">No experiments recorded yet. Complete sweeps or backtests to log records.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Historical Research Workstation Component (Phase 4)
// ---------------------------------------------------------------------------
interface ResearchWorkstationProps {
  summary: StrategyResearchSummaryData | null;
  isLoading: boolean;
  error: string | null;
  selectedObsId: string | null;
  onSelectObsId: (obsId: string, candleIndex: number) => void;
  onRefresh: () => void;
}

function ResearchWorkstation({
  summary,
  isLoading,
  error,
  selectedObsId,
  onSelectObsId,
  onRefresh,
}: ResearchWorkstationProps) {
  const [regimeFilter, setRegimeFilter] = useState<string>('ALL');

  if (isLoading) {
    return (
      <div className="p-12 bg-[#12131b] border border-stone-800 rounded-2xl flex flex-col items-center justify-center text-stone-400 space-y-3 font-mono">
        <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
        <span className="text-xs">Executing Point-in-Time Historical Research Replay…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-rose-950/20 border border-rose-800/40 rounded-2xl text-rose-300 font-mono text-xs space-y-2">
        <div className="flex items-center gap-2 font-bold text-rose-200">
          <AlertTriangle className="w-4 h-4 text-rose-400" />
          <span>Research Replay Failed</span>
        </div>
        <p>{error}</p>
        <button
          onClick={onRefresh}
          className="px-3 py-1 bg-stone-900 hover:bg-stone-800 border border-stone-700 text-stone-200 rounded text-[11px] font-bold cursor-pointer"
        >
          Retry Replay
        </button>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="p-8 bg-[#12131b] border border-stone-800 rounded-2xl text-center text-stone-500 font-mono text-xs">
        No research summary generated yet. Click 'Replay' above.
      </div>
    );
  }

  const isLowSample = summary.total_activations < 5;

  const filteredObservations = summary.observations.filter(obs => {
    if (regimeFilter !== 'ALL' && obs.regime_at_activation !== regimeFilter) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-2.5">
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3">
          <div className="text-[10px] font-mono text-stone-500 uppercase font-bold">Total Activations</div>
          <div className="text-xl font-black text-white font-mono mt-1">{summary.total_activations}</div>
          <div className="text-[10px] font-mono text-stone-400 mt-0.5">{summary.activation_frequency_pct}% of candles</div>
        </div>

        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3">
          <div className="text-[10px] font-mono text-stone-500 uppercase font-bold">Active Episodes</div>
          <div className="text-xl font-black text-violet-400 font-mono mt-1">{summary.active_episodes_count}</div>
          <div className="text-[10px] font-mono text-stone-400 mt-0.5">Avg: {summary.avg_episode_duration_candles} bars</div>
        </div>

        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3">
          <div className="text-[10px] font-mono text-stone-500 uppercase font-bold">Median Duration</div>
          <div className="text-xl font-black text-amber-400 font-mono mt-1">{summary.median_episode_duration_candles} <span className="text-xs font-normal text-stone-400">bars</span></div>
          <div className="text-[10px] font-mono text-stone-400 mt-0.5">Continuous hold</div>
        </div>

        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3">
          <div className="text-[10px] font-mono text-stone-500 uppercase font-bold">Invalidation Freq</div>
          <div className="text-xl font-black text-rose-400 font-mono mt-1">{summary.invalidation_frequency_pct}%</div>
          <div className="text-[10px] font-mono text-stone-400 mt-0.5">{summary.invalidation_count} episodes</div>
        </div>

        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3 col-span-2 sm:col-span-4 lg:col-span-1 flex flex-col justify-between">
          <div className="text-[10px] font-mono text-stone-500 uppercase font-bold">Sample Validity</div>
          <div className="mt-1">
            {isLowSample ? (
              <span className="px-2 py-0.5 rounded bg-amber-950/60 border border-amber-600/50 text-amber-300 font-mono font-bold text-xs inline-flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> LOW SAMPLE (N&lt;5)
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-600/50 text-emerald-300 font-mono font-bold text-xs inline-flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> VALID DATASET
              </span>
            )}
          </div>
          <div className="text-[10px] font-mono text-stone-500 mt-0.5">{summary.total_candles_analyzed} candles</div>
        </div>
      </div>

      <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-800/60 pb-2">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-violet-400" />
            <span className="font-bold text-xs text-stone-200 uppercase font-mono tracking-wider">
              Forward Observation Windows (Empirical Outcome Distributions)
            </span>
          </div>
        </div>

        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-stone-800 text-stone-500 text-[10px] uppercase">
                <th className="pb-2 font-bold">Horizon</th>
                <th className="pb-2 font-bold">Sample (N)</th>
                <th className="pb-2 font-bold">Median Return</th>
                <th className="pb-2 font-bold">Mean Return</th>
                <th className="pb-2 font-bold">Positive Freq %</th>
                <th className="pb-2 font-bold">Median MAE</th>
                <th className="pb-2 font-bold">Median MFE</th>
                <th className="pb-2 font-bold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-800/60">
              {['1', '3', '5', '10', '20'].map(h => {
                const hs = summary.horizons_summary[h];
                if (!hs) return null;
                const isPos = hs.median_return_pct !== null && hs.median_return_pct !== undefined && hs.median_return_pct > 0;
                const isNeg = hs.median_return_pct !== null && hs.median_return_pct !== undefined && hs.median_return_pct < 0;

                return (
                  <tr key={h} className="hover:bg-stone-900/40 transition-all">
                    <td className="py-2.5 font-black text-stone-200">{h} {h === '1' ? 'Candle' : 'Candles'}</td>
                    <td className="py-2.5 text-stone-400">{hs.sample_count}</td>
                    <td className={`py-2.5 font-bold ${isPos ? 'text-emerald-400' : isNeg ? 'text-rose-400' : 'text-stone-400'}`}>
                      {hs.median_return_pct !== null ? `${hs.median_return_pct > 0 ? '+' : ''}${hs.median_return_pct.toFixed(2)}%` : '---'}
                    </td>
                    <td className="py-2.5 text-stone-300">{hs.mean_return_pct !== null ? `${hs.mean_return_pct > 0 ? '+' : ''}${hs.mean_return_pct.toFixed(2)}%` : '---'}</td>
                    <td className="py-2.5 text-stone-300">{hs.positive_return_pct !== null ? `${hs.positive_return_pct.toFixed(1)}%` : '---'}</td>
                    <td className="py-2.5 text-orange-400 font-medium">{hs.median_mae_pct !== null ? `${hs.median_mae_pct.toFixed(2)}%` : '---'}</td>
                    <td className="py-2.5 text-emerald-300 font-medium">{hs.median_mfe_pct !== null ? `${hs.median_mfe_pct.toFixed(2)}%` : '---'}</td>
                    <td className="py-2.5">
                      {hs.is_low_sample ? (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950/40 border border-amber-700/50 text-amber-300">LOW SAMPLE</span>
                      ) : (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/40 border border-emerald-700/50 text-emerald-300">COMPLETE</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Formal Event-Driven Backtesting Workstation (Phase 5)
// ---------------------------------------------------------------------------
interface BacktestWorkstationProps {
  result: BacktestResultData | null;
  isLoading: boolean;
  error: string | null;
  onRunBacktest: (params: any) => void;
}

function BacktestWorkstation({
  result,
  isLoading,
  error,
  onRunBacktest,
}: BacktestWorkstationProps) {
  const [initialCapital, setInitialCapital] = useState<number>(1000000);
  const [positionSize, setPositionSize] = useState<number>(0.10);
  const [targetAtr, setTargetAtr] = useState<number>(2.0);
  const [stopAtr, setStopAtr] = useState<number>(1.0);
  const [selectedTrade, setSelectedTrade] = useState<BacktestTradeData | null>(null);

  if (isLoading) {
    return (
      <div className="p-12 bg-[#12131b] border border-stone-800 rounded-2xl flex flex-col items-center justify-center text-stone-400 space-y-3 font-mono">
        <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
        <span className="text-xs">Running Event-Driven Backtest Simulation…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-rose-950/20 border border-rose-800/40 rounded-2xl text-rose-300 font-mono text-xs space-y-2">
        <div className="flex items-center gap-2 font-bold text-rose-200">
          <AlertTriangle className="w-4 h-4 text-rose-400" />
          <span>Backtest Execution Failed</span>
        </div>
        <p>{error}</p>
      </div>
    );
  }

  const wf = result?.walk_forward;
  const cs = result?.cost_sensitivity;

  return (
    <div className="space-y-4">
      <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-stone-500 font-bold">Capital:</span>
            <input
              type="number"
              value={initialCapital}
              onChange={e => setInitialCapital(Number(e.target.value))}
              className="w-24 px-2 py-1 bg-stone-900 border border-stone-800 rounded text-stone-200 focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-stone-500 font-bold">Risk:</span>
            <input
              type="number"
              step="0.05"
              value={positionSize}
              onChange={e => setPositionSize(Number(e.target.value))}
              className="w-16 px-2 py-1 bg-stone-900 border border-stone-800 rounded text-stone-200 focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-stone-500 font-bold">Target ATR:</span>
            <input
              type="number"
              step="0.5"
              value={targetAtr}
              onChange={e => setTargetAtr(Number(e.target.value))}
              className="w-16 px-2 py-1 bg-stone-900 border border-stone-800 rounded text-stone-200 focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-stone-500 font-bold">Stop ATR:</span>
            <input
              type="number"
              step="0.5"
              value={stopAtr}
              onChange={e => setStopAtr(Number(e.target.value))}
              className="w-16 px-2 py-1 bg-stone-900 border border-stone-800 rounded text-stone-200 focus:outline-none"
            />
          </div>
        </div>

        <button
          onClick={() => onRunBacktest({ initialCapital, positionSize, targetAtr, stopAtr })}
          className="px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white rounded-lg font-bold flex items-center gap-1.5 cursor-pointer shadow-md"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Execute Simulation</span>
        </button>
      </div>

      {result && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2.5">
            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3">
              <div className="text-[10px] font-mono text-stone-500 uppercase font-bold">Total Net Return</div>
              <div className={`text-xl font-black font-mono mt-1 ${result.total_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {result.total_return_pct > 0 ? '+' : ''}{result.total_return_pct.toFixed(2)}%
              </div>
              <div className="text-[10px] font-mono text-stone-400 mt-0.5">Gross: {result.grossReturnPct.toFixed(2)}%</div>
            </div>

            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3">
              <div className="text-[10px] font-mono text-stone-500 uppercase font-bold">Net Profit</div>
              <div className={`text-xl font-black font-mono mt-1 ${result.netProfit >= 0 ? 'text-white' : 'text-rose-400'}`}>
                ₹{result.netProfit.toLocaleString()}
              </div>
            </div>

            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3">
              <div className="text-[10px] font-mono text-stone-500 uppercase font-bold">Win Rate</div>
              <div className="text-xl font-black text-amber-400 font-mono mt-1">{result.win_rate_pct}%</div>
            </div>

            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3">
              <div className="text-[10px] font-mono text-stone-500 uppercase font-bold">Profit Factor</div>
              <div className="text-xl font-black text-violet-400 font-mono mt-1">{result.profit_factor}</div>
            </div>

            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3">
              <div className="text-[10px] font-mono text-stone-500 uppercase font-bold">Sharpe Ratio</div>
              <div className="text-xl font-black text-cyan-400 font-mono mt-1">{result.sharpe_ratio}</div>
            </div>

            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3">
              <div className="text-[10px] font-mono text-stone-500 uppercase font-bold">Max Drawdown</div>
              <div className="text-xl font-black text-rose-400 font-mono mt-1">{result.max_drawdown_pct}%</div>
            </div>
          </div>

          {wf && (
            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3 font-mono">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-800/60 pb-2">
                <span className="font-bold text-xs text-stone-200 uppercase tracking-wider">
                  Walk-Forward Validation (70% In-Sample / 30% Out-Of-Sample)
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                  wf.overfitting_status === 'ACCEPTABLE' ? 'bg-emerald-950/60 border-emerald-600/50 text-emerald-300' :
                  'bg-rose-950/60 border-rose-600/50 text-rose-300'
                }`}>
                  {wf.overfitting_status}
                </span>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Real Conversational Strategy Copilot
// ---------------------------------------------------------------------------
interface StrategyCopilotProps {
  symbol: string;
  selectedStrategy: StrategyResult | null;
  allStrategies: StrategyResult[];
  regime: MarketRegimeData | null;
  confluence: ConfluenceData | null;
  timeframe: string;
  researchSummary?: StrategyResearchSummaryData | null;
  backtestResult?: BacktestResultData | null;
}

function StrategyCopilotChat({
  symbol,
  selectedStrategy,
  allStrategies,
  regime,
  confluence,
  timeframe,
  researchSummary,
  backtestResult,
}: StrategyCopilotProps) {
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
  }, [symbol, selectedStrategy?.strategy_id, timeframe]);

  const quickChips = [
    'CHALLENGE THIS STRATEGY',
    'Which parameter region is stable?',
    'How much did OOS performance degrade?',
    'Is this strategy dependent on one symbol?',
  ];

  const handleSend = async (userText: string) => {
    if (!userText.trim() || !selectedStrategy || isLoading) return;
    const textToSend = userText.trim();
    const isSkeptic = textToSend.toUpperCase().includes('CHALLENGE');
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: textToSend }]);
    setIsLoading(true);

    try {
      const res = await fetch('/api/strategies/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          strategy_id: selectedStrategy.strategy_id,
          evaluation_result: selectedStrategy,
          research_summary: researchSummary || null,
          backtest_result: backtestResult || null,
          user_message: textToSend,
          chat_history: messages.slice(-4),
          is_skeptic_mode: isSkeptic,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: data.reply || 'No response from copilot.',
        evidence_cited: data.evidence_cited || [],
      }]);
    } catch (e: any) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: `Copilot temporarily unavailable: ${e.message}`,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="bg-[#12131b] border border-stone-800/80 rounded-xl flex flex-col h-full overflow-hidden shadow-2xl">
      <div className="p-3 border-b border-stone-800/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-violet-600/20 border border-violet-500/30 flex items-center justify-center text-violet-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold text-white flex items-center gap-1.5">
              <span>Strategy Copilot</span>
              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-violet-950 border border-violet-700/50 text-violet-300">
                DISCOVERY LAB
              </span>
            </div>
            <div className="text-[10px] text-stone-400 font-mono">
              Grounded in verified rules & empirical research
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 p-3 overflow-y-auto custom-scrollbar space-y-3 min-h-[160px] max-h-[300px]">
        {messages.length === 0 ? (
          <div className="text-center py-4 space-y-2">
            <MessageSquare className="w-8 h-8 text-stone-600 mx-auto" />
            <p className="text-xs text-stone-400 font-medium">
              Ask about parameter stability, OOS degradation, or challenge this strategy.
            </p>
            <div className="flex flex-wrap gap-1.5 justify-center pt-2">
              {quickChips.map(chip => (
                <button
                  key={chip}
                  onClick={() => handleSend(chip)}
                  className="text-[10px] font-mono px-2 py-1 rounded-md bg-stone-900/80 border border-stone-800 text-stone-300 hover:text-white hover:border-violet-500/50 transition-all cursor-pointer"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div
                className={`p-2.5 rounded-xl text-xs leading-relaxed max-w-[92%] ${
                  m.role === 'user'
                    ? 'bg-violet-600 text-white rounded-br-none'
                    : 'bg-[#181a24] border border-stone-800 text-stone-200 rounded-bl-none'
                }`}
              >
                <div className="whitespace-pre-wrap">{m.text}</div>
                {m.evidence_cited && m.evidence_cited.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-stone-700/50 text-[10px] font-mono text-violet-300">
                    <span className="text-stone-400">Cited Evidence: </span>
                    {m.evidence_cited.join(' · ')}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        {isLoading && (
          <div className="flex items-center gap-2 text-xs text-violet-400 font-mono">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>Analyzing verified evidence…</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-2 border-t border-stone-800/60 bg-stone-950/40">
        <form
          onSubmit={e => {
            e.preventDefault();
            handleSend(input);
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ask or Challenge this strategy…"
            className="flex-1 bg-stone-900 border border-stone-800 rounded-lg px-2.5 py-1.5 text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-violet-500 font-mono"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="p-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white rounded-lg transition-all cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Master Strategy Lab Component (Phase 6 Discovery & Robustness Lab)
// ---------------------------------------------------------------------------
export const StrategyLabPage: React.FC<StrategyLabPageProps> = ({
  stocks,
  selectedSymbol,
  onSelectSymbol,
}) => {
  const [symbol, setSymbol] = useState<string>(selectedSymbol || 'RELIANCE.NS');
  const [timeframe, setTimeframe] = useState<string>('5m');
  const [activeTab, setActiveTab] = useState<'OBSERVATORY' | 'RESEARCH' | 'BACKTEST' | 'ROBUSTNESS'>('OBSERVATORY');

  const [observatoryData, setObservatoryData] = useState<ObservatoryData | null>(null);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [researchSummary, setResearchSummary] = useState<StrategyResearchSummaryData | null>(null);
  const [isLoadingResearch, setIsLoadingResearch] = useState<boolean>(false);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [selectedObsId, setSelectedObsId] = useState<string | null>(null);

  const [backtestResult, setBacktestResult] = useState<BacktestResultData | null>(null);
  const [isLoadingBacktest, setIsLoadingBacktest] = useState<boolean>(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);

  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [stateFilter, setStateFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const activeReqId = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const currentStock = stocks.find(s => s.symbol === symbol) || stocks[0];

  const handleEvaluate = useCallback(async (symToEval = symbol, tfToEval = timeframe) => {
    const reqId = ++activeReqId.current;
    if (abortControllerRef.current) abortControllerRef.current.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsEvaluating(true);
    setError(null);
    try {
      const res = await fetch(`/api/strategies/evaluate/${encodeURIComponent(symToEval)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_live_feed: true, timeframe: tfToEval }),
        signal: controller.signal,
      });
      if (reqId !== activeReqId.current) return;
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data: ObservatoryData = await res.json();
      if (reqId !== activeReqId.current) return;
      setObservatoryData(data);

      if (data.strategies && data.strategies.length > 0) {
        setSelectedStrategyId(prev => {
          if (prev && data.strategies.some(s => s.strategy_id === prev)) return prev;
          const firstActive = data.strategies.find(s => s.state === 'ACTIVE') || data.strategies[0];
          return firstActive.strategy_id;
        });
      }
    } catch (e: any) {
      if (e.name === 'AbortError') return;
      if (reqId === activeReqId.current) setError(e.message || 'Evaluation failed');
    } finally {
      if (reqId === activeReqId.current) setIsEvaluating(false);
    }
  }, [symbol, timeframe]);

  const handleRunResearch = useCallback(async (stratId = selectedStrategyId, sym = symbol, tf = timeframe) => {
    if (!stratId) return;
    setIsLoadingResearch(true);
    setResearchError(null);
    try {
      const res = await fetch(`/api/strategies/research/${encodeURIComponent(sym)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: stratId,
          timeframe: tf,
          candles: observatoryData?.candles || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data: StrategyResearchSummaryData = await res.json();
      setResearchSummary(data);
    } catch (e: any) {
      setResearchError(e.message || 'Failed to run historical research');
    } finally {
      setIsLoadingResearch(false);
    }
  }, [selectedStrategyId, symbol, timeframe, observatoryData?.candles]);

  const handleRunBacktest = useCallback(async (params: any = {}) => {
    if (!selectedStrategyId) return;
    setIsLoadingBacktest(true);
    setBacktestError(null);
    try {
      const res = await fetch(`/api/strategies/backtest/${encodeURIComponent(symbol)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: selectedStrategyId,
          timeframe,
          initial_capital: params.initialCapital || 1000000,
          position_size_value: params.positionSize || 0.10,
          target_atr_multiple: params.targetAtr || 2.0,
          stop_atr_multiple: params.stopAtr || 1.0,
          candles: observatoryData?.candles || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data: BacktestResultData = await res.json();
      setBacktestResult(data);
    } catch (e: any) {
      setBacktestError(e.message || 'Failed to execute backtest');
    } finally {
      setIsLoadingBacktest(false);
    }
  }, [selectedStrategyId, symbol, timeframe, observatoryData?.candles]);

  useEffect(() => {
    handleEvaluate(symbol, timeframe);
  }, [symbol, timeframe]);

  useEffect(() => {
    if (activeTab === 'RESEARCH' && selectedStrategyId) {
      handleRunResearch(selectedStrategyId, symbol, timeframe);
    } else if (activeTab === 'BACKTEST' && selectedStrategyId) {
      handleRunBacktest();
    }
  }, [activeTab, selectedStrategyId, symbol, timeframe]);

  const selectedStrategy = observatoryData?.strategies?.find(s => s.strategy_id === selectedStrategyId) || null;

  const availableCategories = useMemo(() => {
    if (!observatoryData?.strategies) return ['ALL'];
    const cats = new Set<string>();
    observatoryData.strategies.forEach(s => {
      if (s.category) cats.add(s.category);
    });
    return ['ALL', ...Array.from(cats)];
  }, [observatoryData?.strategies]);

  const filteredStrategies = useMemo(() => {
    if (!observatoryData?.strategies) return [];
    return observatoryData.strategies.filter(s => {
      if (categoryFilter !== 'ALL' && s.category !== categoryFilter) return false;
      if (stateFilter !== 'ALL' && s.state !== stateFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = s.strategy_name.toLowerCase().includes(q) || (s.short_name && s.short_name.toLowerCase().includes(q));
        const matchesDesc = s.description.toLowerCase().includes(q);
        const matchesTag = s.tags && s.tags.some(t => t.toLowerCase().includes(q));
        if (!matchesName && !matchesDesc && !matchesTag) return false;
      }
      return true;
    });
  }, [observatoryData?.strategies, categoryFilter, stateFilter, searchQuery]);

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-175px)] overflow-y-auto custom-scrollbar p-3 space-y-3 bg-[#0a0b10]">
      {/* ── Top Header ── */}
      <div className="bg-[#12131b] border border-stone-800/80 rounded-2xl p-3 flex flex-wrap items-center justify-between gap-3 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-600/20 border border-violet-500/40 flex items-center justify-center text-violet-400 font-black shadow-inner">
            <FlaskConical className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-black text-sm text-white tracking-wide font-mono">{symbol}</span>
              <span className="text-xs text-stone-400 font-semibold hidden sm:inline">{currentStock?.name}</span>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono mt-0.5 flex-wrap">
              <span className="text-stone-100 font-bold">₹{currentStock?.price?.toFixed(2) || '---'}</span>
              <span className={currentStock?.change && currentStock.change >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                {currentStock?.change && currentStock.change >= 0 ? '+' : ''}{currentStock?.change?.toFixed(2)} ({currentStock?.changePercent?.toFixed(2)}%)
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto custom-scrollbar max-w-md">
          {QUICK_SYMBOLS.map(sym => (
            <button
              key={sym}
              onClick={() => { setSymbol(sym); onSelectSymbol?.(sym); }}
              className={`px-2 py-1 text-[10px] font-mono font-bold rounded-lg border transition-all cursor-pointer shrink-0 ${
                symbol === sym
                  ? 'bg-violet-600 text-white border-violet-400 shadow-md'
                  : 'bg-stone-900/60 text-stone-400 border-stone-800 hover:text-stone-200 hover:bg-stone-800'
              }`}
            >
              {sym.replace('.NS', '')}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center bg-stone-900 p-0.5 rounded-xl border border-stone-800 font-mono text-xs">
            <button
              onClick={() => setActiveTab('OBSERVATORY')}
              className={`px-2.5 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'OBSERVATORY' ? 'bg-violet-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Observatory</span>
            </button>
            <button
              onClick={() => setActiveTab('RESEARCH')}
              className={`px-2.5 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'RESEARCH' ? 'bg-violet-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Research</span>
            </button>
            <button
              onClick={() => setActiveTab('BACKTEST')}
              className={`px-2.5 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'BACKTEST' ? 'bg-violet-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              <BarChart2 className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Backtest</span>
            </button>
            <button
              onClick={() => setActiveTab('ROBUSTNESS')}
              className={`px-2.5 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'ROBUSTNESS' ? 'bg-violet-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span className="hidden sm:inline">Robustness Lab</span>
            </button>
          </div>

          <button
            onClick={() => {
              if (activeTab === 'OBSERVATORY') handleEvaluate(symbol, timeframe);
              else if (activeTab === 'RESEARCH') handleRunResearch(selectedStrategyId, symbol, timeframe);
              else if (activeTab === 'BACKTEST') handleRunBacktest();
            }}
            disabled={isEvaluating || isLoadingResearch || isLoadingBacktest}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-violet-500/20 disabled:opacity-60 cursor-pointer font-mono"
          >
            {isEvaluating || isLoadingResearch || isLoadingBacktest ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
            <span>Execute</span>
          </button>
        </div>
      </div>

      {/* ── Extensible Strategy Library Filter Toolbar ── */}
      {observatoryData?.strategies && (
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-1 overflow-x-auto custom-scrollbar">
            <span className="text-[10px] font-mono text-stone-500 font-bold uppercase mr-1 flex items-center gap-1">
              <Filter className="w-3 h-3 text-stone-400" /> Category:
            </span>
            {availableCategories.map(cat => (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={`px-2 py-0.5 rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer ${
                  categoryFilter === cat ? 'bg-violet-600 text-white shadow-sm' : 'bg-stone-900 text-stone-400 hover:text-stone-200 border border-stone-800'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search strategies…"
                className="px-2.5 py-1 pl-7 bg-stone-900 border border-stone-800 rounded-lg text-[11px] font-mono text-stone-200 placeholder-stone-600 focus:outline-none focus:border-violet-500 w-36 sm:w-44"
              />
              <Search className="w-3 h-3 text-stone-500 absolute left-2 top-2" />
            </div>
          </div>
        </div>
      )}

      {/* ── Dynamic Strategy Keypad (20 strategies) ── */}
      {filteredStrategies.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          {filteredStrategies.map(strat => (
            <StrategyKeypadButton
              key={strat.strategy_id}
              strategy={strat}
              isSelected={selectedStrategyId === strat.strategy_id}
              onClick={() => {
                setSelectedStrategyId(strat.strategy_id);
                if (activeTab === 'RESEARCH') handleRunResearch(strat.strategy_id, symbol, timeframe);
                else if (activeTab === 'BACKTEST') handleRunBacktest();
              }}
            />
          ))}
        </div>
      )}

      {/* ── Tab View 1: OBSERVATORY VIEW ── */}
      {activeTab === 'OBSERVATORY' && (
        <>
          {observatoryData?.confluence && (
            <StrategyAlignmentBar confluence={observatoryData.confluence} />
          )}

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
            <div className="lg:col-span-8 space-y-3">
              <ObservatoryChart
                candles={observatoryData?.candles || []}
                indicators={observatoryData?.chart_indicators || {}}
                selectedStrategy={selectedStrategy}
                allStrategies={observatoryData?.strategies || []}
                timeframe={timeframe}
                onTimeframeChange={setTimeframe}
              />
            </div>

            <div className="lg:col-span-4 space-y-3 flex flex-col">
              {selectedStrategy && (
                <>
                  <StrategyRuleInspector strategy={selectedStrategy} />
                  <div className="flex-1 min-h-[300px]">
                    <StrategyCopilotChat
                      symbol={symbol}
                      selectedStrategy={selectedStrategy}
                      allStrategies={observatoryData?.strategies || []}
                      regime={observatoryData?.market_regime || null}
                      confluence={observatoryData?.confluence || null}
                      timeframe={timeframe}
                    />
                  </div>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {/* ── Tab View 2: HISTORICAL RESEARCH VIEW ── */}
      {activeTab === 'RESEARCH' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
          <div className="lg:col-span-8 space-y-3">
            <ObservatoryChart
              candles={observatoryData?.candles || []}
              indicators={observatoryData?.chart_indicators || {}}
              selectedStrategy={selectedStrategy}
              allStrategies={observatoryData?.strategies || []}
              timeframe={timeframe}
              onTimeframeChange={setTimeframe}
            />

            <ResearchWorkstation
              summary={researchSummary}
              isLoading={isLoadingResearch}
              error={researchError}
              selectedObsId={selectedObsId}
              onSelectObsId={setSelectedObsId}
              onRefresh={() => handleRunResearch(selectedStrategyId, symbol, timeframe)}
            />
          </div>

          <div className="lg:col-span-4 space-y-3 flex flex-col">
            <div className="flex-1 min-h-[380px]">
              <StrategyCopilotChat
                symbol={symbol}
                selectedStrategy={selectedStrategy}
                allStrategies={observatoryData?.strategies || []}
                regime={observatoryData?.market_regime || null}
                confluence={observatoryData?.confluence || null}
                timeframe={timeframe}
                researchSummary={researchSummary}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Tab View 3: BACKTEST VIEW ── */}
      {activeTab === 'BACKTEST' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
          <div className="lg:col-span-8 space-y-3">
            <BacktestWorkstation
              result={backtestResult}
              isLoading={isLoadingBacktest}
              error={backtestError}
              onRunBacktest={handleRunBacktest}
            />
          </div>

          <div className="lg:col-span-4 space-y-3 flex flex-col">
            <div className="flex-1 min-h-[380px]">
              <StrategyCopilotChat
                symbol={symbol}
                selectedStrategy={selectedStrategy}
                allStrategies={observatoryData?.strategies || []}
                regime={observatoryData?.market_regime || null}
                confluence={observatoryData?.confluence || null}
                timeframe={timeframe}
                backtestResult={backtestResult}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Tab View 4: ROBUSTNESS & DISCOVERY WORKSTATION ── */}
      {activeTab === 'ROBUSTNESS' && selectedStrategy && (
        <RobustnessWorkstation
          symbol={symbol}
          strategyId={selectedStrategy.strategy_id}
          timeframe={timeframe}
          onSelectCandidate={params => {
            // Callback to highlight candidate params
          }}
          onLaunchChallenge={backtestData => {
            // Trigger Copilot Challenge Mode
          }}
        />
      )}
    </div>
  );
};
