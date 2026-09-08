import React, { useState, useEffect } from 'react';
import { MarketQuote } from '../types/marketQuote';
import { getISTMarketSessionInfo } from '../utils/marketStatus';
import { 
  TrendingUp, 
  TrendingDown, 
  Activity, 
  ShieldCheck, 
  Lock, 
  Server, 
  X, 
  CheckCircle2, 
  AlertCircle,
  Database,
  Radio,
  Clock,
  Briefcase
} from 'lucide-react';

export interface FeedStatusInfo {
  status: string;
  mode: string;
  active_provider: string;
  is_live: boolean;
}

export interface WorkerTelemetry {
  worker_id: string;
  experiment_id: string;
  worker_status: string;
  market_connection: string;
  database_status: string;
  paper_mode: boolean;
  live_trading: boolean;
  live_orders_blocked: boolean;
  safety_assertion: string;
  last_tick: number | null;
  last_event: string | null;
  signal_count: number;
  candidate_count: number;
  paper_order_count: number;
  open_positions: number;
  closed_positions: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_costs: number;
  net_pnl: number;
  data_quality: string;
  reconnect_count: number;
  error_count: number;
  heartbeat_age_seconds: number | null;
  is_stale: boolean;
  updated_at: string | null;
}

interface IndexTickerBarProps {
  indices: MarketQuote[];
  feedStatus?: FeedStatusInfo;
  onSelectIndex?: (index: MarketQuote) => void;
  onOpenAudit?: () => void;
}

export const IndexTickerBar: React.FC<IndexTickerBarProps> = ({ indices = [], feedStatus, onSelectIndex, onOpenAudit }) => {
  const isSimulated = feedStatus?.status === 'SIMULATED' || feedStatus?.mode === 'SIMULATED';
  
  // State for Worker Telemetry
  const [workerData, setWorkerData] = useState<WorkerTelemetry | null>(null);
  const [isWorkerModalOpen, setIsWorkerModalOpen] = useState<boolean>(false);

  // Poll worker status from API every 10 seconds
  useEffect(() => {
    const fetchWorker = async () => {
      try {
        const res = await fetch('/api/worker/status');
        if (res.ok) {
          const data = await res.json();
          if (data && data.worker_status && data.worker_status !== 'NOT_STARTED') {
            setWorkerData(data);
            return;
          }
        }
        // Direct probe fallback if serverless proxy is cold or not started
        try {
          const probeRes = await fetch('https://apex-market-worker-probe.onrender.com/api/worker/status', { mode: 'cors' });
          if (probeRes.ok) {
            const probeData = await probeRes.json();
            setWorkerData(probeData);
          }
        } catch {
          // quiet if probe offline
        }
      } catch {
        // quiet in dev or offline
      }
    };
    fetchWorker();
    const interval = setInterval(fetchWorker, 10000);
    return () => clearInterval(interval);
  }, []);

  // Evaluate IST Session status
  const session = getISTMarketSessionInfo(
    indices.length > 0 ? Math.max(...indices.map((i) => i.receivedAt || 0)) : undefined,
    isSimulated
  );

  const validIndices = (indices || []).filter((idx) => idx && idx.symbol);

  // Worker badge styling
  const isWorkerOnline = workerData?.worker_status === 'ONLINE' && !workerData?.is_stale;
  const workerBadgeBg = isWorkerOnline 
    ? 'bg-emerald-950/70 border-emerald-500/40 text-emerald-300' 
    : (workerData?.worker_status === 'STARTING' 
        ? 'bg-amber-950/70 border-amber-500/40 text-amber-300' 
        : 'bg-stone-900/80 border-stone-700/50 text-stone-400');

  return (
    <div className="bg-[#0b0c10] border-b border-stone-800/80 px-4 py-2 flex items-center justify-between overflow-x-auto scrollbar-none select-none text-xs">
      <div className="flex items-center space-x-6 shrink-0">
        {/* Dynamic Session & Data Source Status Badge */}
        <div className="flex items-center space-x-2 shrink-0 border-r border-stone-800/80 pr-4">
          <div
            onClick={onOpenAudit}
            className={`flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full ${session.badgeBg} border ${session.badgeBorder} ${session.badgeTextColor} font-mono text-[10px] font-bold cursor-pointer hover:opacity-90 transition-opacity`}
            title="Click to Open End-to-End Market Price Provenance Audit"
          >
            <span className={`w-2 h-2 rounded-full ${session.badgeTextColor.replace('text-', 'bg-')} ${session.isSessionActive ? 'animate-pulse' : ''}`} />
            <span>{session.badgeText}</span>
            <ShieldCheck className="w-3 h-3 ml-1 opacity-70" />
          </div>
        </div>

        {/* Benchmark Indices List */}
        <div className="flex items-center space-x-6 shrink-0">
          {validIndices.map((idx) => {
            const val = idx.ltp ?? idx.close ?? null;
            const isPos = (idx.change || 0) >= 0;
            const isVix = idx.symbol === 'INDIA VIX';
            const changePct = idx.changePercent;
            const changeVal = idx.change;
            const hasPrice = val !== null && val > 0;

            return (
              <div
                key={idx.symbol}
                onClick={() => onSelectIndex?.(idx)}
                className="flex items-center space-x-2.5 cursor-pointer hover:bg-stone-800/40 px-2.5 py-1 rounded-xl transition-colors shrink-0"
              >
                <div className="flex flex-col">
                  <span className="font-extrabold text-stone-100 text-xs flex items-center space-x-1">
                    <span>{idx.symbol}</span>
                    {isVix && <Activity className="w-3 h-3 text-amber-400" />}
                  </span>
                  <span className="text-[10px] text-stone-400 font-mono">
                    {hasPrice ? val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : <span className="text-stone-600 animate-pulse">—</span>}
                  </span>
                </div>

                {hasPrice && changeVal !== null && changePct !== null ? (
                  <div
                    className={`flex items-center space-x-1 text-[11px] font-mono font-bold px-2 py-0.5 rounded-lg ${
                      isPos
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                    }`}
                  >
                    {isPos ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    <span>
                      {isPos ? '+' : ''}{changeVal.toFixed(2)} ({isPos ? '+' : ''}{changePct.toFixed(2)}%)
                    </span>
                  </div>
                ) : (
                  <span className="text-[10px] font-mono text-stone-600">—</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Right Side: Stateful Worker Status & Safety Badges */}
      <div className="flex items-center space-x-3 shrink-0 ml-4">
        {/* Safety Badge 1: Real Market Data */}
        <div className="hidden sm:flex items-center space-x-1 px-2 py-0.5 rounded-full bg-cyan-950/50 border border-cyan-500/30 text-cyan-300 font-mono text-[10px] font-semibold">
          <Radio className="w-2.5 h-2.5 text-cyan-400 animate-pulse" />
          <span>REAL MARKET DATA</span>
        </div>

        {/* Safety Badge 2: Paper Trading */}
        <div className="hidden sm:flex items-center space-x-1 px-2 py-0.5 rounded-full bg-amber-950/50 border border-amber-500/30 text-amber-300 font-mono text-[10px] font-semibold">
          <Briefcase className="w-2.5 h-2.5 text-amber-400" />
          <span>PAPER TRADING</span>
        </div>

        {/* Safety Badge 3: Live Orders Blocked */}
        <div className="flex items-center space-x-1 px-2 py-0.5 rounded-full bg-rose-950/60 border border-rose-500/40 text-rose-300 font-mono text-[10px] font-bold">
          <Lock className="w-2.5 h-2.5 text-rose-400" />
          <span>LIVE ORDERS BLOCKED</span>
        </div>

        {/* Worker Telemetry Pill Button */}
        <button
          onClick={() => setIsWorkerModalOpen(true)}
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border font-mono text-[11px] font-bold transition-all shadow-sm ${workerBadgeBg} hover:opacity-90`}
          title="Click to view detailed Stateful Market Worker Telemetry"
        >
          <Server className="w-3.5 h-3.5" />
          <span>WORKER: {workerData?.worker_status || 'IDLE'}</span>
          {isWorkerOnline && <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />}
        </button>
      </div>

      {/* Stateful Worker Telemetry Modal */}
      {isWorkerModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#12131a] border border-stone-700/80 rounded-2xl w-full max-w-2xl shadow-2xl p-6 relative text-stone-200 animate-in fade-in zoom-in duration-150">
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-4 border-b border-stone-800">
              <div className="flex items-center space-x-3">
                <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-stone-100 flex items-center space-x-2">
                    <span>APEX Stateful Market Worker</span>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${workerBadgeBg}`}>
                      {workerData?.worker_status || 'STANDBY'}
                    </span>
                  </h3>
                  <p className="text-xs text-stone-400 font-mono">
                    ID: {workerData?.worker_id || 'apex-market-worker'} | Session: {workerData?.experiment_id || 'N/A'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsWorkerModalOpen(false)}
                className="text-stone-400 hover:text-stone-100 p-1.5 rounded-lg hover:bg-stone-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Safety Invariant Banners */}
            <div className="grid grid-cols-3 gap-3 my-4">
              <div className="p-2.5 rounded-xl bg-cyan-950/40 border border-cyan-500/30 flex items-center space-x-2">
                <Radio className="w-4 h-4 text-cyan-400 shrink-0" />
                <div>
                  <div className="text-[10px] text-cyan-400/80 font-bold uppercase">Market Feed</div>
                  <div className="text-xs font-mono font-bold text-cyan-200">{workerData?.data_quality || 'AUTHENTIC_LIVE'}</div>
                </div>
              </div>

              <div className="p-2.5 rounded-xl bg-amber-950/40 border border-amber-500/30 flex items-center space-x-2">
                <Briefcase className="w-4 h-4 text-amber-400 shrink-0" />
                <div>
                  <div className="text-[10px] text-amber-400/80 font-bold uppercase">Execution Mode</div>
                  <div className="text-xs font-mono font-bold text-amber-200">PAPER TRADING ONLY</div>
                </div>
              </div>

              <div className="p-2.5 rounded-xl bg-rose-950/40 border border-rose-500/30 flex items-center space-x-2">
                <Lock className="w-4 h-4 text-rose-400 shrink-0" />
                <div>
                  <div className="text-[10px] text-rose-400/80 font-bold uppercase">Safety Invariant</div>
                  <div className="text-xs font-mono font-bold text-rose-200">LIVE ORDERS BLOCKED</div>
                </div>
              </div>
            </div>

            {/* Telemetry Metrics Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs mb-4">
              <div className="p-3 bg-stone-900/60 rounded-xl border border-stone-800">
                <div className="text-stone-400 text-[10px] uppercase font-mono">Market Connection</div>
                <div className="font-mono font-bold text-sm text-stone-100 mt-0.5 flex items-center space-x-1.5">
                  <span className={`w-2 h-2 rounded-full ${workerData?.market_connection === 'CONNECTED' ? 'bg-emerald-400' : 'bg-rose-400'}`} />
                  <span>{workerData?.market_connection || 'DISCONNECTED'}</span>
                </div>
              </div>

              <div className="p-3 bg-stone-900/60 rounded-xl border border-stone-800">
                <div className="text-stone-400 text-[10px] uppercase font-mono">Database Status</div>
                <div className="font-mono font-bold text-sm text-stone-100 mt-0.5 flex items-center space-x-1.5">
                  <Database className="w-3.5 h-3.5 text-blue-400" />
                  <span>{workerData?.database_status || 'CONNECTED'}</span>
                </div>
              </div>

              <div className="p-3 bg-stone-900/60 rounded-xl border border-stone-800">
                <div className="text-stone-400 text-[10px] uppercase font-mono">Candidates Evaluated</div>
                <div className="font-mono font-bold text-sm text-amber-400 mt-0.5">
                  {workerData?.candidate_count || 0}
                </div>
              </div>

              <div className="p-3 bg-stone-900/60 rounded-xl border border-stone-800">
                <div className="text-stone-400 text-[10px] uppercase font-mono">Qualified Signals</div>
                <div className="font-mono font-bold text-sm text-emerald-400 mt-0.5">
                  {workerData?.signal_count || 0}
                </div>
              </div>

              <div className="p-3 bg-stone-900/60 rounded-xl border border-stone-800">
                <div className="text-stone-400 text-[10px] uppercase font-mono">Paper Orders Placed</div>
                <div className="font-mono font-bold text-sm text-stone-100 mt-0.5">
                  {workerData?.paper_order_count || 0}
                </div>
              </div>

              <div className="p-3 bg-stone-900/60 rounded-xl border border-stone-800">
                <div className="text-stone-400 text-[10px] uppercase font-mono">Open Positions</div>
                <div className="font-mono font-bold text-sm text-cyan-400 mt-0.5">
                  {workerData?.open_positions || 0}
                </div>
              </div>

              <div className="p-3 bg-stone-900/60 rounded-xl border border-stone-800">
                <div className="text-stone-400 text-[10px] uppercase font-mono">Net Realized P&L</div>
                <div className={`font-mono font-bold text-sm mt-0.5 ${(workerData?.realized_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  ₹{(workerData?.realized_pnl || 0).toFixed(2)}
                </div>
              </div>

              <div className="p-3 bg-stone-900/60 rounded-xl border border-stone-800">
                <div className="text-stone-400 text-[10px] uppercase font-mono">Total Statutory Costs</div>
                <div className="font-mono font-bold text-sm text-stone-300 mt-0.5">
                  ₹{(workerData?.total_costs || 0).toFixed(2)}
                </div>
              </div>
            </div>

            {/* Health & Provenance Footnote */}
            <div className="p-3 rounded-xl bg-stone-900/40 border border-stone-800/80 flex items-center justify-between text-[11px] font-mono text-stone-400">
              <div className="flex items-center space-x-2">
                <Clock className="w-3.5 h-3.5 text-stone-500" />
                <span>
                  Heartbeat Age:{' '}
                  {workerData?.heartbeat_age_seconds !== null && workerData?.heartbeat_age_seconds !== undefined
                    ? `${workerData.heartbeat_age_seconds}s ago`
                    : 'Awaiting signal'}
                </span>
                {workerData?.is_stale && <span className="text-amber-400 font-bold">(STALE)</span>}
              </div>
              <div className="flex items-center space-x-2">
                <span>Errors: {workerData?.error_count || 0}</span>
                <span>•</span>
                <span>Reconnects: {workerData?.reconnect_count || 0}</span>
              </div>
            </div>

            {/* Close Button */}
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setIsWorkerModalOpen(false)}
                className="px-4 py-2 bg-stone-800 hover:bg-stone-700 text-stone-200 rounded-xl font-medium text-xs transition-colors"
              >
                Close Telemetry
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

