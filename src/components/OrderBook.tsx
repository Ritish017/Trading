import React, { useState } from 'react';
import { OrderBook as OrderBookType } from '../types/trading';
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';

interface OrderBookProps {
  orderBook: OrderBookType;
  precision: number;
  onPriceClick?: (price: number) => void;
}

export const OrderBook: React.FC<OrderBookProps> = ({
  orderBook,
  precision,
  onPriceClick,
}) => {
  const [viewMode, setViewMode] = useState<'book' | 'depth'>('book');

  // Max total volume for depth bar calculations
  const maxBidTotal = orderBook.bids[orderBook.bids.length - 1]?.total || 1;
  const maxAskTotal = orderBook.asks[orderBook.asks.length - 1]?.total || 1;
  const maxTotal = Math.max(maxBidTotal, maxAskTotal);

  // Prepare data for Depth Chart view
  const depthChartData = [
    ...orderBook.bids
      .slice()
      .reverse()
      .map((b) => ({
        price: b.price,
        bids: b.total,
        asks: null,
      })),
    ...orderBook.asks.map((a) => ({
      price: a.price,
      bids: null,
      asks: a.total,
    })),
  ];

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-xl p-3 flex flex-col h-full text-stone-200 select-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-stone-800 pb-2 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-stone-400">Order Book</span>
        <div className="flex bg-stone-950 p-0.5 rounded border border-stone-800 text-[11px] font-mono">
          <button
            onClick={() => setViewMode('book')}
            className={`px-2 py-0.5 rounded transition-colors ${
              viewMode === 'book' ? 'bg-stone-700 text-white font-bold' : 'text-stone-400 hover:text-stone-200'
            }`}
          >
            List
          </button>
          <button
            onClick={() => setViewMode('depth')}
            className={`px-2 py-0.5 rounded transition-colors ${
              viewMode === 'depth' ? 'bg-stone-700 text-white font-bold' : 'text-stone-400 hover:text-stone-200'
            }`}
          >
            Depth
          </button>
        </div>
      </div>

      {viewMode === 'book' ? (
        <div className="flex-1 flex flex-col justify-between text-xs font-mono overflow-hidden">
          {/* Table Headings */}
          <div className="grid grid-cols-3 text-[10px] text-stone-500 uppercase pb-1 border-b border-stone-800/60">
            <span>Price (USD)</span>
            <span className="text-right">Size</span>
            <span className="text-right">Total</span>
          </div>

          {/* Asks (Sell Orders - Red) */}
          <div className="flex-1 overflow-y-auto space-y-0.5 my-1 custom-scrollbar">
            {orderBook.asks.slice().reverse().map((ask, i) => {
              const depthPercent = Math.min((ask.total / maxTotal) * 100, 100);
              return (
                <div
                  key={`ask-${i}`}
                  onClick={() => onPriceClick && onPriceClick(ask.price)}
                  className="relative grid grid-cols-3 py-0.5 px-1 hover:bg-stone-800/80 cursor-pointer rounded transition-colors"
                >
                  {/* Depth Background Bar */}
                  <div
                    className="absolute right-0 top-0 bottom-0 bg-rose-500/15 rounded-r"
                    style={{ width: `${depthPercent}%` }}
                  />
                  <span className="text-rose-400 font-semibold relative z-10">${ask.price.toFixed(precision)}</span>
                  <span className="text-right text-stone-300 relative z-10">{ask.amount.toFixed(3)}</span>
                  <span className="text-right text-stone-500 relative z-10">{ask.total.toFixed(2)}</span>
                </div>
              );
            })}
          </div>

          {/* Spread Indicator */}
          <div className="bg-stone-950 py-1.5 px-2 rounded my-1 border border-stone-800/80 flex items-center justify-between text-[11px]">
            <span className="text-stone-400 font-sans">Spread:</span>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-stone-100">${orderBook.spread.toFixed(precision)}</span>
              <span className="text-[10px] text-stone-500">({orderBook.spreadPercent}%)</span>
            </div>
          </div>

          {/* Bids (Buy Orders - Green) */}
          <div className="flex-1 overflow-y-auto space-y-0.5 my-1 custom-scrollbar">
            {orderBook.bids.map((bid, i) => {
              const depthPercent = Math.min((bid.total / maxTotal) * 100, 100);
              return (
                <div
                  key={`bid-${i}`}
                  onClick={() => onPriceClick && onPriceClick(bid.price)}
                  className="relative grid grid-cols-3 py-0.5 px-1 hover:bg-stone-800/80 cursor-pointer rounded transition-colors"
                >
                  {/* Depth Background Bar */}
                  <div
                    className="absolute right-0 top-0 bottom-0 bg-emerald-500/15 rounded-r"
                    style={{ width: `${depthPercent}%` }}
                  />
                  <span className="text-emerald-400 font-semibold relative z-10">${bid.price.toFixed(precision)}</span>
                  <span className="text-right text-stone-300 relative z-10">{bid.amount.toFixed(3)}</span>
                  <span className="text-right text-stone-500 relative z-10">{bid.total.toFixed(2)}</span>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        /* Depth Visualizer Chart */
        <div className="flex-1 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={depthChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <XAxis dataKey="price" stroke="#52525b" fontSize={10} tickFormatter={(val) => `$${val}`} />
              <YAxis stroke="#52525b" fontSize={10} />
              <Tooltip
                contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', borderRadius: '8px', fontSize: '11px' }}
                itemStyle={{ color: '#e7e5e4' }}
              />
              <Area type="stepAfter" dataKey="bids" stroke="#10b981" fill="#10b981" fillOpacity={0.3} />
              <Area type="stepBefore" dataKey="asks" stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.3} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
