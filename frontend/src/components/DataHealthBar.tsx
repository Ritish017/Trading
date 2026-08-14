import React from 'react';
import { MarketStatusCode, MarketProvenance } from '../types/marketQuote';
import { getISTMarketSessionInfo, formatDataAge, getProvenanceBadge } from '../utils/marketStatus';
import { Activity, Wifi, Database, Clock, Server, CheckCircle2 } from 'lucide-react';

interface DataHealthBarProps {
  provider: MarketProvenance;
  status: MarketStatusCode;
  wsConnected: boolean;
  restConnected: boolean;
  lastTickTimeMs?: number;
  subscribedCount: number;
}

export const DataHealthBar: React.FC<DataHealthBarProps> = ({
  provider = 'UPSTOX',
  status = 'LIVE',
  wsConnected = true,
  restConnected = true,
  lastTickTimeMs,
  subscribedCount = 8,
}) => {
  const session = getISTMarketSessionInfo(lastTickTimeMs, provider === 'DEV_MOCK');
  const dataAgeMs = lastTickTimeMs ? Math.max(0, Date.now() - lastTickTimeMs) : 0;
  const dataAgeStr = formatDataAge(dataAgeMs);
  const provBadge = getProvenanceBadge(provider);

  return (
    <footer className="bg-[#0b0c10] border-t border-stone-800/80 px-4 py-1.5 flex flex-wrap items-center justify-between text-[11px] font-mono text-stone-400 select-none">
      {/* Left: Engine & Market Session Status */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2">
          <Server className="w-3.5 h-3.5 text-stone-500" />
          <span className="text-stone-300 font-bold">DATA ENGINE</span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${provBadge.color}`}>
            {provBadge.text}
          </span>
        </div>

        <div className="hidden sm:flex items-center space-x-1.5">
          <span className="text-stone-500">Market State:</span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${session.badgeBg} ${session.badgeTextColor} ${session.badgeBorder}`}>
            {session.badgeText}
          </span>
        </div>
      </div>

      {/* Middle: Tick Freshness & Latency */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-1.5">
          <Clock className="w-3.5 h-3.5 text-amber-400" />
          <span>Last Tick:</span>
          <span className="text-stone-200 font-bold">{dataAgeStr}</span>
        </div>

        <div className="hidden md:flex items-center space-x-1.5">
          <Activity className="w-3.5 h-3.5 text-indigo-400" />
          <span>Subscribed Stream:</span>
          <span className="text-stone-200 font-bold">{subscribedCount} Instruments</span>
        </div>
      </div>

      {/* Right: Subsystem Health */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-1.5">
          <Wifi className={`w-3.5 h-3.5 ${wsConnected ? 'text-emerald-400' : 'text-rose-400'}`} />
          <span>WS:</span>
          <span className={wsConnected ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
            {wsConnected ? 'CONNECTED' : 'OFFLINE'}
          </span>
        </div>

        <div className="flex items-center space-x-1.5">
          <Database className={`w-3.5 h-3.5 ${restConnected ? 'text-emerald-400' : 'text-rose-400'}`} />
          <span>REST:</span>
          <span className={restConnected ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
            {restConnected ? 'HEALTHY' : 'DOWN'}
          </span>
        </div>

        <div className="hidden lg:flex items-center space-x-1">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-stone-300 font-bold">SYSTEM OK</span>
        </div>
      </div>
    </footer>
  );
};
