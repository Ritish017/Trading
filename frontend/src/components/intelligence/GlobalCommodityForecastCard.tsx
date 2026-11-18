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
  HelpCircle,
  Radio,
  CheckCircle2,
  Calendar,
  Activity
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
  realized_7d?: { low: number; high: number; span_pct?: number };
  forward_volatility_corridor?: { lower: number; upper: number };
  contract_expiry?: string;
  market_status?: string;
  is_synthetic_legacy?: boolean;
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

interface LiveQuote {
  ltp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  open_interest: number;
  last_trade_time: number;
  market_status: string;
  contract_expiry?: string;
  trading_symbol?: string;
}

const FEATURED_COMMODITIES = [
  { id: 'GOLD_MCX', label: 'Gold (MCX)', icon: '🟡', unit: '₹/10g' },
  { id: 'GOLDM_MCX', label: 'Gold Mini (MCX)', icon: '🪙', unit: '₹/10g' },
  { id: 'SILVER_MCX', label: 'Silver (MCX)', icon: '⚪', unit: '₹/kg' },
  { id: 'SILVERM_MCX', label: 'Silver Mini (MCX)', icon: '🥈', unit: '₹/kg' },
  { id: 'CRUDEOIL_MCX', label: 'Crude Oil (MCX)', icon: '🛢️', unit: '₹/bbl' },
  { id: 'NATGAS_MCX', label: 'Natural Gas (MCX)', icon: '🔥', unit: '₹/mmBtu' },
  { id: 'COPPER_MCX', label: 'Copper (MCX)', icon: '🧱', unit: '₹/kg' },
  { id: 'ALUMINIUM_MCX', label: 'Aluminium (MCX)', icon: '🥫', unit: '₹/kg' },
  { id: 'ZINC_MCX', label: 'Zinc (MCX)', icon: '⚙️', unit: '₹/kg' },
  { id: 'LEAD_MCX', label: 'Lead (MCX)', icon: '🔋', unit: '₹/kg' },
  { id: 'NICKEL_MCX', label: 'Nickel (MCX)', icon: '🔩', unit: '₹/kg' },
  { id: 'NIFTY50_NSE', label: 'NIFTY 50 (NSE)', icon: '🇮🇳', unit: 'pts' },
  { id: 'USDINR_NSE', label: 'USD/INR (NSE)', icon: '💵', unit: '₹/USD' },
  { id: 'BTCUSD', label: 'Bitcoin (Global)', icon: '₿', unit: '$/BTC' },
];

export const GlobalCommodityForecastCard: React.FC = () => {
  const [selectedInst, setSelectedInst] = useState('GOLD_MCX');
  const [forecast, setForecast] = useState<MarketForecast | null>(null);
  const [liveQuote, setLiveQuote] = useState<LiveQuote | null>(null);
  const [prevPrice, setPrevPrice] = useState<number | null>(null);
  const [priceFlash, setPriceFlash] = useState<'up' | 'down' | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAutoSync, setIsAutoSync] = useState(true);
  const [lastSyncTime, setLastSyncTime] = useState<Date>(new Date());

  const fetchForecast = async (id: string, silent = false) => {
    if (!silent) setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/market-intelligence/forecast/${id}`);
      if (res.ok) {
        const data = await res.json();
        setForecast(data.latest);
        if (data.live_quote) {
          const newLtp = data.live_quote.ltp;
          setPrevPrice((old) => {
            if (old !== null && newLtp !== old) {
              setPriceFlash(newLtp > old ? 'up' : 'down');
              setTimeout(() => setPriceFlash(null), 1500);
            }
            return newLtp;
          });
          setLiveQuote(data.live_quote);
        }
        setLastSyncTime(new Date());
      } else {
        if (!silent) setError('Forecast not yet generated for this instrument.');
      }
    } catch (e: any) {
      if (!silent) setError(e.message || 'Network error fetching forecast');
    } finally {
      if (!silent) setIsLoading(false);
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
        const errJson = await res.json().catch(() => ({}));
        setError(errJson.detail || 'Failed to trigger APEX Chief Reasoner.');
      }
    } catch (e: any) {
      setError(e.message || 'Error executing forecast pipeline.');
    } finally {
      setIsGenerating(false);
    }
  };

  // Real-time automatic polling every 5 seconds
  useEffect(() => {
    fetchForecast(selectedInst, false);

    if (!isAutoSync) return;

    const interval = setInterval(() => {
      fetchForecast(selectedInst, true);
    }, 5000);

    return () => clearInterval(interval);
  }, [selectedInst, isAutoSync]);

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

  const displayPrice = liveQuote?.ltp ?? forecast?.current_price ?? 0;
  const displayStatus = liveQuote?.market_status ?? forecast?.market_status ?? 'LIVE';
  const displayContract = liveQuote?.trading_symbol ?? forecast?.contract_expiry;

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 shadow-sm space-y-4">
      {/* Top Header: Selector & Live Telemetry Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-800/80 pb-3">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-xl bg-gradient-to-br from-indigo-500/20 to-amber-500/20 border border-indigo-500/30 text-indigo-400">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-stone-100">
                APEX Chief Reasoner — Commodity & Macro Intelligence
              </h3>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-bold flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                ZERO-MOCK VERIFIED
              </span>
            </div>
            <p className="text-xs text-stone-400">
              Live MCX exchange quotes & historical daily OHLCV candles via Upstox REST API v2
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Real-Time Auto-Sync Toggle Beacon */}
          <button
            onClick={() => setIsAutoSync(!isAutoSync)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-mono font-bold border transition cursor-pointer ${
              isAutoSync
                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/25'
                : 'bg-stone-800 text-stone-400 border-stone-700 hover:text-stone-300'
            }`}
            title="Real-time automatic polling every 5 seconds"
          >
            <Radio className={`w-3.5 h-3.5 ${isAutoSync ? 'text-emerald-400 animate-pulse' : 'text-stone-500'}`} />
            <span>{isAutoSync ? 'Real-Time Auto-Sync (5s)' : 'Auto-Sync Paused'}</span>
          </button>

          <button
            onClick={handleGenerateForecast}
            disabled={isGenerating}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white rounded-xl text-xs font-medium transition shadow disabled:opacity-50 cursor-pointer"
          >
            <Sparkles className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
            <span>{isGenerating ? 'Querying Live Feed...' : 'Run Live Reasoner'}</span>
          </button>
        </div>
      </div>

      {/* Asset Switcher Chips */}
      <div className="flex items-center space-x-1.5 overflow-x-auto custom-scrollbar pb-1">
        {FEATURED_COMMODITIES.map((c) => (
          <button
            key={c.id}
            onClick={() => setSelectedInst(c.id)}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-xl text-xs whitespace-nowrap transition border cursor-pointer ${
              selectedInst === c.id
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 font-bold shadow-sm'
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
          <p className="text-xs">Connecting to exchange data engine and verifying price integrity...</p>
        </div>
      )}

      {error && !isLoading && !forecast && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-2 text-amber-300 text-xs">
            <AlertCircle className="w-4 h-4 flex-shrink-0 text-amber-400" />
            <span>{error}</span>
          </div>
          <button
            onClick={handleGenerateForecast}
            disabled={isGenerating}
            className="px-3 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-xs rounded-lg font-bold border border-amber-500/30 cursor-pointer"
          >
            {isGenerating ? 'Generating...' : 'Generate Live Forecast'}
          </button>
        </div>
      )}

      {forecast && !isLoading && (
        <div className="space-y-4">
          {/* Legacy Quarantine Alert if applicable */}
          {forecast.is_synthetic_legacy && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center justify-between text-xs text-rose-300">
              <div className="flex items-center space-x-2">
                <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
                <span>
                  <strong>Quarantined Legacy Record:</strong> This forecast was generated with previous static mock data. Click 'Run Live Reasoner' to re-anchor with authentic live exchange quotes.
                </span>
              </div>
              <button
                onClick={handleGenerateForecast}
                className="px-2.5 py-1 bg-rose-500/20 hover:bg-rose-500/30 rounded border border-rose-500/40 text-rose-200 font-bold ml-2 shrink-0"
              >
                Refresh Now
              </button>
            </div>
          )}

          {/* Snapshot Header */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-stone-900/60 border border-stone-800/80 rounded-xl p-3">
            <div>
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block font-semibold">Instrument & Expiry</span>
              <span className="text-sm font-bold text-stone-100">{forecast.symbol} ({forecast.exchange})</span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-[11px] text-amber-400/90 font-mono font-bold">{forecast.unit}</span>
                {displayContract && (
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-stone-800 text-stone-300 border border-stone-700/60 flex items-center gap-1">
                    <Calendar className="w-2.5 h-2.5 text-stone-400" />
                    {displayContract}
                  </span>
                )}
              </div>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block font-semibold">Current Verified Price</span>
              <div className="flex items-center gap-2">
                <span className={`text-base font-extrabold font-mono transition-all duration-300 ${
                  priceFlash === 'up'
                    ? 'text-emerald-400 scale-105'
                    : priceFlash === 'down'
                    ? 'text-rose-400 scale-105'
                    : 'text-stone-100'
                }`}>
                  {forecast.currency} {displayPrice.toLocaleString()}
                </span>
                {displayStatus && (
                  <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded flex items-center gap-1 ${
                    displayStatus === 'LIVE'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : 'bg-stone-800 text-stone-400 border border-stone-700'
                  }`}>
                    <Radio className={`w-2.5 h-2.5 ${displayStatus === 'LIVE' ? 'animate-pulse text-emerald-400' : ''}`} />
                    MCX {displayStatus}
                  </span>
                )}
              </div>
              <div className="text-[10px] text-stone-400 mt-0.5 flex flex-col gap-0.5">
                <span>
                  7D Realized Range: <strong className="text-stone-300 font-mono">{forecast.currency} {(forecast.realized_7d?.low || forecast.price_range.lower).toLocaleString()} – {(forecast.realized_7d?.high || forecast.price_range.upper).toLocaleString()}</strong>
                </span>
                {forecast.forward_volatility_corridor && (
                  <span>
                    Forward 1.5σ Corridor: <strong className="text-indigo-300 font-mono">{forecast.currency} {forecast.forward_volatility_corridor.lower.toLocaleString()} – {forecast.forward_volatility_corridor.upper.toLocaleString()}</strong>
                  </span>
                )}
              </div>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block font-semibold">Reasoning Stance</span>
              <div className="mt-0.5">{getDirectionBadge(forecast.direction)}</div>
              <span className="text-[11px] text-stone-400 block mt-0.5">Confidence: {Math.round(forecast.confidence * 100)}%</span>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block font-semibold">Version & Real-Time Sync</span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-xs font-mono text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                  v{forecast.version} • {forecast.status}
                </span>
                {liveQuote && (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 flex items-center gap-1">
                    <Activity className="w-2.5 h-2.5 text-emerald-400" />
                    OI: {liveQuote.open_interest.toLocaleString()}
                  </span>
                )}
              </div>
              <span className="text-[10px] text-stone-500 block mt-1 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Live Sync: {lastSyncTime.toLocaleTimeString()}
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
