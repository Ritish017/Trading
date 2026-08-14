import React from 'react';
import { NSEWatchlist } from '../NSEWatchlist';
import { IndianCandleChart } from '../IndianCandleChart';
import { NSEStock } from '../../types/indianMarket';
import { IndianCandle } from '../../utils/indianTechnicalAnalysis';

interface TradingTerminalPageProps {
  stocks: NSEStock[];
  selectedStock: NSEStock;
  selectedSymbol: string;
  onSelectStock: (stock: NSEStock) => void;
  onToggleFavorite: (symbol: string) => void;
  onOpenAIForStock: (stock: NSEStock) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onAddCustomStock: (sym: string) => void;
  candles: IndianCandle[];
  timeframe: string;
  onTimeframeChange: (tf: string) => void;
  onQuickBuy?: (stock: NSEStock) => void;
  onQuickSell?: (stock: NSEStock) => void;
}

export const TradingTerminalPage: React.FC<TradingTerminalPageProps> = ({
  stocks,
  selectedStock,
  selectedSymbol,
  onSelectStock,
  onToggleFavorite,
  onOpenAIForStock,
  searchQuery,
  onSearchChange,
  onAddCustomStock,
  candles,
  timeframe,
  onTimeframeChange,
  onQuickBuy,
  onQuickSell,
}) => {
  return (
    <div className="flex-1 p-3 grid grid-cols-1 md:grid-cols-12 gap-3 min-h-0">
      {/* Left Sidebar: NSE Watchlist */}
      <div className="md:col-span-3 h-[calc(100vh-175px)] flex flex-col min-h-0">
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

      {/* Main Center Area: Full-Height Interactive Chart & Quick Trade Bar */}
      <div className="md:col-span-9 flex flex-col space-y-3 h-[calc(100vh-175px)] overflow-y-auto custom-scrollbar pr-0.5">
        <div className="flex-1 min-h-[500px]">
          <IndianCandleChart
            symbol={selectedStock?.symbol || 'RELIANCE.NS'}
            name={selectedStock?.name || 'Reliance Industries'}
            price={selectedStock?.price || 2845.5}
            change={selectedStock?.change || 0}
            changePercent={selectedStock?.changePercent || 0}
            candles={candles}
            timeframe={timeframe}
            onTimeframeChange={onTimeframeChange}
          />
        </div>

        {/* Bottom Quick Order Execution Bar */}
        <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-3 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div className="flex items-center space-x-3">
            <div className="flex flex-col">
              <span className="text-[10px] font-mono uppercase text-stone-400">Selected Instrument</span>
              <span className="font-extrabold font-mono text-sm text-white">{selectedStock?.symbol}</span>
            </div>
            <div className="h-7 w-px bg-stone-800" />
            <div className="flex flex-col">
              <span className="text-[10px] font-mono uppercase text-stone-400">Live Price</span>
              <span className="font-black font-mono text-sm text-amber-400">
                ₹{selectedStock?.price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="h-7 w-px bg-stone-800 hidden sm:block" />
            <div className="flex flex-col hidden sm:flex">
              <span className="text-[10px] font-mono uppercase text-stone-400">Intraday Range</span>
              <span className="font-mono text-xs text-stone-300">
                ₹{selectedStock?.low?.toLocaleString()} - ₹{selectedStock?.high?.toLocaleString()}
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {onQuickBuy && (
              <button
                onClick={() => onQuickBuy(selectedStock)}
                className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-stone-950 font-black font-mono text-xs shadow-lg shadow-emerald-500/20 cursor-pointer transition-all active:scale-95"
              >
                BUY / LONG (CNC/MIS)
              </button>
            )}
            {onQuickSell && (
              <button
                onClick={() => onQuickSell(selectedStock)}
                className="px-4 py-2 rounded-xl bg-rose-500 hover:bg-rose-400 text-stone-950 font-black font-mono text-xs shadow-lg shadow-rose-500/20 cursor-pointer transition-all active:scale-95"
              >
                SELL / SHORT
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
