import React, { useState } from 'react';
import { AICommentary, EvidenceItem } from '../../types/intelligence';
import { Sparkles, AlertTriangle, CheckCircle2, Eye, HelpCircle, RefreshCw, ShieldCheck, Zap, Layers, BarChart3 } from 'lucide-react';

interface SecurityIntelligencePanelProps {
  commentary?: AICommentary | null;
  isLoading?: boolean;
  onRefresh?: () => void;
}

export const SecurityIntelligencePanel: React.FC<SecurityIntelligencePanelProps> = ({
  commentary,
  isLoading = false,
  onRefresh,
}) => {
  const [showAllEvidence, setShowAllEvidence] = useState(false);

  if (isLoading && !commentary) {
    return (
      <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 animate-pulse space-y-3">
        <div className="flex items-center justify-between">
          <div className="h-4 bg-stone-800 rounded w-1/3"></div>
          <div className="h-4 bg-stone-800 rounded w-1/4"></div>
        </div>
        <div className="h-16 bg-stone-800/60 rounded"></div>
        <div className="h-20 bg-stone-800/40 rounded"></div>
      </div>
    );
  }

  if (!commentary) return null;

  const getAttentionColor = (score: number) => {
    if (score >= 80) return 'text-rose-400 bg-rose-500/10 border-rose-500/30';
    if (score >= 65) return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
    if (score >= 45) return 'text-sky-400 bg-sky-500/10 border-sky-500/30';
    return 'text-stone-400 bg-stone-800/60 border-stone-700';
  };

  const getImportanceColor = (imp?: string) => {
    if (imp === 'CRITICAL') return 'bg-rose-500 text-stone-950';
    if (imp === 'HIGH') return 'bg-amber-500 text-stone-950';
    if (imp === 'MEDIUM') return 'bg-sky-500 text-stone-950';
    return 'bg-stone-700 text-stone-200';
  };

  const sym = (commentary.symbol || 'EQUITY').split('.')[0];
  const attnScore = typeof commentary.attention_score === 'number' ? commentary.attention_score : 50;
  const confEv = Array.isArray(commentary.confirming_evidence) ? commentary.confirming_evidence : [];
  const contraEv = Array.isArray(commentary.contradicting_evidence) ? commentary.contradicting_evidence : [];
  const toWatch = Array.isArray(commentary.what_to_watch) ? commentary.what_to_watch : [];
  const confPct = typeof commentary.confidence === 'number' ? (commentary.confidence > 1 ? Math.round(commentary.confidence) : Math.round(commentary.confidence * 100)) : 60;

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 shadow-sm space-y-4">
      {/* Header Row: Symbol, Attention Score, Regime, Refresh */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-800/80 pb-3">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 rounded-xl bg-gradient-to-br from-orange-500/20 to-indigo-500/20 border border-amber-500/30 text-amber-300">
            <Sparkles className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="font-extrabold font-mono text-sm sm:text-base text-white tracking-tight">
                {sym} AI Intelligence
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-[#14151b] text-stone-400 border border-stone-800">
                {commentary.sector || 'NSE Equities'}
              </span>
            </div>
            <p className="text-xs text-stone-400 font-medium">{commentary.headline || ''}</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Attention Score Pill */}
          <div className={`px-2.5 py-1 rounded-xl font-mono text-xs font-black border flex items-center space-x-1.5 ${getAttentionColor(attnScore)}`}>
            <Zap className="w-3.5 h-3.5" />
            <span>ATTN {attnScore} / 100</span>
          </div>

          {/* Importance Pill */}
          <span className={`px-2 py-0.5 rounded-lg font-mono text-[10px] font-bold uppercase tracking-wider ${getImportanceColor(commentary.importance)}`}>
            {commentary.importance || 'NORMAL'}
          </span>

          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="p-1.5 rounded-xl bg-[#14151b] hover:bg-stone-800 border border-stone-800 text-stone-400 hover:text-stone-200 transition-colors cursor-pointer disabled:opacity-50"
              title="Re-run AI Analysis"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* 1. What Changed & Why It Matters (Two Column Card) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="bg-[#14151b] border border-stone-800/80 rounded-xl p-3">
          <div className="flex items-center space-x-1.5 text-[10px] uppercase font-mono font-bold text-amber-400 mb-1.5">
            <BarChart3 className="w-3.5 h-3.5" />
            <span>What Changed?</span>
          </div>
          <p className="text-xs text-stone-200 leading-relaxed font-sans">
            {commentary.what_changed || 'Streaming market updates active.'}
          </p>
        </div>

        <div className="bg-[#14151b] border border-stone-800/80 rounded-xl p-3">
          <div className="flex items-center space-x-1.5 text-[10px] uppercase font-mono font-bold text-sky-400 mb-1.5">
            <Layers className="w-3.5 h-3.5" />
            <span>Why It Matters?</span>
          </div>
          <p className="text-xs text-stone-200 leading-relaxed font-sans">
            {commentary.why_it_matters || 'Multi-dimensional technical and order flow analysis.'}
          </p>
        </div>
      </div>

      {/* 2. Traceable Evidence Breakdown */}
      {confEv.length > 0 && (
        <div className="bg-[#14151b] border border-stone-800/80 rounded-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-1.5 text-[10px] uppercase font-mono font-bold text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Traceable Evidence & Verification</span>
            </div>
            <button
              onClick={() => setShowAllEvidence(!showAllEvidence)}
              className="text-[10px] font-mono text-stone-400 hover:text-stone-200 cursor-pointer"
            >
              {showAllEvidence ? 'Show Less' : `Show All (${confEv.length})`}
            </button>
          </div>

          <div className="space-y-1.5 font-mono text-xs">
            {(showAllEvidence ? confEv : confEv.slice(0, 3)).map((ev, idx) => (
              <div key={idx} className="flex items-start space-x-2 text-stone-300">
                <span className="text-emerald-400 font-bold">✓</span>
                <span className="flex-1">{ev.statement}</span>
                <span className="text-[10px] text-stone-500 font-sans shrink-0">[{ev.source}]</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. Contradiction Detection & Mixed Signals */}
      {contraEv.length > 0 && (
        <div className="bg-amber-500/5 border border-amber-500/30 rounded-xl p-3">
          <div className="flex items-center space-x-1.5 text-[10px] uppercase font-mono font-bold text-amber-400 mb-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Contradiction / Mixed Signals Detected</span>
          </div>
          <div className="space-y-1 font-mono text-xs text-amber-200/90">
            {contraEv.map((c, i) => (
              <p key={i}>• {c.statement}</p>
            ))}
          </div>
        </div>
      )}

      {/* 4. What to Watch Next */}
      {toWatch.length > 0 && (
        <div className="bg-[#14151b] border border-stone-800/80 rounded-xl p-3">
          <div className="flex items-center space-x-1.5 text-[10px] uppercase font-mono font-bold text-indigo-400 mb-1.5">
            <Eye className="w-3.5 h-3.5" />
            <span>What to Watch Next</span>
          </div>
          <ul className="space-y-1 font-mono text-xs text-stone-300">
            {toWatch.map((w, i) => (
              <li key={i} className="flex items-center space-x-1.5">
                <span className="text-indigo-400">•</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer: Freshness & Confidence */}
      <div className="flex items-center justify-between text-[10px] font-mono text-stone-500 pt-1 border-t border-stone-800/60">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Confidence: {confPct}%</span>
          <span>•</span>
          <span>Freshness: {commentary.data_freshness || 'RECENT'}</span>
        </div>
        <span>Updated: {commentary.timestamp || ''}</span>
      </div>
    </div>
  );
};
