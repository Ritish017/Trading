import React from 'react';
import { Asset } from '../types/trading';
import { ArrowUpRight, ArrowDownRight, TrendingUp } from 'lucide-react';

interface AssetStoryCardsProps {
  assets: Asset[];
  activeAsset: Asset;
  onSelectAsset: (asset: Asset) => void;
}

export const AssetStoryCards: React.FC<AssetStoryCardsProps> = ({
  assets,
  activeAsset,
  onSelectAsset,
}) => {
  // Show top 4 assets (e.g. BTC, ETH, SOL, AVAX)
  const displayAssets = assets.slice(0, 4);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4 select-none">
      {displayAssets.map((asset, index) => {
        const isActive = activeAsset.symbol === asset.symbol;
        const isPos = asset.change24h >= 0;

        if (isActive || index === 0 && !displayAssets.some(a => a.symbol === activeAsset.symbol)) {
          // Vibrant Gradient Featured Active Card (Pink to Purple to Indigo)
          return (
            <div
              key={asset.symbol}
              onClick={() => onSelectAsset(asset)}
              className="relative overflow-hidden rounded-2xl p-4 bg-gradient-to-r from-pink-500 via-purple-600 to-indigo-600 text-white shadow-xl shadow-purple-500/20 cursor-pointer transform hover:-translate-y-0.5 transition-all duration-200"
            >
              {/* Background ambient lighting */}
              <div className="absolute -right-6 -bottom-6 w-24 h-24 bg-white/10 rounded-full blur-xl pointer-events-none" />

              <div className="flex justify-between items-center mb-3">
                <div className="flex items-center space-x-2">
                  <div className="w-7 h-7 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center font-bold text-xs">
                    {asset.symbol.substring(0, 1)}
                  </div>
                  <span className="font-bold text-xs tracking-wider uppercase opacity-90">{asset.symbol}</span>
                </div>
                <div className="flex items-center space-x-1 px-2 py-0.5 rounded-full bg-white/20 backdrop-blur-md text-[11px] font-bold">
                  {isPos ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                  <span>{isPos ? '+' : ''}{asset.change24h}%</span>
                </div>
              </div>

              <div className="text-2xl font-black tracking-tight mb-1">
                ${asset.price.toLocaleString(undefined, { minimumFractionDigits: asset.precision })}
              </div>
              <div className="text-[11px] font-medium opacity-80 flex justify-between items-center">
                <span>Active Selected</span>
                <span className="font-mono">Vol: ${(asset.volume24h / 1000000).toFixed(1)}M</span>
              </div>
            </div>
          );
        }

        // Standard Glassmorphism Dark Card
        return (
          <div
            key={asset.symbol}
            onClick={() => onSelectAsset(asset)}
            className="rounded-2xl p-4 bg-[#1e2029] border border-stone-800/80 hover:border-purple-500/40 text-stone-200 cursor-pointer transform hover:-translate-y-0.5 transition-all duration-200 flex flex-col justify-between"
          >
            <div className="flex justify-between items-center mb-3">
              <div className="flex items-center space-x-2">
                <div className="w-7 h-7 rounded-full bg-stone-800 flex items-center justify-center font-bold text-xs text-stone-300">
                  {asset.symbol.substring(0, 1)}
                </div>
                <span className="font-bold text-xs text-stone-300 tracking-wider uppercase">{asset.symbol}</span>
              </div>
              <div
                className={`flex items-center space-x-0.5 px-2 py-0.5 rounded-full text-[11px] font-bold ${
                  isPos ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                }`}
              >
                {isPos ? '+' : ''}{asset.change24h}%
              </div>
            </div>

            <div className="text-2xl font-bold text-white tracking-tight mb-1">
              ${asset.price.toLocaleString(undefined, { minimumFractionDigits: asset.precision })}
            </div>
            <div className="text-[11px] text-stone-500 font-medium">
              24h High: ${asset.high24h.toLocaleString(undefined, { minimumFractionDigits: asset.precision })}
            </div>
          </div>
        );
      })}
    </div>
  );
};
