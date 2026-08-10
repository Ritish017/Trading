import React from 'react';
import { 
  TrendingUp, 
  Sparkles, 
  RotateCcw, 
  Activity, 
  Pause, 
  Play, 
  Wallet,
  Globe,
  Bell
} from 'lucide-react';
import { Asset } from '../types/trading';

interface NavbarProps {
  activeAsset: Asset;
  assets: Asset[];
  onSelectAsset: (asset: Asset) => void;
  balance: number;
  equity: number;
  usedMargin: number;
  unrealizedPnL: number;
  isLiveUpdating: boolean;
  onToggleLive: () => void;
  onOpenDepositModal: () => void;
  onOpenAIAnalyst: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeAsset,
  assets,
  onSelectAsset,
  balance,
  equity,
  usedMargin,
  unrealizedPnL,
  isLiveUpdating,
  onToggleLive,
  onOpenDepositModal,
  onOpenAIAnalyst,
}) => {
  const pnlIsPositive = unrealizedPnL >= 0;

  return (
    <header className="bg-stone-900 border-b border-stone-800 text-stone-100 sticky top-0 z-30 select-none">
      {/* Top Ticker Tape */}
      <div className="bg-stone-950 border-b border-stone-800/80 px-4 py-1 text-xs overflow-x-auto no-scrollbar flex items-center space-x-6">
        <div className="flex items-center space-x-1.5 text-stone-400 shrink-0 font-mono text-[11px]">
          <Activity className="w-3 h-3 text-emerald-400 animate-pulse" />
          <span>MARKETS LIVE</span>
        </div>
        <div className="flex items-center space-x-6 shrink-0">
          {assets.slice(0, 6).map((asset) => {
            const isPos = asset.change24h >= 0;
            return (
              <button
                key={asset.symbol}
                onClick={() => onSelectAsset(asset)}
                className={`flex items-center space-x-2 text-[11px] font-mono transition-colors hover:opacity-80 ${
                  activeAsset.symbol === asset.symbol ? 'text-amber-400 font-bold' : 'text-stone-300'
                }`}
              >
                <span>{asset.symbol}</span>
                <span className="text-stone-200">${asset.price.toLocaleString(undefined, { minimumFractionDigits: asset.precision })}</span>
                <span className={isPos ? 'text-emerald-400' : 'text-rose-400'}>
                  {isPos ? '+' : ''}{asset.change24h}%
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Header Nav */}
      <div className="max-w-[1800px] mx-auto px-4 h-14 flex items-center justify-between gap-4">
        {/* Left: Brand & Active Pair Quick Switcher */}
        <div className="flex items-center space-x-4 shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-black tracking-widest text-sm">
              <TrendingUp className="w-4 h-4" />
            </div>
            <div>
              <span className="font-bold tracking-tight text-white text-base leading-none block">
                APEX<span className="text-emerald-400">TRADER</span>
              </span>
              <span className="text-[10px] text-stone-400 tracking-wider font-mono">PRO STATION</span>
            </div>
          </div>

          <div className="h-6 w-px bg-stone-800 hidden sm:block" />

          {/* Active Asset Badge */}
          <div className="hidden sm:flex items-center space-x-3 bg-stone-800/80 border border-stone-700/60 rounded-lg px-3 py-1">
            <span className="font-bold text-sm text-stone-100">{activeAsset.symbol}</span>
            <span className="text-xs text-stone-400 font-medium hidden md:inline">{activeAsset.name}</span>
            <span className="text-sm font-mono font-semibold text-white">
              ${activeAsset.price.toLocaleString(undefined, { minimumFractionDigits: activeAsset.precision })}
            </span>
            <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
              activeAsset.change24h >= 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
            }`}>
              {activeAsset.change24h >= 0 ? '+' : ''}{activeAsset.change24h}%
            </span>
          </div>
        </div>

        {/* Center/Right: Account Stats & Controls */}
        <div className="flex items-center space-x-3">
          {/* AI Market Assistant Button */}
          <button
            onClick={onOpenAIAnalyst}
            className="flex items-center space-x-1.5 bg-gradient-to-r from-emerald-600/30 via-stone-800 to-indigo-600/30 hover:from-emerald-600/40 hover:to-indigo-600/40 border border-emerald-500/40 text-stone-100 rounded-lg px-3 py-1.5 text-xs font-medium transition-all shadow-xs active:scale-95 cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-emerald-400 animate-spin-slow" />
            <span className="hidden md:inline">AI Technical Analyst</span>
            <span className="md:hidden">AI Signals</span>
          </button>

          {/* Live Update Ticker Toggle */}
          <button
            onClick={onToggleLive}
            title={isLiveUpdating ? "Pause Live Prices" : "Resume Live Prices"}
            className={`p-1.5 rounded-lg border text-xs flex items-center space-x-1.5 transition-colors ${
              isLiveUpdating 
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
                : 'bg-stone-800 border-stone-700 text-stone-400'
            }`}
          >
            {isLiveUpdating ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span className="hidden lg:inline text-[11px] font-mono">{isLiveUpdating ? 'LIVE' : 'PAUSED'}</span>
          </button>

          {/* Portfolio Metrics Widget */}
          <div className="flex items-center space-x-4 bg-stone-950 border border-stone-800 rounded-lg px-3 py-1 text-xs font-mono">
            <div>
              <div className="text-[10px] text-stone-500 font-sans">Account Equity</div>
              <div className="font-semibold text-white">${equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
            </div>
            <div className="hidden lg:block border-l border-stone-800 pl-3">
              <div className="text-[10px] text-stone-500 font-sans">Unrealized PnL</div>
              <div className={`font-semibold ${pnlIsPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                {pnlIsPositive ? '+' : ''}${unrealizedPnL.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
          </div>

          {/* Deposit / Reset Demo Funds */}
          <button
            onClick={onOpenDepositModal}
            className="flex items-center space-x-1.5 bg-stone-800 hover:bg-stone-700 border border-stone-700 text-stone-200 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors cursor-pointer"
            title="Manage Demo Capital"
          >
            <Wallet className="w-3.5 h-3.5 text-amber-400" />
            <span className="hidden sm:inline">Paper Capital</span>
          </button>
        </div>
      </div>
    </header>
  );
};
