import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  FlaskConical, Search, Zap, CheckCircle2, XCircle, AlertTriangle,
  MinusCircle, Clock, Database, ChevronDown, ChevronUp, ChevronRight,
  TrendingUp, TrendingDown, Info, Send, Loader2, Shield, Activity,
  Sliders, Eye, EyeOff, BarChart2, Layers, Sparkles, MessageSquare,
  HelpCircle, RefreshCw, CheckSquare, Square, History, ShieldAlert,
  BarChart, ArrowUpRight, ArrowDownRight, Compass, Filter, Tag
} from 'lucide-react';
import { NSEStock } from '../../types/indianMarket';

// ---------------------------------------------------------------------------
// Types & Extensible Contracts (V3)
// ---------------------------------------------------------------------------
export type RuleOutcome = 'PASS' | 'FAIL' | 'UNAVAILABLE';
export type StrategyState = 'ACTIVE' | 'PARTIAL' | 'INACTIVE' | 'CONFLICTED' | 'UNAVAILABLE';
export type DataFreshness = 'LIVE' | 'RECENT' | 'STALE' | 'UNAVAILABLE';

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
  rsi14?: (number | null)[];
  macd?: (number | null)[];
  macd_signal?: (number | null)[];
  macd_histogram?: (number | null)[];
  bb_upper?: (number | null)[];
  bb_middle?: (number | null)[];
  bb_lower?: (number | null)[];
  atr14?: (number | null)[];
  rvol?: (number | null)[];
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

// Format duration helper (e.g. 7h 12m or 45s)
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
      className={`relative p-2.5 rounded-xl border text-left transition-all duration-150 cursor-pointer flex flex-col justify-between ${
        isSelected
          ? 'bg-violet-950/40 border-violet-500/80 shadow-lg shadow-violet-500/20 ring-1 ring-violet-400/50'
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
  const total = confluence.total_strategies || 8;
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

      {/* Visual Alignment Meter */}
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
// Dynamic Metadata-Driven Observatory Trading Chart (Phase 22)
// ---------------------------------------------------------------------------
interface ObservatoryChartProps {
  candles: ChartCandle[];
  indicators: SeriesIndicators;
  selectedStrategy: StrategyResult | null;
  allStrategies: StrategyResult[];
  timeframe: string;
  onTimeframeChange: (tf: string) => void;
}

function ObservatoryChart({
  candles,
  indicators,
  selectedStrategy,
  allStrategies,
  timeframe,
  onTimeframeChange,
}: ObservatoryChartProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  // Overlay Mode: 'SELECTED' or 'ALL'
  const [overlayMode, setOverlayMode] = useState<'SELECTED' | 'ALL'>('SELECTED');
  const [showLayerMenu, setShowLayerMenu] = useState(false);

  // Manual Layer Toggles
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

  // Dynamic visualization overlays from strategy definition metadata (Phase 22)
  const strategyOverlays = selectedStrategy?.visualization?.overlays || [];
  const isEMA20Active = layers.ema20 || strategyOverlays.includes('ema20');
  const isEMA50Active = layers.ema50 || strategyOverlays.includes('ema50');
  const isEMA200Active = layers.ema200 || strategyOverlays.includes('ema200');
  const isVWAPActive = layers.vwap || strategyOverlays.includes('vwap');
  const isBollingerActive = layers.bollinger || strategyOverlays.includes('bb_upper') || strategyOverlays.includes('bb_middle');
  const isSupertrendActive = layers.supertrend || strategyOverlays.includes('supertrend_band');
  const isORBActive = layers.orb || strategyOverlays.includes('orb_high') || strategyOverlays.includes('orb_low');

  // Dynamic subpanels from strategy definition metadata
  const strategySubpanels = selectedStrategy?.visualization?.subpanels || [];
  const isRSISubpanel = strategySubpanels.includes('rsi14');
  const isMACDSubpanel = strategySubpanels.includes('macd');
  const hasSubpanel = isRSISubpanel || isMACDSubpanel;

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

  const getY = (val: number) => {
    return priceChartHeight - ((val - minPrice) / priceRange) * priceChartHeight;
  };

  const getVolY = (vol: number) => {
    const top = priceChartHeight;
    return top + volumeHeight - (vol / maxVolume) * volumeHeight;
  };

  const getSubY = (val: number, minV: number, maxV: number) => {
    const range = maxV - minV || 1;
    const top = priceChartHeight + volumeHeight + subpanelGap;
    return top + subpanelHeight - ((val - minV) / range) * subpanelHeight;
  };

  // Generate SVG path for line series
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

  // Generate Subpanel Path
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

  // Active Candle for crosshair
  const activeIdx = hoverIndex !== null && hoverIndex >= 0 && hoverIndex < n ? hoverIndex : n - 1;
  const activeCandle = candles[activeIdx];

  // Mouse handler
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * chartWidth;
    const idx = Math.min(Math.max(Math.floor(x / candleStep), 0), n - 1);
    setHoverIndex(idx);
  };

  return (
    <div className="bg-[#12131b] border border-stone-800/80 rounded-2xl p-3 flex flex-col gap-2 shadow-2xl">
      {/* Chart Top Controls Bar */}
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
          {/* Mode switch: Selected Strategy vs All Strategies */}
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

          {/* Timeframe selector */}
          <div className="flex items-center gap-1 bg-stone-900/80 p-0.5 rounded-lg border border-stone-800">
            {(['1m', '5m', '15m', '1h', '1D'] as const).map(tf => (
              <button
                key={tf}
                onClick={() => onTimeframeChange(tf)}
                className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded transition-all cursor-pointer ${
                  timeframe === tf
                    ? 'bg-violet-600 text-white shadow-sm'
                    : 'text-stone-400 hover:text-stone-200'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Layer controls toggle button */}
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

      {/* Active Overlays Legend */}
      <div className="flex items-center gap-3 text-[10px] font-mono text-stone-400 flex-wrap">
        <span className="text-stone-500 font-bold">Active Overlays:</span>
        {isEMA20Active && <span className="flex items-center gap-1 text-cyan-400"><span className="w-2 h-0.5 bg-cyan-400 inline-block" /> EMA20</span>}
        {isEMA50Active && <span className="flex items-center gap-1 text-amber-400"><span className="w-2 h-0.5 bg-amber-400 inline-block" /> EMA50</span>}
        {isEMA200Active && <span className="flex items-center gap-1 text-purple-400"><span className="w-2 h-0.5 bg-purple-400 inline-block" /> EMA200</span>}
        {isVWAPActive && <span className="flex items-center gap-1 text-fuchsia-400"><span className="w-2 h-0.5 bg-fuchsia-400 inline-block" /> VWAP</span>}
        {isBollingerActive && <span className="flex items-center gap-1 text-emerald-400"><span className="w-2 h-0.5 bg-emerald-400 inline-block" /> Bollinger (20, 2σ)</span>}
        {isSupertrendActive && <span className="flex items-center gap-1 text-lime-400"><span className="w-2 h-0.5 bg-lime-400 inline-block" /> Dynamic Support</span>}
        {isORBActive && <span className="flex items-center gap-1 text-yellow-400"><span className="w-2 h-0.5 bg-yellow-400 inline-block" /> ORB Range</span>}
      </div>

      {/* SVG Canvas */}
      <div className="relative overflow-hidden w-full select-none">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${chartWidth} ${totalHeight}`}
          className="w-full h-auto cursor-crosshair"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="bbAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.08" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.02" />
            </linearGradient>
            <linearGradient id="activeZoneGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.02" />
            </linearGradient>
          </defs>

          {/* Price Grid Horizontal Lines */}
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

          {/* Historical Active Regions Highlight Bands */}
          {layers.regions && overlayMode === 'SELECTED' && selectedStrategy?.historical_states?.map((hs, i) => {
            if (hs.state !== 'ACTIVE') return null;
            const x = hs.candle_index * candleStep;
            return (
              <rect
                key={i}
                x={x}
                y={0}
                width={candleStep}
                height={priceChartHeight}
                fill="url(#activeZoneGrad)"
              />
            );
          })}

          {/* Candlesticks */}
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
                <line
                  x1={x}
                  y1={highY}
                  x2={x}
                  y2={lowY}
                  stroke={isBull ? '#10b981' : '#f43f5e'}
                  strokeWidth={1}
                />
                <rect
                  x={x - candleWidth / 2}
                  y={bodyTop}
                  width={candleWidth}
                  height={bodyHeight}
                  fill={isBull ? '#10b981' : '#f43f5e'}
                  rx={0.5}
                />
              </g>
            );
          })}

          {/* Volume Subpanel Bars */}
          {layers.volume && candles.map((c, i) => {
            const x = i * candleStep + candleStep / 2;
            const vy = getVolY(c.volume);
            const vHeight = priceChartHeight + volumeHeight - vy;
            const isBull = c.close >= c.open;
            return (
              <rect
                key={`vol-${i}`}
                x={x - candleWidth / 2}
                y={vy}
                width={candleWidth}
                height={Math.max(1, vHeight)}
                fill={isBull ? '#10b981' : '#f43f5e'}
                opacity={0.35}
              />
            );
          })}

          {/* Indicator Overlays */}
          {isBollingerActive && (
            <>
              <path d={makeLinePath(indicators.bb_upper)} stroke="#10b981" strokeWidth={1} fill="none" strokeDasharray="2,2" />
              <path d={makeLinePath(indicators.bb_middle)} stroke="#34d399" strokeWidth={0.8} fill="none" />
              <path d={makeLinePath(indicators.bb_lower)} stroke="#10b981" strokeWidth={1} fill="none" strokeDasharray="2,2" />
            </>
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

          {/* Strategy Activation Markers */}
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

          {/* Crosshair Cursor */}
          {hoverIndex !== null && hoverIndex >= 0 && hoverIndex < n && (
            <g>
              <line
                x1={hoverIndex * candleStep + candleStep / 2}
                y1={0}
                x2={hoverIndex * candleStep + candleStep / 2}
                y2={priceChartHeight + volumeHeight}
                stroke="#a1a1aa"
                strokeWidth={0.8}
                strokeDasharray="2,2"
              />
              <line
                x1={0}
                y1={getY(candles[hoverIndex].close)}
                x2={chartWidth}
                y2={getY(candles[hoverIndex].close)}
                stroke="#a1a1aa"
                strokeWidth={0.8}
                strokeDasharray="2,2"
              />
            </g>
          )}

          {/* Subpanels for Oscillators (RSI / MACD) */}
          {isRSISubpanel && indicators.rsi14 && (
            <g transform={`translate(0, ${priceChartHeight + volumeHeight + subpanelGap})`}>
              <rect x={0} y={0} width={chartWidth} height={subpanelHeight} fill="#0d0e14" rx={4} stroke="#27272a" strokeWidth={0.8} />
              <line x1={0} y1={getSubY(70, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} x2={chartWidth} y2={getSubY(70, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} stroke="#f43f5e" strokeWidth={0.8} strokeDasharray="2,2" opacity={0.6} />
              <line x1={0} y1={getSubY(50, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} x2={chartWidth} y2={getSubY(50, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} stroke="#71717a" strokeWidth={0.8} strokeDasharray="2,2" opacity={0.4} />
              <line x1={0} y1={getSubY(35, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} x2={chartWidth} y2={getSubY(35, 0, 100) - (priceChartHeight + volumeHeight + subpanelGap)} stroke="#10b981" strokeWidth={0.8} strokeDasharray="2,2" opacity={0.6} />
              <text x={chartWidth - 4} y={12} fill="#71717a" fontSize={9} textAnchor="end" fontFamily="monospace">RSI(14): {indicators.rsi14[activeIdx]?.toFixed(1) || 'N/A'}</text>
              <path d={makeSubpanelPath(indicators.rsi14, 0, 100)} stroke="#a855f7" strokeWidth={1.5} fill="none" />
            </g>
          )}

          {isMACDSubpanel && indicators.macd && (
            <g transform={`translate(0, ${priceChartHeight + volumeHeight + subpanelGap})`}>
              <rect x={0} y={0} width={chartWidth} height={subpanelHeight} fill="#0d0e14" rx={4} stroke="#27272a" strokeWidth={0.8} />
              <text x={chartWidth - 4} y={12} fill="#71717a" fontSize={9} textAnchor="end" fontFamily="monospace">MACD (12,26,9)</text>
              <path d={makeSubpanelPath(indicators.macd, -5, 5)} stroke="#38bdf8" strokeWidth={1.2} fill="none" />
              <path d={makeSubpanelPath(indicators.macd_signal, -5, 5)} stroke="#f97316" strokeWidth={1.2} fill="none" />
            </g>
          )}
        </svg>
      </div>

      {/* Historical Strategy Timeline */}
      {selectedStrategy?.activation_events && selectedStrategy.activation_events.length > 0 && (
        <div className="pt-2 border-t border-stone-800/60 flex items-center gap-2 overflow-x-auto custom-scrollbar text-[10px] font-mono">
          <span className="text-stone-500 shrink-0 font-bold flex items-center gap-1">
            <History className="w-3 h-3 text-stone-400" /> Historical Timeline:
          </span>
          {selectedStrategy.activation_events.slice(-6).map((ev, i) => (
            <div
              key={i}
              className={`shrink-0 px-2 py-0.5 rounded-lg border flex items-center gap-1.5 ${
                ev.event_type === 'ACTIVATED'
                  ? 'bg-emerald-950/40 border-emerald-700/40 text-emerald-300'
                  : ev.event_type === 'INVALIDATED'
                  ? 'bg-rose-950/30 border-rose-800/40 text-rose-300'
                  : 'bg-orange-950/30 border-orange-700/40 text-orange-300'
              }`}
            >
              <span className="font-bold">₹{ev.price.toFixed(2)}</span>
              <span>{ev.label}</span>
            </div>
          ))}
        </div>
      )}
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

      {/* Entry Conditions */}
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

                {/* Mathematical Basis Drilldown */}
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

      {/* Exit Conditions */}
      {exitRules.length > 0 && (
        <div>
          <div className="flex items-center justify-between text-xs font-bold text-stone-300 uppercase mb-2">
            <span className="flex items-center gap-1.5 text-rose-400">
              <TrendingDown className="w-3.5 h-3.5" /> Strategy Exit Conditions
            </span>
          </div>
          <div className="space-y-1.5">
            {exitRules.map(rule => (
              <div key={rule.rule_id} className="p-2 rounded-lg bg-stone-900/40 border border-stone-800 text-xs flex items-center justify-between">
                <span className="text-stone-300">{rule.label}</span>
                <span className="font-mono text-[10px] text-stone-400">{rule.actual_value_label}</span>
              </div>
            ))}
          </div>
        </div>
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
}

function StrategyCopilotChat({
  symbol,
  selectedStrategy,
  allStrategies,
  regime,
  confluence,
  timeframe,
}: StrategyCopilotProps) {
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Clear chat history on symbol, selectedStrategy, or timeframe switch to prevent conversation leakage
  useEffect(() => {
    setMessages([]);
  }, [symbol, selectedStrategy?.strategy_id, timeframe]);

  const quickChips = [
    'Explain this strategy',
    'Why is it active right now?',
    'What would invalidate this strategy?',
    'Compare with VWAP Momentum',
    'Explain current market regime',
    'Explain the mathematics',
  ];

  const handleSend = async (userText: string) => {
    if (!userText.trim() || !selectedStrategy || isLoading) return;
    const textToSend = userText.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: textToSend }]);
    setIsLoading(true);

    try {
      const context = {
        market_regime: regime,
        confluence: confluence,
        timeframe,
        other_strategies: allStrategies.map(s => ({
          name: s.strategy_name,
          state: s.state,
          passing_count: s.entry_rules_passing,
          total_count: s.entry_rules_total,
        })),
      };

      const res = await fetch('/api/strategies/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          strategy_id: selectedStrategy.strategy_id,
          evaluation_result: selectedStrategy,
          user_message: textToSend,
          chat_history: messages.slice(-4),
          context,
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
      {/* Header */}
      <div className="p-3 border-b border-stone-800/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-violet-400" />
          <span className="font-black text-xs text-white uppercase tracking-wider font-mono">AI Strategy Copilot</span>
        </div>
        <span className="text-[9px] font-mono text-stone-500 border border-stone-800 px-1.5 py-0.5 rounded">
          Evidence-Grounded
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-2.5 min-h-[220px]">
        {messages.length === 0 && (
          <div className="text-center py-4 space-y-2">
            <div className="text-xs text-stone-400 font-mono">
              Inquiring about <strong className="text-violet-400">{selectedStrategy?.strategy_name || 'selected strategy'}</strong> on <strong>{symbol}</strong>
            </div>
            <div className="flex flex-wrap gap-1.5 justify-center">
              {quickChips.map(chip => (
                <button
                  key={chip}
                  onClick={() => handleSend(chip)}
                  disabled={!selectedStrategy}
                  className="text-[10px] font-mono px-2 py-1 rounded-lg bg-stone-900/80 hover:bg-stone-800 text-stone-300 border border-stone-700/60 transition-all cursor-pointer disabled:opacity-50"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, idx) => (
          <div key={idx} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
            <div
              className={`max-w-[92%] p-2.5 rounded-xl text-xs leading-relaxed ${
                m.role === 'user'
                  ? 'bg-violet-600/30 text-stone-100 border border-violet-500/40'
                  : 'bg-stone-900/90 text-stone-200 border border-stone-800'
              }`}
            >
              {m.text}
            </div>
            {m.evidence_cited && m.evidence_cited.length > 0 && (
              <div className="text-[9px] font-mono text-stone-500 mt-1 flex items-center gap-1">
                <Database className="w-2.5 h-2.5" /> Cited: {m.evidence_cited.slice(0, 2).join(', ')}
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 text-xs font-mono text-violet-400 p-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Analyzing verified rules & mathematics…
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <div className="p-2.5 border-t border-stone-800/60 bg-[#0e0f15]">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend(input)}
            placeholder={selectedStrategy ? "Ask Strategy Copilot..." : "Select a strategy first..."}
            disabled={!selectedStrategy || isLoading}
            className="flex-1 px-3 py-1.5 bg-stone-900 border border-stone-700/80 rounded-lg text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-violet-500 disabled:opacity-50 font-mono"
          />
          <button
            onClick={() => handleSend(input)}
            disabled={!input.trim() || !selectedStrategy || isLoading}
            className="p-1.5 bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition-all disabled:opacity-40 cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Strategy Lab Observatory Workspace (Dynamic V3 Extensible Architecture)
// ---------------------------------------------------------------------------
export const StrategyLabPage: React.FC<StrategyLabPageProps> = ({
  stocks,
  selectedSymbol,
  onSelectSymbol,
}) => {
  const [symbol, setSymbol] = useState(selectedSymbol || 'RELIANCE.NS');
  const [timeframe, setTimeframe] = useState('5m');
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [observatoryData, setObservatoryData] = useState<ObservatoryData | null>(null);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Dynamic Strategy Search & Filter State (Phase 20)
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [stateFilter, setStateFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const activeReqId = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const currentStock = stocks.find(s => s.symbol === symbol) || stocks[0];

  const handleEvaluate = useCallback(async (symToEval = symbol, tfToEval = timeframe) => {
    const reqId = ++activeReqId.current;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
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

      // Auto-select first active strategy or maintain selected
      if (data.strategies && data.strategies.length > 0) {
        setSelectedStrategyId(prev => {
          if (prev && data.strategies.some(s => s.strategy_id === prev)) {
            return prev;
          }
          const firstActive = data.strategies.find(s => s.state === 'ACTIVE') || data.strategies[0];
          return firstActive.strategy_id;
        });
      }
    } catch (e: any) {
      if (e.name === 'AbortError') return;
      if (reqId === activeReqId.current) {
        setError(e.message || 'Evaluation failed');
      }
    } finally {
      if (reqId === activeReqId.current) {
        setIsEvaluating(false);
      }
    }
  }, [symbol, timeframe]);

  // Initial evaluation on mount or symbol/timeframe switch
  useEffect(() => {
    handleEvaluate(symbol, timeframe);
  }, [symbol, timeframe]);

  const selectedStrategy = observatoryData?.strategies?.find(s => s.strategy_id === selectedStrategyId) || null;

  // Stale & Freshness handling
  const isStale = observatoryData?.data_freshness === 'STALE';
  const isLive = observatoryData?.data_freshness === 'LIVE';
  const isRecent = observatoryData?.data_freshness === 'RECENT';
  const isUnavailable = observatoryData?.data_freshness === 'UNAVAILABLE';
  const isMarketClosed = observatoryData?.market_status === 'CLOSED';
  const isSimulated = observatoryData?.market_status === 'SIMULATED' || observatoryData?.provider === 'MOCK';
  const ageSeconds = observatoryData?.data_age_seconds;
  const provider = observatoryData?.provider || 'UPSTOX';

  // Dynamic Category Extraction from registered strategies (Phase 3 & 20)
  const availableCategories = useMemo(() => {
    if (!observatoryData?.strategies) return ['ALL'];
    const cats = new Set<string>();
    observatoryData.strategies.forEach(s => {
      if (s.category) cats.add(s.category);
    });
    return ['ALL', ...Array.from(cats)];
  }, [observatoryData?.strategies]);

  // Dynamic Strategy Filtering (Phase 20)
  const filteredStrategies = useMemo(() => {
    if (!observatoryData?.strategies) return [];
    return observatoryData.strategies.filter(s => {
      if (categoryFilter !== 'ALL' && s.category !== categoryFilter) {
        return false;
      }
      if (stateFilter !== 'ALL' && s.state !== stateFilter) {
        return false;
      }
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
              {observatoryData && (
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                  isLive ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' :
                  isRecent ? 'bg-sky-500/15 text-sky-400 border-sky-500/30' :
                  isStale ? 'bg-purple-900/30 text-purple-300 border-purple-700/40' :
                  'bg-stone-800 text-stone-400 border-stone-700'
                }`}>
                  {observatoryData.data_freshness} {ageSeconds ? `(${formatDuration(ageSeconds)} old)` : ''}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs font-mono mt-0.5 flex-wrap">
              <span className="text-stone-100 font-bold">₹{currentStock?.price?.toFixed(2) || '---'}</span>
              <span className={currentStock?.change && currentStock.change >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                {currentStock?.change && currentStock.change >= 0 ? '+' : ''}{currentStock?.change?.toFixed(2)} ({currentStock?.changePercent?.toFixed(2)}%)
              </span>
              {observatoryData?.market_regime && (
                <span className="text-stone-400 font-medium hidden md:inline">
                  · Regime: <strong className="text-amber-400">{observatoryData.market_regime.regime}</strong> (Regime Evidence: {observatoryData.market_regime.confidence}%)
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Quick Symbol Switcher Chips */}
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
          <button
            onClick={() => handleEvaluate(symbol, timeframe)}
            disabled={isEvaluating}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-violet-500/20 disabled:opacity-60 cursor-pointer font-mono"
          >
            {isEvaluating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
            {isEvaluating ? 'Evaluating…' : 'Evaluate'}
          </button>
        </div>
      </div>

      {/* Stale / Live / Market Closed / Simulated Data Experience Banner */}
      {isStale && (
        <div className="px-4 py-2.5 rounded-xl bg-purple-950/40 border border-purple-700/50 text-purple-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 shadow-md">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-purple-400 shrink-0" />
            <span>
              <strong>HISTORICAL CONTEXT (DATA AGE: {formatDuration(ageSeconds)}):</strong> Strategy states below describe the last available market data (Provider: {provider}). They are not current live-market conditions.
            </span>
          </div>
          <span className="font-mono text-[10px] text-purple-300 border border-purple-600/40 px-2 py-0.5 rounded shrink-0 self-start sm:self-auto">
            🟣 HISTORICAL CONTEXT
          </span>
        </div>
      )}

      {isMarketClosed && !isStale && (
        <div className="px-4 py-2 rounded-xl bg-sky-950/25 border border-sky-700/40 text-sky-300 text-xs flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-sky-400" />
            <span><strong>MARKET CLOSED:</strong> Standard session hours are 09:15 - 15:30 IST (Mon-Fri). Strategy states reflect closing candle conditions (Provider: {provider}).</span>
          </div>
          <span className="font-mono text-[10px] text-sky-400 border border-sky-600/40 px-2 py-0.5 rounded">🔵 MARKET CLOSED</span>
        </div>
      )}

      {isSimulated && (
        <div className="px-4 py-2 rounded-xl bg-amber-950/25 border border-amber-700/40 text-amber-300 text-xs flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-amber-400" />
            <span><strong>SIMULATED ENVIRONMENT:</strong> Running on development simulated market feed.</span>
          </div>
          <span className="font-mono text-[10px] text-amber-400 border border-amber-600/40 px-2 py-0.5 rounded">🟠 DEV MOCK</span>
        </div>
      )}

      {isLive && !isMarketClosed && (
        <div className="px-4 py-2 rounded-xl bg-emerald-950/25 border border-emerald-700/40 text-emerald-300 text-xs flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-400" />
            <span><strong>LIVE MARKET STREAM:</strong> Real-time deterministic evaluation active (Provider: {provider}, Age: {formatDuration(ageSeconds)}).</span>
          </div>
          <span className="font-mono text-[10px] text-emerald-400 border border-emerald-600/40 px-2 py-0.5 rounded">🟢 LIVE</span>
        </div>
      )}

      {error && (
        <div className="px-4 py-3 rounded-xl bg-rose-950/30 border border-rose-800/50 text-rose-300 text-xs flex items-center gap-2">
          <XCircle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      {/* ── Extensible Strategy Library Filter & Search Toolbar (Phases 20 & 21) ── */}
      {observatoryData?.strategies && (
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
          {/* Category Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto custom-scrollbar">
            <span className="text-[10px] font-mono text-stone-500 font-bold uppercase mr-1 flex items-center gap-1">
              <Filter className="w-3 h-3 text-stone-400" /> Category:
            </span>
            {availableCategories.map(cat => (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={`px-2 py-0.5 rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer ${
                  categoryFilter === cat
                    ? 'bg-violet-600 text-white shadow-sm'
                    : 'bg-stone-900 text-stone-400 hover:text-stone-200 border border-stone-800'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* State Filter & Search Input */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1 bg-stone-900 p-0.5 rounded-lg border border-stone-800 text-[10px] font-mono">
              {(['ALL', 'ACTIVE', 'PARTIAL', 'INACTIVE'] as const).map(st => (
                <button
                  key={st}
                  onClick={() => setStateFilter(st)}
                  className={`px-2 py-0.5 rounded transition-all cursor-pointer font-bold ${
                    stateFilter === st ? 'bg-violet-600 text-white' : 'text-stone-400 hover:text-stone-200'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>

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

      {/* ── Dynamic Strategy Keypad (Scales to 10, 50, 100+ strategies) ── */}
      {filteredStrategies.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          {filteredStrategies.map(strat => (
            <StrategyKeypadButton
              key={strat.strategy_id}
              strategy={strat}
              isSelected={selectedStrategyId === strat.strategy_id}
              onClick={() => setSelectedStrategyId(strat.strategy_id)}
            />
          ))}
        </div>
      ) : (
        <div className="p-4 text-center bg-[#12131b] border border-stone-800 rounded-xl text-stone-500 font-mono text-xs">
          No strategies match the selected category or filter.
        </div>
      )}

      {/* ── Strategy Alignment & Confluence Panel ── */}
      {observatoryData?.confluence && (
        <StrategyAlignmentBar confluence={observatoryData.confluence} />
      )}

      {/* ── Main Layout: Trading Chart + Dynamic Detail Inspector & Copilot ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
        {/* Trading Chart (Left 8 Cols) */}
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

        {/* Selected Strategy Inspector & Copilot (Right 4 Cols) */}
        <div className="lg:col-span-4 space-y-3 flex flex-col">
          {selectedStrategy ? (
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
          ) : (
            <div className="p-8 text-center bg-[#12131b] border border-stone-800 rounded-xl text-stone-500 font-mono text-xs">
              Select a strategy button above to inspect mathematical conditions and launch copilot.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
