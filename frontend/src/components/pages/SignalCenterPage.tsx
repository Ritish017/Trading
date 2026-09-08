import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Radio, Target, TrendingUp, TrendingDown, AlertTriangle, CheckCircle2,
  XCircle, MinusCircle, Zap, Shield, Clock, RefreshCw, Play,
  ChevronRight, ChevronDown, ChevronUp, Activity, BarChart3,
  Database, Info, Eye, Layers, Flame, ArrowUpRight, ArrowDownRight,
  Filter, Download, ExternalLink, Lock, AlertOctagon, PieChart,
  Cpu, Sparkles, GitBranch, ListFilter, Star, Award, X
} from 'lucide-react';

const API = '';

// ─── Types ───────────────────────────────────────────────────────────────────

interface StrategyVote {
  strategy_id: string;
  strategy_name: string;
  category: string;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL' | 'UNAVAILABLE';
  confidence: number;
  strength: number;
  reason_codes: string[];
  rules_passing: number;
  rules_total: number;
  is_correlated_with: string[];
}

interface TimeframeAnalysis {
  timeframe: string;
  trend: string;
  trend_strength: number;
  momentum: string;
  entry_quality: string;
  candles_available: number;
  ema20: number | null;
  ema50: number | null;
  rsi: number | null;
  adx: number | null;
  is_available: boolean;
}

interface ValidationGate {
  gate_id: string;
  gate_name: string;
  gate_type: 'HARD' | 'SOFT';
  result: 'PASS' | 'FAIL' | 'UNAVAILABLE';
  reason: string | null;
  actual_value: any;
  threshold_value: any;
  evidence: string | null;
}

interface StopLossResult {
  price: number;
  method: string;
  method_description: string;
  atr_value: number | null;
  structural_level: number | null;
  risk_per_share: number;
}

interface TargetLevel {
  level: number;
  price: number;
  method: string;
  method_description: string;
  expected_rr: number;
}

interface PositionSizing {
  method: string;
  capital: number;
  risk_per_trade_pct: number;
  max_risk_amount: number;
  entry_price: number;
  stop_price: number;
  risk_per_share: number;
  quantity: number;
  capital_required: number;
  maximum_loss: number;
  sizing_notes: string | null;
}

interface SignalDecision {
  signal_id: string;
  timestamp: string;
  symbol: string;
  exchange: string;
  direction: 'LONG' | 'SHORT' | 'NO_TRADE' | 'WATCHLIST';
  signal_type: string;
  timeframe: string;
  state: string;
  quality_grade: 'A+' | 'A' | 'B' | 'C' | 'NO TRADE';
  opportunity_score: number;
  confidence: number;
  entry: number | null;
  entry_zone_low: number | null;
  entry_zone_high: number | null;
  stop_loss: StopLossResult | null;
  targets: TargetLevel[];
  risk_reward: number | null;
  position_size: PositionSizing | null;
  regime: string;
  regime_confidence: number;
  regime_compatible: boolean;
  strategy_votes: StrategyVote[];
  mtf_alignment: { timeframes: TimeframeAnalysis[]; alignment_score: number; alignment_label: string; confirmation_message: string; conflict_warnings: string[] } | null;
  validation_gates: ValidationGate[];
  hard_gates_passed: number;
  hard_gates_total: number;
  soft_gates_passed: number;
  why_reasons: string[];
  invalidation_conditions: string[];
  rejection_reasons: string[];
  liquidity_score: number;
  data_quality: string;
  provenance: string;
  expiry: string | null;
}

interface PipelineStats {
  universe_size: number;
  data_valid: number;
  initial_screened: number;
  momentum_candidates: number;
  liquidity_pass: number;
  rr_pass: number;
  strategy_confluence_pass: number;
  qualified: number;
  scan_duration_ms: number;
}

interface ScannerResult {
  pipeline_stats: PipelineStats;
  qualified_signals: SignalDecision[];
  watchlist_signals: SignalDecision[];
  rejected_records: any[];
  market_regime: string;
  market_regime_confidence: number;
  is_market_open: boolean;
  scan_timestamp: string;
}

interface RejectionRecord {
  symbol: string;
  timestamp: string;
  gate_failed: string;
  gate_type: string;
  reason: string;
  partial_score: number;
}

// ─── Color helpers ────────────────────────────────────────────────────────────

const gradeColor = (g: string) => {
  if (g === 'A+') return 'text-emerald-300 bg-emerald-500/15 border-emerald-500/40';
  if (g === 'A')  return 'text-green-300 bg-green-500/15 border-green-500/40';
  if (g === 'B')  return 'text-amber-300 bg-amber-500/15 border-amber-500/40';
  if (g === 'C')  return 'text-orange-300 bg-orange-500/15 border-orange-500/40';
  return 'text-stone-400 bg-stone-800/60 border-stone-700';
};

const directionColor = (d: string) => {
  if (d === 'LONG')  return 'text-emerald-300 bg-emerald-500/15 border-emerald-500/40';
  if (d === 'SHORT') return 'text-rose-300 bg-rose-500/15 border-rose-500/40';
  return 'text-stone-400 bg-stone-800/60 border-stone-700';
};

const directionIcon = (d: string, cls = 'w-3.5 h-3.5') => {
  if (d === 'LONG')  return <ArrowUpRight className={`${cls} text-emerald-400`} />;
  if (d === 'SHORT') return <ArrowDownRight className={`${cls} text-rose-400`} />;
  return <MinusCircle className={`${cls} text-stone-500`} />;
};

const gateIcon = (r: string) => {
  if (r === 'PASS')        return <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />;
  if (r === 'FAIL')        return <XCircle className="w-3 h-3 text-rose-400 shrink-0" />;
  return <MinusCircle className="w-3 h-3 text-stone-500 shrink-0" />;
};

const regimeColor = (r: string) => {
  if (r.includes('BULL')) return 'text-emerald-400';
  if (r.includes('BEAR')) return 'text-rose-400';
  if (r.includes('RANGE')) return 'text-amber-400';
  return 'text-stone-400';
};

const trendColor = (t: string) => {
  if (t === 'BULLISH' || t === 'BULLISH_ABOVE') return 'text-emerald-400';
  if (t === 'BEARISH' || t === 'BEARISH_BELOW') return 'text-rose-400';
  if (t === 'PULLBACK') return 'text-amber-400';
  return 'text-stone-400';
};

// ─── Signal Card ──────────────────────────────────────────────────────────────

const SignalCard: React.FC<{
  signal: SignalDecision;
  onSelect: (s: SignalDecision) => void;
  isSelected: boolean;
}> = ({ signal, onSelect, isSelected }) => {
  const isLong = signal.direction === 'LONG';
  const borderColor = isSelected
    ? (isLong ? 'border-emerald-500/60' : 'border-rose-500/60')
    : 'border-stone-800/80';
  const bgColor = isSelected
    ? (isLong ? 'bg-emerald-500/5' : 'bg-rose-500/5')
    : 'bg-[#181a24]/90';

  return (
    <button
      onClick={() => onSelect(signal)}
      className={`w-full text-left p-3 rounded-xl border transition-all duration-200 ${bgColor} ${borderColor} hover:border-stone-600 group`}
    >
      <div className="flex items-start justify-between gap-2">
        {/* Symbol + Direction */}
        <div className="flex items-center gap-2 min-w-0">
          {directionIcon(signal.direction, 'w-4 h-4')}
          <div>
            <div className="font-mono font-bold text-sm text-white">
              {signal.symbol.replace('.NS', '')}
            </div>
            <div className="text-[10px] text-stone-500 font-mono mt-0.5">
              {signal.timeframe} · {signal.exchange}
            </div>
          </div>
        </div>

        {/* Grade + Score */}
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-black border ${gradeColor(signal.quality_grade)}`}>
            {signal.quality_grade}
          </span>
          <div className="text-[10px] text-stone-400 font-mono">
            {signal.opportunity_score.toFixed(0)}/100
          </div>
        </div>
      </div>

      {/* Entry / Stop / Target */}
      {signal.entry && (
        <div className="mt-2 grid grid-cols-3 gap-1">
          <div>
            <div className="text-[9px] text-stone-500 font-mono">ENTRY</div>
            <div className="text-xs font-mono text-white font-bold">₹{signal.entry.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-[9px] text-stone-500 font-mono">STOP</div>
            <div className="text-xs font-mono text-rose-400">
              {signal.stop_loss ? `₹${signal.stop_loss.price.toFixed(2)}` : '—'}
            </div>
          </div>
          <div>
            <div className="text-[9px] text-stone-500 font-mono">T1</div>
            <div className="text-xs font-mono text-emerald-400">
              {signal.targets?.[0] ? `₹${signal.targets[0].price.toFixed(2)}` : '—'}
            </div>
          </div>
        </div>
      )}

      {/* R:R + Confidence */}
      <div className="mt-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {signal.risk_reward && (
            <span className="text-[10px] font-mono text-stone-400">
              R:R <span className="text-amber-300 font-bold">{signal.risk_reward.toFixed(1)}x</span>
            </span>
          )}
          <span className="text-[10px] font-mono text-stone-400">
            Conf <span className="text-indigo-300 font-bold">{signal.confidence.toFixed(0)}%</span>
          </span>
        </div>
        <ChevronRight className="w-3 h-3 text-stone-600 group-hover:text-stone-400 transition-colors" />
      </div>

      {/* Progress bar for score */}
      <div className="mt-2 h-0.5 bg-stone-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            signal.opportunity_score >= 90 ? 'bg-emerald-400' :
            signal.opportunity_score >= 80 ? 'bg-green-400' :
            signal.opportunity_score >= 70 ? 'bg-amber-400' :
            'bg-orange-400'
          }`}
          style={{ width: `${signal.opportunity_score}%` }}
        />
      </div>
    </button>
  );
};

// ─── Scanner Pipeline Visualization ──────────────────────────────────────────

const ScannerPipelineViz: React.FC<{ stats: PipelineStats | null }> = ({ stats }) => {
  if (!stats) {
    return (
      <div className="text-center text-stone-500 text-xs font-mono py-4">
        No scan data. Click SCAN to evaluate the universe.
      </div>
    );
  }

  const stages = [
    { label: 'Universe', value: stats.universe_size, color: 'bg-stone-600' },
    { label: 'Data Valid', value: stats.data_valid, color: 'bg-blue-500/60' },
    { label: 'Screened', value: stats.initial_screened, color: 'bg-indigo-500/60' },
    { label: 'Liq Pass', value: stats.liquidity_pass, color: 'bg-violet-500/60' },
    { label: 'R:R Pass', value: stats.rr_pass, color: 'bg-amber-500/60' },
    { label: 'Confluence', value: stats.strategy_confluence_pass, color: 'bg-orange-500/60' },
    { label: 'Qualified', value: stats.qualified, color: 'bg-emerald-500/70' },
  ];

  const maxVal = stats.universe_size || 1;

  return (
    <div className="space-y-1.5">
      {stages.map((s, i) => (
        <div key={s.label} className="flex items-center gap-2">
          <div className="w-16 text-[9px] text-stone-500 font-mono text-right shrink-0">{s.label}</div>
          <div className="flex-1 h-3 bg-stone-900 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${s.color}`}
              style={{ width: `${(s.value / maxVal) * 100}%`, transitionDelay: `${i * 80}ms` }}
            />
          </div>
          <div className="w-8 text-right text-[9px] font-mono text-stone-400 shrink-0">
            {s.value ?? '?'}
          </div>
          {i < stages.length - 1 && (
            <ChevronRight className="w-2.5 h-2.5 text-stone-700 shrink-0" />
          )}
        </div>
      ))}
      <div className="mt-1 text-right text-[9px] text-stone-600 font-mono">
        {stats.scan_duration_ms > 0 ? `Scan: ${stats.scan_duration_ms.toFixed(0)}ms` : ''}
      </div>
    </div>
  );
};

// ─── Strategy Voting Table ────────────────────────────────────────────────────

const StrategyVotingTable: React.FC<{ votes: StrategyVote[]; direction: string }> = ({ votes, direction }) => {
  const byCategory = useMemo(() => {
    const map: Record<string, StrategyVote[]> = {};
    votes.forEach(v => {
      const cat = v.category || 'OTHER';
      if (!map[cat]) map[cat] = [];
      map[cat].push(v);
    });
    return map as Record<string, StrategyVote[]>;
  }, [votes]);


  return (
    <div className="space-y-3">
      {(Object.entries(byCategory) as [string, StrategyVote[]][]).map(([cat, catVotes]) => (
        <div key={cat}>
          <div className="text-[9px] font-mono font-bold text-stone-500 mb-1 tracking-widest uppercase">
            {cat}
          </div>
          <div className="space-y-0.5">
            {catVotes.map(v => {
              const isAligned = v.direction === direction;
              const isOpposed = v.direction === 'SHORT' && direction === 'LONG' ||
                                v.direction === 'LONG' && direction === 'SHORT';
              return (
                <div key={v.strategy_id} className="flex items-center gap-2 group">
                  <div className="w-2 h-2 rounded-full shrink-0" style={{
                    backgroundColor: isAligned ? '#10b981' : isOpposed ? '#f43f5e' : '#78716c'
                  }} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] font-mono text-stone-300 truncate">
                      {v.strategy_name}
                      {v.is_correlated_with?.length > 0 && (
                        <span className="ml-1 text-[8px] text-amber-600/70">~correlated</span>
                      )}
                    </div>
                  </div>
                  <div className={`text-[9px] font-mono font-bold w-14 text-right ${
                    v.direction === 'LONG' ? 'text-emerald-400' :
                    v.direction === 'SHORT' ? 'text-rose-400' : 'text-stone-500'
                  }`}>{v.direction}</div>
                  <div className="w-20 h-1.5 bg-stone-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${isAligned ? 'bg-emerald-500' : isOpposed ? 'bg-rose-500' : 'bg-stone-600'}`}
                      style={{ width: `${v.confidence}%` }}
                    />
                  </div>
                  <div className="text-[9px] text-stone-500 font-mono w-8 text-right">{v.confidence.toFixed(0)}%</div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};

// ─── Multi-Timeframe Grid ─────────────────────────────────────────────────────

const MTFGrid: React.FC<{ mtf: SignalDecision['mtf_alignment'] }> = ({ mtf }) => {
  if (!mtf) return <div className="text-stone-500 text-xs font-mono">MTF data unavailable</div>;

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-4 gap-1.5">
        {mtf.timeframes.map(tf => (
          <div key={tf.timeframe} className={`rounded-lg p-2 border ${
            tf.trend === 'BULLISH' ? 'bg-emerald-500/10 border-emerald-500/30' :
            tf.trend === 'BEARISH' ? 'bg-rose-500/10 border-rose-500/30' :
            tf.trend === 'UNAVAILABLE' ? 'bg-stone-900 border-stone-800' :
            'bg-amber-500/5 border-amber-500/20'
          }`}>
            <div className="text-[9px] font-mono text-stone-400 font-bold">{tf.timeframe}</div>
            <div className={`text-[10px] font-mono font-bold mt-0.5 ${trendColor(tf.trend)}`}>
              {tf.trend === 'UNAVAILABLE' ? '—' : tf.trend.replace('_ABOVE', '').replace('_BELOW', '')}
            </div>
            {tf.rsi && (
              <div className="text-[9px] text-stone-500 font-mono mt-0.5">RSI {tf.rsi.toFixed(0)}</div>
            )}
            <div className={`text-[9px] font-mono mt-0.5 ${
              tf.entry_quality === 'IDEAL' ? 'text-emerald-400' :
              tf.entry_quality === 'ACCEPTABLE' ? 'text-amber-400' : 'text-stone-500'
            }`}>{tf.entry_quality}</div>
          </div>
        ))}
      </div>

      <div className={`p-2 rounded-lg border text-[10px] font-mono ${
        mtf.alignment_label.includes('CONFIRMED') ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' :
        mtf.alignment_label.includes('CONFLICTING') ? 'bg-rose-500/10 border-rose-500/30 text-rose-300' :
        'bg-amber-500/5 border-amber-500/20 text-amber-300'
      }`}>
        <div className="font-bold">{mtf.alignment_label}</div>
        <div className="text-stone-400 mt-0.5 text-[9px]">{mtf.confirmation_message}</div>
      </div>

      {mtf.conflict_warnings?.length > 0 && (
        <div className="space-y-1">
          {mtf.conflict_warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-1.5 text-[9px] font-mono text-amber-400">
              <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── Signal Detail Panel ──────────────────────────────────────────────────────

const SignalDetailPanel: React.FC<{
  signal: SignalDecision;
  onClose: () => void;
  onPaperTrade: (signal: SignalDecision) => void;
}> = ({ signal, onClose, onPaperTrade }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'strategy' | 'mtf' | 'gates'>('overview');

  const hardGates = signal.validation_gates.filter(g => g.gate_type === 'HARD');
  const softGates = signal.validation_gates.filter(g => g.gate_type === 'SOFT');

  return (
    <div className="h-full flex flex-col bg-[#14151e] border-l border-stone-800">
      {/* Header */}
      <div className="px-4 py-3 border-b border-stone-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          {directionIcon(signal.direction, 'w-5 h-5')}
          <div>
            <div className="font-mono font-black text-base text-white">
              {signal.symbol.replace('.NS', '')}
            </div>
            <div className="text-[10px] font-mono text-stone-500">
              {signal.direction} · {signal.timeframe} · {signal.state}
            </div>
          </div>
          <span className={`px-2.5 py-1 rounded-lg text-xs font-mono font-black border ${gradeColor(signal.quality_grade)}`}>
            {signal.quality_grade}
          </span>
        </div>
        <button onClick={onClose} className="text-stone-500 hover:text-stone-300 transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Score bar */}
      <div className="px-4 py-3 border-b border-stone-800 shrink-0">
        <div className="flex items-center justify-between mb-1">
          <div className="text-[10px] font-mono text-stone-500">OPPORTUNITY SCORE</div>
          <div className="font-mono font-black text-white">{signal.opportunity_score.toFixed(1)}<span className="text-stone-500 text-xs">/100</span></div>
        </div>
        <div className="h-2 bg-stone-900 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${
              signal.opportunity_score >= 90 ? 'bg-gradient-to-r from-emerald-400 to-green-300' :
              signal.opportunity_score >= 80 ? 'bg-gradient-to-r from-green-400 to-emerald-300' :
              signal.opportunity_score >= 70 ? 'bg-gradient-to-r from-amber-400 to-yellow-300' :
              'bg-gradient-to-r from-orange-400 to-amber-300'
            }`}
            style={{ width: `${signal.opportunity_score}%` }}
          />
        </div>
        <div className="flex items-center justify-between mt-1">
          <div className="text-[9px] text-stone-500 font-mono">Confidence: {signal.confidence.toFixed(0)}%</div>
          {signal.risk_reward && (
            <div className="text-[9px] text-amber-400 font-mono font-bold">R:R {signal.risk_reward.toFixed(2)}x</div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-stone-800 shrink-0">
        {(['overview', 'strategy', 'mtf', 'gates'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2 text-[10px] font-mono font-bold uppercase tracking-wider transition-colors ${
              activeTab === tab
                ? 'text-amber-400 border-b-2 border-amber-400'
                : 'text-stone-500 hover:text-stone-300'
            }`}
          >
            {tab === 'overview' ? 'Overview' : tab === 'strategy' ? 'Strategies' : tab === 'mtf' ? 'MTF' : 'Gates'}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
        {activeTab === 'overview' && (
          <>
            {/* Entry/Stop/Target */}
            <div>
              <div className="text-[10px] font-mono text-stone-500 mb-2 tracking-widest">TRADE PARAMETERS</div>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 rounded-lg bg-stone-900 border border-stone-800">
                  <div className="text-[9px] font-mono text-stone-500">ENTRY ZONE</div>
                  <div className="font-mono font-bold text-white mt-0.5">
                    ₹{signal.entry?.toFixed(2) ?? '—'}
                  </div>
                  {signal.entry_zone_low && signal.entry_zone_high && (
                    <div className="text-[9px] text-stone-500 font-mono">
                      ₹{signal.entry_zone_low.toFixed(2)} – ₹{signal.entry_zone_high.toFixed(2)}
                    </div>
                  )}
                </div>
                <div className="p-2.5 rounded-lg bg-rose-500/5 border border-rose-500/20">
                  <div className="text-[9px] font-mono text-stone-500">STOP LOSS</div>
                  <div className="font-mono font-bold text-rose-300 mt-0.5">
                    {signal.stop_loss ? `₹${signal.stop_loss.price.toFixed(2)}` : '—'}
                  </div>
                  {signal.stop_loss && (
                    <div className="text-[9px] text-stone-500 font-mono truncate">
                      {signal.stop_loss.method}
                    </div>
                  )}
                </div>
                {signal.targets?.map(t => (
                  <div key={t.level} className="p-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                    <div className="text-[9px] font-mono text-stone-500">TARGET {t.level}</div>
                    <div className="font-mono font-bold text-emerald-300 mt-0.5">₹{t.price.toFixed(2)}</div>
                    <div className="text-[9px] text-stone-500 font-mono">R:R {t.expected_rr.toFixed(1)}x</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Position Sizing */}
            {signal.position_size && (
              <div>
                <div className="text-[10px] font-mono text-stone-500 mb-2 tracking-widest">POSITION SIZING</div>
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-2 rounded-lg bg-stone-900 border border-stone-800 text-center">
                    <div className="text-[9px] font-mono text-stone-500">QTY</div>
                    <div className="font-mono font-bold text-white mt-0.5">{signal.position_size.quantity}</div>
                  </div>
                  <div className="p-2 rounded-lg bg-stone-900 border border-stone-800 text-center">
                    <div className="text-[9px] font-mono text-stone-500">CAPITAL</div>
                    <div className="font-mono font-bold text-white mt-0.5 text-[10px]">
                      ₹{(signal.position_size.capital_required / 1000).toFixed(0)}K
                    </div>
                  </div>
                  <div className="p-2 rounded-lg bg-rose-500/5 border border-rose-500/20 text-center">
                    <div className="text-[9px] font-mono text-stone-500">MAX LOSS</div>
                    <div className="font-mono font-bold text-rose-300 mt-0.5 text-[10px]">
                      ₹{signal.position_size.maximum_loss.toFixed(0)}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Why This Trade */}
            {signal.why_reasons?.length > 0 && (
              <div>
                <div className="text-[10px] font-mono text-stone-500 mb-2 tracking-widest">WHY THIS TRADE?</div>
                <div className="space-y-1">
                  {signal.why_reasons.map((reason, i) => {
                    const isPass = reason.startsWith('✓');
                    const isFail = reason.startsWith('✗');
                    return (
                      <div key={i} className={`flex items-start gap-1.5 text-[10px] font-mono ${
                        isPass ? 'text-emerald-300' : isFail ? 'text-rose-300' : 'text-stone-400'
                      }`}>
                        <span className="shrink-0">{reason[0]}</span>
                        <span>{reason.slice(2)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Invalidation Conditions */}
            {signal.invalidation_conditions?.length > 0 && (
              <div>
                <div className="text-[10px] font-mono text-stone-500 mb-2 tracking-widest flex items-center gap-1.5">
                  <AlertTriangle className="w-3 h-3 text-amber-500" />
                  INVALIDATION CONDITIONS
                </div>
                <div className="space-y-1">
                  {signal.invalidation_conditions.map((cond, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-[10px] font-mono text-amber-300/80">
                      <span className="shrink-0 mt-0.5">→</span>
                      <span>{cond}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Regime */}
            <div>
              <div className="text-[10px] font-mono text-stone-500 mb-2 tracking-widest">MARKET REGIME</div>
              <div className="flex items-center gap-2">
                <span className={`font-mono font-bold text-sm ${regimeColor(signal.regime)}`}>
                  {signal.regime.replace(/_/g, ' ')}
                </span>
                <span className="text-[9px] text-stone-500 font-mono">
                  {signal.regime_confidence.toFixed(0)}% confidence
                </span>
                {signal.regime_compatible && (
                  <span className="text-[9px] text-emerald-400 font-mono flex items-center gap-0.5">
                    <CheckCircle2 className="w-3 h-3" /> Compatible
                  </span>
                )}
              </div>
            </div>

            {/* Data Provenance */}
            <div className="text-[9px] font-mono text-stone-600 border border-stone-800/60 rounded-lg p-2 space-y-0.5">
              <div>PROVENANCE: <span className="text-stone-400">{signal.provenance}</span></div>
              <div>QUALITY: <span className="text-stone-400">{signal.data_quality}</span></div>
              {signal.expiry && (
                <div>EXPIRES: <span className="text-stone-400">{new Date(signal.expiry).toLocaleTimeString()}</span></div>
              )}
            </div>
          </>
        )}

        {activeTab === 'strategy' && (
          <StrategyVotingTable votes={signal.strategy_votes} direction={signal.direction} />
        )}

        {activeTab === 'mtf' && (
          <MTFGrid mtf={signal.mtf_alignment} />
        )}

        {activeTab === 'gates' && (
          <div className="space-y-3">
            <div>
              <div className="text-[10px] font-mono text-stone-500 mb-2 tracking-widest flex items-center gap-1.5">
                <Lock className="w-3 h-3 text-rose-400" /> HARD GATES ({signal.hard_gates_passed}/{signal.hard_gates_total})
              </div>
              <div className="space-y-1.5">
                {hardGates.map(g => (
                  <div key={g.gate_id} className={`p-2 rounded-lg border ${
                    g.result === 'PASS' ? 'bg-emerald-500/5 border-emerald-500/20' :
                    g.result === 'FAIL' ? 'bg-rose-500/10 border-rose-500/30' :
                    'bg-stone-900 border-stone-800'
                  }`}>
                    <div className="flex items-center gap-1.5">
                      {gateIcon(g.result)}
                      <span className="text-[10px] font-mono font-bold text-stone-200">{g.gate_name}</span>
                    </div>
                    {(g.evidence || g.reason) && (
                      <div className="mt-0.5 text-[9px] font-mono text-stone-400 pl-4">
                        {g.evidence || g.reason}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="text-[10px] font-mono text-stone-500 mb-2 tracking-widest flex items-center gap-1.5">
                <Activity className="w-3 h-3 text-amber-400" /> SOFT EVIDENCE ({signal.soft_gates_passed} passed)
              </div>
              <div className="space-y-1.5">
                {softGates.map(g => (
                  <div key={g.gate_id} className={`p-2 rounded-lg border ${
                    g.result === 'PASS' ? 'bg-emerald-500/5 border-emerald-500/20' :
                    g.result === 'FAIL' ? 'bg-amber-500/5 border-amber-500/20' :
                    'bg-stone-900 border-stone-800'
                  }`}>
                    <div className="flex items-center gap-1.5">
                      {gateIcon(g.result)}
                      <span className="text-[10px] font-mono font-bold text-stone-200">{g.gate_name}</span>
                    </div>
                    {(g.evidence || g.reason) && (
                      <div className="mt-0.5 text-[9px] font-mono text-stone-400 pl-4">
                        {g.evidence || g.reason}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Action bar */}
      <div className="p-3 border-t border-stone-800 shrink-0">
        <button
          onClick={() => onPaperTrade(signal)}
          disabled={signal.direction === 'NO_TRADE'}
          className={`w-full py-2.5 rounded-xl font-mono font-bold text-sm transition-all ${
            signal.direction === 'LONG'
              ? 'bg-emerald-500 hover:bg-emerald-400 text-stone-950 disabled:opacity-40'
              : signal.direction === 'SHORT'
              ? 'bg-rose-500 hover:bg-rose-400 text-white disabled:opacity-40'
              : 'bg-stone-800 text-stone-500 cursor-not-allowed'
          }`}
        >
          {signal.direction === 'NO_TRADE' ? 'NO TRADE' : `PAPER ${signal.direction}`}
        </button>
        <div className="mt-2 text-center text-[9px] font-mono text-stone-600">
          Paper trading only · Not financial advice
        </div>
      </div>
    </div>
  );
};

// ─── Rejected Opportunities ───────────────────────────────────────────────────

const RejectedOpportunitiesPanel: React.FC<{ rejections: RejectionRecord[] }> = ({ rejections }) => {
  if (!rejections?.length) {
    return (
      <div className="text-center text-stone-600 text-xs font-mono py-6">
        No rejections recorded yet. Run a scan to see evaluated candidates.
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {rejections.slice(0, 20).map((r, i) => (
        <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-stone-900/60 border border-stone-800/60">
          <XCircle className="w-3 h-3 text-rose-500/70 shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono font-bold text-stone-300">
                {r.symbol?.replace('.NS', '')}
              </span>
              <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded border ${
                r.gate_type === 'HARD'
                  ? 'text-rose-400 border-rose-500/30 bg-rose-500/10'
                  : 'text-amber-400 border-amber-500/30 bg-amber-500/10'
              }`}>{r.gate_failed}</span>
            </div>
            <div className="text-[9px] font-mono text-stone-500 mt-0.5 truncate">{r.reason}</div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ─── Main Signal Center Page ──────────────────────────────────────────────────

const SignalCenterPage: React.FC = () => {
  const [scanResult, setScanResult] = useState<ScannerResult | null>(null);
  const [activeSignals, setActiveSignals] = useState<SignalDecision[]>([]);
  const [rejections, setRejections] = useState<RejectionRecord[]>([]);
  const [selectedSignal, setSelectedSignal] = useState<SignalDecision | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [lastScanTime, setLastScanTime] = useState<Date | null>(null);
  const [activeTab, setActiveTab] = useState<'qualified' | 'watchlist' | 'rejected'>('qualified');
  const [scanError, setScanError] = useState<string | null>(null);
  const [paperTradeStatus, setPaperTradeStatus] = useState<string | null>(null);

  const runScan = useCallback(async (force = false) => {
    setIsScanning(true);
    setScanError(null);
    try {
      const res = await fetch(`${API}/api/signals/scan?force=${force}`);
      if (!res.ok) throw new Error(`Scan failed: ${res.status}`);
      const data = await res.json();
      setScanResult(data);
      setLastScanTime(new Date());

      // Also refresh active signals
      const activeRes = await fetch(`${API}/api/signals/active`);
      if (activeRes.ok) {
        const activeData = await activeRes.json();
        setActiveSignals(activeData.signals || []);
      }

      // Fetch rejections
      const rejRes = await fetch(`${API}/api/signals/rejected/recent?limit=30`);
      if (rejRes.ok) {
        const rejData = await rejRes.json();
        setRejections(rejData.rejections || []);
      }
    } catch (err) {
      setScanError(err instanceof Error ? err.message : 'Scan failed');
    } finally {
      setIsScanning(false);
    }
  }, []);

  // Fetch active signals on mount
  useEffect(() => {
    fetch(`${API}/api/signals/active`)
      .then(r => r.json())
      .then(d => setActiveSignals(d.signals || []))
      .catch(() => {});

    fetch(`${API}/api/signals/rejected/recent?limit=20`)
      .then(r => r.json())
      .then(d => setRejections(d.rejections || []))
      .catch(() => {});
  }, []);

  const handlePaperTrade = useCallback(async (signal: SignalDecision) => {
    try {
      const res = await fetch(`${API}/api/signals/${signal.signal_id}/paper-trade`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': 'apex_default_dev_key' },
        body: JSON.stringify({ signal_id: signal.signal_id }),
      });
      const data = await res.json();
      if (res.ok) {
        setPaperTradeStatus(`✓ ${signal.direction} ${signal.symbol.replace('.NS', '')} — Paper order placed`);
        setTimeout(() => setPaperTradeStatus(null), 4000);
      } else {
        setPaperTradeStatus(`✗ ${data.detail || 'Paper trade failed'}`);
        setTimeout(() => setPaperTradeStatus(null), 4000);
      }
    } catch (err) {
      setPaperTradeStatus('✗ Paper trade request failed');
      setTimeout(() => setPaperTradeStatus(null), 4000);
    }
  }, []);

  const qualifiedSignals = scanResult?.qualified_signals || activeSignals;
  const watchlistSignals = scanResult?.watchlist_signals || [];

  return (
    <div className="h-full flex flex-col overflow-hidden bg-[#0e0f16]">
      {/* Paper trade notification */}
      {paperTradeStatus && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2.5 rounded-xl border font-mono text-sm font-bold shadow-2xl transition-all duration-300 ${
          paperTradeStatus.startsWith('✓')
            ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
            : 'bg-rose-500/20 border-rose-500/40 text-rose-300'
        }`}>
          {paperTradeStatus}
        </div>
      )}

      {/* Header Bar */}
      <div className="bg-[#12131a] border-b border-stone-800 px-4 py-2.5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="font-mono font-black text-amber-400 text-sm tracking-wider">SIGNAL INTELLIGENCE ENGINE</span>
          </div>
          {scanResult && (
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
              scanResult.is_market_open
                ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
                : 'text-stone-500 border-stone-700 bg-stone-800/50'
            }`}>
              {scanResult.is_market_open ? '● MARKET OPEN' : '○ MARKET CLOSED'}
            </span>
          )}
          {scanResult?.market_regime && (
            <span className={`text-[10px] font-mono ${regimeColor(scanResult.market_regime)}`}>
              {scanResult.market_regime.replace(/_/g, ' ')}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {lastScanTime && (
            <span className="text-[9px] font-mono text-stone-600">
              Last scan: {lastScanTime.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={() => runScan(true)}
            disabled={isScanning}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-60 text-stone-950 font-mono font-bold text-xs rounded-lg transition-all"
          >
            {isScanning ? (
              <><RefreshCw className="w-3 h-3 animate-spin" /> SCANNING...</>
            ) : (
              <><Play className="w-3 h-3" /> SCAN UNIVERSE</>
            )}
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {scanError && (
        <div className="bg-rose-500/10 border-b border-rose-500/30 px-4 py-2 flex items-center gap-2 shrink-0">
          <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
          <span className="text-xs font-mono text-rose-300">{scanError}</span>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel: Pipeline + Signals */}
        <div className="flex flex-col w-80 border-r border-stone-800 overflow-hidden shrink-0">
          {/* Pipeline Stats */}
          <div className="p-3 border-b border-stone-800 shrink-0">
            <div className="text-[10px] font-mono text-stone-500 mb-2 tracking-widest flex items-center gap-1.5">
              <Cpu className="w-3 h-3" /> EVALUATION PIPELINE
            </div>
            <ScannerPipelineViz stats={scanResult?.pipeline_stats || null} />
          </div>

          {/* Tabs */}
          <div className="flex border-b border-stone-800 shrink-0">
            {([
              { id: 'qualified', label: `Signals (${qualifiedSignals.length})`, color: 'text-emerald-400' },
              { id: 'watchlist', label: `Watch (${watchlistSignals.length})`, color: 'text-amber-400' },
              { id: 'rejected', label: `Rejected (${rejections.length})`, color: 'text-stone-500' },
            ] as const).map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2 text-[9px] font-mono font-bold uppercase tracking-wider transition-colors ${
                  activeTab === tab.id
                    ? `${tab.color} border-b-2 border-current`
                    : 'text-stone-600 hover:text-stone-400'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Signal List */}
          <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1.5">
            {activeTab === 'qualified' && (
              <>
                {qualifiedSignals.length === 0 ? (
                  <div className="text-center py-8 space-y-2">
                    <Shield className="w-8 h-8 text-stone-700 mx-auto" />
                    <div className="text-xs font-mono text-stone-600">
                      {isScanning ? 'Scanning universe...' : 'No qualified signals'}
                    </div>
                    <div className="text-[10px] font-mono text-stone-700 px-4 text-center">
                      The system is comfortable finding zero opportunities when conditions are not met.
                    </div>
                  </div>
                ) : (
                  qualifiedSignals.map(s => (
                    <SignalCard
                      key={s.signal_id}
                      signal={s}
                      onSelect={setSelectedSignal}
                      isSelected={selectedSignal?.signal_id === s.signal_id}
                    />
                  ))
                )}
              </>
            )}

            {activeTab === 'watchlist' && (
              <>
                {watchlistSignals.length === 0 ? (
                  <div className="text-center py-8 text-xs font-mono text-stone-600">
                    No watchlist candidates
                  </div>
                ) : (
                  watchlistSignals.map(s => (
                    <SignalCard
                      key={s.signal_id}
                      signal={s}
                      onSelect={setSelectedSignal}
                      isSelected={selectedSignal?.signal_id === s.signal_id}
                    />
                  ))
                )}
              </>
            )}

            {activeTab === 'rejected' && (
              <RejectedOpportunitiesPanel rejections={rejections} />
            )}
          </div>
        </div>

        {/* Right Panel: Signal Detail or Empty State */}
        <div className="flex-1 overflow-hidden">
          {selectedSignal ? (
            <SignalDetailPanel
              signal={selectedSignal}
              onClose={() => setSelectedSignal(null)}
              onPaperTrade={handlePaperTrade}
            />
          ) : (
            <div className="h-full flex flex-col items-center justify-center gap-4 text-center px-8">
              <div className="relative">
                <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                  <Radio className="w-8 h-8 text-amber-400" />
                </div>
                <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-amber-500 flex items-center justify-center">
                  <Zap className="w-2.5 h-2.5 text-stone-950" />
                </div>
              </div>
              <div className="space-y-2">
                <div className="font-mono font-black text-lg text-white">Signal Intelligence Center</div>
                <div className="text-sm text-stone-400 max-w-md font-mono leading-relaxed">
                  The engine continuously evaluates the NIFTY 50 universe through a
                  14-stage validation pipeline. Click SCAN UNIVERSE to run a full scan
                  or select a signal to view its complete audit trail.
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 w-full max-w-xs mt-2">
                {[
                  { icon: Shield, label: '14 Gates', color: 'text-emerald-400' },
                  { icon: GitBranch, label: 'Multi-TF', color: 'text-indigo-400' },
                  { icon: PieChart, label: 'Correlation-Free', color: 'text-amber-400' },
                ].map(({ icon: Icon, label, color }) => (
                  <div key={label} className="flex flex-col items-center gap-1.5 p-3 rounded-xl bg-stone-900 border border-stone-800">
                    <Icon className={`w-4 h-4 ${color}`} />
                    <span className="text-[9px] font-mono text-stone-500">{label}</span>
                  </div>
                ))}
              </div>

              <div className="text-[10px] font-mono text-stone-700 max-w-xs">
                The system is comfortable producing zero qualified signals when conditions are not met.
                Truth over appearance.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SignalCenterPage;
