import React from 'react';
import { OptionChainSummary as OptionChainType } from '../types/indianMarket';
import { BarChart3, ShieldAlert, Zap } from 'lucide-react';

interface OptionChainSummaryProps {
  optionSummary: OptionChainType;
}

export const OptionChainSummary: React.FC<OptionChainSummaryProps> = ({ optionSummary }) => {
  const { spotPrice, atmStrike, pcr, maxPainStrike, totalCallOI, totalPutOI, impliedVolatility, expiryDate } = optionSummary;

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

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 select-none flex flex-col justify-between">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold">
            <BarChart3 className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-white">NIFTY Option Chain Analytics</h3>
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
          <div className="font-extrabold text-white">₹{spotPrice.toLocaleString()}</div>
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
          <span className="text-emerald-400">Put OI: {totalPutOI} Lakhs</span>
          <span className="text-rose-400">Call OI: {totalCallOI} Lakhs</span>
        </div>
        <div className="w-full bg-stone-800 h-2 rounded-full overflow-hidden flex">
          <div
            className="bg-emerald-500 h-full"
            style={{ width: `${(totalPutOI / (totalPutOI + totalCallOI)) * 100}%` }}
          />
          <div
            className="bg-rose-500 h-full"
            style={{ width: `${(totalCallOI / (totalPutOI + totalCallOI)) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
};
