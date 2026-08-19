import React, { useState, useEffect, useCallback } from 'react';
import {
  Cpu, FlaskConical, Layers, TrendingUp, TrendingDown, DollarSign,
  PieChart, BarChart3, Sparkles, Shield, AlertTriangle, CheckCircle2,
  XCircle, MinusCircle, Clock, Calendar, RefreshCw, Search, ArrowUpRight,
  ArrowDownRight, Compass, Target, Bookmark, Split, GitMerge, Flame,
  Send, Loader2, MessageSquare, AlertOctagon, Sliders, Eye, Play
} from 'lucide-react';
import { NSEStock } from '../../types/indianMarket';

export interface ResearchHypothesisData {
  hypothesis_id: string;
  name: string;
  version: string;
  description: string;
  category: string;
  technical_dependencies: string[];
  fundamental_dependencies: string[];
  regime_filter?: string | null;
  entry_conditions: string[];
  exit_conditions: string[];
  timeframe: string;
  universe: string[];
  status: string;
  rejection_reasons: string[];
  rejection_notes?: string | null;
  k_tested: number;
}

export interface ValidationScorecardData {
  hypothesis_id: string;
  hypothesis_name: string;
  sample_size: number;
  benchmark_beat_pct: number;
  oos_result: {
    is_return_pct: number;
    oos_return_pct: number;
    is_sharpe: number;
    oos_sharpe: number;
    is_max_drawdown_pct: number;
    oos_max_drawdown_pct: number;
    is_trade_count: number;
    oos_trade_count: number;
    oos_degradation_pct: number;
    is_validated: boolean;
  };
  cross_symbol_result: {
    median_return_pct: number;
    mean_return_pct: number;
    iqr_return_pct: number;
    std_return_pct: number;
    winning_symbols_count: number;
    losing_symbols_count: number;
    best_symbol: string;
    worst_symbol: string;
    is_generalizable: boolean;
  };
  regime_result: {
    regime_returns: Record<string, number>;
    regime_sharpes: Record<string, number>;
    regime_win_rates: Record<string, number>;
    regime_trade_counts: Record<string, number>;
    is_regime_resilient: boolean;
    weakest_regime: string;
  };
  cost_result: {
    zero_friction_cagr: number;
    normal_friction_cagr: number;
    high_friction_cagr: number;
    triple_friction_cagr: number;
    cost_drag_pct: number;
    is_cost_resilient: boolean;
  };
  parameter_result: {
    plateau_stability: string;
    neighborhood_variance_pct: number;
    is_robust: boolean;
  };
  redundancy_index: number;
  multiple_testing_k: number;
  multiple_testing_risk: string;
  research_decay_status: string;
  overall_recommendation: string;
  falsification_criteria: string[];
}

export interface ResearchFactoryPageProps {
  stocks: NSEStock[];
  selectedSymbol: string;
  onSelectSymbol?: (symbol: string) => void;
}

export const ResearchFactoryPage: React.FC<ResearchFactoryPageProps> = ({
  stocks,
  selectedSymbol,
  onSelectSymbol,
}) => {
  const [hypotheses, setHypotheses] = useState<ResearchHypothesisData[]>([]);
  const [selectedHypothesisId, setSelectedHypothesisId] = useState<string>('');
  const [scorecard, setScorecard] = useState<ValidationScorecardData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // New Experiment Builder State
  const [builderName, setBuilderName] = useState<string>('Custom Momentum Quality');
  const [builderStrategy, setBuilderStrategy] = useState<string>('EMA_TREND_MOMENTUM');
  const [builderFactor, setBuilderFactor] = useState<string>('PROFITABILITY_ROE');
  const [builderRegime, setBuilderRegime] = useState<string>('TRENDING_BULLISH');
  const [builderK, setBuilderK] = useState<number>(1);

  // Live Observation State
  const [liveObs, setLiveObs] = useState<any>(null);

  // Copilot State
  const [copilotMessages, setCopilotMessages] = useState<Array<{ role: string; text: string }>>([]);
  const [copilotInput, setCopilotInput] = useState<string>('');
  const [isCopilotLoading, setIsCopilotLoading] = useState<boolean>(false);

  const loadHypotheses = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/research-factory/hypotheses');
      if (res.ok) {
        const data = await res.json();
        const list = data.hypotheses || [];
        setHypotheses(list);
        if (list.length > 0 && !selectedHypothesisId) {
          setSelectedHypothesisId(list[0].hypothesis_id);
        }
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, [selectedHypothesisId]);

  const loadScorecard = useCallback(async (hypId: string) => {
    if (!hypId) return;
    try {
      const res = await fetch(`/api/research-factory/scorecard/${encodeURIComponent(hypId)}`);
      if (res.ok) {
        const data = await res.json();
        setScorecard(data.scorecard || null);
      }
      const obsRes = await fetch(`/api/research-factory/live-observation/${encodeURIComponent(hypId)}`);
      if (obsRes.ok) {
        const obsData = await obsRes.json();
        setLiveObs(obsData);
      }
    } catch (e) {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadHypotheses();
  }, [loadHypotheses]);

  useEffect(() => {
    if (selectedHypothesisId) {
      loadScorecard(selectedHypothesisId);
    }
  }, [selectedHypothesisId, loadScorecard]);

  const handleGenerateCustom = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/research-factory/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: builderName,
          technical_strategy_id: builderStrategy,
          fundamental_factor_id: builderFactor,
          regime_filter: builderRegime,
          k_batch_size: builderK,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        await loadHypotheses();
        setSelectedHypothesisId(data.hypothesis.hypothesis_id);
      }
    } catch (e) {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  const handlePromote = async (hypId: string) => {
    try {
      const res = await fetch(`/api/research-factory/promote/${encodeURIComponent(hypId)}`, { method: 'POST' });
      if (res.ok) {
        await loadHypotheses();
        if (selectedHypothesisId === hypId) loadScorecard(hypId);
      }
    } catch (e) {
      // ignore
    }
  };

  const handleReject = async (hypId: string) => {
    try {
      const res = await fetch(`/api/research-factory/reject/${encodeURIComponent(hypId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reasons: ['HIGH_COST_DRAG', 'OOS_FAILURE'], notes: 'Manual rejection by researcher.' }),
      });
      if (res.ok) {
        await loadHypotheses();
        if (selectedHypothesisId === hypId) loadScorecard(hypId);
      }
    } catch (e) {
      // ignore
    }
  };

  const handleCopilotSend = async (userText: string) => {
    if (!userText.trim() || isCopilotLoading) return;
    const textToSend = userText.trim();
    const isSkeptic = textToSend.toUpperCase().includes('CHALLENGE');
    setCopilotInput('');
    setCopilotMessages(prev => [...prev, { role: 'user', text: textToSend }]);
    setIsCopilotLoading(true);

    const currHyp = hypotheses.find(h => h.hypothesis_id === selectedHypothesisId);

    try {
      const endpoint = isSkeptic ? `/api/research-factory/challenge/${encodeURIComponent(selectedHypothesisId)}` : '/api/research-factory/copilot';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hypothesis_id: selectedHypothesisId,
          user_message: textToSend,
          hypothesis: currHyp || null,
          scorecard: scorecard || null,
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

  const currentHyp = hypotheses.find(h => h.hypothesis_id === selectedHypothesisId);

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-175px)] overflow-y-auto custom-scrollbar p-3 space-y-3 bg-[#0a0b10] font-mono text-stone-100">
      {/* ── Header ── */}
      <div className="bg-[#12131b] border border-cyan-500/30 rounded-2xl p-3 flex flex-wrap items-center justify-between gap-3 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-600/20 border border-cyan-500/40 flex items-center justify-center text-cyan-400 font-black shadow-inner">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-black text-sm text-white tracking-wide">RESEARCH FACTORY</span>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-700/50">
                P-HACKING & LOOKAHEAD PROTECTED
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs text-stone-400 mt-0.5">
              <span>Multiple Testing Factor (K) Tracked</span>
              <span>● Out-of-Sample Walk-Forward Isolation</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Experiment Builder ── */}
      <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3 space-y-2.5">
        <div className="flex items-center justify-between text-xs border-b border-stone-800/60 pb-1.5">
          <span className="font-bold text-white flex items-center gap-1.5">
            <Sliders className="w-4 h-4 text-cyan-400" /> Quantitative Experiment Builder (Bounded Search Space)
          </span>
          <span className="text-[10px] text-stone-400">Search Space Bounded: K ≤ 50</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-5 gap-2.5 text-xs">
          <div>
            <label className="text-[10px] text-stone-500 block mb-1 font-bold">Hypothesis Name</label>
            <input
              type="text"
              value={builderName}
              onChange={e => setBuilderName(e.target.value)}
              className="w-full bg-stone-900 border border-stone-800 rounded px-2 py-1 text-xs text-white"
            />
          </div>
          <div>
            <label className="text-[10px] text-stone-500 block mb-1 font-bold">Technical Strategy</label>
            <select
              value={builderStrategy}
              onChange={e => setBuilderStrategy(e.target.value)}
              className="w-full bg-stone-900 border border-stone-800 rounded px-2 py-1 text-xs text-white"
            >
              <option value="EMA_TREND_MOMENTUM">EMA Trend Momentum</option>
              <option value="RSI_MEAN_REVERSION">RSI Mean Reversion</option>
              <option value="BB_SQUEEZE_BREAKOUT">Bollinger Bands Squeeze</option>
              <option value="MACD_ZERO_CROSS">MACD Zero Cross</option>
              <option value="VWAP_PULLBACK">VWAP Pullback</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] text-stone-500 block mb-1 font-bold">Fundamental Factor</label>
            <select
              value={builderFactor}
              onChange={e => setBuilderFactor(e.target.value)}
              className="w-full bg-stone-900 border border-stone-800 rounded px-2 py-1 text-xs text-white"
            >
              <option value="PROFITABILITY_ROE">ROE Profitability</option>
              <option value="VALUATION_PE">P/E Valuation Multiple</option>
              <option value="GROWTH_REVENUE_YOY">YoY Revenue Growth</option>
              <option value="CASHFLOW_FCF_CONVERSION">FCF Conversion Quality</option>
              <option value="LEVERAGE_DEBT_TO_EQUITY">Low Debt/Equity</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] text-stone-500 block mb-1 font-bold">Regime Filter</label>
            <select
              value={builderRegime}
              onChange={e => setBuilderRegime(e.target.value)}
              className="w-full bg-stone-900 border border-stone-800 rounded px-2 py-1 text-xs text-white"
            >
              <option value="TRENDING_BULLISH">Trending Bullish</option>
              <option value="RANGE_BOUND">Range Bound</option>
              <option value="HIGH_VOLATILITY">High Volatility</option>
              <option value="BULLISH_ACCUMULATION">Bullish Accumulation</option>
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={handleGenerateCustom}
              className="w-full py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded font-bold text-xs flex items-center justify-center gap-1.5 cursor-pointer shadow-md"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Run Empirical Validation</span>
            </button>
          </div>
        </div>
      </div>

      {/* ── Main Discovery & Scorecard Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 flex-1">
        {/* Left: Discovery Table & Hypothesis Details */}
        <div className="lg:col-span-8 space-y-3">
          {/* Discovery Table */}
          <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3 space-y-2">
            <div className="flex items-center justify-between text-xs border-b border-stone-800/60 pb-1.5">
              <span className="font-bold text-white uppercase">Research Discovery Table</span>
              <span className="text-[10px] text-stone-500">{hypotheses.length} Candidate Hypotheses Tracked</span>
            </div>

            <div className="overflow-x-auto custom-scrollbar">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-stone-800 text-stone-500 text-[10px] uppercase">
                    <th className="pb-1.5 font-bold">Hypothesis</th>
                    <th className="pb-1.5 font-bold">Category</th>
                    <th className="pb-1.5 font-bold">K (Tests)</th>
                    <th className="pb-1.5 font-bold">Status</th>
                    <th className="pb-1.5 font-bold text-right pr-2">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-800/60 text-[11px]">
                  {hypotheses.map(h => (
                    <tr
                      key={h.hypothesis_id}
                      onClick={() => setSelectedHypothesisId(h.hypothesis_id)}
                      className={`hover:bg-stone-900/60 cursor-pointer transition-all ${
                        selectedHypothesisId === h.hypothesis_id ? 'bg-cyan-950/40 border-l-2 border-cyan-400' : ''
                      }`}
                    >
                      <td className="py-2 font-bold text-white">
                        <div>{h.name}</div>
                        <div className="text-[9px] text-stone-400">{h.description}</div>
                      </td>
                      <td className="py-2 text-stone-300 text-[10px]">{h.category}</td>
                      <td className="py-2 text-cyan-400 font-bold">{h.k_tested}</td>
                      <td className="py-2">
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                          h.status === 'RESEARCH_CANDIDATE' ? 'bg-emerald-950 text-emerald-300 border border-emerald-700/50' :
                          h.status === 'PAPER_TESTING' ? 'bg-amber-950 text-amber-300 border border-amber-700/50' :
                          h.status === 'REJECTED' ? 'bg-rose-950 text-rose-300 border border-rose-700/50' : 'bg-stone-900 text-stone-400'
                        }`}>
                          {h.status}
                        </span>
                      </td>
                      <td className="py-2 text-right pr-2">
                        {h.status === 'RESEARCH_CANDIDATE' && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handlePromote(h.hypothesis_id); }}
                            className="px-2 py-0.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[9px] font-bold cursor-pointer"
                          >
                            Promote
                          </button>
                        )}
                        {h.status !== 'REJECTED' && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleReject(h.hypothesis_id); }}
                            className="ml-1.5 px-2 py-0.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded text-[9px] font-bold cursor-pointer"
                          >
                            Reject
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Validation Scorecard */}
          {scorecard && (
            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
              <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
                <span className="font-bold text-white uppercase flex items-center gap-1.5">
                  <Shield className="w-4 h-4 text-cyan-400" /> Multi-Dimensional Validation Scorecard ({scorecard.hypothesis_name})
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  scorecard.overall_recommendation === 'PROMOTABLE_CANDIDATE' ? 'bg-emerald-950 text-emerald-300 border border-emerald-600/50' : 'bg-rose-950 text-rose-300 border border-rose-600/50'
                }`}>
                  {scorecard.overall_recommendation}
                </span>
              </div>

              {/* 5 Dimensional Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                <div className="p-2.5 bg-stone-900/40 border border-stone-800 rounded-lg">
                  <div className="text-[10px] text-stone-500 uppercase font-bold">OOS Walk-Forward</div>
                  <div className="text-base font-black text-cyan-400 mt-0.5">Sharpe {scorecard.oos_result.oos_sharpe}</div>
                  <div className="text-[10px] text-stone-400">Degradation: {scorecard.oos_result.oos_degradation_pct}%</div>
                </div>
                <div className="p-2.5 bg-stone-900/40 border border-stone-800 rounded-lg">
                  <div className="text-[10px] text-stone-500 uppercase font-bold">Cross-Symbol Basket</div>
                  <div className="text-base font-black text-emerald-400 mt-0.5">Median {scorecard.cross_symbol_result.median_return_pct}%</div>
                  <div className="text-[10px] text-stone-400">IQR: {scorecard.cross_symbol_result.iqr_return_pct}%</div>
                </div>
                <div className="p-2.5 bg-stone-900/40 border border-stone-800 rounded-lg">
                  <div className="text-[10px] text-stone-500 uppercase font-bold">Cost Resilience</div>
                  <div className="text-base font-black text-amber-400 mt-0.5">Net {scorecard.cost_result.normal_friction_cagr}%</div>
                  <div className="text-[10px] text-stone-400">Drag: {scorecard.cost_result.cost_drag_pct}%</div>
                </div>
                <div className="p-2.5 bg-stone-900/40 border border-stone-800 rounded-lg">
                  <div className="text-[10px] text-stone-500 uppercase font-bold">Parameter Stability</div>
                  <div className="text-base font-black text-white mt-0.5">{scorecard.parameter_result.plateau_stability}</div>
                  <div className="text-[10px] text-stone-400">Variance: {scorecard.parameter_result.neighborhood_variance_pct}%</div>
                </div>
              </div>

              {/* Falsification Criteria */}
              <div className="p-2.5 bg-stone-900/30 border border-stone-800/60 rounded-lg text-xs space-y-1">
                <div className="text-[10px] text-stone-400 font-bold uppercase">Empirical Falsification Criteria:</div>
                {scorecard.falsification_criteria.map((crit, idx) => (
                  <div key={idx} className="text-stone-300 text-[11px]">● {crit}</div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Copilot & Skeptic Mode */}
        <div className="lg:col-span-4 flex flex-col space-y-3">
          <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3 flex flex-col h-full shadow-2xl">
            <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 mb-2">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <Sparkles className="w-4 h-4 text-cyan-400" />
                <span>Research Copilot</span>
              </div>
              <button
                onClick={() => handleCopilotSend('CHALLENGE THIS HYPOTHESIS')}
                className="px-2 py-0.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded text-[10px] font-bold flex items-center gap-1 cursor-pointer"
              >
                <Flame className="w-3 h-3 text-rose-400" />
                <span>Skeptic Audit</span>
              </button>
            </div>

            <div className="flex-1 space-y-2 overflow-y-auto custom-scrollbar max-h-[420px] text-xs">
              {copilotMessages.length === 0 ? (
                <div className="text-center py-6 text-stone-500 text-xs space-y-2">
                  <MessageSquare className="w-8 h-8 mx-auto text-stone-600" />
                  <div>Ask why this hypothesis was promoted/rejected, or launch a Skeptic Audit to probe for P-Hacking.</div>
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
                  <span>Auditing hypothesis evidence…</span>
                </div>
              )}
            </div>

            <div className="pt-2 border-t border-stone-800/60 flex items-center gap-2">
              <input
                type="text"
                value={copilotInput}
                onChange={e => setCopilotInput(e.target.value)}
                placeholder="Ask or Challenge hypothesis…"
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
    </div>
  );
};
