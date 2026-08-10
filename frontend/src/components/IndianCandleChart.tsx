import React, { useState } from 'react';
import { NSEStock } from '../types/indianMarket';
import { IndianCandle, calculateEMA, calculateVWAP } from '../utils/indianTechnicalAnalysis';
import { Maximize2, Layers, TrendingUp, BarChart2, Eye, Activity } from 'lucide-react';

interface IndianCandleChartProps {
  stock: NSEStock;
  candles: IndianCandle[];
  timeframe: '1m' | '5m' | '15m' | '1h' | '1D';
  onTimeframeChange: (tf: '1m' | '5m' | '15m' | '1h' | '1D') => void;
}

export const IndianCandleChart: React.FC<IndianCandleChartProps> = ({
  stock,
  candles,
  timeframe,
  onTimeframeChange,
}) => {
  const [chartType, setChartType] = useState<'Candle' | 'Area'>('Candle');
  const [showEMA20, setShowEMA20] = useState(true);
  const [showEMA50, setShowEMA50] = useState(true);
  const [showVWAP, setShowVWAP] = useState(true);

  const closes = candles.map((c) => c.close);
  const ema20Values = calculateEMA(closes, 20);
  const ema50Values = calculateEMA(closes, 50);
  const currentVWAP = calculateVWAP(candles);

  const lastCandle = candles.length > 0 ? candles[candles.length - 1] : {
    open: stock.price,
    high: stock.price,
    low: stock.price,
    close: stock.price,
    volumeLakhs: 5.2,
  };

  const isPos = stock.change >= 0;

  // Chart coordinate calculations
  const minPrice = Math.min(...candles.map((c) => c.low)) * 0.998;
  const maxPrice = Math.max(...candles.map((c) => c.high)) * 1.002;
  const priceRange = maxPrice - minPrice || 1;

  const chartHeight = 280;
  const chartWidth = 800; // viewBox SVG scale width

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 flex flex-col justify-between h-full select-none">
      {/* Chart Top Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-stone-800/60">
        {/* Stock Title & Live Price */}
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center font-black text-amber-400 text-sm">
            ₹
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-black text-white text-sm font-mono tracking-wide">{stock.symbol}</span>
              <span className="text-[10px] text-stone-400 font-medium">{stock.name}</span>
            </div>
            <div className="flex items-center space-x-2 font-mono text-xs">
              <span className="font-extrabold text-white">
                ₹{stock.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className={`font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                {isPos ? '+' : ''}{stock.changePercent.toFixed(2)}%
              </span>
            </div>
          </div>
        </div>

        {/* OHLC Readout */}
        <div className="hidden md:flex items-center space-x-4 font-mono text-[11px] bg-[#14151b] px-3 py-1.5 rounded-xl border border-stone-800 text-stone-300">
          <div>O: <span className="text-white font-bold">₹{lastCandle.open.toFixed(2)}</span></div>
          <div>H: <span className="text-emerald-400 font-bold">₹{lastCandle.high.toFixed(2)}</span></div>
          <div>L: <span className="text-rose-400 font-bold">₹{lastCandle.low.toFixed(2)}</span></div>
          <div>C: <span className="text-white font-bold">₹{lastCandle.close.toFixed(2)}</span></div>
          <div>VWAP: <span className="text-amber-400 font-bold">₹{currentVWAP.toFixed(2)}</span></div>
        </div>

        {/* Chart Controls & Indicator Toggles */}
        <div className="flex items-center space-x-2">
          {/* Timeframe selector */}
          <div className="flex space-x-1 bg-[#14151b] p-1 rounded-xl border border-stone-800">
            {(['1m', '5m', '15m', '1h', '1D'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => onTimeframeChange(tf)}
                className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer ${
                  timeframe === tf ? 'bg-amber-500 text-stone-950 shadow-md' : 'text-stone-400 hover:text-stone-200'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Indicator Toggles */}
          <button
            onClick={() => setShowEMA20(!showEMA20)}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold border cursor-pointer ${
              showEMA20 ? 'bg-sky-500/20 text-sky-400 border-sky-500/30' : 'bg-[#14151b] text-stone-500 border-stone-800'
            }`}
          >
            EMA20
          </button>
          <button
            onClick={() => setShowEMA50(!showEMA50)}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold border cursor-pointer ${
              showEMA50 ? 'bg-purple-500/20 text-purple-400 border-purple-500/30' : 'bg-[#14151b] text-stone-500 border-stone-800'
            }`}
          >
            EMA50
          </button>
          <button
            onClick={() => setShowVWAP(!showVWAP)}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold border cursor-pointer ${
              showVWAP ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' : 'bg-[#14151b] text-stone-500 border-stone-800'
            }`}
          >
            VWAP
          </button>
        </div>
      </div>

      {/* Candlestick Canvas / SVG Chart View */}
      <div className="relative w-full h-[300px] my-2 bg-[#14151b] rounded-xl border border-stone-800/80 p-2 overflow-hidden">
        {/* Background Grid Lines */}
        <div className="absolute inset-0 flex flex-col justify-between pointer-events-none p-4 opacity-20">
          <div className="border-b border-stone-700 border-dashed w-full" />
          <div className="border-b border-stone-700 border-dashed w-full" />
          <div className="border-b border-stone-700 border-dashed w-full" />
          <div className="border-b border-stone-700 border-dashed w-full" />
        </div>

        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full h-full preserve-3d">
          {/* Render Volume Bars at the bottom */}
          {candles.map((c, idx) => {
            const x = (idx / (candles.length - 1 || 1)) * (chartWidth - 40) + 20;
            const volHeight = Math.min((c.volumeLakhs / 15) * 50, 50);
            const isBullish = c.close >= c.open;

            return (
              <rect
                key={`vol-${idx}`}
                x={x - 2}
                y={chartHeight - volHeight}
                width={4}
                height={volHeight}
                fill={isBullish ? 'rgba(16, 185, 129, 0.25)' : 'rgba(244, 63, 94, 0.25)'}
              />
            );
          })}

          {/* Render Candlesticks */}
          {candles.map((c, idx) => {
            const x = (idx / (candles.length - 1 || 1)) * (chartWidth - 40) + 20;
            const highY = chartHeight - 60 - ((c.high - minPrice) / priceRange) * (chartHeight - 80);
            const lowY = chartHeight - 60 - ((c.low - minPrice) / priceRange) * (chartHeight - 80);
            const openY = chartHeight - 60 - ((c.open - minPrice) / priceRange) * (chartHeight - 80);
            const closeY = chartHeight - 60 - ((c.close - minPrice) / priceRange) * (chartHeight - 80);

            const isBullish = c.close >= c.open;
            const bodyTop = Math.min(openY, closeY);
            const bodyHeight = Math.max(Math.abs(closeY - openY), 2);

            return (
              <g key={`candle-${idx}`}>
                {/* Wick */}
                <line
                  x1={x}
                  y1={highY}
                  x2={x}
                  y2={lowY}
                  stroke={isBullish ? '#10b981' : '#f43f5e'}
                  strokeWidth="1.2"
                />
                {/* Candle Body */}
                <rect
                  x={x - 3.5}
                  y={bodyTop}
                  width={7}
                  height={bodyHeight}
                  fill={isBullish ? '#10b981' : '#f43f5e'}
                  rx="1"
                />
              </g>
            );
          })}

          {/* EMA 20 Line Overlay */}
          {showEMA20 && (
            <path
              d={ema20Values.reduce((acc, val, i) => {
                const x = (i / (ema20Values.length - 1 || 1)) * (chartWidth - 40) + 20;
                const y = chartHeight - 60 - ((val - minPrice) / priceRange) * (chartHeight - 80);
                return acc + `${i === 0 ? 'M' : 'L'} ${x} ${y} `;
              }, '')}
              fill="none"
              stroke="#38bdf8"
              strokeWidth="1.8"
              strokeDasharray="4 2"
            />
          )}

          {/* EMA 50 Line Overlay */}
          {showEMA50 && (
            <path
              d={ema50Values.reduce((acc, val, i) => {
                const x = (i / (ema50Values.length - 1 || 1)) * (chartWidth - 40) + 20;
                const y = chartHeight - 60 - ((val - minPrice) / priceRange) * (chartHeight - 80);
                return acc + `${i === 0 ? 'M' : 'L'} ${x} ${y} `;
              }, '')}
              fill="none"
              stroke="#a855f7"
              strokeWidth="1.8"
            />
          )}

          {/* VWAP Horizontal Indicator */}
          {showVWAP && (
            <line
              x1="20"
              y1={chartHeight - 60 - ((currentVWAP - minPrice) / priceRange) * (chartHeight - 80)}
              x2={chartWidth - 20}
              y2={chartHeight - 60 - ((currentVWAP - minPrice) / priceRange) * (chartHeight - 80)}
              stroke="#f59e0b"
              strokeWidth="1.5"
              strokeDasharray="6 3"
            />
          )}
        </svg>

        {/* Live Price Tag Badge */}
        <div className="absolute right-3 top-4 bg-amber-500 text-stone-950 font-mono font-black text-xs px-2 py-1 rounded-lg shadow-lg">
          LIVE ₹{stock.price.toFixed(2)}
        </div>
      </div>

      {/* Bottom Technical Indicators Summary */}
      <div className="flex items-center justify-between text-[11px] font-mono text-stone-400 pt-1">
        <div className="flex items-center space-x-3">
          <span>RSI (14): <strong className="text-white">58.4 (Bullish)</strong></span>
          <span>MACD (12,26,9): <strong className="text-emerald-400">+4.20 Bullish Cross</strong></span>
        </div>
        <div className="flex items-center space-x-2 text-[10px] text-stone-500">
          <Activity className="w-3.5 h-3.5 text-amber-400" />
          <span>Real-time NSE Tick Engine</span>
        </div>
      </div>
    </div>
  );
};
