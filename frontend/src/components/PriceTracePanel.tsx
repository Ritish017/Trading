import React, { useState, useEffect } from 'react';
import { X, RefreshCw, CheckCircle2, AlertCircle, ShieldCheck, Activity } from 'lucide-react';
import { CanonicalQuote } from '../types/marketQuote';
import { canonicalQuoteStore } from '../stores/canonicalQuoteStore';

interface PriceTracePanelProps {
  symbol: string;
  isOpen: boolean;
  onClose: () => void;
}

interface DiagnosticResponse {
  symbol: string;
  instrument_key?: string;
  provider: string;
  provider_mode: string;
  authenticated: boolean;
  connected: boolean;
  data_available: boolean;
  raw_ltp: number | null;
  provider_timestamp: number | null;
  received_timestamp: number | null;
  data_age_seconds: number | null;
  market_data_status: string;
  canonical_source?: string;
  quote_sequence_id?: number;
  rest_ltp?: number | null;
  rest_ts?: number | null;
  ws_ltp?: number | null;
  ws_ts?: number | null;
  is_live: boolean;
  is_stale: boolean;
  integrity: string;
}

export const PriceTracePanel: React.FC<PriceTracePanelProps> = ({ symbol, isOpen, onClose }) => {
  const [diagData, setDiagData] = useState<DiagnosticResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [clientCanonical, setClientCanonical] = useState<CanonicalQuote | undefined>(undefined);

  const fetchDiagnostic = async () => {
    try {
      setLoading(true);
      const res = await fetch(`/api/market/diagnostic/${encodeURIComponent(symbol)}`);
      if (res.ok) {
        const data = await res.json();
        setDiagData(data);
      }
    } catch {
      // Diagnostic quiet fallback
    } finally {
      setLoading(false);
      setClientCanonical(canonicalQuoteStore.getQuote(symbol));
    }
  };

  useEffect(() => {
    if (isOpen && symbol) {
      fetchDiagnostic();
      const interval = setInterval(fetchDiagnostic, 3000);
      return () => clearInterval(interval);
    }
  }, [isOpen, symbol]);

  if (!isOpen) return null;

  const formatTs = (ts?: number | null) => {
    if (!ts) return 'N/A';
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString('en-IN', { hour12: false }) + `.${String(d.getMilliseconds()).padStart(3, '0')}`;
  };

  const formatPrice = (p?: number | null) => {
    if (p === null || p === undefined || p <= 0) return '—';
    return `₹${p.toFixed(2)}`;
  };

  const isPass = diagData?.integrity === 'PASS';
  const diff = (diagData?.raw_ltp && clientCanonical?.ltp)
    ? Math.abs(diagData.raw_ltp - clientCanonical.ltp)
    : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="bg-[#10121a] border border-stone-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden font-sans text-stone-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-stone-800 bg-[#141622]">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="font-extrabold text-white text-base tracking-tight">Market Price Provenance & Truth Audit</h3>
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                  isPass ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}>
                  {diagData?.integrity || 'AUDITING'}
                </span>
              </div>
              <p className="text-xs text-stone-400 font-mono">Tracing canonical quote: <strong className="text-stone-200">{symbol}</strong></p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={fetchDiagnostic}
              disabled={loading}
              className="p-2 rounded-lg bg-stone-800/80 hover:bg-stone-700 text-stone-300 transition-colors"
              title="Refresh Audit"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-amber-400' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg bg-stone-800/80 hover:bg-stone-700 text-stone-300 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-6 max-h-[80vh] overflow-y-auto font-mono text-xs">
          {/* Status Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-[#161826] border border-stone-800/80">
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block">Provider</span>
              <span className="font-bold text-stone-200 text-sm">{diagData?.provider || 'UPSTOX'}</span>
              <span className="text-[9px] text-stone-400 block">{diagData?.provider_mode || 'UNAVAILABLE'}</span>
            </div>
            <div className="p-3 rounded-xl bg-[#161826] border border-stone-800/80">
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block">Auth & Link</span>
              <div className="flex items-center space-x-1 mt-0.5">
                {diagData?.authenticated ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <AlertCircle className="w-3.5 h-3.5 text-rose-400" />}
                <span className="font-bold text-stone-200">{diagData?.authenticated ? 'AUTH OK' : 'NO AUTH'}</span>
              </div>
              <span className="text-[9px] text-stone-400 block">{diagData?.connected ? 'Connected' : 'Disconnected'}</span>
            </div>
            <div className="p-3 rounded-xl bg-[#161826] border border-stone-800/80">
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block">Data Age</span>
              <span className="font-bold text-stone-200 text-sm">{diagData?.data_age_seconds !== null ? `${diagData?.data_age_seconds}s` : '—'}</span>
              <span className="text-[9px] text-stone-400 block">{diagData?.market_data_status || 'UNKNOWN'}</span>
            </div>
            <div className="p-3 rounded-xl bg-[#161826] border border-stone-800/80">
              <span className="text-[10px] text-stone-500 uppercase tracking-wider block">End-To-End Diff</span>
              <span className={`font-bold text-sm ${diff === 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                ₹{diff.toFixed(2)}
              </span>
              <span className="text-[9px] text-stone-400 block">{diff === 0 ? 'Exact Match' : 'Divergent'}</span>
            </div>
          </div>

          {/* Trace Pipeline Table */}
          <div className="rounded-xl border border-stone-800 bg-[#141624] overflow-hidden">
            <div className="px-4 py-2.5 bg-[#181a2c] border-b border-stone-800 flex items-center justify-between">
              <span className="font-bold text-stone-300 flex items-center space-x-1.5">
                <Activity className="w-3.5 h-3.5 text-amber-400" />
                <span>Price Provenance Pipeline</span>
              </span>
              <span className="text-[10px] text-stone-400">Seq #{diagData?.quote_sequence_id || 0}</span>
            </div>

            <table className="w-full text-left">
              <thead>
                <tr className="text-stone-500 border-b border-stone-800 text-[10px] uppercase">
                  <th className="py-2 px-4 font-semibold">Stage</th>
                  <th className="py-2 px-4 font-semibold">Source</th>
                  <th className="py-2 px-4 font-semibold">LTP (₹)</th>
                  <th className="py-2 px-4 font-semibold">Exchange Timestamp</th>
                  <th className="py-2 px-4 font-semibold text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-800/60 text-xs">
                <tr>
                  <td className="py-2 px-4 font-medium text-stone-400">1. Upstox REST</td>
                  <td className="py-2 px-4 text-stone-300">REST API</td>
                  <td className="py-2 px-4 font-bold text-amber-400">{formatPrice(diagData?.rest_ltp)}</td>
                  <td className="py-2 px-4 text-stone-400">{formatTs(diagData?.rest_ts)}</td>
                  <td className="py-2 px-4 text-right text-stone-400">Polled</td>
                </tr>
                <tr>
                  <td className="py-2 px-4 font-medium text-stone-400">2. Upstox WS</td>
                  <td className="py-2 px-4 text-stone-300">WebSocket</td>
                  <td className="py-2 px-4 font-bold text-amber-400">{formatPrice(diagData?.ws_ltp)}</td>
                  <td className="py-2 px-4 text-stone-400">{formatTs(diagData?.ws_ts)}</td>
                  <td className="py-2 px-4 text-right text-stone-400">Streamed</td>
                </tr>
                <tr className="bg-amber-500/5">
                  <td className="py-2 px-4 font-medium text-stone-300">3. Backend Canonical</td>
                  <td className="py-2 px-4 font-bold text-stone-200">{diagData?.canonical_source || 'REST'} (Winner)</td>
                  <td className="py-2 px-4 font-black text-emerald-400 text-sm">{formatPrice(diagData?.raw_ltp)}</td>
                  <td className="py-2 px-4 text-stone-300">{formatTs(diagData?.provider_timestamp)}</td>
                  <td className="py-2 px-4 text-right">
                    <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold text-[10px]">
                      Canonical
                    </span>
                  </td>
                </tr>
                <tr>
                  <td className="py-2 px-4 font-medium text-stone-400">4. React Store</td>
                  <td className="py-2 px-4 text-stone-300">Client Memory</td>
                  <td className="py-2 px-4 font-bold text-stone-200">{formatPrice(clientCanonical?.ltp)}</td>
                  <td className="py-2 px-4 text-stone-400">{formatTs(clientCanonical?.provider_timestamp)}</td>
                  <td className="py-2 px-4 text-right text-stone-400">Synced</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Instrument Metadata Details */}
          <div className="p-3 rounded-xl bg-[#121420] border border-stone-800 text-[11px] text-stone-400 space-y-1">
            <div><strong>Instrument Key:</strong> <span className="text-stone-300">{diagData?.instrument_key || symbol}</span></div>
            <div><strong>Live Policy:</strong> <span className="text-stone-300">MarketDataService ➔ CanonicalQuoteStore ➔ UI (Zero Static Fallback)</span></div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-stone-800 bg-[#141622] flex items-center justify-between text-xs text-stone-400">
          <span>APEX Market Price Integrity Guard</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-white font-medium transition-colors"
          >
            Close Audit
          </button>
        </div>
      </div>
    </div>
  );
};
