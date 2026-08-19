import React, { useState, useEffect } from 'react';
import { PaperPosition, NSEStock } from '../../types/indianMarket';
import {
  Briefcase, TrendingUp, TrendingDown, DollarSign, PlusCircle,
  ArrowUpRight, ArrowDownRight, Flame, Shield, Sparkles, Send,
  Loader2, Layers, GitMerge, AlertTriangle, CheckCircle2, ChevronRight,
  RefreshCw, MessageSquare
} from 'lucide-react';

interface PortfolioPageProps {
  balance: number;
  positions: PaperPosition[];
  stocks: NSEStock[];
  onOpenOrderModal: () => void;
  onClosePosition: (id: string, closePrice?: number) => void;
}

export interface ResearchCandidateData {
  candidate_id: string;
  strategy_id: string;
  strategy_name: string;
  lifecycle_state: string;
  backtest_cagr_pct?: number | null;
  backtest_sharpe?: number | null;
  walk_forward_efficiency?: number | null;
  notes?: string | null;
}

export const PortfolioPage: React.FC<PortfolioPageProps> = ({
  balance,
  positions = [],
  stocks,
  onOpenOrderModal,
  onClosePosition,
}) => {
  const [activeTab, setActiveTab] = useState<'POSITIONS' | 'LIFECYCLE' | 'AUDIT'>('POSITIONS');
  const [candidates, setCandidates] = useState<ResearchCandidateData[]>([]);
  const [selectedPosForAudit, setSelectedPosForAudit] = useState<PaperPosition | null>(null);

  // Copilot State
  const [copilotMessages, setCopilotMessages] = useState<Array<{ role: string; text: string }>>([]);
  const [copilotInput, setCopilotInput] = useState<string>('');
  const [isCopilotLoading, setIsCopilotLoading] = useState<boolean>(false);

  const totalInvested = positions.reduce((acc, p) => acc + (p.quantity * p.entryPrice), 0);
  const totalCurrent = positions.reduce((acc, p) => acc + (p.quantity * p.currentPrice), 0);
  const totalPnL = positions.reduce((acc, p) => acc + p.unrealizedPnL, 0);
  const totalPnLPct = totalInvested > 0 ? (totalPnL / totalInvested) * 100 : 0;
  const portfolioEquity = balance + totalCurrent;

  const loadCandidates = async () => {
    try {
      const res = await fetch('/api/paper/lifecycle/candidates');
      if (res.ok) {
        const data = await res.json();
        setCandidates(data.candidates || []);
      }
    } catch (e) {
      // ignore
    }
  };

  useEffect(() => {
    loadCandidates();
  }, []);

  const handlePromoteCandidate = async (candidateId: string, newState: string) => {
    try {
      const res = await fetch('/api/paper/lifecycle/transition', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ candidate_id: candidateId, new_state: newState, reason: 'User Promotion' }),
      });
      if (res.ok) {
        await loadCandidates();
      }
    } catch (e) {
      // ignore
    }
  };

  const handleCopilotSend = async (userText: string, pos?: PaperPosition) => {
    if (!userText.trim() || isCopilotLoading) return;
    const textToSend = userText.trim();
    const isSkeptic = textToSend.toUpperCase().includes('CHALLENGE');
    setCopilotInput('');
    setCopilotMessages(prev => [...prev, { role: 'user', text: textToSend }]);
    setIsCopilotLoading(true);

    const targetPos = pos || selectedPosForAudit || positions[0] || null;

    try {
      const endpoint = isSkeptic ? '/api/paper/challenge' : '/api/paper/copilot';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: targetPos ? targetPos.symbol : 'RELIANCE.NS',
          user_message: textToSend,
          position: targetPos ? {
            entry_price: targetPos.entryPrice,
            current_price: targetPos.currentPrice,
            quantity: targetPos.quantity,
            unrealized_pnl: targetPos.unrealizedPnL,
            fees_paid: 40.0,
            slippage_paid: 25.0,
            side: targetPos.type,
          } : null,
          signal: {
            strategy_id: 'EMA_TREND_MOMENTUM',
            strategy_version: '1.0.0',
            strategy_state: 'ACTIVE',
            regime: 'BULL_TREND',
            confluence_state: 'HIGH_CONVICTION_LONG',
            rule_evidence: ['Fast EMA above Slow EMA', 'RSI > 55'],
          },
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
    <div className="flex-1 p-3 flex flex-col space-y-3 h-[calc(100vh-175px)] overflow-y-auto custom-scrollbar font-mono bg-[#0a0b10]">
      {/* Paper Mode Guarantee Badge */}
      <div className="bg-[#12131b] border border-amber-500/30 rounded-xl px-3.5 py-2 flex items-center justify-between gap-3 text-xs shadow-lg">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
          <span className="font-bold text-amber-300 uppercase tracking-wide">
            Paper Trading Simulator Active
          </span>
          <span className="text-stone-400 hidden sm:inline">
            — Next-Bar Execution Semantics & Indian Equity Frictions Model (STT, SEBI, GST, Slippage)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('POSITIONS')}
            className={`px-2.5 py-1 rounded font-bold cursor-pointer transition-all ${activeTab === 'POSITIONS' ? 'bg-amber-500 text-stone-950 shadow' : 'text-stone-400 hover:text-stone-200'}`}
          >
            Positions ({positions.length})
          </button>
          <button
            onClick={() => setActiveTab('LIFECYCLE')}
            className={`px-2.5 py-1 rounded font-bold cursor-pointer transition-all ${activeTab === 'LIFECYCLE' ? 'bg-amber-500 text-stone-950 shadow' : 'text-stone-400 hover:text-stone-200'}`}
          >
            Research Lifecycle ({candidates.length})
          </button>
        </div>
      </div>

      {/* Portfolio Overview KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase text-stone-400">Total Portfolio Value</span>
            <div className="text-lg font-black text-white">
              ₹{portfolioEquity.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
            <Briefcase className="w-4 h-4" />
          </div>
        </div>

        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase text-stone-400">Available Paper Cash</span>
            <div className="text-lg font-black text-stone-200">
              ₹{balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div className="p-2 rounded-lg bg-sky-500/10 border border-sky-500/30 text-sky-400">
            <DollarSign className="w-4 h-4" />
          </div>
        </div>

        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase text-stone-400">Unrealized Net P&L</span>
            <div className={`text-lg font-black flex items-center space-x-1 ${totalPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {totalPnL >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
              <span>{totalPnL >= 0 ? '+' : ''}₹{totalPnL.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
            </div>
          </div>
          <div className={`p-2 rounded-lg border ${totalPnL >= 0 ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-rose-500/10 border-rose-500/30 text-rose-400'}`}>
            {totalPnL >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          </div>
        </div>

        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase text-stone-400">Return on Capital</span>
            <div className={`text-lg font-black ${totalPnLPct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {totalPnLPct >= 0 ? '+' : ''}{totalPnLPct.toFixed(2)}%
            </div>
          </div>
          <button
            onClick={onOpenOrderModal}
            className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold text-xs shadow-md cursor-pointer transition-all active:scale-95"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            <span>New Order</span>
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 flex-1">
        <div className="lg:col-span-8 flex flex-col space-y-3">
          {activeTab === 'POSITIONS' ? (
            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 flex-1 flex flex-col min-h-[350px]">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-stone-800/60 text-xs">
                <span className="font-bold text-stone-200 uppercase">Active Positions with Quant Provenance</span>
                <span className="text-[10px] text-stone-500">Next-Bar Execution Semantics</span>
              </div>

              {positions.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-3">
                  <Briefcase className="w-8 h-8 text-stone-600" />
                  <p className="text-xs text-stone-400">No active paper trading positions.</p>
                  <button
                    onClick={onOpenOrderModal}
                    className="px-3 py-1.5 rounded-lg bg-amber-500 text-stone-950 font-bold text-xs cursor-pointer shadow-md"
                  >
                    Place Your First Paper Trade
                  </button>
                </div>
              ) : (
                <div className="overflow-x-auto custom-scrollbar flex-1">
                  <table className="w-full text-left text-xs border-collapse min-w-[700px]">
                    <thead>
                      <tr className="text-stone-500 border-b border-stone-800/60 pb-2 text-[10px] uppercase">
                        <th className="pb-2 font-bold">Symbol / Strategy</th>
                        <th className="pb-2 font-bold">Type</th>
                        <th className="pb-2 font-bold">Qty</th>
                        <th className="pb-2 font-bold">Entry Price</th>
                        <th className="pb-2 font-bold">LTP</th>
                        <th className="pb-2 font-bold">P&L (₹)</th>
                        <th className="pb-2 font-bold">Audit</th>
                        <th className="pb-2 font-bold text-right pr-2">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-800/40 text-[11px]">
                      {positions.map((pos) => {
                        const isPos = pos.unrealizedPnL >= 0;
                        return (
                          <tr key={pos.id} className="hover:bg-stone-900/40 transition-colors">
                            <td className="py-2.5 font-bold text-white">
                              <div>{pos.symbol.split('.')[0]}</div>
                              <div className="text-[9px] text-amber-400 font-normal">EMA_TREND_MOMENTUM (v1.0)</div>
                            </td>
                            <td className="py-2.5">
                              <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                pos.type === 'BUY' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                              }`}>
                                {pos.type}
                              </span>
                            </td>
                            <td className="py-2.5 text-stone-200">{pos.quantity}</td>
                            <td className="py-2.5 text-stone-300">₹{pos.entryPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                            <td className="py-2.5 text-stone-100 font-bold">₹{pos.currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                            <td className={`py-2.5 font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {isPos ? '+' : ''}₹{pos.unrealizedPnL.toLocaleString('en-IN', { minimumFractionDigits: 2 })} ({pos.unrealizedPnLPercent.toFixed(2)}%)
                            </td>
                            <td className="py-2.5">
                              <button
                                onClick={() => {
                                  setSelectedPosForAudit(pos);
                                  handleCopilotSend('CHALLENGE THIS SIGNAL', pos);
                                }}
                                className="px-2 py-0.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded text-[9px] font-bold flex items-center gap-1 cursor-pointer"
                              >
                                <Flame className="w-2.5 h-2.5 text-rose-400" />
                                <span>Skeptic</span>
                              </button>
                            </td>
                            <td className="py-2.5 text-right pr-2">
                              <button
                                onClick={() => onClosePosition(pos.id, pos.currentPrice)}
                                className="px-2 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[10px] font-bold cursor-pointer transition-colors"
                              >
                                Close
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
              <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
                <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-amber-400" /> Research Lifecycle Promotion Ledger
                </span>
              </div>

              <div className="space-y-2">
                {candidates.map((cand) => (
                  <div key={cand.candidate_id} className="p-3 bg-stone-900/40 border border-stone-800 rounded-lg flex items-center justify-between gap-3 text-xs">
                    <div>
                      <div className="font-bold text-white">{cand.strategy_name}</div>
                      <div className="text-[10px] text-stone-400 mt-0.5">
                        Sharpe: <span className="text-cyan-400">{cand.backtest_sharpe || '---'}</span> | CAGR: <span className="text-emerald-400">{cand.backtest_cagr_pct ? `${cand.backtest_cagr_pct}%` : '---'}</span> | WFE: <span className="text-amber-400">{cand.walk_forward_efficiency ? `${cand.walk_forward_efficiency}%` : '---'}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 bg-stone-800 text-stone-300 rounded text-[10px] font-bold border border-stone-700">
                        {cand.lifecycle_state}
                      </span>
                      {cand.lifecycle_state === 'RESEARCH_CANDIDATE' && (
                        <button
                          onClick={() => handlePromoteCandidate(cand.candidate_id, 'PAPER_TESTING')}
                          className="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-bold cursor-pointer shadow"
                        >
                          Promote to Paper
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Paper Copilot Sidebar */}
        <div className="lg:col-span-4 flex flex-col space-y-3">
          <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3 flex flex-col h-full shadow-xl">
            <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 mb-2">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <span>Paper Trade Copilot</span>
              </div>
              <button
                onClick={() => handleCopilotSend('CHALLENGE THIS SIGNAL')}
                className="px-2 py-0.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded text-[10px] font-bold flex items-center gap-1 cursor-pointer"
              >
                <Flame className="w-3 h-3 text-rose-400" />
                <span>Skeptic Audit</span>
              </button>
            </div>

            <div className="flex-1 space-y-2 overflow-y-auto custom-scrollbar max-h-[380px] text-xs">
              {copilotMessages.length === 0 ? (
                <div className="text-center py-6 text-stone-500 text-xs space-y-2">
                  <MessageSquare className="w-8 h-8 mx-auto text-stone-600" />
                  <div>Interrogate paper signals, verify next-bar entry evidence, or launch a Skeptic Audit.</div>
                </div>
              ) : (
                copilotMessages.map((m, i) => (
                  <div key={i} className={`p-2.5 rounded-lg leading-relaxed ${m.role === 'user' ? 'bg-amber-600 text-stone-950 font-bold ml-auto max-w-[85%]' : 'bg-[#181a24] text-stone-200 border border-stone-800'}`}>
                    <div className="whitespace-pre-wrap">{m.text}</div>
                  </div>
                ))
              )}
              {isCopilotLoading && (
                <div className="text-xs text-amber-400 flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Auditing paper execution & frictions…</span>
                </div>
              )}
            </div>

            <div className="pt-2 border-t border-stone-800/60 flex items-center gap-2">
              <input
                type="text"
                value={copilotInput}
                onChange={e => setCopilotInput(e.target.value)}
                placeholder="Ask why this trade occurred…"
                className="flex-1 bg-stone-900 border border-stone-800 rounded px-2.5 py-1.5 text-xs text-stone-200 placeholder-stone-600 focus:outline-none"
                onKeyDown={e => { if (e.key === 'Enter') handleCopilotSend(copilotInput); }}
              />
              <button
                onClick={() => handleCopilotSend(copilotInput)}
                className="p-1.5 bg-amber-500 text-stone-950 rounded font-bold cursor-pointer"
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
