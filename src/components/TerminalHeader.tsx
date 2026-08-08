import React, { useState } from 'react';
import { Search, Sparkles, Building2, Bell, RefreshCw, BarChart2, ShieldCheck } from 'lucide-react';
import { FIIDIINetFlow, MarketBreadth } from '../types/indianMarket';

interface TerminalHeaderProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  fiiDiiFlow: FIIDIINetFlow;
  breadth: MarketBreadth;
  onOpenAIIntelligence: () => void;
  onOpenPaperTrading: () => void;
}

export const TerminalHeader: React.FC<TerminalHeaderProps> = ({
  searchQuery,
  onSearchChange,
  fiiDiiFlow,
  breadth,
  onOpenAIIntelligence,
  onOpenPaperTrading,
}) => {
  const [showNotifications, setShowNotifications] = useState(false);

  return (
    <header className="bg-[#14151b] border-b border-stone-800/80 px-5 py-3 flex flex-wrap items-center justify-between gap-4 select-none shrink-0">
      {/* Brand & Market Session Status */}
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 via-orange-500 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-orange-500/20 font-black">
          <Building2 className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-extrabold text-lg text-white tracking-tight">
              Apex<span className="text-orange-400">NSE</span>
            </span>
            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">
              MARKET INTEL V2.5
            </span>
          </div>
          <p className="text-[10px] text-stone-400 font-medium flex items-center space-x-1.5">
            <ShieldCheck className="w-3 h-3 text-emerald-400" />
            <span>NSE/BSE Data Engine • IST Market Hours (09:15 - 15:30)</span>
          </p>
        </div>
      </div>

      {/* Institutional FII/DII Net Flow Bar */}
      <div className="hidden lg:flex items-center space-x-3 bg-[#1c1e27] border border-stone-800/80 px-3.5 py-1.5 rounded-xl text-xs font-mono">
        <div className="flex flex-col">
          <span className="text-[9px] text-stone-400 font-sans uppercase">FII Net Cash</span>
          <span className={`font-bold ${fiiDiiFlow.fiiCashNetCr >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {fiiDiiFlow.fiiCashNetCr >= 0 ? '+' : ''}₹{fiiDiiFlow.fiiCashNetCr.toLocaleString()} Cr
          </span>
        </div>
        <div className="h-6 w-px bg-stone-800" />
        <div className="flex flex-col">
          <span className="text-[9px] text-stone-400 font-sans uppercase">DII Net Cash</span>
          <span className={`font-bold ${fiiDiiFlow.diiCashNetCr >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {fiiDiiFlow.diiCashNetCr >= 0 ? '+' : ''}₹{fiiDiiFlow.diiCashNetCr.toLocaleString()} Cr
          </span>
        </div>
        <div className="h-6 w-px bg-stone-800" />
        <div className="flex flex-col">
          <span className="text-[9px] text-stone-400 font-sans uppercase">Advance / Decline</span>
          <span className="font-bold text-sky-400">
            {breadth.advances} A : {breadth.declines} D ({breadth.ratio}x)
          </span>
        </div>
      </div>

      {/* Search Input for NSE/BSE Tickers */}
      <div className="relative w-64 xl:w-80">
        <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search NSE/BSE Stock (e.g. RELIANCE, TCS, HDFC)..."
          className="w-full bg-[#1c1e27] border border-stone-800/80 rounded-xl pl-9 pr-4 py-2 text-xs font-medium text-stone-200 placeholder-stone-500 focus:outline-none focus:border-amber-500/50 transition-all"
        />
      </div>

      {/* Right Action Buttons */}
      <div className="flex items-center space-x-3">
        {/* Gemini AI Intelligence Desk Button */}
        <button
          onClick={onOpenAIIntelligence}
          className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-gradient-to-r from-orange-500 via-amber-500 to-indigo-600 hover:from-orange-600 hover:to-indigo-700 text-white font-bold text-xs shadow-lg shadow-orange-500/20 cursor-pointer transition-all transform active:scale-95"
        >
          <Sparkles className="w-4 h-4 animate-pulse text-amber-200" />
          <span>Gemini AI Market Intel</span>
        </button>

        {/* Paper Order Terminal Button */}
        <button
          onClick={onOpenPaperTrading}
          className="flex items-center space-x-2 px-3 py-2 rounded-xl bg-[#1c1e27] border border-stone-800/80 hover:border-amber-500/40 text-stone-200 hover:text-white font-bold text-xs transition-all cursor-pointer"
        >
          <BarChart2 className="w-4 h-4 text-amber-400" />
          <span>Paper Order Terminal</span>
        </button>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="p-2 bg-[#1c1e27] border border-stone-800/80 rounded-xl text-stone-300 hover:text-white transition-colors cursor-pointer"
          >
            <Bell className="w-4 h-4" />
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-72 bg-[#1c1e27] border border-stone-800 rounded-xl shadow-2xl p-3 z-50 text-xs">
              <div className="font-bold text-white mb-2 pb-1 border-b border-stone-800">SEBI & NSE Market Alerts</div>
              <div className="space-y-2 text-[11px] text-stone-300">
                <div className="p-2 bg-[#14151b] rounded-lg border border-stone-800">
                  <div className="font-semibold text-amber-400">NIFTY 50 Breakout</div>
                  <div>NIFTY crossed 24,550 resistance zone supported by banking rally.</div>
                </div>
                <div className="p-2 bg-[#14151b] rounded-lg border border-stone-800">
                  <div className="font-semibold text-emerald-400">FII Institutional Buying</div>
                  <div>FII cash net purchases exceeded ₹1,800 Cr in early market session.</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
