import React, { useState } from 'react';
import { Asset } from '../types/trading';
import { ArrowUpRight, ArrowDownRight, ChevronDown } from 'lucide-react';

interface TransactionsTableProps {
  assets: Asset[];
  activeAsset: Asset;
  onSelectAsset: (asset: Asset) => void;
}

export const TransactionsTable: React.FC<TransactionsTableProps> = ({
  assets,
  activeAsset,
  onSelectAsset,
}) => {
  const [timeFilter, setTimeFilter] = useState<'Day' | 'Week' | 'Month'>('Week');

  return (
    <div className="bg-[#1e2029] border border-stone-800/80 rounded-2xl p-4 select-none flex flex-col justify-between">
      {/* Table Title Bar */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-bold text-white tracking-tight">Transaction</h3>

        <div className="relative">
          <select
            value={timeFilter}
            onChange={(e) => setTimeFilter(e.target.value as any)}
            className="appearance-none bg-[#16171d] border border-stone-800 rounded-xl px-3 py-1.5 pr-8 text-xs font-semibold text-stone-300 focus:outline-none cursor-pointer"
          >
            <option value="Day">Day</option>
            <option value="Week">Week</option>
            <option value="Month">Month</option>
          </select>
          <ChevronDown className="w-3.5 h-3.5 text-stone-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
        </div>
      </div>

      {/* Table Body */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-sans">
          <thead>
            <tr className="text-stone-400 font-medium border-b border-stone-800/60 pb-2">
              <th className="pb-2.5 font-medium">Type</th>
              <th className="pb-2.5 font-medium">Price</th>
              <th className="pb-2.5 font-medium">1h</th>
              <th className="pb-2.5 font-medium">24 Volume</th>
              <th className="pb-2.5 font-medium">Market Cap</th>
              <th className="pb-2.5 font-medium text-right">Last 7 Days</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-800/40">
            {assets.slice(0, 5).map((asset, idx) => {
              const isSelected = activeAsset.symbol === asset.symbol;
              const isPos = asset.change24h >= 0;
              const isBuySignal = idx % 2 === 0;

              return (
                <tr
                  key={asset.symbol}
                  onClick={() => onSelectAsset(asset)}
                  className={`hover:bg-stone-800/40 transition-colors cursor-pointer ${
                    isSelected ? 'bg-purple-500/10' : ''
                  }`}
                >
                  {/* Type / Crypto Name + Badge */}
                  <td className="py-3 pr-2">
                    <div className="flex items-center space-x-2.5">
                      <div className="w-7 h-7 rounded-full bg-stone-800 flex items-center justify-center font-bold text-xs text-stone-200 shrink-0">
                        {asset.symbol.substring(0, 1)}
                      </div>
                      <div>
                        <div className="font-bold text-stone-100 flex items-center space-x-1.5">
                          <span>{asset.name}</span>
                          <span className="text-stone-400 text-[10px] uppercase font-mono">{asset.symbol.split('/')[0]}</span>
                          <span
                            className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                              isBuySignal
                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            }`}
                          >
                            {isBuySignal ? 'BUY' : 'SELL'}
                          </span>
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Price */}
                  <td className="py-3 font-mono font-bold text-stone-200">
                    ${asset.price.toLocaleString(undefined, { minimumFractionDigits: asset.precision })}
                  </td>

                  {/* 1h % */}
                  <td className={`py-3 font-mono font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {isPos ? '+' : ''}{(asset.change24h / 2.5).toFixed(2)}%
                  </td>

                  {/* 24 Volume */}
                  <td className="py-3 font-mono text-stone-300">
                    ${(asset.volume24h * asset.price).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>

                  {/* Market Cap */}
                  <td className="py-3 font-mono text-stone-300">
                    ${(asset.price * 18500000).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>

                  {/* Last 7 Days Sparkline */}
                  <td className="py-3 text-right">
                    <div className="w-20 h-6 inline-block">
                      <svg viewBox="0 0 80 24" className="w-full h-full">
                        <path
                          d={asset.sparkline.reduce((acc, val, i) => {
                            const x = (i / (asset.sparkline.length - 1)) * 80;
                            const min = Math.min(...asset.sparkline);
                            const max = Math.max(...asset.sparkline);
                            const y = 22 - ((val - min) / (max - min || 1)) * 20;
                            return acc + `${i === 0 ? 'M' : 'L'} ${x} ${y} `;
                          }, '')}
                          fill="none"
                          stroke={isPos ? '#10b981' : '#f43f5e'}
                          strokeWidth="1.8"
                        />
                      </svg>
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
