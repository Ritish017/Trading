import React, { useState } from 'react';
import { Search, Star, TrendingUp, TrendingDown, Filter } from 'lucide-react';
import { Asset, AssetCategory } from '../types/trading';

interface WatchlistProps {
  assets: Asset[];
  activeAsset: Asset;
  onSelectAsset: (asset: Asset) => void;
  onToggleFavorite: (symbol: string) => void;
}

export const Watchlist: React.FC<WatchlistProps> = ({
  assets,
  activeAsset,
  onSelectAsset,
  onToggleFavorite,
}) => {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<AssetCategory | 'All' | 'Favorites'>('All');

  const categories: (AssetCategory | 'All' | 'Favorites')[] = [
    'All',
    'Favorites',
    'Crypto',
    'Stocks',
    'Forex',
    'Commodities',
  ];

  const filteredAssets = assets.filter((asset) => {
    const matchesSearch =
      asset.symbol.toLowerCase().includes(search.toLowerCase()) ||
      asset.name.toLowerCase().includes(search.toLowerCase());

    if (!matchesSearch) return false;

    if (category === 'All') return true;
    if (category === 'Favorites') return asset.isFavorite;
    return asset.category === category;
  });

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-xl p-3 flex flex-col h-full overflow-hidden text-stone-200">
      {/* Header & Search */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-stone-400">Markets Watchlist</span>
          <span className="text-[11px] text-stone-500 font-mono">{filteredAssets.length} Assets</span>
        </div>

        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-stone-500" />
          <input
            type="text"
            placeholder="Search market (e.g. BTC, NVDA)..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-stone-950 border border-stone-800 text-stone-200 text-xs rounded-lg pl-8 pr-3 py-1.5 focus:outline-none focus:border-stone-600 transition-colors placeholder:text-stone-600 font-sans"
          />
        </div>
      </div>

      {/* Category Pills */}
      <div className="flex space-x-1 mb-2 overflow-x-auto no-scrollbar pb-1">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={`px-2.5 py-1 rounded-md text-[11px] font-medium whitespace-nowrap transition-colors ${
              category === cat
                ? 'bg-stone-700 text-white font-semibold'
                : 'bg-stone-950 text-stone-400 hover:text-stone-200 hover:bg-stone-800'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Asset List */}
      <div className="flex-1 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
        {filteredAssets.length === 0 ? (
          <div className="text-center py-8 text-stone-500 text-xs">
            No markets match your criteria.
          </div>
        ) : (
          filteredAssets.map((asset) => {
            const isSelected = activeAsset.symbol === asset.symbol;
            const isPos = asset.change24h >= 0;

            return (
              <div
                key={asset.symbol}
                onClick={() => onSelectAsset(asset)}
                className={`p-2 rounded-lg cursor-pointer transition-all flex items-center justify-between border ${
                  isSelected
                    ? 'bg-stone-800/90 border-stone-700 shadow-xs'
                    : 'bg-stone-950/50 hover:bg-stone-800/40 border-stone-800/50'
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleFavorite(asset.symbol);
                    }}
                    className="text-stone-600 hover:text-amber-400 transition-colors p-0.5"
                  >
                    <Star
                      className={`w-3.5 h-3.5 ${
                        asset.isFavorite ? 'fill-amber-400 text-amber-400' : ''
                      }`}
                    />
                  </button>
                  <div>
                    <div className="text-xs font-bold text-stone-100 flex items-center space-x-1 font-mono">
                      <span>{asset.symbol}</span>
                    </div>
                    <div className="text-[10px] text-stone-500 font-sans truncate max-w-[90px]">
                      {asset.name}
                    </div>
                  </div>
                </div>

                <div className="text-right font-mono">
                  <div className="text-xs font-semibold text-stone-200">
                    ${asset.price.toLocaleString(undefined, { minimumFractionDigits: asset.precision })}
                  </div>
                  <div className={`text-[11px] font-medium flex items-center justify-end ${
                    isPos ? 'text-emerald-400' : 'text-rose-400'
                  }`}>
                    {isPos ? <TrendingUp className="w-3 h-3 mr-0.5" /> : <TrendingDown className="w-3 h-3 mr-0.5" />}
                    {isPos ? '+' : ''}{asset.change24h}%
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
