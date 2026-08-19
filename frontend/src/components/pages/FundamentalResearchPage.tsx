import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Building2, Landmark, TrendingUp, TrendingDown, DollarSign,
  PieChart, BarChart3, Layers, Sparkles, Shield, AlertTriangle,
  CheckCircle2, XCircle, MinusCircle, Clock, Calendar, RefreshCw,
  Search, ArrowUpRight, ArrowDownRight, Compass, Target, Bookmark,
  Split, GitMerge, Flame, Send, Loader2, MessageSquare, AlertOctagon,
  ChevronDown, ChevronUp, Sliders, Eye
} from 'lucide-react';
import { NSEStock } from '../../types/indianMarket';

export interface CompanyProfileData {
  symbol: string;
  company_name: string;
  sector: string;
  industry: string;
  market_cap_crores?: number | null;
  shares_outstanding?: number | null;
  listing_date?: string | null;
  description?: string | null;
  isin?: string | null;
  data_status: string;
}

export interface IncomeStatementData {
  symbol: string;
  period_end: string;
  publication_timestamp: number;
  frequency: string;
  revenue?: number | null;
  ebitda?: number | null;
  ebit?: number | null;
  operating_profit?: number | null;
  interest_expense?: number | null;
  tax_expense?: number | null;
  net_profit?: number | null;
  eps?: number | null;
  shares_outstanding?: number | null;
}

export interface BalanceSheetData {
  symbol: string;
  period_end: string;
  publication_timestamp: number;
  frequency: string;
  cash_and_equivalents?: number | null;
  total_current_assets?: number | null;
  total_assets?: number | null;
  total_debt?: number | null;
  net_debt?: number | null;
  total_current_liabilities?: number | null;
  total_liabilities?: number | null;
  shareholders_equity?: number | null;
  working_capital?: number | null;
}

export interface CashFlowData {
  symbol: string;
  period_end: string;
  publication_timestamp: number;
  frequency: string;
  operating_cash_flow?: number | null;
  capex?: number | null;
  free_cash_flow?: number | null;
  dividends_paid?: number | null;
}

export interface FactorScorecardItemData {
  factor_id: string;
  name: string;
  category: string;
  raw_value?: number | null;
  unit: string;
  formula: string;
  direction_preference: string;
  percentile_rank?: number | null;
  data_status: string;
  publication_date?: string | null;
  reporting_period?: string | null;
  source: string;
}

export interface FactorScorecardData {
  symbol: string;
  company_name: string;
  sector: string;
  industry: string;
  market_cap_crores?: number | null;
  as_of_date: string;
  overall_fundamental_profile: string;
  category_summaries: Record<string, {
    average_percentile: number;
    rating: string;
    factors_available: number;
  }>;
  factors: FactorScorecardItemData[];
}

export interface ConfluenceMatrixData {
  symbol: string;
  technical_state: string;
  technical_evidence: string;
  fundamental_state: string;
  fundamental_evidence: string;
  confluence_quadrant: string;
  evidence_breakdown: Array<{ layer: string; state?: string; detail: string }>;
}

export interface PortfolioSimulationData {
  strategy_name: string;
  target_factor_id: string;
  rebalance_frequency: string;
  universe_size: number;
  total_rebalances: number;
  cagr_pct: number;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  annual_turnover_pct: number;
  avg_sector_hhi: number;
  max_single_stock_exposure_pct: number;
  hit_rate_pct: number;
  rebalance_history: Array<{
    rebalance_date: string;
    selected_constituents: string[];
    weights: Record<string, number>;
    turnover_pct: number;
    top_sector: string;
    top_sector_weight_pct: number;
    sector_hhi: number;
    period_return_pct: number;
  }>;
  equity_curve: number[];
}

export interface FundamentalResearchPageProps {
  stocks: NSEStock[];
  selectedSymbol: string;
  onSelectSymbol?: (symbol: string) => void;
}

const QUICK_SYMBOLS = [
  'RELIANCE.NS',
  'TCS.NS',
  'HDFCBANK.NS',
  'INFY.NS',
  'ICICIBANK.NS',
  'TATAMOTORS.NS',
  'SBIN.NS',
];

export const FundamentalResearchPage: React.FC<FundamentalResearchPageProps> = ({
  stocks,
  selectedSymbol,
  onSelectSymbol,
}) => {
  const [symbol, setSymbol] = useState<string>(selectedSymbol || 'RELIANCE.NS');
  const [activeTab, setActiveTab] = useState<'SCORECARD' | 'STATEMENTS' | 'CONFLUENCE' | 'PORTFOLIO'>('SCORECARD');

  const [profile, setProfile] = useState<CompanyProfileData | null>(null);
  const [scorecard, setScorecard] = useState<FactorScorecardData | null>(null);
  const [confluence, setConfluence] = useState<ConfluenceMatrixData | null>(null);
  const [incomes, setIncomes] = useState<IncomeStatementData[]>([]);
  const [balances, setBalances] = useState<BalanceSheetData[]>([]);
  const [cashflows, setCashflows] = useState<CashFlowData[]>([]);
  const [simResult, setSimResult] = useState<PortfolioSimulationData | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Copilot State
  const [copilotMessages, setCopilotMessages] = useState<Array<{ role: string; text: string }>>([]);
  const [copilotInput, setCopilotInput] = useState<string>('');
  const [isCopilotLoading, setIsCopilotLoading] = useState<boolean>(false);

  const loadData = useCallback(async (sym = symbol) => {
    setIsLoading(true);
    setError(null);
    try {
      // 1. Profile
      const profRes = await fetch(`/api/fundamentals/company/${encodeURIComponent(sym)}`);
      if (profRes.ok) {
        const profJson = await profRes.json();
        setProfile(profJson.profile || null);
      }

      // 2. Statements
      const stmtRes = await fetch(`/api/fundamentals/statements/${encodeURIComponent(sym)}`);
      if (stmtRes.ok) {
        const stmtJson = await stmtRes.json();
        setIncomes(stmtJson.income_statements || []);
        setBalances(stmtJson.balance_sheets || []);
        setCashflows(stmtJson.cash_flows || []);
      }

      // 3. Scorecard
      const scoreRes = await fetch(`/api/fundamentals/scorecard/${encodeURIComponent(sym)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (scoreRes.ok) {
        const scoreJson = await scoreRes.json();
        setScorecard(scoreJson.scorecard || null);
      }

      // 4. Confluence
      const confRes = await fetch(`/api/fundamentals/confluence/${encodeURIComponent(sym)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ technical_active_count: 5, technical_total_count: 20 }),
      });
      if (confRes.ok) {
        const confJson = await confRes.json();
        setConfluence(confJson.confluence_matrix || null);
      }
    } catch (e: any) {
      setError(e.message || "Failed to load fundamental data");
    } finally {
      setIsLoading(false);
    }
  }, [symbol]);

  const runSimulation = useCallback(async (factorId = 'PROFITABILITY_ROE') => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/fundamentals/portfolio-research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ factor_id: factorId, rebalance_frequency: 'QUARTERLY', top_quantile: 0.30 }),
      });
      if (res.ok) {
        const data = await res.json();
        setSimResult(data.simulation_result || null);
      }
    } catch (e) {
      // ignore
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData(symbol);
  }, [symbol, loadData]);

  const handleCopilotSend = async (userText: string) => {
    if (!userText.trim() || isCopilotLoading) return;
    const textToSend = userText.trim();
    const isSkeptic = textToSend.toUpperCase().includes('CHALLENGE');
    setCopilotInput('');
    setCopilotMessages(prev => [...prev, { role: 'user', text: textToSend }]);
    setIsCopilotLoading(true);

    try {
      const endpoint = isSkeptic ? `/api/fundamentals/challenge/${encodeURIComponent(symbol)}` : '/api/fundamentals/copilot';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          user_message: textToSend,
          scorecard: scorecard || null,
          confluence: confluence || null,
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
    <div className="flex-1 flex flex-col h-[calc(100vh-175px)] overflow-y-auto custom-scrollbar p-3 space-y-3 bg-[#0a0b10] font-mono">
      {/* ── Header ── */}
      <div className="bg-[#12131b] border border-stone-800/80 rounded-2xl p-3 flex flex-wrap items-center justify-between gap-3 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-600/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-black shadow-inner">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-black text-sm text-white tracking-wide">{symbol}</span>
              <span className="text-xs text-stone-400 font-semibold">{profile?.company_name}</span>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-stone-900 border border-stone-800 text-stone-300">
                {profile?.sector || 'SECTOR'}
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs text-stone-400 mt-0.5">
              <span>MCap: ₹{profile?.market_cap_crores ? (profile.market_cap_crores / 1000).toFixed(1) + 'k Cr' : '---'}</span>
              <span>ISIN: {profile?.isin || '---'}</span>
              <span className="text-emerald-400 font-bold">● Point-in-Time Audited</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto custom-scrollbar max-w-md">
          {QUICK_SYMBOLS.map(sym => (
            <button
              key={sym}
              onClick={() => { setSymbol(sym); onSelectSymbol?.(sym); }}
              className={`px-2 py-1 text-[10px] font-bold rounded-lg border transition-all cursor-pointer shrink-0 ${
                symbol === sym
                  ? 'bg-emerald-600 text-white border-emerald-400 shadow-md'
                  : 'bg-stone-900/60 text-stone-400 border-stone-800 hover:text-stone-200 hover:bg-stone-800'
              }`}
            >
              {sym.replace('.NS', '')}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center bg-stone-900 p-0.5 rounded-xl border border-stone-800 text-xs">
            <button
              onClick={() => setActiveTab('SCORECARD')}
              className={`px-2.5 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'SCORECARD' ? 'bg-emerald-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              <PieChart className="w-3.5 h-3.5" />
              <span>Factor Scorecard</span>
            </button>
            <button
              onClick={() => setActiveTab('STATEMENTS')}
              className={`px-2.5 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'STATEMENTS' ? 'bg-emerald-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              <Landmark className="w-3.5 h-3.5" />
              <span>Financial Statements</span>
            </button>
            <button
              onClick={() => setActiveTab('CONFLUENCE')}
              className={`px-2.5 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'CONFLUENCE' ? 'bg-emerald-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              <GitMerge className="w-3.5 h-3.5" />
              <span>Tech × Fund Matrix</span>
            </button>
            <button
              onClick={() => { setActiveTab('PORTFOLIO'); runSimulation(); }}
              className={`px-2.5 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'PORTFOLIO' ? 'bg-emerald-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              <Split className="w-3.5 h-3.5" />
              <span>Factor Portfolio</span>
            </button>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="p-12 bg-[#12131b] border border-stone-800 rounded-2xl flex flex-col items-center justify-center text-stone-400 space-y-3">
          <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
          <span className="text-xs">Computing Point-in-Time Factors & Sector Percentiles…</span>
        </div>
      )}

      {/* ── SubTab 1: FACTOR SCORECARD ── */}
      {activeTab === 'SCORECARD' && scorecard && !isLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
          <div className="lg:col-span-8 space-y-3">
            {/* Category KPI Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {Object.entries(scorecard.category_summaries).map(([cat, c]) => (
                <div key={cat} className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3 space-y-1">
                  <div className="text-[10px] text-stone-500 uppercase font-bold">{cat}</div>
                  <div className="text-xl font-black text-white">{c.average_percentile}%</div>
                  <div className="text-[10px] text-stone-400 flex items-center justify-between">
                    <span>Rating:</span>
                    <span className={`font-bold ${c.rating === 'STRONG' ? 'text-emerald-400' : c.rating === 'WEAK' ? 'text-rose-400' : 'text-amber-400'}`}>
                      {c.rating}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Factor Table */}
            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
              <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
                <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
                  <BarChart3 className="w-4 h-4 text-emerald-400" /> Quantitative Factor Registry & Sector Percentiles
                </span>
                <span className="text-[10px] text-stone-500">As of: {scorecard.as_of_date}</span>
              </div>

              <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-stone-800 text-stone-500 text-[10px] uppercase">
                      <th className="pb-2 font-bold">Factor</th>
                      <th className="pb-2 font-bold">Raw Value</th>
                      <th className="pb-2 font-bold">Sector Percentile</th>
                      <th className="pb-2 font-bold">Preference</th>
                      <th className="pb-2 font-bold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-800/60 text-[11px]">
                    {scorecard.factors.map(f => (
                      <tr key={f.factor_id} className="hover:bg-stone-900/40 transition-all">
                        <td className="py-2.5 font-bold text-stone-200">
                          <div>{f.name}</div>
                          <div className="text-[9px] text-stone-500">{f.formula}</div>
                        </td>
                        <td className="py-2.5 font-bold text-white">
                          {f.raw_value !== null && f.raw_value !== undefined ? `${f.raw_value} ${f.unit === 'PERCENT' ? '%' : ''}` : '---'}
                        </td>
                        <td className="py-2.5">
                          {f.percentile_rank !== null && f.percentile_rank !== undefined ? (
                            <div className="flex items-center gap-2">
                              <div className="w-16 h-1.5 bg-stone-900 rounded-full overflow-hidden flex border border-stone-800">
                                <div style={{ width: `${f.percentile_rank}%` }} className="bg-emerald-500" />
                              </div>
                              <span className="font-bold text-stone-300">{f.percentile_rank}%</span>
                            </div>
                          ) : '---'}
                        </td>
                        <td className="py-2.5 text-stone-400 text-[10px]">{f.direction_preference}</td>
                        <td className="py-2.5">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${f.data_status === 'AVAILABLE' ? 'bg-emerald-950 text-emerald-300' : 'bg-stone-900 text-stone-500'}`}>
                            {f.data_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Copilot Sidebar */}
          <div className="lg:col-span-4 space-y-3 flex flex-col">
            <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3 flex flex-col h-full shadow-2xl">
              <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 mb-2">
                <div className="flex items-center gap-2 text-xs font-bold text-white">
                  <Sparkles className="w-4 h-4 text-emerald-400" />
                  <span>Fundamental Copilot</span>
                </div>
                <button
                  onClick={() => handleCopilotSend('CHALLENGE THIS FUNDAMENTAL THESIS')}
                  className="px-2 py-0.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded text-[10px] font-bold flex items-center gap-1 cursor-pointer"
                >
                  <Flame className="w-3 h-3 text-rose-400" />
                  <span>Skeptic Audit</span>
                </button>
              </div>

              <div className="flex-1 space-y-2 overflow-y-auto custom-scrollbar max-h-[400px] text-xs">
                {copilotMessages.length === 0 ? (
                  <div className="text-center py-6 text-stone-500 text-xs space-y-2">
                    <MessageSquare className="w-8 h-8 mx-auto text-stone-600" />
                    <div>Ask about ROE drivers, debt leverage, cash conversion, or launch a Skeptic Audit.</div>
                  </div>
                ) : (
                  copilotMessages.map((m, i) => (
                    <div key={i} className={`p-2.5 rounded-lg leading-relaxed ${m.role === 'user' ? 'bg-emerald-600 text-white ml-auto max-w-[85%]' : 'bg-[#181a24] text-stone-200 border border-stone-800'}`}>
                      <div className="whitespace-pre-wrap">{m.text}</div>
                    </div>
                  ))
                )}
                {isCopilotLoading && (
                  <div className="text-xs text-emerald-400 flex items-center gap-2">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Auditing financial filings…</span>
                  </div>
                )}
              </div>

              <div className="pt-2 border-t border-stone-800/60 flex items-center gap-2">
                <input
                  type="text"
                  value={copilotInput}
                  onChange={e => setCopilotInput(e.target.value)}
                  placeholder="Ask or Challenge this thesis…"
                  className="flex-1 bg-stone-900 border border-stone-800 rounded px-2.5 py-1.5 text-xs text-stone-200 placeholder-stone-600 focus:outline-none"
                  onKeyDown={e => { if (e.key === 'Enter') handleCopilotSend(copilotInput); }}
                />
                <button
                  onClick={() => handleCopilotSend(copilotInput)}
                  className="p-1.5 bg-emerald-600 text-white rounded cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── SubTab 2: FINANCIAL STATEMENTS ── */}
      {activeTab === 'STATEMENTS' && !isLoading && (
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
          <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
            <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
              <Landmark className="w-4 h-4 text-emerald-400" /> Multi-Year Normalized Financial Statements (₹ in Crores)
            </span>
          </div>

          <div className="space-y-4">
            <div>
              <div className="font-bold text-xs text-stone-300 mb-1.5">Income Statement</div>
              <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-stone-800 text-stone-500 text-[10px]">
                      <th className="pb-1.5">Metric</th>
                      {incomes.map(inc => (
                        <th key={inc.period_end} className="pb-1.5">{inc.period_end}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-800/60 text-[11px]">
                    <tr>
                      <td className="py-2 text-stone-400 font-bold">Revenue</td>
                      {incomes.map(inc => <td key={inc.period_end} className="py-2 font-bold text-white">₹{inc.revenue?.toLocaleString() || '---'}</td>)}
                    </tr>
                    <tr>
                      <td className="py-2 text-stone-400 font-bold">EBITDA</td>
                      {incomes.map(inc => <td key={inc.period_end} className="py-2 text-emerald-400">₹{inc.ebitda?.toLocaleString() || '---'}</td>)}
                    </tr>
                    <tr>
                      <td className="py-2 text-stone-400 font-bold">Net Profit</td>
                      {incomes.map(inc => <td key={inc.period_end} className="py-2 font-black text-white">₹{inc.net_profit?.toLocaleString() || '---'}</td>)}
                    </tr>
                    <tr>
                      <td className="py-2 text-stone-400 font-bold">Diluted EPS</td>
                      {incomes.map(inc => <td key={inc.period_end} className="py-2 text-amber-400">₹{inc.eps || '---'}</td>)}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <div className="font-bold text-xs text-stone-300 mb-1.5">Balance Sheet & Solvency</div>
              <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-stone-800 text-stone-500 text-[10px]">
                      <th className="pb-1.5">Metric</th>
                      {balances.map(b => (
                        <th key={b.period_end} className="pb-1.5">{b.period_end}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-800/60 text-[11px]">
                    <tr>
                      <td className="py-2 text-stone-400 font-bold">Shareholders' Equity</td>
                      {balances.map(b => <td key={b.period_end} className="py-2 text-white">₹{b.shareholders_equity?.toLocaleString() || '---'}</td>)}
                    </tr>
                    <tr>
                      <td className="py-2 text-stone-400 font-bold">Total Debt</td>
                      {balances.map(b => <td key={b.period_end} className="py-2 text-rose-400">₹{b.total_debt?.toLocaleString() || '0'}</td>)}
                    </tr>
                    <tr>
                      <td className="py-2 text-stone-400 font-bold">Cash & Equivalents</td>
                      {balances.map(b => <td key={b.period_end} className="py-2 text-emerald-400">₹{b.cash_and_equivalents?.toLocaleString() || '---'}</td>)}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── SubTab 3: TECH x FUND CONFLUENCE ── */}
      {activeTab === 'CONFLUENCE' && confluence && !isLoading && (
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
          <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
            <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
              <GitMerge className="w-4 h-4 text-violet-400" /> Multi-Layer Technical × Fundamental Confluence Matrix
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-violet-950 border border-violet-600/50 text-violet-300">
              {confluence.confluence_quadrant}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-stone-900/40 border border-stone-800 space-y-1">
              <div className="text-[10px] text-stone-500 uppercase font-bold">Technical Layer Status</div>
              <div className="text-base font-black text-white">{confluence.technical_state}</div>
              <div className="text-[11px] text-stone-400">{confluence.technical_evidence}</div>
            </div>
            <div className="p-3 rounded-lg bg-stone-900/40 border border-stone-800 space-y-1">
              <div className="text-[10px] text-stone-500 uppercase font-bold">Fundamental Factor Layer</div>
              <div className="text-base font-black text-emerald-400">{confluence.fundamental_state}</div>
              <div className="text-[11px] text-stone-400">{confluence.fundamental_evidence}</div>
            </div>
          </div>
        </div>
      )}

      {/* ── SubTab 4: FACTOR PORTFOLIO SIMULATOR ── */}
      {activeTab === 'PORTFOLIO' && simResult && !isLoading && (
        <div className="bg-[#12131b] border border-stone-800/80 rounded-xl p-3.5 space-y-3">
          <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 text-xs">
            <span className="font-bold text-stone-200 uppercase flex items-center gap-1.5">
              <Split className="w-4 h-4 text-emerald-400" /> Cross-Sectional Factor Portfolio Simulation ({simResult.strategy_name})
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">CAGR</div>
              <div className="text-lg font-black text-emerald-400 mt-0.5">{simResult.cagr_pct}%</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Sharpe Ratio</div>
              <div className="text-lg font-black text-cyan-400 mt-0.5">{simResult.sharpe_ratio}</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Max Drawdown</div>
              <div className="text-lg font-black text-rose-400 mt-0.5">{simResult.max_drawdown_pct}%</div>
            </div>
            <div className="p-2.5 rounded bg-stone-900/40 border border-stone-800">
              <div className="text-[10px] text-stone-500 uppercase">Avg Sector HHI</div>
              <div className="text-lg font-black text-white mt-0.5">{simResult.avg_sector_hhi}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
