import React from 'react';
import { FIIDIINetFlow } from '../types/indianMarket';
import { Globe, Landmark, Clock, ShieldCheck } from 'lucide-react';
import { INITIAL_FII_DII_FLOWS } from '../data/indianMarketData';

interface FIIDIITrackerProps {
  flows?: FIIDIINetFlow[];
  flow?: FIIDIINetFlow;
}

export const FIIDIITracker: React.FC<FIIDIITrackerProps> = ({ flows, flow }) => {
  const latest = flow || (flows && flows[0]) || INITIAL_FII_DII_FLOWS[0] || {
    date: '10 Aug 2026',
    fiiCashNetCr: +1840.50,
    diiCashNetCr: +1210.80,
    fiiIndexFuturesCr: +680.20,
    fiiIndexOptionsCr: +3450.00,
  };

  const fiiCash = latest.fiiCashNetCr ?? 0;
  const diiCash = latest.diiCashNetCr ?? 0;
  const fiiFut = latest.fiiIndexFuturesCr ?? 0;
  const fiiOpt = latest.fiiIndexOptionsCr ?? 0;

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 select-none flex flex-col justify-between">
      <div className="flex items-center justify-between mb-3 border-b border-stone-800/60 pb-2">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold">
            <Globe className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-white">FII & DII Institutional Net Flows</h3>
            <span className="text-[10px] text-stone-400">Cash & Derivatives Positioning (₹ Crores)</span>
          </div>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 font-bold border border-sky-500/20">
            DAILY SETTLEMENT
          </span>
          <span className="text-[9px] text-stone-500 font-mono mt-0.5">SOURCE: NSE/NSDL</span>
        </div>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        {/* FII Cash Net */}
        <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800">
          <div className="flex items-center justify-between text-[10px] text-stone-400 mb-1">
            <span className="flex items-center space-x-1">
              <Globe className="w-3 h-3 text-sky-400" />
              <span>FII CASH NET</span>
            </span>
            <span className="font-mono text-[9px]">{latest.date || '10 Aug 2026'}</span>
          </div>
          <div className={`text-base font-black font-mono ${fiiCash >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {fiiCash >= 0 ? '+' : ''}₹{fiiCash.toLocaleString()} Cr
          </div>
          <div className="text-[9px] text-stone-500 mt-0.5">Updated: End of Day</div>
        </div>

        {/* DII Cash Net */}
        <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800">
          <div className="flex items-center justify-between text-[10px] text-stone-400 mb-1">
            <span className="flex items-center space-x-1">
              <Landmark className="w-3 h-3 text-purple-400" />
              <span>DII CASH NET</span>
            </span>
            <span className="font-mono text-[9px]">{latest.date || '10 Aug 2026'}</span>
          </div>
          <div className={`text-base font-black font-mono ${diiCash >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {diiCash >= 0 ? '+' : ''}₹{diiCash.toLocaleString()} Cr
          </div>
          <div className="text-[9px] text-stone-500 mt-0.5">Updated: End of Day</div>
        </div>
      </div>

      {/* FII F&O Derivatives Positioning */}
      <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800 space-y-2 text-xs font-mono">
        <div className="text-[10px] text-stone-400 font-sans uppercase font-bold border-b border-stone-800/80 pb-1 flex justify-between">
          <span>FII Derivatives F&O Segment</span>
          <span className="text-stone-500 font-normal">Official Clearing Data</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-stone-400">Index Futures Net:</span>
          <span className={`font-bold ${fiiFut >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {fiiFut >= 0 ? '+' : ''}₹{fiiFut.toLocaleString()} Cr
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-stone-400">Index Options Net:</span>
          <span className={`font-bold ${fiiOpt >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {fiiOpt >= 0 ? '+' : ''}₹{fiiOpt.toLocaleString()} Cr
          </span>
        </div>
      </div>
    </div>
  );
};
