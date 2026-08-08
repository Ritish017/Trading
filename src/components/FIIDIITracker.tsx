import React from 'react';
import { FIIDIINetFlow } from '../types/indianMarket';
import { ArrowUpRight, ArrowDownRight, Globe, Landmark, Activity } from 'lucide-react';

interface FIIDIITrackerProps {
  flows: FIIDIINetFlow[];
}

export const FIIDIITracker: React.FC<FIIDIITrackerProps> = ({ flows }) => {
  const latest = flows[0] || {
    fiiCashNetCr: +1840.50,
    diiCashNetCr: +1210.80,
    fiiIndexFuturesCr: +680.20,
    fiiIndexOptionsCr: +3450.00,
  };

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 select-none flex flex-col justify-between">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold">
            <Globe className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-white">FII & DII Institutional Net Flows</h3>
            <span className="text-[10px] text-stone-400">Cash & Derivatives Positioning (₹ Crores)</span>
          </div>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20">
          Net Inflow Trend
        </span>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        {/* FII Cash Net */}
        <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800">
          <div className="flex items-center justify-between text-[10px] text-stone-400 mb-1">
            <span className="flex items-center space-x-1">
              <Globe className="w-3 h-3 text-sky-400" />
              <span>FII Cash Net</span>
            </span>
            <span className="font-mono">{latest.date}</span>
          </div>
          <div className={`text-base font-black font-mono ${latest.fiiCashNetCr >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {latest.fiiCashNetCr >= 0 ? '+' : ''}₹{latest.fiiCashNetCr.toLocaleString()} Cr
          </div>
        </div>

        {/* DII Cash Net */}
        <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800">
          <div className="flex items-center justify-between text-[10px] text-stone-400 mb-1">
            <span className="flex items-center space-x-1">
              <Landmark className="w-3 h-3 text-purple-400" />
              <span>DII Cash Net</span>
            </span>
            <span className="font-mono">{latest.date}</span>
          </div>
          <div className={`text-base font-black font-mono ${latest.diiCashNetCr >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {latest.diiCashNetCr >= 0 ? '+' : ''}₹{latest.diiCashNetCr.toLocaleString()} Cr
          </div>
        </div>
      </div>

      {/* FII F&O Derivatives Positioning */}
      <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800 space-y-2 text-xs font-mono">
        <div className="text-[10px] text-stone-400 font-sans uppercase font-bold border-b border-stone-800/80 pb-1">
          FII Derivatives F&O Segment
        </div>
        <div className="flex justify-between items-center">
          <span className="text-stone-400">Index Futures Net:</span>
          <span className={`font-bold ${latest.fiiIndexFuturesCr >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {latest.fiiIndexFuturesCr >= 0 ? '+' : ''}₹{latest.fiiIndexFuturesCr} Cr
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-stone-400">Index Options Net:</span>
          <span className={`font-bold ${latest.fiiIndexOptionsCr >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {latest.fiiIndexOptionsCr >= 0 ? '+' : ''}₹{latest.fiiIndexOptionsCr} Cr
          </span>
        </div>
      </div>
    </div>
  );
};
