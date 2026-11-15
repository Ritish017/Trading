import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  TrendingUp, 
  TrendingDown, 
  Minus, 
  RefreshCw, 
  AlertCircle, 
  ShieldAlert, 
  Clock, 
  ExternalLink,
  Target,
  Compass,
  Layers,
  HelpCircle
} from 'lucide-react';

interface ScenarioDetail {
  price_target: number;
  probability: number;
  expected_change_pct: number;
  supporting_evidence: string[];
}

interface HorizonForecast {
  horizon: string;
  expected_price: number;
  lower_bound: number;
  upper_bound: number;
  volatility_assessment: string;
}

interface MarketForecast {
  forecast_id: string;
  version: number;
  instrument_id: string;
  symbol: string;
  current_price: number;
  currency: string;
  unit: string;
  exchange: string;
  forecast_timestamp: number;
  valid_until: number;
  direction: string;
  confidence: number;
  bullish_scenario: ScenarioDetail;
  base_scenario: ScenarioDetail;
  bearish_scenario: ScenarioDetail;
  price_range: { lower: number; upper: number };
  expected_change_percent: number;
  volatility_assessment: string;
  horizons: HorizonForecast[];
  self_challenge_critique: string;
  invalidation_conditions: string[];
  key_risks: string[];
  evidence_references: Array<{ type: string; statement: string; source: string; timestamp: number }>;
  reasoning_summary: string;
  status: string;
}

const FEATURED_COMMODITIES = [
  { id: 'GOLD_MCX', label: 'Gold (MCX)', icon: '🟡', unit: '₹/10g' },
  { id: 'SILVER_MCX', label: 'Silver (MCX)', icon: '⚪', unit: '₹/kg' },
  { id: 'CRUDEOIL_MCX', label: 'Crude Oil (MCX)', icon: '🛢️', unit: '₹/bbl' },
  { id: 'NATGAS_MCX', label: 'Natural Gas (MCX)', icon: '🔥', unit: '₹/mmBtu' },
  { id: 'COPPER_MCX', label: 'Copper (MCX)', icon: '🧱', unit: '₹/kg' },
  { id: 'NIFTY50_NSE', label: 'NIFTY 50 (NSE)', icon: '🇮🇳', unit: 'pts' },
  { id: 'USDINR_NSE', label: 'USD/INR (NSE)', icon: '💵', unit: '₹/USD' },
  { id: 'BTCUSD', label: 'Bitcoin (Global)', icon: '₿', unit: '$/BTC' },
];

export const GlobalCommodityForecastCard: React.FC = () => {
  const [selectedInst, setSelectedInst] = useState('GOLD_MCX');
  const [forecast, setForecast] = useState<MarketForecast | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchForecast = async (id: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/market-intelligence/forecast/${id}`);
      if (res.ok) {
        const data = await res.json();
        setForecast(data.latest);
      } else {
        setError('Forecast not yet generated for this instrument.');
      }
    } catch (e: any) {
      setError(e.message || 'Network error fetching forecast');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateForecast = async () => {
    setIsGenerating(true);
    setError(null);
    try {
      const res = await fetch(`/api/market-intelligence/forecast/generate/${selectedInst}`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setForecast(data);
      } else {
        setError('Failed to trigger APEX Chief Reasoner.');
      }
    } catch (e: any) {
      setError(e.message || 'Error executing forecast pipeline.');
    } finally {
      setIsGenerating(false);
    }
  };

  useEffect(() => {
    fetchForecast(selectedInst);
  }, [selectedInst]);

  const getDirectionBadge = (dir: string) => {
    if (dir === 'BULLISH') {
      return (
        <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <TrendingUp className="w-3.5 h-3.5 mr-1" />
          BULLISH
        </span>
      );
    }
    if (dir === 'BEARISH') {
      return (
        <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
          <TrendingDown className="w-3.5 h-3.5 mr-1" />
          BEARISH
        </span>
      );
    }
    return (
      <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
        <Minus className="w-3.5 h-3.5 mr-1" />
        CONSOLIDATION
      </span>
    );
  };

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 shadow-sm space-y-4">
      {/* Top Header: Selector & Run AI Pipeline */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-800/80 pb-3">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-xl bg-gradient-to-br from-indigo-500/20 to-amber-500/20 border border-indigo-500/30 text-indigo-400">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-stone-100 flex items-center gap-2">
              APEX Chief Reasoner — Global Market Intelligence
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                Single-LLM Protocol
              </span>
            </h3>
            <p className="text-xs text-stone-400">
              10-step dialectical reasoning across spot, futures curve, inventories & macro evidence
            </p>
          </div>
        </div>

        <button
          onClick={handleGenerateForecast}
          disabled={isGenerating}
          className="flex items-center space-x-1.5 px-3 py-1.5 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white rounded-xl text-xs font-medium transition shadow disabled:opacity-50"
        >
          <Sparkles className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
          <span>{isGenerating ? 'Executing 10-Step AI Protocol...' : 'Run Single-LLM Forecast'}</span>
        </button>
      </div>

      {/* Asset Switcher Chips */}
      <div className="flex items-center space-x-1.5 overflow-x-auto custom-scrollbar pb-1">
        {FEATURED_COMMODITIES.map((c) => (
          <button
            key={c.id}
            onClick={() => setSelectedInst(c.id)}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-xl text-xs whitespace-nowrap transition border ${
              selectedInst === c.id
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 font-semibold'
                : 'bg-stone-900/60 text-stone-400 border-stone-800 hover:text-stone-200'
            }`}
          >
            <span>{c.icon}</span>
            <span>{c.label}</span>
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="py-12 flex flex-col items-center justify-center space-y-2 text-stone-400">
          <RefreshCw className="w-5 h-5 animate-spin text-amber-400" />
          <p className="text-xs">Loading factual market intelligence & price scenarios...</p>
        </div>
      )}

      {error && !isLoading && !forecast && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-between">
          <div className="flex items-center space-x-2 text-amber-300 text-xs">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={handleGenerateForecast}
            className="px-3 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-xs rounded-lg font-medium border border-amber-500/30"
          >
            Generate Now
          </button>
        </div>
      )}

      {forecast && !isLoading && (
        <div className="space-y-4">
          {/* Snapshot Header */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-stone-900/60 border border-stone-800/80 rounded-xl p-3">
            <div>
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block font-semibold">Instrument & Unit</span>
              <span className="text-sm font-bold text-stone-100">{forecast.symbol} ({forecast.exchange})</span>
              <span className="text-[11px] text-stone-400 block font-mono">{forecast.unit}</span>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block font-semibold">Current Price</span>
              <span className="text-sm font-bold text-stone-100 font-mono">
                {forecast.currency} {forecast.current_price.toLocaleString()}
              </span>
              <span className="text-[11px] text-stone-400 block">7D Range: {forecast.price_range.lower.toLocaleString()} – {forecast.price_range.upper.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block font-semibold">Reasoning Stance</span>
              <div className="mt-0.5">{getDirectionBadge(forecast.direction)}</div>
              <span className="text-[11px] text-stone-400 block mt-0.5">Confidence: {Math.round(forecast.confidence * 100)}%</span>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block font-semibold">Version & Status</span>
              <span className="text-xs font-mono text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                v{forecast.version} • {forecast.status}
              </span>
              <span className="text-[10px] text-stone-500 block mt-1 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Updated {new Date(forecast.forecast_timestamp * 1000).toLocaleTimeString()}
              </span>
            </div>
          </div>

          {/* Reasoning Synthesis */}
          <div className="p-3 bg-stone-900/40 border border-stone-800/60 rounded-xl">
            <h4 className="text-xs font-semibold text-stone-300 uppercase tracking-wider mb-1 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              Central Reasoning Synthesis (10-Step Dialectic)
            </h4>
            <p className="text-xs text-stone-300 leading-relaxed">{forecast.reasoning_summary}</p>
          </div>

          {/* 3 Scenario Cards (Probabilities sum to 100%) */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-orange-400" />
                Future Price Scenarios (Normalized $\sum P = 1.00$)
              </h4>
              <span className="text-[10px] text-stone-500 font-mono">
                P(Bull): {Math.round(forecast.bullish_scenario.probability * 100)}% | 
                P(Base): {Math.round(forecast.base_scenario.probability * 100)}% | 
                P(Bear): {Math.round(forecast.bearish_scenario.probability * 100)}%
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Bullish Scenario */}
              <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-xl p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-emerald-400 flex items-center gap-1">
                    <TrendingUp className="w-3.5 h-3.5" /> Bullish Target
                  </span>
                  <span className="text-xs font-mono font-bold text-emerald-300 px-1.5 py-0.5 rounded bg-emerald-500/10">
                    {Math.round(forecast.bullish_scenario.probability * 100)}% Prob
                  </span>
                </div>
                <div className="text-base font-bold font-mono text-emerald-200">
                  {forecast.currency} {forecast.bullish_scenario.price_target.toLocaleString()}
                  <span className="text-xs font-normal text-emerald-400 ml-1.5">
                    ({forecast.bullish_scenario.expected_change_pct > 0 ? '+' : ''}{forecast.bullish_scenario.expected_change_pct}%)
                  </span>
                </div>
                <ul className="text-[11px] text-stone-400 space-y-1">
                  {forecast.bullish_scenario.supporting_evidence.map((ev, i) => (
                    <li key={i} className="flex items-start gap-1">
                      <span className="text-emerald-400 font-bold">•</span>
                      <span>{ev}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Base Scenario */}
              <div className="bg-stone-900/60 border border-stone-700/80 rounded-xl p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-stone-300 flex items-center gap-1">
                    <Minus className="w-3.5 h-3.5" /> Base Scenario
                  </span>
                  <span className="text-xs font-mono font-bold text-stone-200 px-1.5 py-0.5 rounded bg-stone-700/40">
                    {Math.round(forecast.base_scenario.probability * 100)}% Prob
                  </span>
                </div>
                <div className="text-base font-bold font-mono text-stone-100">
                  {forecast.currency} {forecast.base_scenario.price_target.toLocaleString()}
                  <span className="text-xs font-normal text-stone-400 ml-1.5">
                    ({forecast.base_scenario.expected_change_pct > 0 ? '+' : ''}{forecast.base_scenario.expected_change_pct}%)
                  </span>
                </div>
                <ul className="text-[11px] text-stone-400 space-y-1">
                  {forecast.base_scenario.supporting_evidence.map((ev, i) => (
                    <li key={i} className="flex items-start gap-1">
                      <span className="text-stone-400 font-bold">•</span>
                      <span>{ev}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Bearish Scenario */}
              <div className="bg-rose-950/20 border border-rose-500/30 rounded-xl p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-rose-400 flex items-center gap-1">
                    <TrendingDown className="w-3.5 h-3.5" /> Bearish Target
                  </span>
                  <span className="text-xs font-mono font-bold text-rose-300 px-1.5 py-0.5 rounded bg-rose-500/10">
                    {Math.round(forecast.bearish_scenario.probability * 100)}% Prob
                  </span>
                </div>
                <div className="text-base font-bold font-mono text-rose-200">
                  {forecast.currency} {forecast.bearish_scenario.price_target.toLocaleString()}
                  <span className="text-xs font-normal text-rose-400 ml-1.5">
                    ({forecast.bearish_scenario.expected_change_pct}%)
                  </span>
                </div>
                <ul className="text-[11px] text-stone-400 space-y-1">
                  {forecast.bearish_scenario.supporting_evidence.map((ev, i) => (
                    <li key={i} className="flex items-start gap-1">
                      <span className="text-rose-400 font-bold">•</span>
                      <span>{ev}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* Self-Challenge Dialectic Card */}
          <div className="p-3 bg-amber-950/20 border border-amber-500/30 rounded-xl space-y-2">
            <h4 className="text-xs font-bold text-amber-400 flex items-center gap-1.5">
              <ShieldAlert className="w-4 h-4 text-amber-400 flex-shrink-0" />
              Step 7: Dialectical Self-Critique & Anti-Overconfidence Challenge
            </h4>
            <p className="text-xs text-amber-200/90 leading-relaxed italic">
              "{forecast.self_challenge_critique}"
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1 border-t border-amber-500/20 text-[11px]">
              <div>
                <span className="text-stone-400 font-semibold block">Invalidation Triggers:</span>
                <ul className="text-rose-300 list-disc list-inside">
                  {forecast.invalidation_conditions.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
              <div>
                <span className="text-stone-400 font-semibold block">Primary Macro Risks:</span>
                <ul className="text-amber-300 list-disc list-inside">
                  {forecast.key_risks.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* Factual Evidence & Provenance Explorer */}
          <div className="p-3 bg-stone-900/60 border border-stone-800/80 rounded-xl space-y-2">
            <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              Traceable Evidence References & Provenance
            </h4>
            <div className="space-y-1.5">
              {forecast.evidence_references.map((ref, idx) => (
                <div key={idx} className="flex items-center justify-between text-[11px] p-1.5 bg-stone-950/40 rounded border border-stone-800/40">
                  <div className="flex items-center space-x-2">
                    <span className="px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300 font-mono text-[9px] border border-indigo-500/20">
                      {ref.type}
                    </span>
                    <span className="text-stone-300">{ref.statement}</span>
                  </div>
                  <span className="text-stone-500 text-[10px] font-mono">{ref.source}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
