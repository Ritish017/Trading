import React, { useState, useEffect, useCallback } from 'react';
import {
  Radio, Compass, Cpu, Layers, TrendingUp, TrendingDown, DollarSign,
  PieChart, BarChart3, Sparkles, Shield, AlertTriangle, CheckCircle2,
  XCircle, MinusCircle, Clock, Calendar, RefreshCw, Search, ArrowUpRight,
  ArrowDownRight, Target, Bookmark, Split, GitMerge, Flame,
  Send, Loader2, MessageSquare, AlertOctagon, Sliders, Eye, Play,
  CheckCheck, Scale, FileText, ChevronDown, ChevronUp, Database, Activity,
  Lock, Zap, Info, ListFilter, ShieldCheck, History, ExternalLink
} from 'lucide-react';
import { NSEStock } from '../../types/indianMarket';

export interface EvidenceProvenanceRecord {
  metric_key: string;
  value: any;
  unit: string;
  classification: string;
  source: string;
  provider: string;
  source_timestamp?: number | null;
  calculation_timestamp?: number | null;
  market_timestamp?: number | null;
  publication_timestamp?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  data_status: string;
  freshness: string;
  calculation_method: string;
  dependencies: string[];
  is_derived: boolean;
  is_point_in_time_valid: boolean;
  confidence_basis: string;
}

export interface CommandCenterSnapshotData {
  market: {
    symbol: string;
    timeframe: string;
    current_price: number;
    change_pct: number;
    market_regime: string;
    volatility_state: string;
    trend_state: string;
    volume_state: string;
    technical_freshness: string;
    fundamental_freshness: string;
    provider: string;
    timestamp: number;
    market_status: string;
  };
  strategies: Array<{
    strategy_id: string;
    strategy_name: string;
    category: string;
    description: string;
    state: string;
    passing_rules: number;
    total_rules: number;
    rule_coverage_pct: number;
    tags: string[];
    rule_evaluations: Array<{
      rule_id: string;
      outcome: string;
      actual_value?: number | null;
      threshold_value?: number | null;
      difference?: number | null;
      description: string;
    }>;
  }>;
  alignment: {
    active_count: number;
    partial_count: number;
    inactive_count: number;
    conflicted_count: number;
    unavailable_count: number;
    total_strategies: number;
    passing_rules_total: number;
    total_rules_count: number;
    rule_coverage_pct: number;
    label: string;
  };
  confluence: {
    technical_state: string;
    fundamental_state: string;
    confluence_quadrant: string;
    research_classification: string;
    disclaimer: string;
  };
  fundamentals: Array<{
    metric_name: string;
    raw_value: number | null;
    display_value: string;
    unit: string;
    source: string;
    publication_date: string;
    data_status: string;
  }>;
  historical_analogues: {
    total_similar_observations: number;
    matched_regime: string;
    matched_technical: string;
    matched_fundamental: string;
    forward_1_bar_median: number;
    forward_3_bar_median: number;
    forward_5_bar_median: number;
    forward_10_bar_median: number;
    forward_20_bar_median: number;
    mae_median: number;
    mfe_median: number;
    win_rate_forward_5: number;
    disclaimer: string;
  };
  contradictions: {
    supporting_evidence: string[];
    contradicting_evidence: string[];
    unknowns: string[];
  };
  paper_status: {
    hypothesis_id: string;
    version: string;
    decision: string;
    trade_count: number;
    required_sample_size: number;
    progress_pct: number;
    fingerprint: string;
    survivorship_warning: string;
  };
  evidence_hierarchy: {
    level_1_live_market: Record<string, any>;
    level_2_pit_fundamentals: Record<string, any>;
    level_3_deterministic_strategies: Record<string, any>;
    level_4_historical_research: Record<string, any>;
    level_5_backtest: Record<string, any>;
    level_6_forward_paper: Record<string, any>;
    level_7_model_interpretation: Record<string, any>;
  };
  timeline: Array<{
    time: string;
    event_type: string;
    source: string;
    evidence: string;
  }>;
  watchlist: Array<{
    symbol: string;
    company_name: string;
    price: number;
    change_pct: number;
    regime: string;
    active_strategies_count: number;
    technical_state: string;
    fundamental_state: string;
    confluence: string;
    research_status: string;
    data_freshness: string;
  }>;
  cross_stock: Array<{
    symbol: string;
    price: number;
    regime: string;
    active_strategies: number;
    rule_coverage_pct: number;
    roe: number | null;
    pe: number | null;
    technical_state: string;
    fundamental_state: string;
    research_status: string;
  }>;
  provenance?: Record<string, EvidenceProvenanceRecord>;
}

export interface CommandCenterPageProps {
  stocks: NSEStock[];
  selectedSymbol: string;
  onSelectSymbol?: (symbol: string) => void;
}

export const CommandCenterPage: React.FC<CommandCenterPageProps> = ({
  stocks,
  selectedSymbol: initialSymbol,
  onSelectSymbol,
}) => {
  const [symbol, setSymbol] = useState<string>(initialSymbol || 'RELIANCE.NS');
  const [timeframe, setTimeframe] = useState<string>('1D');
  const [snapshot, setSnapshot] = useState<CommandCenterSnapshotData | null>(null);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [selectedProvenanceMetric, setSelectedProvenanceMetric] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Copilot State
  const [copilotMessages, setCopilotMessages] = useState<Array<{ role: string; text: string }>>([]);
  const [copilotInput, setCopilotInput] = useState<string>('');
  const [isCopilotLoading, setIsCopilotLoading] = useState<boolean>(false);

  const loadSnapshot = useCallback(async (sym: string, tf: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/research-command-center/${encodeURIComponent(sym)}?timeframe=${encodeURIComponent(tf)}`);
      if (res.ok) {
        const data = await res.json();
        setSnapshot(data.snapshot || null);
      } else {
        setError(`Failed to load command center snapshot: ${res.statusText}`);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSnapshot(symbol, timeframe);
  }, [symbol, timeframe, loadSnapshot]);

  const handleSymbolChange = (newSym: string) => {
    setSymbol(newSym);
    if (onSelectSymbol) onSelectSymbol(newSym);
  };

  const handleCopilotSend = async (userText: string) => {
    if (!userText.trim() || isCopilotLoading) return;
    const textToSend = userText.trim();
    const isSkeptic = textToSend.toUpperCase().includes('CHALLENGE') || textToSend.toUpperCase().includes('DISPROVE');
    setCopilotInput('');
    setCopilotMessages(prev => [...prev, { role: 'user', text: textToSend }]);
    setIsCopilotLoading(true);

    try {
      let endpoint = '/api/research-command-center/copilot';
      if (isSkeptic) {
        endpoint = `/api/research-command-center/challenge/${encodeURIComponent(symbol)}`;
      }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: symbol,
          user_message: textToSend,
          snapshot: snapshot || null,
          chat_history: copilotMessages,
          is_skeptic_mode: isSkeptic,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setCopilotMessages(prev => [...prev, { role: 'assistant', text: data.reply || 'No response.' }]);
      }
    } catch (e: any) {
      setCopilotMessages(prev => [...prev, { role: 'assistant', text: `Copilot error: ${e.message}` }]);
    } finally {
      setIsCopilotLoading(false);
    }
  };

  const selectedStrategy = snapshot?.strategies.find(s => s.strategy_id === selectedStrategyId);
  const activeProv = selectedProvenanceMetric && snapshot?.provenance ? snapshot.provenance[selectedProvenanceMetric] : null;

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-175px)] overflow-y-auto custom-scrollbar p-3 space-y-3 bg-[#0a0b10] font-mono text-stone-100">
      {/* ── Top Header Command Bar ── */}
      <div className="bg-[#12131b] border border-cyan-500/40 rounded-2xl p-3 flex flex-wrap items-center justify-between gap-3 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-600/20 border border-cyan-500/50 flex items-center justify-center text-cyan-400 font-black shadow-inner">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-black text-sm text-white tracking-wide">APEX LIVE QUANT RESEARCH COMMAND CENTER</span>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-700/50">
                PHASE 14: FORENSIC PROVENANCE
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs text-stone-400 mt-0.5">
              <span>● 20 Deterministic Strategies</span>
              <span>● PIT Audited Fundamentals</span>
              <span>● Zero Lookahead Analogues</span>
              <span>● Audited Provenance</span>
            </div>
          </div>
        </div>

        {/* Symbol & Timeframe Selectors */}
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={symbol}
            onChange={(e) => handleSymbolChange(e.target.value)}
            className="bg-stone-900 border border-stone-700 rounded-lg px-2.5 py-1 text-xs text-stone-200 font-bold focus:outline-none"
          >
            {['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS', 'TATAMOTORS.NS', 'SBIN.NS'].map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <div className="flex items-center bg-stone-900 border border-stone-800 rounded-lg p-0.5 text-xs">
            {['1m', '5m', '15m', '1h', '1D'].map(tf => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-2 py-0.5 rounded font-bold transition-all cursor-pointer ${
                  timeframe === tf ? 'bg-cyan-600 text-white' : 'text-stone-400 hover:text-stone-200'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          <button
            onClick={() => loadSnapshot(symbol, timeframe)}
            className="p-1.5 bg-stone-900 hover:bg-stone-800 border border-stone-700 rounded-lg text-stone-300 cursor-pointer"
            title="Refresh Snapshot"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {snapshot && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 flex-1">
          {/* Left 8 Cols */}
          <div className="lg:col-span-8 space-y-3">
            {/* Market Snapshot & Regime Bar */}
            <div className="bg-[#12131b] border border-stone-800/90 rounded-xl p-3.5 space-y-3 shadow-xl">
              <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-black text-white">{snapshot.market.symbol}</span>
                  <span className="text-base font-bold text-cyan-400">₹{snapshot.market.current_price}</span>
                  <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                    snapshot.market.change_pct >= 0 ? 'bg-emerald-950 text-emerald-300' : 'bg-rose-950 text-rose-300'
                  }`}>
                    {snapshot.market.change_pct >= 0 ? '+' : ''}{snapshot.market.change_pct}%
                  </span>
                  <button
                    onClick={() => setSelectedProvenanceMetric('current_price')}
                    className="px-1.5 py-0.2 rounded text-[8px] font-bold bg-cyan-950 text-cyan-400 border border-cyan-800 hover:bg-cyan-900 cursor-pointer"
                  >
                    Evidence
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-stone-500 uppercase">Provider:</span>
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-stone-900 text-stone-300 border border-stone-700">
                    {snapshot.market.provider} ● {snapshot.market.market_status} ● {snapshot.market.technical_freshness}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div className="p-2 bg-stone-950 border border-stone-800 rounded">
                  <div className="flex items-center justify-between">
                    <span className="text-[9px] text-stone-500 uppercase font-bold">Market Regime</span>
                    <button onClick={() => setSelectedProvenanceMetric('market_regime')} className="text-[8px] text-cyan-400 hover:underline">Provenance</button>
                  </div>
                  <div className="text-xs font-black text-cyan-300 mt-0.5">{snapshot.market.market_regime}</div>
                </div>
                <div className="p-2 bg-stone-950 border border-stone-800 rounded">
                  <div className="text-[9px] text-stone-500 uppercase font-bold">Trend State</div>
                  <div className="text-xs font-black text-emerald-400 mt-0.5">{snapshot.market.trend_state}</div>
                </div>
                <div className="p-2 bg-stone-950 border border-stone-800 rounded">
                  <div className="flex items-center justify-between">
                    <span className="text-[9px] text-stone-500 uppercase font-bold">Strategy Alignment</span>
                    <button onClick={() => setSelectedProvenanceMetric('strategy_alignment')} className="text-[8px] text-cyan-400 hover:underline">Provenance</button>
                  </div>
                  <div className="text-xs font-black text-amber-400 mt-0.5">
                    {snapshot.alignment.active_count} / {snapshot.alignment.total_strategies} Active ({snapshot.alignment.rule_coverage_pct}%)
                  </div>
                </div>
                <div className="p-2 bg-stone-950 border border-stone-800 rounded">
                  <div className="flex items-center justify-between">
                    <span className="text-[9px] text-stone-500 uppercase font-bold">Confluence State</span>
                    <button onClick={() => setSelectedProvenanceMetric('confluence_quadrant')} className="text-[8px] text-cyan-400 hover:underline">Provenance</button>
                  </div>
                  <div className="text-xs font-black text-purple-400 mt-0.5">{snapshot.confluence.confluence_quadrant}</div>
                </div>
              </div>
            </div>

            {/* Evidence Provenance Inspector Drawer (Modal view if active) */}
            {activeProv && (
              <div className="p-3.5 bg-[#0f1422] border border-cyan-500/60 rounded-xl space-y-2 shadow-2xl animate-in fade-in">
                <div className="flex items-center justify-between border-b border-cyan-800/60 pb-2 text-xs">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-cyan-400" />
                    <span className="font-bold text-white uppercase">EVIDENCE PROVENANCE AUDIT: {activeProv.metric_key}</span>
                  </div>
                  <button onClick={() => setSelectedProvenanceMetric(null)} className="text-stone-400 hover:text-white text-xs cursor-pointer font-bold">✕ Close</button>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div className="p-2 bg-stone-950 border border-stone-800 rounded">
                    <div className="text-[9px] text-stone-500 uppercase">Classification</div>
                    <div className="text-[10px] font-bold text-cyan-300">{activeProv.classification}</div>
                  </div>
                  <div className="p-2 bg-stone-950 border border-stone-800 rounded">
                    <div className="text-[9px] text-stone-500 uppercase">Source & Provider</div>
                    <div className="text-[10px] font-bold text-white">{activeProv.source} ({activeProv.provider})</div>
                  </div>
                  <div className="p-2 bg-stone-950 border border-stone-800 rounded">
                    <div className="text-[9px] text-stone-500 uppercase">PIT Validity</div>
                    <div className="text-[10px] font-bold text-emerald-400">{activeProv.is_point_in_time_valid ? 'STRICT PIT VALID' : 'NON_PIT'}</div>
                  </div>
                  <div className="p-2 bg-stone-950 border border-stone-800 rounded">
                    <div className="text-[9px] text-stone-500 uppercase">Freshness</div>
                    <div className="text-[10px] font-bold text-amber-300">{activeProv.freshness}</div>
                  </div>
                </div>
                <div className="p-2 bg-stone-950 border border-stone-800 rounded text-xs space-y-1">
                  <div className="text-[9px] text-stone-500 uppercase font-bold">Calculation Method:</div>
                  <div className="text-[10px] text-stone-300 font-mono">{activeProv.calculation_method}</div>
                  <div className="text-[9px] text-stone-500 uppercase font-bold pt-1">Evidence Basis / Semantics:</div>
                  <div className="text-[10px] text-cyan-300">{activeProv.confidence_basis}</div>
                </div>
              </div>
            )}

            {/* 20 Strategies Confluence Matrix */}
            <div className="bg-[#12131b] border border-stone-800/90 rounded-xl p-3.5 space-y-2.5 shadow-xl">
              <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
                <span className="font-bold text-white uppercase flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-cyan-400" />
                  <span>Deterministic Strategy Matrix (20 Strategies)</span>
                </span>
                <span className="text-[10px] text-stone-500">{snapshot.alignment.label}</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                {snapshot.strategies.map(s => (
                  <div
                    key={s.strategy_id}
                    onClick={() => setSelectedStrategyId(s.strategy_id)}
                    className={`p-2 rounded-lg border transition-all cursor-pointer ${
                      selectedStrategyId === s.strategy_id
                        ? 'bg-cyan-950/60 border-cyan-500 shadow-md'
                        : 'bg-stone-950/80 border-stone-800/90 hover:border-stone-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-white truncate max-w-[100px]">{s.strategy_name}</span>
                      <span className={`px-1.5 py-0.2 rounded text-[8px] font-black ${
                        s.state === 'ACTIVE' ? 'bg-emerald-950 text-emerald-300' :
                        s.state === 'PARTIAL' ? 'bg-amber-950 text-amber-300' :
                        s.state === 'CONFLICTED' ? 'bg-purple-950 text-purple-300' : 'bg-stone-900 text-stone-500'
                      }`}>
                        {s.state}
                      </span>
                    </div>
                    <div className="text-[9px] text-stone-500 mt-1">Rules: {s.passing_rules}/{s.total_rules} ({s.rule_coverage_pct}%)</div>
                  </div>
                ))}
              </div>

              {/* Selected Strategy Rule Detail Drawer */}
              {selectedStrategy && (
                <div className="p-3 bg-stone-950 border border-cyan-800/50 rounded-lg space-y-2 mt-2">
                  <div className="flex items-center justify-between border-b border-stone-800 pb-1.5 text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-cyan-300">{selectedStrategy.strategy_name}</span>
                      <span className="text-[9px] text-stone-500 font-mono">({selectedStrategy.category})</span>
                    </div>
                    <button onClick={() => setSelectedStrategyId(null)} className="text-stone-500 hover:text-white text-xs">✕</button>
                  </div>
                  <div className="text-[10px] text-stone-400">{selectedStrategy.description}</div>
                  <div className="space-y-1">
                    <div className="text-[9px] font-bold text-stone-400 uppercase">Exact Rule Math Evaluation:</div>
                    {selectedStrategy.rule_evaluations.map((r, i) => (
                      <div key={i} className="flex items-center justify-between text-[10px] p-1.5 bg-stone-900/60 rounded border border-stone-800">
                        <span className="text-stone-300 font-mono">{r.description}</span>
                        <div className="flex items-center gap-2">
                          {r.actual_value !== undefined && r.threshold_value !== undefined && (
                            <span className="text-[9px] text-stone-400 font-mono">
                              Val: {r.actual_value} | Thresh: {r.threshold_value}
                            </span>
                          )}
                          <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${
                            r.outcome === 'PASS' ? 'bg-emerald-950 text-emerald-300' : 'bg-rose-950 text-rose-300'
                          }`}>
                            {r.outcome}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Point-in-Time Fundamentals & Historical Analogues */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Fundamental Snapshot */}
              <div className="bg-[#12131b] border border-stone-800/90 rounded-xl p-3 space-y-2 shadow-xl">
                <div className="flex items-center justify-between border-b border-stone-800 pb-1.5 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white uppercase">PIT Fundamental Ratios</span>
                    <button onClick={() => setSelectedProvenanceMetric('return_on_equity')} className="text-[8px] text-cyan-400 hover:underline">Evidence</button>
                  </div>
                  <span className="text-[9px] text-emerald-400 font-bold">{snapshot.confluence.fundamental_state}</span>
                </div>
                <div className="grid grid-cols-2 gap-1.5 text-xs">
                  {snapshot.fundamentals.slice(0, 8).map((f, i) => (
                    <div key={i} className="p-1.5 bg-stone-950 border border-stone-800/80 rounded space-y-0.5">
                      <div className="text-[9px] text-stone-500 truncate">{f.metric_name}</div>
                      <div className="text-xs font-bold text-white">{f.display_value}</div>
                      <div className="text-[8px] text-stone-600">Pub: {f.publication_date}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Historical Analogue Search */}
              <div className="bg-[#12131b] border border-stone-800/90 rounded-xl p-3 space-y-2 shadow-xl">
                <div className="flex items-center justify-between border-b border-stone-800 pb-1.5 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white uppercase">Historical Analogue Search</span>
                    <button onClick={() => setSelectedProvenanceMetric('historical_analogues')} className="text-[8px] text-cyan-400 hover:underline">Evidence</button>
                  </div>
                  <span className="text-[9px] text-cyan-400 font-bold">{snapshot.historical_analogues.total_similar_observations} Matches</span>
                </div>
                <div className="text-[9px] text-stone-400">{snapshot.historical_analogues.disclaimer}</div>
                <div className="grid grid-cols-2 gap-1.5 text-xs">
                  <div className="p-1.5 bg-stone-950 border border-stone-800 rounded">
                    <div className="text-[9px] text-stone-500">+1 Bar Forward</div>
                    <div className="text-xs font-bold text-cyan-300">+{snapshot.historical_analogues.forward_1_bar_median}%</div>
                  </div>
                  <div className="p-1.5 bg-stone-950 border border-stone-800 rounded">
                    <div className="text-[9px] text-stone-500">+5 Bar Forward</div>
                    <div className="text-xs font-bold text-emerald-400">+{snapshot.historical_analogues.forward_5_bar_median}%</div>
                  </div>
                  <div className="p-1.5 bg-stone-950 border border-stone-800 rounded">
                    <div className="text-[9px] text-stone-500">+20 Bar Forward</div>
                    <div className="text-xs font-bold text-emerald-300">+{snapshot.historical_analogues.forward_20_bar_median}%</div>
                  </div>
                  <div className="p-1.5 bg-stone-950 border border-stone-800 rounded">
                    <div className="text-[9px] text-stone-500">Median MAE / MFE</div>
                    <div className="text-xs font-bold text-amber-300">{snapshot.historical_analogues.mae_median}% / {snapshot.historical_analogues.mfe_median}%</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Frozen Paper Validation Status & Contradiction Analysis */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Paper Validation Status */}
              <div className="bg-[#12131b] border border-cyan-800/40 rounded-xl p-3 space-y-2 shadow-xl">
                <div className="flex items-center justify-between border-b border-stone-800 pb-1.5 text-xs">
                  <div className="flex items-center gap-1.5">
                    <Lock className="w-3.5 h-3.5 text-cyan-400" />
                    <span className="font-bold text-white uppercase">Frozen Paper Hypothesis</span>
                    <button onClick={() => setSelectedProvenanceMetric('paper_validation')} className="text-[8px] text-cyan-400 hover:underline">Evidence</button>
                  </div>
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-black bg-amber-950 text-amber-300 border border-amber-500/60">
                    {snapshot.paper_status.decision}
                  </span>
                </div>
                <div className="text-xs font-bold text-cyan-300">
                  {snapshot.paper_status.hypothesis_id} v{snapshot.paper_status.version}
                </div>
                <div className="text-[10px] text-stone-400">
                  Progress: {snapshot.paper_status.trade_count} / {snapshot.paper_status.required_sample_size} Trades ({snapshot.paper_status.progress_pct}%)
                </div>
                <div className="text-[9px] text-stone-500 truncate font-mono">
                  SHA: {snapshot.paper_status.fingerprint.slice(0, 16)}...
                </div>
              </div>

              {/* Contradictions & Evidence */}
              <div className="bg-[#12131b] border border-stone-800/90 rounded-xl p-3 space-y-2 shadow-xl">
                <div className="flex items-center justify-between border-b border-stone-800 pb-1.5 text-xs">
                  <span className="font-bold text-white uppercase">Supporting & Contradicting Evidence</span>
                  <span className="text-[9px] text-stone-500">Forensic Audit</span>
                </div>
                <div className="space-y-1 text-[10px]">
                  {snapshot.contradictions.supporting_evidence.map((s, i) => (
                    <div key={i} className="text-emerald-300 flex items-center gap-1">
                      <span>✓</span> <span>{s}</span>
                    </div>
                  ))}
                  {snapshot.contradictions.contradicting_evidence.map((c, i) => (
                    <div key={i} className="text-amber-300 flex items-center gap-1">
                      <span>⚠</span> <span>{c}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Cross-Stock Comparison Table */}
            <div className="bg-[#12131b] border border-stone-800/90 rounded-xl p-3 space-y-2 shadow-xl">
              <div className="flex items-center justify-between border-b border-stone-800 pb-1.5 text-xs">
                <span className="font-bold text-white uppercase">Cross-Stock Research Comparison</span>
                <span className="text-[9px] text-stone-500">Top NSE Universe</span>
              </div>
              <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="border-b border-stone-800 text-stone-500 text-[9px] uppercase">
                      <th className="pb-1">Symbol</th>
                      <th className="pb-1">Price</th>
                      <th className="pb-1">Regime</th>
                      <th className="pb-1">Active Strats</th>
                      <th className="pb-1">Coverage</th>
                      <th className="pb-1">ROE</th>
                      <th className="pb-1">P/E</th>
                      <th className="pb-1 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-800/60 text-[10px]">
                    {snapshot.cross_stock.map((cs, idx) => (
                      <tr
                        key={idx}
                        onClick={() => handleSymbolChange(cs.symbol)}
                        className={`hover:bg-stone-900/60 cursor-pointer ${
                          cs.symbol === symbol ? 'bg-cyan-950/40 border-l-2 border-cyan-400' : ''
                        }`}
                      >
                        <td className="py-1 font-bold text-white">{cs.symbol}</td>
                        <td className="py-1 text-stone-300">₹{cs.price}</td>
                        <td className="py-1 text-stone-400">{cs.regime}</td>
                        <td className="py-1 text-cyan-300 font-bold">{cs.active_strategies}/20</td>
                        <td className="py-1 text-stone-300">{cs.rule_coverage_pct}%</td>
                        <td className="py-1 text-emerald-400">{cs.roe ? `${cs.roe}%` : '-'}</td>
                        <td className="py-1 text-amber-400">{cs.pe ? `${cs.pe}x` : '-'}</td>
                        <td className="py-1 text-right text-stone-400">{cs.research_status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Right 4 Cols: Command Center Copilot & Skeptic Mode */}
          <div className="lg:col-span-4 flex flex-col space-y-3">
            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3 flex flex-col h-full shadow-2xl">
              <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 mb-2">
                <div className="flex items-center gap-2 text-xs font-bold text-white">
                  <Sparkles className="w-4 h-4 text-cyan-400" />
                  <span>Command Center Copilot</span>
                </div>
                <button
                  onClick={() => handleCopilotSend(`CHALLENGE THIS STOCK (${symbol})`)}
                  className="px-2 py-0.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded text-[10px] font-bold flex items-center gap-1 cursor-pointer"
                >
                  <Flame className="w-3 h-3 text-rose-400" />
                  <span>Skeptic Audit</span>
                </button>
              </div>

              <div className="flex-1 space-y-2 overflow-y-auto custom-scrollbar max-h-[520px] text-xs">
                {copilotMessages.length === 0 ? (
                  <div className="text-center py-10 text-stone-500 text-xs space-y-2">
                    <MessageSquare className="w-8 h-8 mx-auto text-stone-600" />
                    <div>Ask what is happening in {symbol}, inspect active strategy rules, or challenge the thesis.</div>
                  </div>
                ) : (
                  copilotMessages.map((m, i) => (
                    <div key={i} className={`p-2.5 rounded-lg leading-relaxed ${m.role === 'user' ? 'bg-cyan-600 text-white ml-auto max-w-[85%]' : 'bg-[#181a24] text-stone-200 border border-stone-800'}`}>
                      <div className="whitespace-pre-wrap">{m.text}</div>
                    </div>
                  ))
                )}
                {isCopilotLoading && (
                  <div className="text-xs text-cyan-400 flex items-center gap-2">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Auditing Command Center evidence…</span>
                  </div>
                )}
              </div>

              <div className="pt-2 border-t border-stone-800/60 flex items-center gap-2">
                <input
                  type="text"
                  value={copilotInput}
                  onChange={e => setCopilotInput(e.target.value)}
                  placeholder={`Ask about ${symbol} evidence or rules…`}
                  className="flex-1 bg-stone-900 border border-stone-800 rounded px-2.5 py-1.5 text-xs text-stone-200 placeholder-stone-600 focus:outline-none"
                  onKeyDown={e => { if (e.key === 'Enter') handleCopilotSend(copilotInput); }}
                />
                <button
                  onClick={() => handleCopilotSend(copilotInput)}
                  className="p-1.5 bg-cyan-600 text-white rounded cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
