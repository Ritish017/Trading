import React, { useState } from 'react';
import { NSEStock } from '../types/indianMarket';
import { Star, ArrowUpRight, ArrowDownRight, Sparkles, LayoutList, Columns, Search, X, PlusCircle } from 'lucide-react';

interface NSEWatchlistProps {
  stocks: NSEStock[];
  selectedStock: NSEStock;
  onSelectStock: (stock: NSEStock) => void;
  onToggleFavorite: (symbol: string) => void;
  onOpenAIForStock: (stock: NSEStock) => void;
  searchQuery?: string;
  onSearchChange?: (q: string) => void;
  onAddCustomStock?: (symbol: string) => void;
}

export const NSEWatchlist: React.FC<NSEWatchlistProps> = ({
  stocks,
  selectedStock,
  onSelectStock,
  onToggleFavorite,
  onOpenAIForStock,
  searchQuery = '',
  onSearchChange,
  onAddCustomStock,
}) => {
  const [selectedSector, setSelectedSector] = useState<string>('All');
  const [viewMode, setViewMode] = useState<'Compact' | 'Detailed'>('Compact');
  const [localSearch, setLocalSearch] = useState<string>('');

  const effectiveSearch = onSearchChange ? searchQuery : localSearch;
  const handleSearch = (val: string) => {
    if (onSearchChange) onSearchChange(val);
    else setLocalSearch(val);
  };

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

  // Smart Typo-Tolerant & Fuzzy Search Matcher
  const isMatch = (stock: NSEStock, rawQuery: string) => {
    if (!rawQuery) return true;
    const q = rawQuery.toLowerCase().trim();
    const sym = (stock.symbol || '').toLowerCase();
    const cleanSym = sym.replace('.ns', '').replace('.bo', '');
    const name = (stock.name || '').toLowerCase();
    const sector = (stock.sector || '').toLowerCase();

    // 1. Direct substring match
    if (sym.includes(q) || cleanSym.includes(q) || name.includes(q) || sector.includes(q)) {
      return true;
    }

    // 2. Vowel-stripped / typo match (e.g. "mref" -> "mrf", "rlinc" -> "reliance")
    const stripVowels = (s: string) => s.replace(/[aeiou\s\-_.]/g, '');
    const qStripped = stripVowels(q);
    const symStripped = stripVowels(cleanSym);
    const nameStripped = stripVowels(name);

    if (qStripped.length >= 2 && (symStripped.includes(qStripped) || nameStripped.includes(qStripped) || qStripped.includes(symStripped))) {
      return true;
    }

    return false;
  };

  const filteredStocks = (stocks || []).filter((stock) => {
    if (!stock || !stock.symbol) return false;
    if (!isMatch(stock, effectiveSearch)) return false;
    if (selectedSector === 'All') return true;
    if (selectedSector === 'Favorites') return stock.isFavorite;
    if (selectedSector === 'NIFTY 50') return stock.isNifty50;
    return stock.sector === selectedSector;
  });

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-3 h-full flex flex-col justify-between overflow-hidden shadow-sm">
      {/* Header & View Mode Switcher */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-stone-800/60 shrink-0">
        <div className="flex items-center space-x-2">
          <span className="font-extrabold text-xs text-white uppercase tracking-wider font-mono">NSE Watchlist</span>
          <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            {filteredStocks.length} Stocks
          </span>
        </div>

        <div className="flex items-center space-x-1 bg-[#14151b] p-0.5 rounded-lg border border-stone-800">
          <button
            onClick={() => setViewMode('Compact')}
            className={`p-1.5 rounded text-[10px] font-bold transition-all cursor-pointer ${
              viewMode === 'Compact' ? 'bg-amber-500 text-stone-950 shadow-sm' : 'text-stone-400 hover:text-stone-200'
            }`}
            title="Compact View (Recommended for Sidebar)"
          >
            <LayoutList className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setViewMode('Detailed')}
            className={`p-1.5 rounded text-[10px] font-bold transition-all cursor-pointer ${
              viewMode === 'Detailed' ? 'bg-amber-500 text-stone-950 shadow-sm' : 'text-stone-400 hover:text-stone-200'
            }`}
            title="Detailed Table View"
          >
            <Columns className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Integrated Search Input */}
      <div className="relative mb-2 shrink-0">
        <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={effectiveSearch}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Search stock (e.g. MRF, TCS)..."
          className="w-full bg-[#14151b] border border-stone-800 rounded-xl pl-8 pr-7 py-1.5 text-xs text-stone-200 placeholder-stone-500 focus:outline-none focus:border-amber-500/50 transition-all font-mono"
        />
        {effectiveSearch && (
          <button
            onClick={() => handleSearch('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-500 hover:text-stone-300"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Sector Filter Chips */}
      <div className="flex items-center space-x-1.5 overflow-x-auto custom-scrollbar pb-2 mb-2 border-b border-stone-800/60 shrink-0">
        {sectors.map((sec) => (
          <button
            key={sec}
            onClick={() => setSelectedSector(sec)}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-semibold whitespace-nowrap transition-all cursor-pointer ${
              selectedSector === sec
                ? 'bg-amber-500 text-stone-950 font-bold shadow-sm'
                : 'bg-[#14151b] text-stone-400 hover:text-stone-200 hover:bg-stone-800/60'
            }`}
          >
            {sec}
          </button>
        ))}
      </div>

      {/* Watchlist Body */}
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto custom-scrollbar pr-0.5">
        {filteredStocks.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-4 text-center space-y-3 bg-[#14151b]/40 rounded-xl border border-dashed border-stone-800 my-2">
            <span className="text-xs text-stone-400">
              No local stock matching &ldquo;<strong className="text-amber-400">{effectiveSearch}</strong>&rdquo;
            </span>
            {effectiveSearch && onAddCustomStock && (
              <button
                onClick={() => onAddCustomStock(effectiveSearch.trim().toUpperCase())}
                className="flex items-center space-x-1.5 px-3 py-1.5 bg-amber-500 hover:bg-amber-400 text-stone-950 rounded-xl text-xs font-bold font-mono transition-all shadow-md cursor-pointer"
              >
                <PlusCircle className="w-3.5 h-3.5" />
                <span>Load &ldquo;{effectiveSearch.trim().toUpperCase()}&rdquo; Live</span>
              </button>
            )}
          </div>
        ) : viewMode === 'Compact' ? (

          /* COMPACT SIDEBAR VIEW (Optimized for sidebar with full price and change visibility) */
          <div className="space-y-1.5">
            {filteredStocks.map((stock) => {
              const isSelected = selectedStock?.symbol === stock.symbol;
              const isPos = (stock.change || 0) >= 0;
              const priceVal = stock.price || 0;
              const changeVal = stock.change || 0;
              const changePct = stock.changePercent || 0;

              return (
                <div
                  key={stock.symbol}
                  onClick={() => onSelectStock(stock)}
                  className={`flex items-center justify-between p-2 rounded-xl transition-all cursor-pointer border ${
                    isSelected
                      ? 'bg-amber-500/10 border-amber-500/50 text-white shadow-sm'
                      : 'bg-[#14151b]/70 hover:bg-stone-800/50 border-stone-800/40 text-stone-200'
                  }`}
                >
                  {/* Left: Star + Symbol & Name */}
                  <div className="flex items-center space-x-2 min-w-0 pr-1.5 flex-1">
                    <Star
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleFavorite(stock.symbol);
                      }}
                      className={`w-3.5 h-3.5 shrink-0 cursor-pointer transition-colors ${
                        stock.isFavorite ? 'text-amber-400 fill-amber-400' : 'text-stone-600 hover:text-stone-400'
                      }`}
                    />

                    <div className="flex flex-col min-w-0 flex-1">
                      <div className="flex items-center space-x-1">
                        <span className="font-extrabold font-mono text-xs tracking-tight text-white">
                          {stock.symbol.split('.')[0]}
                        </span>
                        {stock.isNifty50 && (
                          <span className="px-1 py-0.2 text-[7px] font-bold rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                            N50
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-stone-400 truncate">
                        {stock.name}
                      </span>
                    </div>
                  </div>

                  {/* Right: Price (₹) & Change (%) */}
                  <div className="flex items-center space-x-1.5 shrink-0 text-right">
                    <div className="flex flex-col items-end">
                      <span className="font-black font-mono text-xs text-stone-100 whitespace-nowrap">
                        ₹{priceVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                      <div className={`flex items-center space-x-0.5 text-[10px] font-mono font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isPos ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                        <span>{isPos ? '+' : ''}{changePct.toFixed(2)}%</span>
                      </div>
                    </div>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenAIForStock(stock);
                      }}
                      className="p-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 transition-colors cursor-pointer shrink-0"
                      title="Run Gemini AI Intelligence"
                    >
                      <Sparkles className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          /* DETAILED TABLE VIEW (With Horizontal Scrollbar & Priority Column Ordering) */
          <div className="w-full">
            <table className="w-full text-left text-xs font-sans border-collapse min-w-[550px]">
              <thead>
                <tr className="text-stone-400 font-medium border-b border-stone-800/60 pb-2">
                  <th className="pb-2 pl-1 font-medium w-6">Fav</th>
                  <th className="pb-2 font-medium min-w-[100px]">Symbol</th>
                  <th className="pb-2 font-medium min-w-[85px]">Price (₹)</th>
                  <th className="pb-2 font-medium min-w-[75px]">Change</th>
                  <th className="pb-2 font-medium min-w-[90px]">Sector</th>
                  <th className="pb-2 font-medium min-w-[65px]">Vol (L)</th>
                  <th className="pb-2 font-medium min-w-[70px]">Turn (Cr)</th>
                  <th className="pb-2 font-medium min-w-[40px]">PE</th>
                  <th className="pb-2 font-medium text-right pr-1 min-w-[45px]">AI</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-800/40">
                {filteredStocks.map((stock) => {
                  const isSelected = selectedStock?.symbol === stock.symbol;
                  const isPos = (stock.change || 0) >= 0;
                  const priceVal = stock.price || 0;
                  const changeVal = stock.change || 0;
                  const changePct = stock.changePercent || 0;

                  return (
                    <tr
                      key={stock.symbol}
                      onClick={() => onSelectStock(stock)}
                      className={`hover:bg-stone-800/40 transition-colors cursor-pointer ${
                        isSelected ? 'bg-amber-500/10 border-l-2 border-amber-500' : ''
                      }`}
                    >
                      <td className="py-2 pl-1 shrink-0" onClick={(e) => { e.stopPropagation(); onToggleFavorite(stock.symbol); }}>
                        <Star
                          className={`w-3.5 h-3.5 cursor-pointer transition-colors ${
                            stock.isFavorite ? 'text-amber-400 fill-amber-400' : 'text-stone-600 hover:text-stone-400'
                          }`}
                        />
                      </td>

                      <td className="py-2 pr-2">
                        <div className="flex flex-col">
                          <span className="font-extrabold text-stone-100 font-mono text-xs">{stock.symbol.split('.')[0]}</span>
                          <span className="text-[9px] text-stone-400 font-medium truncate max-w-[95px]">
                            {stock.name}
                          </span>
                        </div>
                      </td>

                      <td className="py-2 font-mono font-black text-stone-100 text-xs whitespace-nowrap">
                        ₹{priceVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>

                      <td className="py-2 font-mono whitespace-nowrap">
                        <div className={`flex items-center space-x-1 text-xs font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isPos ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                          <span>{isPos ? '+' : ''}{changePct.toFixed(2)}%</span>
                        </div>
                      </td>

                      <td className="py-2 pr-2">
                        <span className="px-1.5 py-0.5 rounded text-[8px] font-medium bg-[#14151b] text-stone-300 border border-stone-800 whitespace-nowrap">
                          {stock.sector}
                        </span>
                      </td>

                      <td className="py-2 font-mono text-stone-300 text-xs whitespace-nowrap">
                        {(stock.volumeLakhs || 12.4).toFixed(1)} L
                      </td>

                      <td className="py-2 font-mono text-stone-300 text-xs whitespace-nowrap">
                        ₹{(stock.turnoverCr || 85.0).toFixed(1)} Cr
                      </td>

                      <td className="py-2 font-mono text-stone-400 text-xs">
                        {stock.peRatio || 24.5}x
                      </td>

                      <td className="py-2 text-right pr-1" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => onOpenAIForStock(stock)}
                          className="p-1 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 transition-colors cursor-pointer"
                          title="Run Gemini AI Intelligence"
                        >
                          <Sparkles className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

