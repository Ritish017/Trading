import React from 'react';
import { NSEWatchlist } from '../NSEWatchlist';
import { OptionChainSummary } from '../OptionChainSummary';
import { NSEStock, OptionChainSummary as OptionChainType } from '../../types/indianMarket';
import { Layers, Activity, TrendingUp, TrendingDown } from 'lucide-react';

interface DerivativesLabPageProps {
  stocks: NSEStock[];
  selectedStock: NSEStock;
  onSelectStock: (stock: NSEStock) => void;
  onToggleFavorite: (symbol: string) => void;
  onOpenAIForStock: (stock: NSEStock) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onAddCustomStock: (sym: string) => void;
  optionSummary?: OptionChainType;
}

export const DerivativesLabPage: React.FC<DerivativesLabPageProps> = ({
  stocks,
  selectedStock,
  onSelectStock,
  onToggleFavorite,
  onOpenAIForStock,
  searchQuery,
  onSearchChange,
  onAddCustomStock,
  optionSummary,
}) => {
  const pcr = optionSummary?.pcr ?? 1.18;
  const isPcrBullish = pcr >= 1.0;

  return (
    <div className="flex-1 p-3 grid grid-cols-1 md:grid-cols-12 gap-3 h-[calc(100vh-175px)] min-h-0">
      {/* Left Sidebar: NSE Stock & Index Selector */}
      <div className="md:col-span-3 h-full flex flex-col min-h-0">
        <NSEWatchlist
          stocks={stocks}
          selectedStock={selectedStock}
          onSelectStock={onSelectStock}
          onToggleFavorite={onToggleFavorite}
          onOpenAIForStock={onOpenAIForStock}
          searchQuery={searchQuery}
          onSearchChange={onSearchChange}
          onAddCustomStock={onAddCustomStock}
        />
      </div>

      {/* Right Area: Comprehensive Option Chain & F&O Analytics */}
      <div className="md:col-span-9 flex flex-col space-y-3 h-full overflow-y-auto custom-scrollbar pr-0.5">
        {/* Derivatives Overview Top Header */}
        <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold font-mono text-base text-white">
                  {selectedStock?.symbol.split('.')[0]} Derivatives Desk
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30">
                  NSE F&O
                </span>
              </div>
              <p className="text-xs text-stone-400">Real-time Open Interest, Put-Call Ratio, and Greeks Matrix</p>
            </div>
          </div>

          <div className="flex items-center space-x-3 text-xs font-mono">
            <div className="flex flex-col items-end">
              <span className="text-[10px] text-stone-500 uppercase">Put-Call Ratio (PCR)</span>
              <span className={`font-black ${isPcrBullish ? 'text-emerald-400' : 'text-rose-400'}`}>
                {pcr.toFixed(2)} ({isPcrBullish ? 'Bullish Put Bias' : 'Call Resistance'})
              </span>
            </div>
            <div className="h-8 w-px bg-stone-800" />
            <div className="flex flex-col items-end">
              <span className="text-[10px] text-stone-500 uppercase">Max Pain Strike</span>
              <span className="font-black text-amber-400">
                ₹{optionSummary?.maxPainStrike?.toLocaleString() ?? 24500}
              </span>
            </div>
          </div>
        </div>

        {/* Option Chain Component */}
        <div className="flex-1 min-h-[450px]">
          <OptionChainSummary
            symbol={selectedStock?.symbol || 'NIFTY'}
            price={selectedStock?.price || 24580.0}
            optionSummary={optionSummary}
          />
        </div>
      </div>
    </div>
  );
};
