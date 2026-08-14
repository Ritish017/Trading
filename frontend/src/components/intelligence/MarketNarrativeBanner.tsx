import React from 'react';
import { MarketNarrative } from '../../types/intelligence';
import { Sparkles, Globe, TrendingUp, TrendingDown, Compass, RefreshCw } from 'lucide-react';

interface MarketNarrativeBannerProps {
  narrative?: MarketNarrative;
  isLoading?: boolean;
  onRefresh?: () => void;
}

export const MarketNarrativeBanner: React.FC<MarketNarrativeBannerProps> = ({
  narrative,
  isLoading,
  onRefresh,
}) => {
  if (!narrative) return null;

  const isBullish = narrative.primary_regime.includes('BULLISH') || narrative.primary_regime.includes('RISK_ON');
  const isBearish = narrative.primary_regime.includes('BEARISH') || narrative.primary_regime.includes('RISK_OFF');

  return (
    <div className="bg-gradient-to-r from-[#181a24] via-[#1c1e29] to-[#161720] border border-amber-500/30 rounded-2xl p-3 shadow-md transition-all">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-stone-800/80 pb-2 mb-2">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
            <Compass className="w-4 h-4 animate-spin-slow" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-black uppercase tracking-wider text-amber-400 font-mono">
                Today&apos;s Market Narrative
              </span>
              <span className="text-[10px] font-mono text-stone-500">{narrative.date}</span>
            </div>
            <h3 className="text-xs sm:text-sm font-bold text-stone-100">{narrative.headline}</h3>
          </div>
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          <span className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-extrabold uppercase border ${
            isBullish
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              : isBearish
              ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
              : 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30'
          }`}>
            {narrative.primary_regime.replace(/_/g, ' ')}
          </span>

          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="p-1.5 rounded-lg bg-stone-800/80 hover:bg-stone-700 text-stone-400 hover:text-stone-200 transition-colors cursor-pointer disabled:opacity-50"
              title="Refresh Narrative"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      <p className="text-xs text-stone-300 leading-relaxed font-sans mb-2.5">
        {narrative.narrative_summary}
      </p>

      {/* Sector Drivers & Institutional Bias Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2 border-t border-stone-800/40 text-[11px] font-mono">
        <div className="flex items-center space-x-1.5 text-stone-400">
          <TrendingUp className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span className="truncate">
            <strong className="text-stone-200">Leaders:</strong> {narrative.sector_leaders.join(', ')}
          </span>
        </div>

        <div className="flex items-center space-x-1.5 text-stone-400">
          <TrendingDown className="w-3.5 h-3.5 text-rose-400 shrink-0" />
          <span className="truncate">
            <strong className="text-stone-200">Laggards:</strong> {narrative.sector_laggards.join(', ')}
          </span>
        </div>

        <div className="flex items-center space-x-1.5 text-stone-400 sm:justify-end">
          <Globe className="w-3.5 h-3.5 text-sky-400 shrink-0" />
          <span className="truncate">
            <strong className="text-stone-200">Flow:</strong> {narrative.institutional_bias}
          </span>
        </div>
      </div>
    </div>
  );
};
