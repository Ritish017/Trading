import React from 'react';
import { MarketIndex } from '../types/indianMarket';
import { TrendingUp, TrendingDown, Activity, Wifi, AlertTriangle, WifiOff } from 'lucide-react';

export interface FeedStatusInfo {
  status: string;
  mode: string;
  active_provider: string;
  is_live: boolean;
}

interface IndexTickerBarProps {
  indices: MarketIndex[];
  feedStatus?: FeedStatusInfo;
  onSelectIndex?: (index: MarketIndex) => void;
}

export const IndexTickerBar: React.FC<IndexTickerBarProps> = ({ indices = [], feedStatus, onSelectIndex }) => {
  const isLive = feedStatus?.is_live && feedStatus?.status === 'CONNECTED';
  const isSimulated = feedStatus?.status === 'SIMULATED' || feedStatus?.mode === 'SIMULATED';
  const providerName = feedStatus?.active_provider || 'UPSTOX';

  const validIndices = (indices || []).filter((idx) => idx && idx.symbol);

  return (
    <div className="bg-[#0f1015] border-b border-stone-800/80 px-4 py-2 flex items-center space-x-6 overflow-x-auto scrollbar-none select-none text-xs">
      {/* Live Data Provider Status Indicator */}
      <div className="flex items-center space-x-2 shrink-0 border-r border-stone-800/80 pr-4">
        {isLive ? (
          <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono text-[10px] font-bold">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <Wifi className="w-3 h-3" />
            <span>LIVE — {providerName}</span>
          </div>
        ) : isSimulated ? (
          <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 font-mono text-[10px] font-bold">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <AlertTriangle className="w-3 h-3" />
            <span>SIMULATED — DEV MOCK</span>
          </div>
        ) : (
          <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400 font-mono text-[10px] font-bold">
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            <WifiOff className="w-3 h-3" />
            <span>DISCONNECTED</span>
          </div>
        )}
      </div>

      <div className="flex items-center space-x-6 shrink-0">
        {validIndices.map((idx) => {
          const isPos = (idx.change || 0) >= 0;
          const isVix = idx.symbol === 'INDIA VIX';
          const changePct = idx.changePercent ?? 0;
          const val = idx.value ?? 0;

          return (
            <div
              key={idx.symbol}
              onClick={() => onSelectIndex?.(idx)}
              className="flex items-center space-x-2.5 cursor-pointer hover:bg-stone-800/30 px-2 py-1 rounded-lg transition-colors shrink-0"
            >
              <div className="flex flex-col">
                <span className="font-bold text-stone-200 text-xs flex items-center space-x-1">
                  <span>{idx.symbol}</span>
                  {isVix && <Activity className="w-3 h-3 text-amber-400" />}
                </span>
                <span className="text-[10px] text-stone-400 font-mono">
                  {val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>

              <div
                className={`flex items-center space-x-0.5 text-[11px] font-mono font-bold px-1.5 py-0.5 rounded ${
                  isPos
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                }`}
              >
                {isPos ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                <span>
                  {isPos ? '+' : ''}
                  {changePct.toFixed(2)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
