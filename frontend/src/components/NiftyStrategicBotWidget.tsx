import React, { useState, useEffect, useCallback } from 'react';
import { 
  Bot, 
  Play, 
  Power, 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  ShieldAlert, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Layers, 
  Newspaper, 
  Zap,
  Activity,
  Gauge,
  Cpu,
  Sparkles,
  Cloud,
  ChevronDown,
  ChevronUp,
  Sliders,
  ExternalLink,
  Key
} from 'lucide-react';
import { getAuthHeaders } from '../utils/auth';

interface BotStatus {
  bot_state: string;
  auto_trade_enabled: boolean;
  circuit_breaker_triggered: boolean;
  daily_loss_limit_pct: number;
  daily_pnl: number;
  daily_drawdown_pct: number;
  initial_capital: number;
  active_positions_count: number;
  active_positions: any[];
  last_scan_timestamp: number;
  last_signal: any;
  active_rules_count?: number;
  rules?: any[];
  is_market_open: boolean;
  is_expiry_day: boolean;
  is_post_1pm_expiry: boolean;
}

interface NewsSentiment {
  aggregate_sentiment: number;
  sentiment_label: string;
  high_impact_catalyst_detected: boolean;
  catalyst_summary: string;
  headline_count: number;
  top_headlines: Array<{
    title: string;
    source: string;
    sentiment_score: number;
    urgency: string;
    affected_segment: string;
  }>;
}

interface DynamicRule {
  rule_id: string;
  name: string;
  regime: string;
  status: string;
  confidence: number;
  action_type: string;
  rule_description: string;
  condition_logic: string;
  trades_applied: number;
  win_count: number;
  loss_count: number;
  synthesized_by: string;
  generation: number;
}

export const NiftyStrategicBotWidget: React.FC = () => {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [news, setNews] = useState<NewsSentiment | null>(null);
  const [rules, setRules] = useState<DynamicRule[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [toggling, setToggling] = useState<boolean>(false);
  const [scanning, setScanning] = useState<boolean>(false);
  const [evolving, setEvolving] = useState<boolean>(false);
  const [showRulesDrawer, setShowRulesDrawer] = useState<boolean>(false);
  const [showDeployModal, setShowDeployModal] = useState<boolean>(false);
  const [showKeyModal, setShowKeyModal] = useState<boolean>(false);
  const [geminiApiKeyInput, setGeminiApiKeyInput] = useState<string>('');
  const [amdApiKeyInput, setAmdApiKeyInput] = useState<string>('');
  const [providerPreference, setProviderPreference] = useState<string>('auto');
  const [aiTelemetry, setAiTelemetry] = useState<any>(null);
  const [instaboxKeyInput, setInstaboxKeyInput] = useState<string>('');
  const [deployingCloud, setDeployingCloud] = useState<boolean>(false);
  const [deployResult, setDeployResult] = useState<any>(null);
  const [lastScanResult, setLastScanResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activeModelInfo, setActiveModelInfo] = useState<{ fast: string; pro: string; hasKey: boolean }>({
    fast: 'gemini-3.8-flash',
    pro: 'DeepSeek-V4-Flash',
    hasKey: true
  });

  const fetchBotStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/nifty-bot/status', {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
        if (data.rules) {
          setRules(data.rules);
        }
      }
    } catch (err: any) {
      console.warn('Failed to fetch bot status:', err);
    }
  }, []);

  const fetchNewsSentiment = useCallback(async () => {
    try {
      const res = await fetch('/api/news/sentiment', {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setNews(data);
      }
    } catch (err: any) {
      console.warn('Failed to fetch news sentiment:', err);
    }
  }, []);

  const fetchRules = useCallback(async () => {
    try {
      const res = await fetch('/api/nifty-bot/rules', {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.rules) setRules(data.rules);
      }
    } catch (err) {
      console.warn('Failed to fetch rules:', err);
    }
  }, []);

  const fetchModels = useCallback(async () => {
    try {
      const res = await fetch('/api/ai/models', {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setActiveModelInfo({
          fast: data.fast_model || 'gemini-3.8-flash',
          pro: data.amd_model || 'DeepSeek-V4-Flash',
          hasKey: Boolean(data.has_gemini_key || data.has_amd_key),
        });
        if (data.telemetry) {
          setAiTelemetry(data.telemetry);
        }
      }
    } catch (err) {
      console.warn('Failed to fetch AI models:', err);
    }
  }, []);

  useEffect(() => {
    fetchBotStatus();
    fetchNewsSentiment();
    fetchRules();
    fetchModels();
    const interval = setInterval(() => {
      fetchBotStatus();
    }, 15000);
    return () => clearInterval(interval);
  }, [fetchBotStatus, fetchNewsSentiment, fetchRules, fetchModels]);

  const handleToggle = async () => {
    if (!status) return;
    setToggling(true);
    setErrorMsg(null);
    try {
      const nextState = !status.auto_trade_enabled;
      const res = await fetch('/api/nifty-bot/toggle', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({ enabled: nextState }),
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(prev => prev ? { ...prev, auto_trade_enabled: data.auto_trade_enabled, bot_state: data.bot_state } : null);
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || 'Failed to toggle bot auto-trade state.');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Network error toggling bot.');
    } finally {
      setToggling(false);
    }
  };

  const handleManualScan = async () => {
    setScanning(true);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/nifty-bot/scan?force_scan=true', {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setLastScanResult(data);
        fetchBotStatus();
        fetchRules();
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || 'Manual scan encountered an error.');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Network error triggering scan.');
    } finally {
      setScanning(false);
    }
  };

  const handleEvolveRules = async () => {
    setEvolving(true);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/nifty-bot/rules/evolve', {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        await fetchRules();
        await fetchBotStatus();
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || 'Failed to evolve rules.');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Rule evolution error.');
    } finally {
      setEvolving(false);
    }
  };

  const handleToggleRuleStatus = async (ruleId: string) => {
    try {
      const res = await fetch(`/api/nifty-bot/rules/toggle/${ruleId}`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        fetchRules();
      }
    } catch (err) {
      console.warn('Failed to toggle rule:', err);
    }
  };

  const handleSaveAIKeys = async () => {
    try {
      const payload: any = {};
      if (geminiApiKeyInput.trim()) payload.api_key = geminiApiKeyInput.trim();
      if (amdApiKeyInput.trim()) payload.amd_api_key = amdApiKeyInput.trim();
      if (providerPreference) payload.provider_preference = providerPreference;

      const res = await fetch('/api/ai/set-key', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setShowKeyModal(false);
        fetchModels();
      }
    } catch (err: any) {
      setErrorMsg('Failed to update AI keys: ' + err.message);
    }
  };

  const handleDeployInstabox = async () => {
    setDeployingCloud(true);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/instabox/deploy', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({
          api_key: instaboxKeyInput.trim() || undefined,
          machine_name: 'apex-quant-lab',
          gemini_api_key: geminiApiKeyInput.trim() || undefined,
          amd_api_key: amdApiKeyInput.trim() || undefined,
        }),
      });
      const data = await res.json();
      setDeployResult(data);
    } catch (err: any) {
      setErrorMsg('Cloud deploy error: ' + err.message);
    } finally {
      setDeployingCloud(false);
    }
  };

  const sentimentScore = news?.aggregate_sentiment ?? 0.0;
  const sentimentPct = Math.min(100, Math.max(0, (sentimentScore + 1) * 50));
  const lastSignal = status?.last_signal || lastScanResult?.signal;

  const getSentimentColor = (s: number) => {
    if (s >= 0.25) return 'text-emerald-400';
    if (s <= -0.25) return 'text-rose-400';
    return 'text-amber-400';
  };

  const getSentimentBg = (s: number) => {
    if (s >= 0.25) return 'bg-emerald-500/10 border-emerald-500/30';
    if (s <= -0.25) return 'bg-rose-500/10 border-rose-500/30';
    return 'bg-amber-500/10 border-amber-500/30';
  };

  return (
    <div className="bg-[#0b0d10] border border-stone-800 rounded-2xl p-4 flex flex-col space-y-4 shadow-xl mb-4">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-800/80 pb-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-gradient-to-br from-amber-500/20 to-orange-500/10 rounded-xl border border-amber-500/30 text-amber-400">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="font-mono font-bold text-white text-sm tracking-wide">
                NIFTY 50 Autonomous Quant Bot
              </h3>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider border ${
                status?.auto_trade_enabled 
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' 
                  : 'bg-stone-800 text-stone-400 border-stone-700'
              }`}>
                {status?.bot_state || 'IDLE'}
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-sky-500/10 text-sky-400 border border-sky-500/30 flex items-center space-x-1">
                <Sparkles className="w-3 h-3" />
                <span>J.A.R.V.I.S. Adaptive</span>
              </span>
            </div>
            <p className="text-xs text-stone-400">
              Multi-week autonomous paper execution with Gemini Pro adaptive rule evolution &amp; ₹10,000 risk ledger.
            </p>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center space-x-2">
          {/* Active Dual-Provider AI Engine Indicator */}
          <div 
            onClick={() => setShowKeyModal(true)}
            className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1.5 bg-[#121418] hover:bg-stone-800 border border-stone-800 rounded-xl text-[10px] font-mono text-stone-300 cursor-pointer transition-colors"
            title="Click to view or configure Gemini 3.8 Flash & AMD Token Lab AI engines"
          >
            <Cpu className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-amber-300 font-bold">{activeModelInfo.fast}</span>
            <span className="text-stone-500">+</span>
            <span className="text-sky-400 font-bold">{activeModelInfo.pro}</span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse ml-0.5" />
          </div>

          {/* InstaBox Cloud 24/7 Button */}
          <button
            onClick={() => setShowDeployModal(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 rounded-xl text-xs font-mono transition-colors"
            title="Deploy to InstaBox microVM to run 24/7 even when computer is off"
          >
            <Cloud className="w-3.5 h-3.5" />
            <span className="hidden md:inline">InstaBox Cloud</span>
            <span className="md:hidden">Cloud</span>
          </button>

          {/* Scan Now */}
          <button
            onClick={handleManualScan}
            disabled={scanning}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-stone-800 hover:bg-stone-700 text-stone-200 border border-stone-700 rounded-xl text-xs font-mono transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scanning ? 'animate-spin text-amber-400' : ''}`} />
            <span>{scanning ? 'Scanning...' : 'Scan Now'}</span>
          </button>

          {/* Auto-Trade Arm/Disarm Toggle */}
          <button
            onClick={handleToggle}
            disabled={toggling}
            className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-mono font-bold transition-all border ${
              status?.auto_trade_enabled
                ? 'bg-rose-500/10 text-rose-400 border-rose-500/40 hover:bg-rose-500/20 shadow-[0_0_15px_rgba(244,63,94,0.15)]'
                : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/40 hover:bg-emerald-500/20'
            }`}
          >
            <Power className="w-3.5 h-3.5" />
            <span>{status?.auto_trade_enabled ? 'Disarm Auto-Trade' : 'Arm Auto-Trade'}</span>
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-2.5 text-xs text-rose-400 flex items-center space-x-2 font-mono">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Grid: 3 Telemetry Columns */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Column 1: Financial News NLP Sentiment */}
        <div className="bg-[#121418] border border-stone-800/80 rounded-xl p-3 flex flex-col justify-between space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono text-stone-400 flex items-center space-x-1.5">
              <Newspaper className="w-3.5 h-3.5 text-indigo-400" />
              <span>LIVE NEWS &amp; MACRO SENTIMENT</span>
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${getSentimentBg(sentimentScore)} ${getSentimentColor(sentimentScore)}`}>
              {news?.sentiment_label || 'NEUTRAL'}
            </span>
          </div>

          <div>
            <div className="flex justify-between items-center text-xs font-mono mb-1">
              <span className="text-stone-500">Sentiment Score:</span>
              <span className={`font-black ${getSentimentColor(sentimentScore)}`}>
                {sentimentScore > 0 ? `+${sentimentScore.toFixed(2)}` : sentimentScore.toFixed(2)}
              </span>
            </div>
            <div className="w-full bg-stone-800 h-2 rounded-full overflow-hidden flex">
              <div 
                className={`h-full transition-all duration-500 ${
                  sentimentScore >= 0.25 ? 'bg-emerald-500' : sentimentScore <= -0.25 ? 'bg-rose-500' : 'bg-amber-500'
                }`}
                style={{ width: `${sentimentPct}%` }}
              />
            </div>
          </div>

          <div className="text-[11px] text-stone-400 font-sans line-clamp-2 italic">
            "{news?.catalyst_summary || 'Normal market regime. No extreme macro catalyst detected.'}"
          </div>

          <div className="text-[10px] font-mono text-stone-500 border-t border-stone-800 pt-1 flex justify-between">
            <span>Gemini Flash NLP Engine</span>
            <span className="text-stone-400">{news?.headline_count || 14} Headlines Evaluated</span>
          </div>
        </div>

        {/* Column 2: Futures Basis & Open Interest Mechanics */}
        <div className="bg-[#121418] border border-stone-800/80 rounded-xl p-3 flex flex-col justify-between space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono text-stone-400 flex items-center space-x-1.5">
              <Activity className="w-3.5 h-3.5 text-sky-400" />
              <span>FUTURES BASIS &amp; OI DYNAMICS</span>
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20">
              {lastScanResult?.oi_pattern || 'LONG_BUILDUP'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div>
              <span className="text-[10px] text-stone-500 block">Spot Price</span>
              <span className="font-bold text-white">
                ₹{lastScanResult?.spot_price ? lastScanResult.spot_price.toLocaleString() : '24,500.0'}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 block">Futures Price</span>
              <span className="font-bold text-white">
                ₹{lastScanResult?.futures_price ? lastScanResult.futures_price.toLocaleString() : '24,565.0'}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 block">Basis (Spread)</span>
              <span className={`font-bold ${(lastScanResult?.basis ?? 65) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {(lastScanResult?.basis ?? 65) >= 0 ? `+₹${lastScanResult?.basis ?? 65}` : `-₹${Math.abs(lastScanResult?.basis ?? 65)}`}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 block">Basis Velocity</span>
              <span className={`font-bold ${(lastScanResult?.basis_velocity ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {(lastScanResult?.basis_velocity ?? 0) >= 0 ? `+${lastScanResult?.basis_velocity ?? 0} pts` : `${lastScanResult?.basis_velocity ?? 0} pts`}
              </span>
            </div>
          </div>

          <div className="text-[10px] font-mono text-stone-500 flex justify-between border-t border-stone-800 pt-1">
            <span>PCR: <strong className="text-stone-300">{lastScanResult?.pcr ?? 1.15}</strong></span>
            <span>ATM IV: <strong className="text-stone-300">{Math.round((lastScanResult?.atm_iv ?? 0.16) * 100)}%</strong></span>
            <span>IVP: <strong className="text-stone-300">{lastScanResult?.iv_percentile ?? 55}%</strong></span>
          </div>
        </div>

        {/* Column 3: Institutional Risk & Daily Circuit Breaker */}
        <div className="bg-[#121418] border border-stone-800/80 rounded-xl p-3 flex flex-col justify-between space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono text-stone-400 flex items-center space-x-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
              <span>₹10,000 RISK BUDGET</span>
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
              2.0% (₹200) CIRCUIT BREAKER
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div>
              <span className="text-[10px] text-stone-500 block">Daily P&amp;L</span>
              <span className={`font-black text-sm ${(status?.daily_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {(status?.daily_pnl ?? 0) >= 0 ? `+₹${(status?.daily_pnl ?? 0).toLocaleString()}` : `-₹${Math.abs(status?.daily_pnl ?? 0).toLocaleString()}`}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 block">Daily Drawdown</span>
              <span className={`font-black text-sm ${(status?.daily_drawdown_pct ?? 0) <= -2.0 ? 'text-rose-500' : 'text-stone-300'}`}>
                {(status?.daily_drawdown_pct ?? 0).toFixed(2)}% / -2.00%
              </span>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 block">Risk per Trade</span>
              <span className="font-bold text-stone-300">1.0% - 2.0% (₹100 - ₹200)</span>
            </div>
            <div>
              <span className="text-[10px] text-stone-500 block">Active Positions</span>
              <span className="font-bold text-sky-400">{status?.active_positions_count ?? 0}</span>
            </div>
          </div>

          <div className="text-[10px] font-mono text-stone-500 border-t border-stone-800 pt-1 flex justify-between">
            <span>Capital: <strong className="text-emerald-400">₹{status?.initial_capital ? status.initial_capital.toLocaleString() : '10,000'}</strong></span>
            <span className="text-stone-400">1 Lot Micro-Sizing Guard</span>
          </div>
        </div>
      </div>

      {/* J.A.R.V.I.S. Adaptive Rules Drawer Toggle Bar */}
      <div className="bg-[#121418] border border-stone-800/80 rounded-xl p-3 flex flex-col space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Sliders className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-mono font-bold text-white">
              J.A.R.V.I.S. Adaptive Quantitative Rules ({rules.filter(r => r.status === 'ACTIVE').length} Active / {rules.length} Total)
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleEvolveRules}
              disabled={evolving}
              className="flex items-center space-x-1.5 px-3 py-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-lg text-xs font-mono transition-colors disabled:opacity-50"
              title="Trigger J.A.R.V.I.S. Gemini Pro reflection to synthesize new rules or refine thresholds"
            >
              <Sparkles className={`w-3.5 h-3.5 ${evolving ? 'animate-spin' : ''}`} />
              <span>{evolving ? 'Synthesizing...' : 'Evolve Rules (Gemini Pro)'}</span>
            </button>

            <button
              onClick={() => setShowRulesDrawer(!showRulesDrawer)}
              className="p-1 hover:bg-stone-800 rounded text-stone-400 transition-colors"
            >
              {showRulesDrawer ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Evolving Rules List (Collapsible) */}
        {showRulesDrawer && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 pt-2 border-t border-stone-800">
            {rules.map((rule) => (
              <div 
                key={rule.rule_id}
                className={`p-2.5 rounded-xl border text-xs font-mono transition-all flex flex-col justify-between space-y-1.5 ${
                  rule.status === 'ACTIVE' 
                    ? 'bg-[#16191f] border-stone-700/80 text-stone-200' 
                    : 'bg-[#0f1114] border-stone-800/50 text-stone-500 opacity-60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-1.5">
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      {rule.rule_id}
                    </span>
                    <span className="font-bold text-white text-[11px] truncate max-w-[200px]">
                      {rule.name}
                    </span>
                  </div>

                  <button
                    onClick={() => handleToggleRuleStatus(rule.rule_id)}
                    className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase transition-colors border ${
                      rule.status === 'ACTIVE'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-rose-500/10 hover:text-rose-400 hover:border-rose-500/30'
                        : 'bg-stone-800 text-stone-400 border-stone-700 hover:bg-emerald-500/10 hover:text-emerald-400'
                    }`}
                  >
                    {rule.status}
                  </button>
                </div>

                <p className="text-[11px] text-stone-300 font-sans leading-relaxed">
                  {rule.rule_description}
                </p>

                <div className="flex items-center justify-between text-[10px] text-stone-500 border-t border-stone-800/80 pt-1">
                  <span>Regime: <strong className="text-stone-400">{rule.regime}</strong></span>
                  <span>Confidence: <strong className="text-amber-400">{Math.round(rule.confidence * 100)}%</strong></span>
                  <span>Gen {rule.generation} · {rule.trades_applied} Trades</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Latest Strategy Signal & Execution Details */}
      {lastSignal && (
        <div className="bg-[#121418] border border-stone-800 rounded-xl p-3 flex flex-col space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-800 pb-2">
            <div className="flex items-center space-x-2">
              <Zap className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-mono font-bold text-white">
                Active Strategy Formulation:
              </span>
              <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                {lastSignal.strategy_name}
              </span>
              <span className="text-xs font-mono text-stone-400">
                ({lastSignal.regime})
              </span>
            </div>

            <div className="flex items-center space-x-3 text-xs font-mono">
              <span className="text-stone-400">
                Max Loss: <strong className="text-rose-400">₹{Math.round(lastSignal.max_loss || 0).toLocaleString()}</strong>
              </span>
              <span className="text-stone-400">
                Max Gain: <strong className="text-emerald-400">₹{Math.round(lastSignal.max_gain || 0).toLocaleString()}</strong>
              </span>
              <span className="text-stone-400">
                R:R: <strong className="text-amber-400">{lastSignal.risk_reward_ratio || 0}</strong>
              </span>
            </div>
          </div>

          {/* Legs Breakdown */}
          {lastSignal.legs && lastSignal.legs.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-1">
              {lastSignal.legs.map((leg: any, idx: number) => (
                <div 
                  key={idx}
                  className={`px-2.5 py-1 rounded text-[11px] font-mono border flex items-center space-x-2 ${
                    leg.action === 'BUY'
                      ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                      : 'bg-rose-500/10 text-rose-300 border-rose-500/30'
                  }`}
                >
                  <span className="font-extrabold">{leg.action}</span>
                  <span>{leg.symbol}</span>
                  <span className="text-stone-400">({leg.quantity} Qty @ ₹{leg.price})</span>
                </div>
              ))}
            </div>
          )}

          <div className="text-xs font-mono text-stone-300 bg-stone-900/60 p-2 rounded-lg border border-stone-800">
            <strong>Rationale:</strong> {lastSignal.rationale}
          </div>
        </div>
      )}

      {/* InstaBox Cloud 24/7 Deployment Modal */}
      {showDeployModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#121418] border border-stone-700 rounded-2xl max-w-lg w-full p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-stone-800 pb-3">
              <div className="flex items-center space-x-2.5">
                <Cloud className="w-5 h-5 text-sky-400" />
                <h4 className="font-mono font-bold text-white text-sm">Deploy to InstaBox 24/7 Cloud</h4>
              </div>
              <button 
                onClick={() => setShowDeployModal(false)}
                className="text-stone-400 hover:text-white text-xs font-mono"
              >
                ✕ Close
              </button>
            </div>

            <p className="text-xs text-stone-300 font-sans leading-relaxed">
              InstaBox provisions a dedicated Firecracker Linux microVM that keeps your APEX Quant Lab &amp; J.A.R.V.I.S. trading bot active 24/7 in the cloud, continuing paper trading even when your local computer is powered off.
            </p>

            <div className="space-y-2">
              <label className="text-xs font-mono text-stone-400 block">
                InstaBox API Key (starts with <code className="text-amber-400">ibk_</code>):
              </label>
              <input
                type="password"
                placeholder="ibk_xxxxxxxxxxxxxxxxxxxxxxxx"
                value={instaboxKeyInput}
                onChange={(e) => setInstaboxKeyInput(e.target.value)}
                className="w-full bg-stone-900 border border-stone-700 rounded-xl px-3 py-2 text-xs font-mono text-white placeholder-stone-600 focus:outline-none focus:border-sky-500"
              />
              <span className="text-[10px] text-stone-500 block">
                Find your key at <a href="https://dashboard.instabox.sh/dashboard/api-keys" target="_blank" rel="noreferrer" className="text-sky-400 underline">dashboard.instabox.sh/dashboard/api-keys</a>
              </span>
            </div>

            {deployResult && (
              <div className={`p-3 rounded-xl border text-xs font-mono space-y-1.5 ${
                deployResult.status === 'DEPLOYED' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              }`}>
                <div className="font-bold flex items-center space-x-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Deployment Status: {deployResult.status}</span>
                </div>
                {deployResult.dashboard_url && (
                  <div className="pt-1">
                    <span className="text-stone-400">Remote Dashboard: </span>
                    <a href={deployResult.dashboard_url} target="_blank" rel="noreferrer" className="text-sky-400 underline break-all font-bold">
                      {deployResult.dashboard_url}
                    </a>
                  </div>
                )}
                <p className="text-[11px] text-stone-400">{deployResult.message}</p>
              </div>
            )}

            <div className="flex justify-end space-x-2 pt-2 border-t border-stone-800">
              <button
                onClick={() => setShowDeployModal(false)}
                className="px-4 py-2 bg-stone-800 hover:bg-stone-700 text-stone-300 rounded-xl text-xs font-mono"
              >
                Cancel
              </button>
              <button
                onClick={handleDeployInstabox}
                disabled={deployingCloud}
                className="px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white font-bold rounded-xl text-xs font-mono flex items-center space-x-1.5 disabled:opacity-50"
              >
                <Cloud className={`w-3.5 h-3.5 ${deployingCloud ? 'animate-spin' : ''}`} />
                <span>{deployingCloud ? 'Deploying to Cloud...' : 'Launch Cloud Sandbox'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Dual AI Engine Configuration Modal */}
      {showKeyModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#121418] border border-stone-700 rounded-2xl max-w-lg w-full p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-stone-800 pb-3">
              <div className="flex items-center space-x-2.5">
                <Cpu className="w-5 h-5 text-indigo-400" />
                <h4 className="font-mono font-bold text-white text-sm">Dual AI Engine: Gemini &amp; AMD Token Lab</h4>
              </div>
              <button 
                onClick={() => setShowKeyModal(false)}
                className="text-stone-400 hover:text-white text-xs font-mono"
              >
                ✕ Close
              </button>
            </div>

            <p className="text-xs text-stone-300 font-sans leading-relaxed">
              J.A.R.V.I.S. coordinates both <strong className="text-amber-400">Gemini 3.8 Flash</strong> for fast market scans and <strong className="text-sky-400">AMD Token Lab (DeepSeek-V4-Flash)</strong> on AMD GPUs for autonomous rule synthesis with zero-downtime failover.
            </p>

            {/* Provider Status Cards */}
            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div className="p-2.5 bg-stone-900/80 border border-amber-500/30 rounded-xl space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-amber-400 font-bold">Google Gemini</span>
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <div className="text-[10px] text-stone-400">Primary: {activeModelInfo.fast}</div>
              </div>

              <div className="p-2.5 bg-stone-900/80 border border-sky-500/30 rounded-xl space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-sky-400 font-bold">AMD Token Lab</span>
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <div className="text-[10px] text-stone-400">Model: {activeModelInfo.pro}</div>
              </div>
            </div>

            {/* Inputs */}
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-mono text-stone-400 block">
                  Gemini API Key (<code className="text-amber-400">AIzaSy...</code>):
                </label>
                <input
                  type="password"
                  placeholder="AIzaSy..."
                  value={geminiApiKeyInput}
                  onChange={(e) => setGeminiApiKeyInput(e.target.value)}
                  className="w-full bg-stone-900 border border-stone-700 rounded-xl px-3 py-2 text-xs font-mono text-white placeholder-stone-600 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-mono text-stone-400 block">
                  AMD Token Lab API Key (<code className="text-sky-400">tl-...</code>):
                </label>
                <input
                  type="password"
                  placeholder="tl-9a80aca..."
                  value={amdApiKeyInput}
                  onChange={(e) => setAmdApiKeyInput(e.target.value)}
                  className="w-full bg-stone-900 border border-stone-700 rounded-xl px-3 py-2 text-xs font-mono text-white placeholder-stone-600 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-mono text-stone-400 block">
                  Execution Routing Mode:
                </label>
                <select
                  value={providerPreference}
                  onChange={(e) => setProviderPreference(e.target.value)}
                  className="w-full bg-stone-900 border border-stone-700 rounded-xl px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="auto">Auto-Hybrid (Gemini 3.8 Flash + DeepSeek Failover)</option>
                  <option value="amd">AMD Token Lab (DeepSeek-V4-Flash) Free Tokens</option>
                  <option value="gemini">Google Gemini Only</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-2 border-t border-stone-800">
              <button
                onClick={() => setShowKeyModal(false)}
                className="px-4 py-2 bg-stone-800 hover:bg-stone-700 text-stone-300 rounded-xl text-xs font-mono"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveAIKeys}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl text-xs font-mono"
              >
                Save &amp; Connect Engines
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
