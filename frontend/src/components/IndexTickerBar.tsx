import React from 'react';
import { MarketQuote } from '../types/marketQuote';
import { getISTMarketSessionInfo, formatDataAge } from '../utils/marketStatus';
import { TrendingUp, TrendingDown, Activity, Wifi, AlertTriangle, WifiOff } from 'lucide-react';

export interface FeedStatusInfo {
  status: string;
  mode: string;
  active_provider: string;
  is_live: boolean;
}

interface IndexTickerBarProps {
  indices: MarketQuote[];
  feedStatus?: FeedStatusInfo;
  onSelectIndex?: (index: MarketQuote) => void;
}

export const IndexTickerBar: React.FC<IndexTickerBarProps> = ({ indices = [], feedStatus, onSelectIndex }) => {
  const providerName = feedStatus?.active_provider || 'UPSTOX';
  const isSimulated = feedStatus?.status === 'SIMULATED' || feedStatus?.mode === 'SIMULATED';
  
  // Evaluate IST Session status
  const session = getISTMarketSessionInfo(
    indices.length > 0 ? Math.max(...indices.map((i) => i.receivedAt || 0)) : undefined,
    isSimulated
  );

  const validIndices = (indices || []).filter((idx) => idx && idx.symbol);

  return (
    <div className="bg-[#0b0c10] border-b border-stone-800/80 px-4 py-2 flex items-center space-x-6 overflow-x-auto scrollbar-none select-none text-xs">
      {/* Dynamic Session & Data Source Status Badge */}
      <div className="flex items-center space-x-2 shrink-0 border-r border-stone-800/80 pr-4">
        <div className={`flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full ${session.badgeBg} border ${session.badgeBorder} ${session.badgeTextColor} font-mono text-[10px] font-bold`}>
          <span className={`w-2 h-2 rounded-full ${session.badgeTextColor.replace('text-', 'bg-')} ${session.isSessionActive ? 'animate-pulse' : ''}`} />
          <span>{session.badgeText}</span>
        </div>
      </div>

      {/* Benchmark Indices List */}
      <div className="flex items-center space-x-6 shrink-0">
        {validIndices.map((idx) => {
          const isPos = (idx.change || 0) >= 0;
          const isVix = idx.symbol === 'INDIA VIX';
          const changePct = idx.changePercent ?? 0;
          const val = idx.ltp ?? idx.close ?? 0;
          const changeVal = idx.change ?? 0;

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
                  {val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>

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
            </div>
          );
        })}
      </div>
    </div>
  );
};
