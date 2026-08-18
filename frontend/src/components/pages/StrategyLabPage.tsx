import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  FlaskConical, Search, Zap, CheckCircle2, XCircle, AlertTriangle,
  MinusCircle, RefreshCw, ChevronRight, Cpu, Activity, BarChart3,
  TrendingUp, TrendingDown, Info, MessageSquare, Send, Loader2,
  Shield, Clock, Database, BookOpen
} from 'lucide-react';
import { NSEStock } from '../../types/indianMarket';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type RuleOutcome = 'PASS' | 'FAIL' | 'UNAVAILABLE';
type StrategyState = 'ACTIVE' | 'PARTIAL' | 'INACTIVE' | 'CONFLICTED' | 'UNAVAILABLE' | 'STALE';

interface RuleEvaluation {
  rule_id: string;
  label: string;
  dependency_keys: string[];
  outcome: RuleOutcome;
  actual_value: number | null;
  actual_value_label: string;
  is_entry_rule: boolean;
}

interface StrategyEvaluationResult {
  strategy_id: string;
  strategy_name: string;
  category: string;
  description: string;
  state: StrategyState;
  entry_rules_total: number;
  entry_rules_passing: number;
  entry_rules_unavailable: number;
  exit_rules_triggered: number;
  exit_rules_total: number;
  rule_evaluations: RuleEvaluation[];
  feature_vector: Record<string, number>;
  data_freshness: string;
  evaluated_at: string;
  candles_used: number;
  tags: string[];
}

interface CopilotMessage {
  role: 'user' | 'assistant';
  text: string;
  evidence_cited?: string[];
}

interface StrategyLabPageProps {
  stocks: NSEStock[];
  selectedSymbol: string;
  onSelectSymbol?: (symbol: string) => void;
}

// ---------------------------------------------------------------------------
// State Badge
// ---------------------------------------------------------------------------
const STATE_CONFIG: Record<StrategyState, { label: string; bg: string; border: string; text: string; dot: string; icon: React.FC<any> }> = {
  ACTIVE:      { label: 'ACTIVE',      bg: 'bg-emerald-500/15', border: 'border-emerald-500/40', text: 'text-emerald-400',  dot: 'bg-emerald-400',  icon: CheckCircle2   },
  PARTIAL:     { label: 'PARTIAL',     bg: 'bg-amber-500/15',   border: 'border-amber-500/40',   text: 'text-amber-400',    dot: 'bg-amber-400',    icon: AlertTriangle  },
  INACTIVE:    { label: 'INACTIVE',    bg: 'bg-stone-700/30',   border: 'border-stone-600/40',   text: 'text-stone-400',    dot: 'bg-stone-500',    icon: MinusCircle    },
  CONFLICTED:  { label: 'CONFLICTED',  bg: 'bg-orange-500/15',  border: 'border-orange-500/40',  text: 'text-orange-400',   dot: 'bg-orange-400',   icon: AlertTriangle  },
  UNAVAILABLE: { label: 'UNAVAILABLE', bg: 'bg-rose-900/20',    border: 'border-rose-700/40',    text: 'text-rose-400',     dot: 'bg-rose-500',     icon: XCircle        },
  STALE:       { label: 'STALE',       bg: 'bg-purple-900/20',  border: 'border-purple-700/40',  text: 'text-purple-400',   dot: 'bg-purple-500',   icon: Clock          },
};

function StateBadge({ state, size = 'md' }: { state: StrategyState; size?: 'sm' | 'md' }) {
  const cfg = STATE_CONFIG[state] || STATE_CONFIG.UNAVAILABLE;
  const Icon = cfg.icon;
  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border font-bold font-mono ${sizeClass} ${cfg.bg} ${cfg.border} ${cfg.text}`}>
      <Icon className={size === 'sm' ? 'w-2.5 h-2.5' : 'w-3 h-3'} />
      {cfg.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Rule Row
// ---------------------------------------------------------------------------
function RuleRow({ rule }: { rule: RuleEvaluation }) {
  const isPass = rule.outcome === 'PASS';
  const isUnavail = rule.outcome === 'UNAVAILABLE';

  return (
    <div className={`flex items-start gap-2.5 px-3 py-2.5 rounded-lg border text-xs transition-all ${
      isPass    ? 'bg-emerald-900/10 border-emerald-800/30' :
      isUnavail ? 'bg-stone-800/30 border-stone-700/30' :
                  'bg-rose-900/10 border-rose-900/20'
    }`}>
      <div className="mt-0.5 shrink-0">
        {isPass    ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> :
         isUnavail ? <AlertTriangle className="w-3.5 h-3.5 text-stone-500" /> :
                     <XCircle className="w-3.5 h-3.5 text-rose-400" />}
      </div>
      <div className="flex-1 min-w-0">
        <span className={`font-medium ${isPass ? 'text-stone-200' : isUnavail ? 'text-stone-500' : 'text-stone-300'}`}>
          {rule.label}
        </span>
        <div className={`mt-0.5 font-mono text-[10px] ${
          isPass ? 'text-emerald-400' : isUnavail ? 'text-stone-600' : 'text-rose-400'
        }`}>
          {rule.actual_value_label !== 'UNAVAILABLE' ? rule.actual_value_label : 'Value unavailable — insufficient data'}
        </div>
      </div>
      <span className={`shrink-0 font-mono font-black text-[9px] px-1.5 py-0.5 rounded border ${
        isPass    ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-400' :
        isUnavail ? 'bg-stone-800 border-stone-700 text-stone-600' :
                    'bg-rose-900/30 border-rose-700/30 text-rose-400'
      }`}>
        {rule.outcome}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Strategy Card (left matrix)
// ---------------------------------------------------------------------------
function StrategyCard({
  result,
  isSelected,
  onClick,
}: {
  result: StrategyEvaluationResult;
  isSelected: boolean;
  onClick: () => void;
}) {
  const cfg = STATE_CONFIG[result.state] || STATE_CONFIG.UNAVAILABLE;
  const pct = result.entry_rules_total > 0
    ? Math.round((result.entry_rules_passing / result.entry_rules_total) * 100)
    : 0;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3.5 rounded-xl border transition-all duration-200 group ${
        isSelected
          ? `${cfg.bg} ${cfg.border} ring-1 ring-violet-500/40`
          : 'bg-[#181a24] border-stone-800/60 hover:border-stone-700/60 hover:bg-stone-800/20'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <div className="font-bold text-sm text-stone-100 truncate">{result.strategy_name}</div>
          <div className="text-[10px] font-mono text-stone-500 mt-0.5">{result.category}</div>
        </div>
        <StateBadge state={result.state} size="sm" />
      </div>

      {/* Progress bar */}
      <div className="mt-2">
        <div className="flex justify-between items-center mb-1">
          <span className="text-[10px] text-stone-500 font-mono">
            {result.entry_rules_passing}/{result.entry_rules_total} rules pass
          </span>
          {result.entry_rules_unavailable > 0 && (
            <span className="text-[10px] text-stone-600 font-mono">
              {result.entry_rules_unavailable} unavail
            </span>
          )}
        </div>
        <div className="h-1 bg-stone-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              result.state === 'ACTIVE'  ? 'bg-emerald-500' :
              result.state === 'PARTIAL' ? 'bg-amber-500' :
              result.state === 'CONFLICTED' ? 'bg-orange-500' :
              'bg-stone-700'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="mt-2 flex items-center gap-1.5 flex-wrap">
        {result.tags.slice(0, 3).map(t => (
          <span key={t} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-stone-800 text-stone-500 border border-stone-700/50">
            {t}
          </span>
        ))}
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Feature Vector Panel
// ---------------------------------------------------------------------------
function FeatureVectorPanel({ fv }: { fv: Record<string, number> }) {
  const entries = Object.entries(fv);
  if (entries.length === 0) return null;
  return (
    <div className="bg-[#0e0f15] border border-stone-800/60 rounded-xl p-3">
      <div className="flex items-center gap-1.5 mb-2">
        <Database className="w-3 h-3 text-stone-500" />
        <span className="text-[10px] font-mono font-bold text-stone-500 uppercase tracking-wider">Computed Indicators</span>
      </div>
      <div className="grid grid-cols-2 gap-1">
        {entries.map(([k, v]) => (
          <div key={k} className="flex justify-between items-center px-2 py-1 rounded bg-stone-900/40 border border-stone-800/30">
            <span className="text-[10px] font-mono text-stone-500 uppercase">{k}</span>
            <span className="text-[10px] font-mono text-stone-300 font-bold">{typeof v === 'number' ? v.toFixed(3) : String(v)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Strategy Lab Page
// ---------------------------------------------------------------------------
export const StrategyLabPage: React.FC<StrategyLabPageProps> = ({
  stocks,
  selectedSymbol,
  onSelectSymbol,
}) => {
  const [symbol, setSymbol] = useState(selectedSymbol || 'RELIANCE.NS');
  const [symbolSearch, setSymbolSearch] = useState('');
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluations, setEvaluations] = useState<StrategyEvaluationResult[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [evaluatedAt, setEvaluatedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Copilot state
  const [copilotMessages, setCopilotMessages] = useState<CopilotMessage[]>([]);
  const [copilotInput, setCopilotInput] = useState('');
  const [isCopilotLoading, setIsCopilotLoading] = useState(false);
  const copilotEndRef = useRef<HTMLDivElement>(null);

  const selectedEval = evaluations.find(e => e.strategy_id === selectedStrategyId) || null;

  // Filtered stocks for symbol selector
  const filteredStocks = stocks.filter(s =>
    !symbolSearch ||
    s.symbol.toLowerCase().includes(symbolSearch.toLowerCase()) ||
    s.name.toLowerCase().includes(symbolSearch.toLowerCase())
  ).slice(0, 8);

  // Run evaluation
  const handleEvaluate = useCallback(async () => {
    setIsEvaluating(true);
    setError(null);
    try {
      const res = await fetch(`/api/strategies/evaluate/${encodeURIComponent(symbol)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_live_feed: false }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data: StrategyEvaluationResult[] = await res.json();
      setEvaluations(data);
      setEvaluatedAt(new Date().toLocaleTimeString());
      // Auto-select the most interesting strategy
      const priority = ['ACTIVE', 'PARTIAL', 'CONFLICTED', 'INACTIVE', 'STALE', 'UNAVAILABLE'];
      for (const state of priority) {
        const found = data.find(e => e.state === state);
        if (found) { setSelectedStrategyId(found.strategy_id); break; }
      }
      setCopilotMessages([]);
    } catch (e: any) {
      setError(e.message || 'Evaluation failed');
    } finally {
      setIsEvaluating(false);
    }
  }, [symbol]);

  // Copilot chat
  const handleCopilotSend = useCallback(async () => {
    if (!copilotInput.trim() || !selectedEval || isCopilotLoading) return;
    const userMsg = copilotInput.trim();
    setCopilotInput('');
    setCopilotMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setIsCopilotLoading(true);
    try {
      const res = await fetch('/api/strategies/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          strategy_id: selectedEval.strategy_id,
          evaluation_result: selectedEval,
          user_message: userMsg,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCopilotMessages(prev => [...prev, {
        role: 'assistant',
        text: data.reply || 'No response.',
        evidence_cited: data.evidence_cited || [],
      }]);
    } catch (e: any) {
      setCopilotMessages(prev => [...prev, {
        role: 'assistant',
        text: `Copilot unavailable: ${e.message}`,
      }]);
    } finally {
      setIsCopilotLoading(false);
    }
  }, [copilotInput, selectedEval, isCopilotLoading, symbol]);

  useEffect(() => {
    copilotEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [copilotMessages]);

  // Summary counts
  const activeCount    = evaluations.filter(e => e.state === 'ACTIVE').length;
  const partialCount   = evaluations.filter(e => e.state === 'PARTIAL').length;
  const inactiveCount  = evaluations.filter(e => e.state === 'INACTIVE').length;
  const unavailCount   = evaluations.filter(e => e.state === 'UNAVAILABLE' || e.state === 'STALE').length;

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-175px)] overflow-hidden">

      {/* ── Header ── */}
      <div className="shrink-0 bg-[#12131a] border-b border-stone-800/60 px-4 py-3">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          {/* Title */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-700 flex items-center justify-center shadow-lg shadow-violet-500/20">
              <FlaskConical className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="font-black text-sm text-white tracking-tight">STRATEGY LAB</div>
              <div className="text-[10px] text-stone-500 font-mono">Deterministic Rule Evaluation · {evaluations.length > 0 ? `${evaluations.length} strategies` : 'No evaluation yet'}</div>
            </div>
          </div>

          {/* Symbol selector */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-stone-500" />
              <input
                type="text"
                placeholder="Symbol..."
                value={symbolSearch}
                onChange={e => setSymbolSearch(e.target.value)}
                onFocus={() => setSymbolSearch(symbol)}
                onBlur={() => setTimeout(() => setSymbolSearch(''), 200)}
                className="pl-6 pr-3 py-1.5 bg-stone-900 border border-stone-700 rounded-lg text-xs text-stone-200 font-mono placeholder-stone-600 w-36 focus:outline-none focus:border-violet-500/60"
              />
              {symbolSearch.length > 0 && filteredStocks.length > 0 && (
                <div className="absolute top-full left-0 mt-1 w-56 bg-[#1a1b24] border border-stone-700 rounded-xl overflow-hidden z-50 shadow-xl">
                  {filteredStocks.map(s => (
                    <button
                      key={s.symbol}
                      onMouseDown={() => { setSymbol(s.symbol); setSymbolSearch(''); onSelectSymbol?.(s.symbol); }}
                      className="w-full flex items-center justify-between px-3 py-2 hover:bg-stone-800 text-xs text-left"
                    >
                      <span className="font-bold text-stone-200 font-mono">{s.symbol.replace('.NS', '')}</span>
                      <span className="text-stone-500 truncate max-w-[100px]">{s.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="px-3 py-1.5 bg-stone-900 border border-stone-700 rounded-lg text-xs font-mono font-bold text-violet-400">
              {symbol.replace('.NS', '')}
            </div>

            <button
              onClick={handleEvaluate}
              disabled={isEvaluating}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-xs font-bold rounded-lg transition-all shadow-md shadow-violet-500/20 disabled:opacity-60"
            >
              {isEvaluating
                ? <Loader2 className="w-3 h-3 animate-spin" />
                : <Zap className="w-3 h-3" />}
              {isEvaluating ? 'Evaluating…' : 'Evaluate'}
            </button>

            {evaluatedAt && (
              <span className="text-[10px] text-stone-500 font-mono flex items-center gap-1">
                <Clock className="w-2.5 h-2.5" /> {evaluatedAt}
              </span>
            )}
          </div>
        </div>

        {/* Summary bar */}
        {evaluations.length > 0 && (
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            <Pill label="Active" count={activeCount} color="emerald" />
            <Pill label="Partial" count={partialCount} color="amber" />
            <Pill label="Inactive" count={inactiveCount} color="stone" />
            <Pill label="N/A" count={unavailCount} color="rose" />
          </div>
        )}
      </div>

      {/* ── Body ── */}
      {!evaluations.length && !isEvaluating && !error && (
        <EmptyState onEvaluate={handleEvaluate} symbol={symbol} />
      )}

      {error && (
        <div className="m-4 px-4 py-3 rounded-xl bg-rose-900/20 border border-rose-700/40 text-rose-400 text-sm flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {isEvaluating && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-3">
            <Loader2 className="w-8 h-8 animate-spin text-violet-400 mx-auto" />
            <div className="text-sm text-stone-400 font-mono">Computing indicators & evaluating {symbol}…</div>
          </div>
        </div>
      )}

      {evaluations.length > 0 && !isEvaluating && (
        <div className="flex-1 flex overflow-hidden">

          {/* ── Left: Strategy Matrix ── */}
          <div className="w-64 shrink-0 border-r border-stone-800/60 flex flex-col overflow-hidden">
            <div className="px-3 py-2 border-b border-stone-800/40">
              <span className="text-[10px] font-mono font-bold text-stone-500 uppercase tracking-wider">Strategy Matrix</span>
            </div>
            <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1.5">
              {evaluations.map(ev => (
                <StrategyCard
                  key={ev.strategy_id}
                  result={ev}
                  isSelected={selectedStrategyId === ev.strategy_id}
                  onClick={() => { setSelectedStrategyId(ev.strategy_id); setCopilotMessages([]); }}
                />
              ))}
            </div>
          </div>

          {/* ── Center: Strategy Detail ── */}
          <div className="flex-1 flex flex-col overflow-hidden border-r border-stone-800/60">
            {selectedEval ? (
              <>
                <div className="shrink-0 px-4 py-3 border-b border-stone-800/40 flex items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-black text-sm text-white">{selectedEval.strategy_name}</span>
                      <StateBadge state={selectedEval.state} />
                    </div>
                    <div className="text-[10px] text-stone-500 font-mono mt-0.5">
                      {selectedEval.category} · {selectedEval.candles_used} candles · Freshness: {selectedEval.data_freshness}
                    </div>
                  </div>
                  {selectedEval.exit_rules_triggered > 0 && (
                    <span className="flex items-center gap-1 text-[10px] font-mono text-orange-400 border border-orange-500/30 bg-orange-500/10 px-2 py-1 rounded-lg">
                      <TrendingDown className="w-3 h-3" /> Exit signal active
                    </span>
                  )}
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
                  {/* Description */}
                  <div className="text-xs text-stone-400 leading-relaxed bg-stone-900/40 border border-stone-800/40 rounded-xl p-3">
                    <Info className="w-3.5 h-3.5 inline mr-1.5 text-stone-500" />
                    {selectedEval.description}
                  </div>

                  {/* Entry rules */}
                  <div>
                    <div className="flex items-center gap-1.5 mb-2">
                      <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-xs font-bold text-stone-300 uppercase tracking-wider">Entry Rules</span>
                      <span className="text-[10px] font-mono text-stone-500">
                        ({selectedEval.entry_rules_passing}/{selectedEval.entry_rules_total} pass)
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {selectedEval.rule_evaluations.filter(r => r.is_entry_rule).map(r => (
                        <RuleRow key={r.rule_id} rule={r} />
                      ))}
                    </div>
                  </div>

                  {/* Exit rules */}
                  {selectedEval.rule_evaluations.filter(r => !r.is_entry_rule).length > 0 && (
                    <div>
                      <div className="flex items-center gap-1.5 mb-2">
                        <TrendingDown className="w-3.5 h-3.5 text-rose-400" />
                        <span className="text-xs font-bold text-stone-300 uppercase tracking-wider">Exit Rules</span>
                        <span className="text-[10px] font-mono text-stone-500">
                          ({selectedEval.exit_rules_triggered}/{selectedEval.exit_rules_total} triggered)
                        </span>
                      </div>
                      <div className="space-y-1.5">
                        {selectedEval.rule_evaluations.filter(r => !r.is_entry_rule).map(r => (
                          <RuleRow key={r.rule_id} rule={r} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Feature vector */}
                  {Object.keys(selectedEval.feature_vector).length > 0 && (
                    <FeatureVectorPanel fv={selectedEval.feature_vector} />
                  )}

                  {/* Tags */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {selectedEval.tags.map(t => (
                      <span key={t} className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-violet-900/20 border border-violet-700/30 text-violet-400">
                        #{t}
                      </span>
                    ))}
                  </div>

                  {/* Data integrity notice */}
                  {selectedEval.entry_rules_unavailable > 0 && (
                    <div className="flex items-start gap-2 px-3 py-2.5 rounded-xl bg-stone-900/50 border border-stone-700/40 text-xs text-stone-500">
                      <Shield className="w-3.5 h-3.5 shrink-0 text-stone-600 mt-0.5" />
                      <span>
                        <span className="font-bold text-stone-400">{selectedEval.entry_rules_unavailable} rule(s) could not be evaluated</span> due to insufficient candle history (need {' '}
                        at least {evaluations.find(e => e.strategy_id === selectedEval.strategy_id)?.candles_used} bars). 
                        These are marked UNAVAILABLE — not treated as FAIL.
                      </span>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center space-y-2">
                  <ChevronRight className="w-6 h-6 text-stone-700 mx-auto" />
                  <div className="text-sm text-stone-600 font-mono">Select a strategy from the matrix</div>
                </div>
              </div>
            )}
          </div>

          {/* ── Right: AI Strategy Copilot ── */}
          <div className="w-80 shrink-0 flex flex-col overflow-hidden">
            <div className="shrink-0 px-3 py-2 border-b border-stone-800/40 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-violet-400" />
              <span className="text-[10px] font-mono font-bold text-stone-400 uppercase tracking-wider">Strategy Copilot</span>
              <span className="ml-auto text-[9px] font-mono text-stone-600 border border-stone-700/50 px-1.5 py-0.5 rounded">Evidence-grounded</span>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-2">
              {!selectedEval && (
                <div className="text-[11px] text-stone-600 font-mono text-center mt-4">
                  Select a strategy to start the copilot chat.
                </div>
              )}
              {selectedEval && copilotMessages.length === 0 && (
                <CopilotWelcome strategyName={selectedEval.strategy_name} state={selectedEval.state} />
              )}
              {copilotMessages.map((msg, i) => (
                <CopilotBubble key={i} message={msg} />
              ))}
              {isCopilotLoading && (
                <div className="flex items-center gap-2 text-[11px] text-stone-500">
                  <Loader2 className="w-3 h-3 animate-spin" /> Interpreting evidence…
                </div>
              )}
              <div ref={copilotEndRef} />
            </div>

            {/* Input */}
            <div className="shrink-0 border-t border-stone-800/40 p-2.5">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={copilotInput}
                  onChange={e => setCopilotInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleCopilotSend()}
                  placeholder={selectedEval ? "Ask about this strategy…" : "Select a strategy first"}
                  disabled={!selectedEval || isCopilotLoading}
                  className="flex-1 px-3 py-2 bg-stone-900 border border-stone-700 rounded-xl text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-violet-500/60 disabled:opacity-50"
                />
                <button
                  onClick={handleCopilotSend}
                  disabled={!copilotInput.trim() || !selectedEval || isCopilotLoading}
                  className="w-8 h-8 flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-500 text-white transition-all disabled:opacity-40"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="text-[9px] text-stone-700 font-mono mt-1.5 text-center">
                Copilot can only interpret verified, computed rule values — it never invents data.
              </div>
            </div>
          </div>

        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Pill({ label, count, color }: { label: string; count: number; color: 'emerald' | 'amber' | 'stone' | 'rose' }) {
  const cls = {
    emerald: 'bg-emerald-500/15 text-emerald-400 border-emerald-700/30',
    amber:   'bg-amber-500/15 text-amber-400 border-amber-700/30',
    stone:   'bg-stone-700/30 text-stone-500 border-stone-700/40',
    rose:    'bg-rose-900/20 text-rose-400 border-rose-700/30',
  }[color];
  return (
    <span className={`flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${cls}`}>
      {count} {label}
    </span>
  );
}

function CopilotWelcome({ strategyName, state }: { strategyName: string; state: StrategyState }) {
  const suggestions = [
    "Why is this strategy active right now?",
    "Which rule is failing and why?",
    "What would make this strategy ACTIVE?",
    "Explain the data freshness warning.",
  ];
  return (
    <div className="space-y-2 mt-1">
      <div className="text-[10px] text-stone-600 font-mono text-center">
        <span className="text-violet-400 font-bold">{strategyName}</span> is <span className="font-bold">{state}</span>.
        <br />Ask the copilot about the evidence.
      </div>
      <div className="space-y-1">
        {suggestions.map(s => (
          <div key={s} className="text-[10px] text-stone-500 px-2 py-1 rounded-lg bg-stone-900/50 border border-stone-800/40 cursor-default font-mono">
            "{s}"
          </div>
        ))}
      </div>
    </div>
  );
}

function CopilotBubble({ message }: { message: CopilotMessage }) {
  const isUser = message.role === 'user';
  return (
    <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
      <div className={`max-w-[90%] px-3 py-2 rounded-xl text-[11px] leading-relaxed ${
        isUser
          ? 'bg-violet-700/30 border border-violet-500/30 text-stone-200'
          : 'bg-stone-900/60 border border-stone-700/40 text-stone-300'
      }`}>
        {message.text}
      </div>
      {!isUser && message.evidence_cited && message.evidence_cited.length > 0 && (
        <div className="max-w-[90%] space-y-0.5">
          {message.evidence_cited.slice(0, 3).map((ev, i) => (
            <div key={i} className="text-[9px] font-mono text-stone-600 flex items-center gap-1">
              <BookOpen className="w-2 h-2 shrink-0" /> {ev}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyState({ onEvaluate, symbol }: { onEvaluate: () => void; symbol: string }) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-sm space-y-5">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-600/30 to-indigo-700/20 border border-violet-500/30 flex items-center justify-center mx-auto">
          <FlaskConical className="w-8 h-8 text-violet-400" />
        </div>
        <div>
          <div className="text-lg font-black text-white mb-1">Strategy Lab</div>
          <div className="text-sm text-stone-400 leading-relaxed">
            Evaluate a library of 8 systematic quantitative strategies against{' '}
            <span className="font-bold text-violet-400">{symbol}</span>.
            Each rule is deterministically assessed against real indicator values — never fabricated.
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 text-left">
          {[
            ['VWAP Momentum', 'Momentum'],
            ['EMA Golden Cross', 'Trend'],
            ['RSI Reversal', 'Mean-Rev'],
            ['Bollinger Squeeze', 'Breakout'],
            ['MACD Crossover', 'Momentum'],
            ['ORB Breakout', 'Breakout'],
            ['Supertrend ATR', 'Trend'],
            ['RVOL Surge', 'Volume'],
          ].map(([name, cat]) => (
            <div key={name} className="flex items-center gap-1.5 text-[10px] font-mono text-stone-500">
              <Activity className="w-2.5 h-2.5 text-violet-500 shrink-0" />
              <span className="font-bold text-stone-400">{name}</span>
              <span className="text-stone-700">·</span>
              <span>{cat}</span>
            </div>
          ))}
        </div>
        <button
          onClick={onEvaluate}
          className="w-full py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-violet-500/20"
        >
          <Zap className="w-4 h-4 inline mr-2" />
          Evaluate {symbol.replace('.NS', '')} Now
        </button>
      </div>
    </div>
  );
}
