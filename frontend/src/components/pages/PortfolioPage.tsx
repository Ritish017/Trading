import React from 'react';
import { PaperPosition, NSEStock } from '../../types/indianMarket';
import { Briefcase, TrendingUp, TrendingDown, DollarSign, PlusCircle, ArrowUpRight, ArrowDownRight, Trash2 } from 'lucide-react';

interface PortfolioPageProps {
  balance: number;
  positions: PaperPosition[];
  stocks: NSEStock[];
  onOpenOrderModal: () => void;
  onClosePosition: (id: string, closePrice?: number) => void;
}

export const PortfolioPage: React.FC<PortfolioPageProps> = ({
  balance,
  positions = [],
  stocks,
  onOpenOrderModal,
  onClosePosition,
}) => {
  const totalInvested = positions.reduce((acc, p) => acc + (p.quantity * p.entryPrice), 0);
  const totalCurrent = positions.reduce((acc, p) => acc + (p.quantity * p.currentPrice), 0);
  const totalPnL = positions.reduce((acc, p) => acc + p.unrealizedPnL, 0);
  const totalPnLPct = totalInvested > 0 ? (totalPnL / totalInvested) * 100 : 0;
  const portfolioEquity = balance + totalCurrent;

  return (
    <div className="flex-1 p-3 flex flex-col space-y-3 h-[calc(100vh-175px)] overflow-y-auto custom-scrollbar">
      {/* Portfolio Overview KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-mono text-stone-400">Total Portfolio Value</span>
            <div className="text-lg font-black font-mono text-white">
              ₹{portfolioEquity.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
            <Briefcase className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-mono text-stone-400">Available Paper Margin</span>
            <div className="text-lg font-black font-mono text-stone-200">
              ₹{balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400">
            <DollarSign className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-mono text-stone-400">Total Unrealized P&L</span>
            <div className={`text-lg font-black font-mono flex items-center space-x-1 ${totalPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {totalPnL >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
              <span>{totalPnL >= 0 ? '+' : ''}₹{totalPnL.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
            </div>
          </div>
          <div className={`p-2.5 rounded-xl border ${totalPnL >= 0 ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-rose-500/10 border-rose-500/30 text-rose-400'}`}>
            {totalPnL >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
          </div>
        </div>

        <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-mono text-stone-400">Return on Capital</span>
            <div className={`text-lg font-black font-mono ${totalPnLPct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {totalPnLPct >= 0 ? '+' : ''}{totalPnLPct.toFixed(2)}%
            </div>
          </div>
          <button
            onClick={onOpenOrderModal}
            className="flex items-center space-x-1 px-3 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold font-mono text-xs shadow-md cursor-pointer transition-all active:scale-95"
          >
            <PlusCircle className="w-4 h-4" />
            <span>New Order</span>
          </button>
        </div>
      </div>

      {/* Positions Table Card */}
      <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 flex-1 flex flex-col min-h-[350px]">
        <div className="flex items-center justify-between pb-3 mb-3 border-b border-stone-800/60">
          <div className="flex items-center space-x-2">
            <span className="font-extrabold text-sm text-white font-mono uppercase">Open Positions</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">
              {positions.length} Active
            </span>
          </div>
        </div>

        {positions.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-3">
            <Briefcase className="w-10 h-10 text-stone-600" />
            <p className="text-xs text-stone-400 font-mono">No active paper trading positions.</p>
            <button
              onClick={onOpenOrderModal}
              className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold font-mono text-xs cursor-pointer shadow-md"
            >
              Place Your First Paper Trade
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto custom-scrollbar flex-1">
            <table className="w-full text-left text-xs font-mono border-collapse min-w-[700px]">
              <thead>
                <tr className="text-stone-400 border-b border-stone-800/60 pb-2">
                  <th className="pb-2 font-medium">Symbol</th>
                  <th className="pb-2 font-medium">Type</th>
                  <th className="pb-2 font-medium">Qty</th>
                  <th className="pb-2 font-medium">Entry Price</th>
                  <th className="pb-2 font-medium">LTP</th>
                  <th className="pb-2 font-medium">Invested</th>
                  <th className="pb-2 font-medium">Current</th>
                  <th className="pb-2 font-medium">P&L (₹)</th>
                  <th className="pb-2 font-medium">P&L (%)</th>
                  <th className="pb-2 font-medium text-right pr-2">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-800/40">
                {positions.map((pos) => {
                  const isPos = pos.unrealizedPnL >= 0;
                  return (
                    <tr key={pos.id} className="hover:bg-stone-800/40 transition-colors">
                      <td className="py-3 font-bold text-white">{pos.symbol.split('.')[0]}</td>
                      <td className="py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          pos.type === 'BUY' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                        }`}>
                          {pos.type}
                        </span>
                      </td>
                      <td className="py-3 text-stone-200">{pos.quantity}</td>
                      <td className="py-3 text-stone-300">₹{pos.entryPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                      <td className="py-3 text-stone-100 font-bold">₹{pos.currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                      <td className="py-3 text-stone-300">₹{(pos.quantity * pos.entryPrice).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                      <td className="py-3 text-stone-300">₹{(pos.quantity * pos.currentPrice).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                      <td className={`py-3 font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isPos ? '+' : ''}₹{pos.unrealizedPnL.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className={`py-3 font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isPos ? '+' : ''}{pos.unrealizedPnLPercent.toFixed(2)}%
                      </td>
                      <td className="py-3 text-right pr-2">
                        <button
                          onClick={() => onClosePosition(pos.id, pos.currentPrice)}
                          className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[11px] font-bold cursor-pointer transition-colors"
                        >
                          Close
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
