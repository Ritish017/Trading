import React from 'react';
import { OptionChainSummary as OptionChainType } from '../types/indianMarket';
import { BarChart3 } from 'lucide-react';
import { INITIAL_OPTION_CHAIN } from '../data/indianMarketData';

interface OptionChainSummaryProps {
  optionSummary?: OptionChainType;
  optionChain?: OptionChainType;
  symbol?: string;
  price?: number;
}

export const OptionChainSummary: React.FC<OptionChainSummaryProps> = ({ optionSummary, optionChain, symbol, price }) => {
  const summary = optionSummary || optionChain || INITIAL_OPTION_CHAIN;
  
  const spotPrice = price ?? summary.spotPrice ?? 24580;
  const atmStrike = summary.atmStrike ?? Math.round(spotPrice / 50) * 50;
  const pcr = summary.pcr ?? 1.18;
  const maxPainStrike = summary.maxPainStrike ?? atmStrike - 50;
  const totalCallOI = summary.totalCallOI ?? 4820000;
  const totalPutOI = summary.totalPutOI ?? 5680000;
  const impliedVolatility = summary.impliedVolatility ?? 13.4;
  const expiryDate = summary.expiryDate || 'NEAR';
  const sym = symbol || summary.symbol || 'NIFTY';
  const source = (summary as any).source || 'UPSTOX';

  // PCR Signal interpretation
  let pcrSignal = 'Neutral';
  let pcrColor = 'text-amber-400 bg-amber-500/10 border-amber-500/30';
  if (pcr > 1.2) {
    pcrSignal = 'Strong Bullish (Put Writing)';
    pcrColor = 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
  } else if (pcr < 0.8) {
    pcrSignal = 'Bearish (Call Writing)';
    pcrColor = 'text-rose-400 bg-rose-500/10 border-rose-500/30';
  }

  const callOIFmt = (totalCallOI / 100000).toFixed(1);
  const putOIFmt = (totalPutOI / 100000).toFixed(1);
  const totalOI = (totalPutOI + totalCallOI) || 1;

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 select-none flex flex-col justify-between">
      <div className="flex items-center justify-between mb-3 border-b border-stone-800/60 pb-2">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold">
            <BarChart3 className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <h3 className="text-xs font-bold text-white">{sym} Option Chain Analytics</h3>
              <span className="px-1.5 py-0.2 rounded text-[8px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {source}
              </span>
            </div>
            <span className="text-[10px] text-stone-400">Expiry: {expiryDate}</span>
          </div>
        </div>
        <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold border ${pcrColor}`}>
          PCR {pcr} • {pcrSignal}
        </span>
      </div>

      {/* Grid Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3 text-xs font-mono">
        <div className="bg-[#14151b] p-2.5 rounded-xl border border-stone-800">
          <div className="text-[10px] text-stone-400">Spot Price</div>
          <div className="font-extrabold text-white">₹{spotPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>
        <div className="bg-[#14151b] p-2.5 rounded-xl border border-stone-800">
          <div className="text-[10px] text-stone-400">ATM Strike</div>
          <div className="font-extrabold text-amber-400">₹{atmStrike}</div>
        </div>
        <div className="bg-[#14151b] p-2.5 rounded-xl border border-stone-800">
          <div className="text-[10px] text-stone-400">Max Pain Strike</div>
          <div className="font-extrabold text-sky-400">₹{maxPainStrike}</div>
        </div>
        <div className="bg-[#14151b] p-2.5 rounded-xl border border-stone-800">
          <div className="text-[10px] text-stone-400">Implied Volatility</div>
          <div className="font-extrabold text-purple-400">{impliedVolatility}% IV</div>
        </div>
      </div>

      {/* Put vs Call Open Interest Bar */}
      <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800 space-y-1.5">
        <div className="flex justify-between text-[10px] font-mono font-bold">
          <span className="text-emerald-400">Put OI: {putOIFmt} Lakhs</span>
          <span className="text-rose-400">Call OI: {callOIFmt} Lakhs</span>
        </div>
        <div className="w-full bg-stone-800 h-2 rounded-full overflow-hidden flex">
          <div
            className="bg-emerald-500 h-full"
            style={{ width: `${(totalPutOI / totalOI) * 100}%` }}
          />
          <div
            className="bg-rose-500 h-full"
            style={{ width: `${(totalCallOI / totalOI) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
};
