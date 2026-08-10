import React, { useState } from 'react';
import { NSEStock } from '../types/indianMarket';
import { Star, ArrowUpRight, ArrowDownRight, Sparkles } from 'lucide-react';

interface NSEWatchlistProps {
  stocks: NSEStock[];
  selectedStock: NSEStock;
  onSelectStock: (stock: NSEStock) => void;
  onToggleFavorite: (symbol: string) => void;
  onOpenAIForStock: (stock: NSEStock) => void;
}

export const NSEWatchlist: React.FC<NSEWatchlistProps> = ({
  stocks,
  selectedStock,
  onSelectStock,
  onToggleFavorite,
  onOpenAIForStock,
}) => {
  const [selectedSector, setSelectedSector] = useState<string>('All');

  const sectors: string[] = [
    'All',
    'Favorites',
    'NIFTY 50',
    'IT Services',
    'Banking & Financials',
    'Energy & Oil',
    'Automotive',
    'FMCG',
    'Pharmaceuticals',
  ];

  const filteredStocks = (stocks || []).filter((stock) => {
    if (!stock || !stock.symbol) return false;
    if (selectedSector === 'All') return true;
    if (selectedSector === 'Favorites') return stock.isFavorite;
    if (selectedSector === 'NIFTY 50') return stock.isNifty50;
    return stock.sector === selectedSector;
  });

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 select-none h-full flex flex-col justify-between">
      {/* Sector Filter Bar */}
      <div className="flex items-center space-x-2 overflow-x-auto scrollbar-none pb-3 mb-3 border-b border-stone-800/60 shrink-0">
        {sectors.map((sec) => (
          <button
            key={sec}
            onClick={() => setSelectedSector(sec)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
              selectedSector === sec
                ? 'bg-amber-500 text-stone-950 font-bold shadow-md shadow-amber-500/20'
                : 'bg-[#14151b] text-stone-400 hover:text-stone-200 hover:bg-stone-800/60'
            }`}
          >
            {sec}
          </button>
        ))}
      </div>

      {/* Stocks Table with Fixed Grid Column Scaling */}
      <div className="overflow-x-auto flex-1 min-h-0 scrollbar-none">
        <table className="w-full text-left text-xs font-sans border-collapse min-w-[720px]">
          <thead>
            <tr className="text-stone-400 font-medium border-b border-stone-800/60 pb-2">
              <th className="pb-2.5 pl-2 font-medium w-8">Fav</th>
              <th className="pb-2.5 font-medium min-w-[140px]">NSE Symbol / Name</th>
              <th className="pb-2.5 font-medium min-w-[110px]">Sector</th>
              <th className="pb-2.5 font-medium min-w-[90px]">Price (₹)</th>
              <th className="pb-2.5 font-medium min-w-[100px]">24h Change</th>
              <th className="pb-2.5 font-medium min-w-[90px]">Volume (L)</th>
              <th className="pb-2.5 font-medium min-w-[90px]">Turnover (Cr)</th>
              <th className="pb-2.5 font-medium min-w-[50px]">PE</th>
              <th className="pb-2.5 font-medium min-w-[110px]">52W Range</th>
              <th className="pb-2.5 font-medium text-right pr-2 min-w-[70px]">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-800/40">
            {filteredStocks.map((stock) => {
              const isSelected = selectedStock?.symbol === stock.symbol;
              const isPos = (stock.change || 0) >= 0;
              const priceVal = stock.price || 0;
              const changeVal = stock.change || 0;
              const changePct = stock.changePercent || 0;

              // Compute 52-Week Range position percentage
              const rangeSpan = (stock.week52High || 1) - (stock.week52Low || 0) || 1;
              const rangePos = Math.min(Math.max(((priceVal - (stock.week52Low || 0)) / rangeSpan) * 100, 0), 100);

              return (
                <tr
                  key={stock.symbol}
                  onClick={() => onSelectStock(stock)}
                  className={`hover:bg-stone-800/40 transition-colors cursor-pointer ${
                    isSelected ? 'bg-amber-500/10 border-l-2 border-amber-500' : ''
                  }`}
                >
                  {/* Favorite Toggle */}
                  <td className="py-2.5 pl-2 shrink-0" onClick={(e) => { e.stopPropagation(); onToggleFavorite(stock.symbol); }}>
                    <Star
                      className={`w-3.5 h-3.5 cursor-pointer transition-colors ${
                        stock.isFavorite ? 'text-amber-400 fill-amber-400' : 'text-stone-600 hover:text-stone-400'
                      }`}
                    />
                  </td>

                  {/* Symbol & Name */}
                  <td className="py-2.5 pr-2">
                    <div className="flex flex-col">
                      <div className="flex items-center space-x-1.5">
                        <span className="font-extrabold text-stone-100 font-mono text-xs">{stock.symbol.split('.')[0]}</span>
                        <span className="text-[9px] text-stone-500 font-mono">BSE:{stock.bseCode || '500325'}</span>
                        {stock.isNifty50 && (
                          <span className="px-1 py-0.2 text-[8px] font-bold rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                            NIFTY50
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-stone-400 font-medium truncate max-w-[140px]">
                        {stock.name}
                      </span>
                    </div>
                  </td>

                  {/* Sector Tag */}
                  <td className="py-2.5 pr-2">
                    <span className="px-1.5 py-0.5 rounded-lg text-[9px] font-medium bg-[#14151b] text-stone-300 border border-stone-800 whitespace-nowrap">
                      {stock.sector}
                    </span>
                  </td>

                  {/* Price */}
                  <td className="py-2.5 font-mono font-black text-stone-100 text-xs whitespace-nowrap">
                    ₹{priceVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </td>

                  {/* Change */}
                  <td className="py-2.5 font-mono whitespace-nowrap">
                    <div className={`flex items-center space-x-1 text-xs font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {isPos ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                      <span>{isPos ? '+' : ''}{changePct.toFixed(2)}%</span>
                    </div>
                    <div className="text-[9px] text-stone-500 font-mono">
                      {isPos ? '+' : ''}₹{changeVal.toFixed(2)}
                    </div>
                  </td>

                  {/* Volume in Lakhs */}
                  <td className="py-2.5 font-mono text-stone-300 text-xs whitespace-nowrap">
                    {(stock.volumeLakhs || 12.4).toFixed(1)} L
                  </td>

                  {/* Turnover in ₹ Cr */}
                  <td className="py-2.5 font-mono text-stone-300 text-xs whitespace-nowrap">
                    ₹{(stock.turnoverCr || 85.0).toFixed(1)} Cr
                  </td>

                  {/* PE Ratio */}
                  <td className="py-2.5 font-mono text-stone-400 text-xs">
                    {stock.peRatio || 24.5}x
                  </td>

                  {/* 52W Range Progress Bar */}
                  <td className="py-2.5 pr-2">
                    <div className="w-20 flex flex-col space-y-0.5">
                      <div className="flex justify-between text-[8px] text-stone-500 font-mono">
                        <span>₹{(stock.week52Low || priceVal * 0.8).toFixed(0)}</span>
                        <span>₹{(stock.week52High || priceVal * 1.2).toFixed(0)}</span>
                      </div>
                      <div className="w-full bg-stone-800 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-amber-500 to-emerald-400 h-full rounded-full"
                          style={{ width: `${rangePos}%` }}
                        />
                      </div>
                    </div>
                  </td>

                  {/* Action Buttons */}
                  <td className="py-2.5 text-right pr-2" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-end space-x-1">
                      <button
                        onClick={() => onOpenAIForStock(stock)}
                        className="p-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 transition-colors cursor-pointer"
                        title="Run Gemini AI Intelligence"
                      >
                        <Sparkles className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => onSelectStock(stock)}
                        className="px-2 py-0.5 rounded-lg bg-[#14151b] hover:bg-stone-800 text-stone-300 text-[10px] font-bold border border-stone-800 cursor-pointer"
                      >
                        Chart
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
