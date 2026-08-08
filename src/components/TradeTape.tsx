import React from 'react';
import { ExecutedTrade } from '../types/trading';

interface TradeTapeProps {
  trades: ExecutedTrade[];
  precision: number;
}

export const TradeTape: React.FC<TradeTapeProps> = ({ trades, precision }) => {
  return (
    <div className="bg-stone-900 border border-stone-800 rounded-xl p-3 flex flex-col h-full text-stone-200 select-none">
      <div className="flex items-center justify-between border-b border-stone-800 pb-2 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-stone-400">Market Trades</span>
        <span className="text-[10px] text-emerald-400 font-mono animate-pulse">● LIVE STREAM</span>
      </div>

      <div className="grid grid-cols-3 text-[10px] text-stone-500 uppercase pb-1 border-b border-stone-800/60 font-mono">
        <span>Price (USD)</span>
        <span className="text-right">Size</span>
        <span className="text-right">Time</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1 my-1 custom-scrollbar text-xs font-mono">
        {trades.map((trade) => {
          const isBuy = trade.side === 'Buy';
          return (
            <div
              key={trade.id}
              className="grid grid-cols-3 py-0.5 px-1 hover:bg-stone-800/50 rounded transition-colors"
            >
              <span className={`font-semibold ${isBuy ? 'text-emerald-400' : 'text-rose-400'}`}>
                ${trade.price.toFixed(precision)}
              </span>
              <span className="text-right text-stone-300">{trade.amount.toFixed(3)}</span>
              <span className="text-right text-stone-500 text-[11px]">{trade.time}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
