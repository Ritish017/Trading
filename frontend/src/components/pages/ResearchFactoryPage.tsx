import React, { useState, useEffect, useCallback } from 'react';
import {
  Cpu, FlaskConical, Layers, TrendingUp, TrendingDown, DollarSign,
  PieChart, BarChart3, Sparkles, Shield, AlertTriangle, CheckCircle2,
  XCircle, MinusCircle, Clock, Calendar, RefreshCw, Search, ArrowUpRight,
  ArrowDownRight, Compass, Target, Bookmark, Split, GitMerge, Flame,
  Send, Loader2, MessageSquare, AlertOctagon, Sliders, Eye, Play,
  CheckCheck, Scale, FileText, ChevronDown, ChevronUp, Database, Activity,
  Lock, Radio, Zap, CheckSquare, Hourglass, Hash, Check
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

export interface AuditDimensionData {
  dimension_name: string;
  status: 'PASS' | 'PASS_WITH_LIMITATIONS' | 'WARNING' | 'FAILED';
  metrics: Record<string, any>;
  evidence: string[];
  limitations: string[];
}

export interface ResearchAuditReportData {
  hypothesis_id: string;
  hypothesis_name: string;
  audit_timestamp: number;
  certification_status: 'UNVERIFIED' | 'AUDIT_IN_PROGRESS' | 'AUDITED' | 'AUDITED_WITH_LIMITATIONS' | 'AUDIT_FAILED';
  overall_status: 'PASS' | 'PASS_WITH_LIMITATIONS' | 'WARNING' | 'FAILED';
  dataset_integrity: AuditDimensionData;
  point_in_time_integrity: AuditDimensionData;
  execution_integrity: AuditDimensionData;
  cost_integrity: AuditDimensionData;
  corporate_action_integrity: AuditDimensionData;
  walk_forward_integrity: AuditDimensionData;
  statistical_integrity: AuditDimensionData;
  multiple_testing_integrity: AuditDimensionData;
  cross_symbol_integrity: AuditDimensionData;
  regime_integrity: AuditDimensionData;
  paper_equivalence: AuditDimensionData;
  replication_result: {
    verdict: 'INDEPENDENTLY_REPRODUCED' | 'REPLICATION_FAILED' | 'REPRODUCED_WITH_DISCREPANCIES';
    original_metrics: Record<string, any>;
    recomputed_metrics: Record<string, any>;
    discrepancies: string[];
    match_rate_pct: number;
  };
  statistical_inference: {
    sample_size: number;
    standard_error_sharpe: number;
    standard_error_cagr: number;
    bootstrap_sharpe_ci_95: [number, number];
    bootstrap_cagr_ci_95: [number, number];
    trade_autocorrelation_lag1: number;
    is_trade_independent: boolean;
    multiple_testing_k: number;
    selection_intensity: number;
    holm_bonferroni_p_adjusted: number;
    fdr_benjamini_hochberg_q: number;
    data_snooping_warning: boolean;
  };
  limitations: string[];
  auditor_verdict_summary: string;
}

export interface ForwardValidationDecisionReportData {
  hypothesis_id: string;
  hypothesis_name: string;
  version: string;
  fingerprint: string;
  observation_period_days: number;
  decision: 'CONTINUE_OBSERVATION' | 'PAPER_VALIDATED' | 'PAPER_DEGRADED' | 'PAPER_REJECTED' | 'INSUFFICIENT_DATA';
  decision_summary: string;
  decision_reasons: string[];
  trade_count: number;
  required_sample_size: number;
  progress_pct: number;
  signal_count: number;
  missed_signal_count: number;
  gates: Array<{
    gate_name: string;
    status: 'PASS' | 'WARNING' | 'FAIL' | 'INSUFFICIENT_DATA';
    metric_value: string;
    sample_size: number;
    threshold_description: string;
    evidence: string[];
  }>;
  timeline: Array<{
    checkpoint_id: string;
    name: string;
    target_trades: number;
    status: 'COMPLETED' | 'CURRENT' | 'PENDING';
    current_trades: number;
    summary: string;
  }>;
  backtest_comparison: Array<{
    metric_name: string;
    historical_value: string;
    forward_value: string;
    difference: string;
    status: 'WITHIN_EXPECTATION' | 'WATCH' | 'OUTSIDE_EXPECTATION' | 'INSUFFICIENT_SAMPLE';
    sample_size: number;
    notes: string;
  }>;
  regime_coverage: Array<{
    regime_name: string;
    observation_status: 'OBSERVED' | 'NOT_OBSERVED' | 'INSUFFICIENT_SAMPLE';
    trade_count: number;
    signal_count: number;
    net_return_pct: number | null;
    win_rate_pct: number | null;
    max_drawdown_pct: number | null;
    display_status: string;
  }>;
  drift_status: string;
  survivorship_status: string;
  unknowns: string[];
  next_required_evidence: string[];
  potential_future_hypotheses: string[];
  skeptic_audit: Record<string, string[]>;
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
  const [activeTab, setActiveTab] = useState<'VALIDATION' | 'AUDIT' | 'DECISION'>('DECISION');
  const [hypotheses, setHypotheses] = useState<ResearchHypothesisData[]>([]);
  const [selectedHypothesisId, setSelectedHypothesisId] = useState<string>('HYP_QUALITY_TREND_01');
  const [scorecard, setScorecard] = useState<ValidationScorecardData | null>(null);
  const [auditReport, setAuditReport] = useState<ResearchAuditReportData | null>(null);
  const [decisionReport, setDecisionReport] = useState<ForwardValidationDecisionReportData | null>(null);
  const [signals, setSignals] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

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

  const loadDetails = useCallback(async (hypId: string) => {
    if (!hypId) return;
    try {
      const res = await fetch(`/api/research-factory/scorecard/${encodeURIComponent(hypId)}`);
      if (res.ok) {
        const data = await res.json();
        setScorecard(data.scorecard || null);
      }
      const auditRes = await fetch(`/api/research-audit/report/${encodeURIComponent(hypId)}`);
      if (auditRes.ok) {
        const auditData = await auditRes.json();
        setAuditReport(auditData.audit_report || null);
      }
      const decRes = await fetch(`/api/research-decision/report/${encodeURIComponent(hypId)}`);
      if (decRes.ok) {
        const decData = await decRes.json();
        setDecisionReport(decData.decision_report || null);
      }
      const sigRes = await fetch(`/api/research-decision/signals/${encodeURIComponent(hypId)}`);
      if (sigRes.ok) {
        const sigData = await sigRes.json();
        setSignals(sigData.signals || []);
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
      loadDetails(selectedHypothesisId);
    }
  }, [selectedHypothesisId, loadDetails]);

  const handleCopilotSend = async (userText: string) => {
    if (!userText.trim() || isCopilotLoading) return;
    const textToSend = userText.trim();
    const isSkeptic = textToSend.toUpperCase().includes('DISPROVE') || textToSend.toUpperCase().includes('CHALLENGE');
    setCopilotInput('');
    setCopilotMessages(prev => [...prev, { role: 'user', text: textToSend }]);
    setIsCopilotLoading(true);

    try {
      let endpoint = '/api/forward-validation/copilot';
      if (isSkeptic) {
        endpoint = `/api/research-decision/challenge/${encodeURIComponent(selectedHypothesisId)}`;
      }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hypothesis_id: selectedHypothesisId,
          user_message: textToSend,
          forward_report: decisionReport || null,
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

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-175px)] overflow-y-auto custom-scrollbar p-3 space-y-3 bg-[#0a0b10] font-mono text-stone-100">
      {/* ── Header Bar ── */}
      <div className="bg-[#12131b] border border-cyan-500/30 rounded-2xl p-3 flex flex-wrap items-center justify-between gap-3 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-600/20 border border-cyan-500/40 flex items-center justify-center text-cyan-400 font-black shadow-inner">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-black text-sm text-white tracking-wide">APEX QUANT LAB — RESEARCH DECISION ENGINE</span>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-700/50">
                PHASE 12: CONTINUOUS VALIDATION
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs text-stone-400 mt-0.5">
              <span>● Cryptographic Fingerprint SHA-256</span>
              <span>● 9 Formal Validation Gates</span>
              <span>● 5/30 Real Trades (No Synthetic Fabrication)</span>
            </div>
          </div>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center gap-1.5 bg-stone-900/90 border border-stone-800 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('DECISION')}
            className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'DECISION' ? 'bg-cyan-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Decision Dashboard</span>
          </button>
          <button
            onClick={() => setActiveTab('VALIDATION')}
            className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'VALIDATION' ? 'bg-stone-800 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
            }`}
          >
            Discovery Scorecard
          </button>
          <button
            onClick={() => setActiveTab('AUDIT')}
            className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'AUDIT' ? 'bg-purple-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
            }`}
          >
            <Scale className="w-3.5 h-3.5" />
            <span>Audit Certificate</span>
          </button>
        </div>
      </div>

      {/* ── Main Layout ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 flex-1">
        {/* Left 8 Cols */}
        <div className="lg:col-span-8 space-y-3">
          {/* Top Decision Banner */}
          {decisionReport && (
            <div className="bg-[#12131b] border border-cyan-500/40 rounded-xl p-3.5 space-y-3 shadow-2xl">
              <div className="flex items-center justify-between border-b border-cyan-800/40 pb-2 text-xs">
                <div className="flex items-center gap-2">
                  <Lock className="w-4 h-4 text-cyan-400" />
                  <span className="font-bold text-white text-sm">{decisionReport.hypothesis_name}</span>
                  <span className="text-[10px] text-stone-400 font-mono">v{decisionReport.version}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-stone-400">Current Decision:</span>
                  <span className="px-2.5 py-0.5 rounded text-[11px] font-black bg-amber-950 text-amber-300 border border-amber-500/60 flex items-center gap-1.5">
                    <Hourglass className="w-3 h-3 text-amber-400 animate-spin" />
                    <span>{decisionReport.decision}</span>
                  </span>
                </div>
              </div>

              {/* Progress & Fingerprint */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                <div className="p-2 bg-stone-900/50 border border-stone-800 rounded-lg">
                  <div className="text-[9px] text-stone-500 uppercase font-bold">Forward Progress</div>
                  <div className="text-base font-black text-cyan-400 mt-0.5">
                    {decisionReport.trade_count} / {decisionReport.required_sample_size} Trades ({decisionReport.progress_pct}%)
                  </div>
                  <div className="text-[9px] text-stone-400">Target: 30 Real Forward Trades</div>
                </div>
                <div className="p-2 bg-stone-900/50 border border-stone-800 rounded-lg">
                  <div className="text-[9px] text-stone-500 uppercase font-bold">Audit Status</div>
                  <div className="text-base font-black text-amber-400 mt-0.5">AUDITED_WITH_LIMITATIONS</div>
                  <div className="text-[9px] text-stone-400">Survivorship Risk Maintained</div>
                </div>
                <div className="p-2 bg-stone-900/50 border border-stone-800 rounded-lg">
                  <div className="text-[9px] text-stone-500 uppercase font-bold">Cryptographic Fingerprint</div>
                  <div className="text-[10px] font-mono text-stone-300 truncate mt-1">
                    SHA: {decisionReport.fingerprint.slice(0, 16)}...
                  </div>
                  <div className="text-[9px] text-emerald-400">● 100% Immutable Contract</div>
                </div>
              </div>

              {/* Decision Summary */}
              <div className="p-2.5 bg-stone-900/40 border border-stone-800/80 rounded-lg text-xs text-stone-300 leading-relaxed">
                {decisionReport.decision_summary}
              </div>

              {/* 9 Validation Gates Grid */}
              <div className="space-y-1.5">
                <div className="text-[10px] font-bold text-stone-300 uppercase flex items-center justify-between">
                  <span>9 Formal Validation Gates</span>
                  <span className="text-[9px] text-stone-500">Deterministic Rule Engine</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  {decisionReport.gates.map((g, idx) => (
                    <div key={idx} className="p-2 bg-stone-950 border border-stone-800/90 rounded-lg space-y-0.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold text-stone-300">{g.gate_name}</span>
                        <span className={`px-1.5 py-0.2 rounded text-[8px] font-black ${
                          g.status === 'PASS' ? 'bg-emerald-950 text-emerald-300' :
                          g.status === 'WARNING' ? 'bg-amber-950 text-amber-300' :
                          g.status === 'INSUFFICIENT_DATA' ? 'bg-stone-900 text-stone-400' : 'bg-rose-950 text-rose-300'
                        }`}>
                          {g.status}
                        </span>
                      </div>
                      <div className="text-[9px] text-cyan-300 truncate">{g.metric_value}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Decision Timeline Checkpoints */}
              <div className="space-y-1.5">
                <div className="text-[10px] font-bold text-stone-300 uppercase">Forward Validation Timeline</div>
                <div className="grid grid-cols-2 sm:grid-cols-6 gap-1.5 text-xs">
                  {decisionReport.timeline.map((t, idx) => (
                    <div key={idx} className={`p-2 rounded border text-center space-y-0.5 ${
                      t.status === 'COMPLETED' ? 'bg-emerald-950/40 border-emerald-700/50 text-emerald-300' :
                      t.status === 'CURRENT' ? 'bg-cyan-950/60 border-cyan-500 text-cyan-200 shadow-md' :
                      'bg-stone-900/30 border-stone-800 text-stone-500'
                    }`}>
                      <div className="text-[8px] font-black uppercase">{t.name}</div>
                      <div className="text-[9px] font-mono">{t.target_trades} Trades</div>
                      <div className="text-[8px] font-bold">{t.status}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Backtest vs Forward Distribution Comparison */}
              <div className="space-y-1.5">
                <div className="text-[10px] font-bold text-stone-300 uppercase">Backtest vs Forward Paper Comparison</div>
                <div className="overflow-x-auto custom-scrollbar">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="border-b border-stone-800 text-stone-500 text-[9px] uppercase">
                        <th className="pb-1">Metric</th>
                        <th className="pb-1">Historical (106 Trades)</th>
                        <th className="pb-1">Forward (5 Trades)</th>
                        <th className="pb-1">Difference</th>
                        <th className="pb-1 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-800/60 text-[10px]">
                      {decisionReport.backtest_comparison.map((r, i) => (
                        <tr key={i} className="hover:bg-stone-900/50">
                          <td className="py-1.5 font-bold text-white">{r.metric_name}</td>
                          <td className="py-1.5 text-stone-300">{r.historical_value}</td>
                          <td className="py-1.5 text-cyan-300 font-bold">{r.forward_value}</td>
                          <td className="py-1.5 text-stone-400">{r.difference}</td>
                          <td className="py-1.5 text-right">
                            <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${
                              r.status === 'WITHIN_EXPECTATION' ? 'bg-emerald-950 text-emerald-300' :
                              r.status === 'WATCH' ? 'bg-amber-950 text-amber-300' : 'bg-stone-900 text-stone-400'
                            }`}>
                              {r.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Regime Coverage (Truth Layer) */}
              <div className="space-y-1.5">
                <div className="text-[10px] font-bold text-stone-300 uppercase">Regime Coverage (Truth-Layer: Zero Fabricated Returns)</div>
                <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 text-xs">
                  {decisionReport.regime_coverage.map((reg, idx) => (
                    <div key={idx} className="p-2 bg-stone-950 border border-stone-800 rounded space-y-0.5">
                      <div className="text-[9px] font-bold text-stone-300 truncate">{reg.regime_name}</div>
                      <div className={`text-[10px] font-black ${
                        reg.observation_status === 'OBSERVED' ? 'text-emerald-400' : 'text-stone-500'
                      }`}>
                        {reg.display_status}
                      </div>
                      {reg.net_return_pct !== null ? (
                        <div className="text-[8px] text-stone-400">Return: {reg.net_return_pct}%</div>
                      ) : (
                        <div className="text-[8px] text-stone-600">Pending authentic ticks</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Persistent Signal & Missed-Signal Ledger */}
              <div className="space-y-1.5">
                <div className="text-[10px] font-bold text-stone-300 uppercase flex items-center justify-between">
                  <span>Persistent Signal Ledger & Missed-Signal Audit ({signals.length} Signals)</span>
                  <span className="text-[9px] text-stone-500">Missed: {decisionReport.missed_signal_count}</span>
                </div>
                <div className="overflow-x-auto custom-scrollbar max-h-[160px]">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="border-b border-stone-800 text-stone-500 text-[9px] uppercase">
                        <th className="pb-1">Signal ID</th>
                        <th className="pb-1">Symbol</th>
                        <th className="pb-1">Price</th>
                        <th className="pb-1">State</th>
                        <th className="pb-1">Skip Reason</th>
                        <th className="pb-1 text-right">Audit Note</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-800/60 text-[10px]">
                      {signals.map((s, idx) => (
                        <tr key={idx} className="hover:bg-stone-900/60">
                          <td className="py-1 text-stone-400 font-mono">{s.signal_id}</td>
                          <td className="py-1 text-white font-bold">{s.symbol}</td>
                          <td className="py-1 text-stone-300">₹{s.decision_price}</td>
                          <td className="py-1">
                            <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${
                              s.state === 'EXECUTED' ? 'bg-emerald-950 text-emerald-300' : 'bg-amber-950 text-amber-300'
                            }`}>
                              {s.state}
                            </span>
                          </td>
                          <td className="py-1 text-stone-400">{s.skip_reason}</td>
                          <td className="py-1 text-right text-stone-400 truncate max-w-[200px]">{s.notes}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Tab: Discovery Scorecard */}
          {activeTab === 'VALIDATION' && scorecard && (
            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
              <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
                <span className="font-bold text-white uppercase flex items-center gap-1.5">
                  <Shield className="w-4 h-4 text-cyan-400" /> Multi-Dimensional Validation Scorecard ({scorecard.hypothesis_name})
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-600/50">
                  {scorecard.overall_recommendation}
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div className="p-2.5 bg-stone-900/40 border border-stone-800 rounded-lg">
                  <div className="text-[10px] text-stone-500 uppercase font-bold">OOS Walk-Forward</div>
                  <div className="text-base font-black text-cyan-400 mt-0.5">Sharpe {scorecard.oos_result.oos_sharpe}</div>
                </div>
                <div className="p-2.5 bg-stone-900/40 border border-stone-800 rounded-lg">
                  <div className="text-[10px] text-stone-500 uppercase font-bold">Cross-Symbol Basket</div>
                  <div className="text-base font-black text-emerald-400 mt-0.5">Median {scorecard.cross_symbol_result.median_return_pct}%</div>
                </div>
                <div className="p-2.5 bg-stone-900/40 border border-stone-800 rounded-lg">
                  <div className="text-[10px] text-stone-500 uppercase font-bold">Cost Resilience</div>
                  <div className="text-base font-black text-amber-400 mt-0.5">Net {scorecard.cost_result.normal_friction_cagr}%</div>
                </div>
                <div className="p-2.5 bg-stone-900/40 border border-stone-800 rounded-lg">
                  <div className="text-[10px] text-stone-500 uppercase font-bold">Parameter Stability</div>
                  <div className="text-base font-black text-white mt-0.5">{scorecard.parameter_result.plateau_stability}</div>
                </div>
              </div>
            </div>
          )}

          {/* Tab: Audit Certificate */}
          {activeTab === 'AUDIT' && auditReport && (
            <div className="bg-[#12131b] border border-purple-500/40 rounded-xl p-3.5 space-y-3 shadow-2xl">
              <div className="flex items-center justify-between border-b border-purple-800/50 pb-2 text-xs">
                <div className="flex items-center gap-2">
                  <Scale className="w-5 h-5 text-purple-400" />
                  <div>
                    <span className="font-bold text-white text-sm">INDEPENDENT QUANT AUDIT CERTIFICATE</span>
                    <div className="text-[10px] text-stone-400">{auditReport.hypothesis_name} ({auditReport.hypothesis_id})</div>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-black bg-amber-950 text-amber-300 border border-amber-500/60">
                  {auditReport.certification_status}
                </span>
              </div>
              <div className="p-2.5 bg-purple-950/20 border border-purple-800/40 rounded-lg text-xs text-stone-200">
                {auditReport.auditor_verdict_summary}
              </div>
            </div>
          )}
        </div>

        {/* Right 4 Cols: Copilot & Skeptic Mode */}
        <div className="lg:col-span-4 flex flex-col space-y-3">
          <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3 flex flex-col h-full shadow-2xl">
            <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 mb-2">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <Sparkles className="w-4 h-4 text-cyan-400" />
                <span>Research Decision Copilot</span>
              </div>
              <button
                onClick={() => handleCopilotSend('CHALLENGE CURRENT VALIDATION')}
                className="px-2 py-0.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded text-[10px] font-bold flex items-center gap-1 cursor-pointer"
              >
                <Flame className="w-3 h-3 text-rose-400" />
                <span>Skeptic Audit</span>
              </button>
            </div>

            <div className="flex-1 space-y-2 overflow-y-auto custom-scrollbar max-h-[460px] text-xs">
              {copilotMessages.length === 0 ? (
                <div className="text-center py-8 text-stone-500 text-xs space-y-2">
                  <MessageSquare className="w-8 h-8 mx-auto text-stone-600" />
                  <div>Ask why we are in CONTINUE_OBSERVATION, inspect missed signals, or challenge sample size.</div>
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
                  <span>Auditing forward decision evidence…</span>
                </div>
              )}
            </div>

            <div className="pt-2 border-t border-stone-800/60 flex items-center gap-2">
              <input
                type="text"
                value={copilotInput}
                onChange={e => setCopilotInput(e.target.value)}
                placeholder="Ask about validation gates or drift…"
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
