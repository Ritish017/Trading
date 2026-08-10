import React, { useState } from 'react';
import { NSEStock } from '../types/indianMarket';
import { IndianCandle, calculateEMA, calculateVWAP } from '../utils/indianTechnicalAnalysis';
import { Maximize2, Layers, TrendingUp, BarChart2, Eye, Activity } from 'lucide-react';

interface IndianCandleChartProps {
  stock?: NSEStock;
  symbol?: string;
  name?: string;
  price?: number;
  change?: number;
  changePercent?: number;
  candles?: IndianCandle[];
  timeframe: '1m' | '5m' | '15m' | '1h' | '1D';
  onTimeframeChange: (tf: '1m' | '5m' | '15m' | '1h' | '1D') => void;
}

export const IndianCandleChart: React.FC<IndianCandleChartProps> = ({
  stock,
  symbol,
  name,
  price,
  change,
  changePercent,
  candles = [],
  timeframe,
  onTimeframeChange,
}) => {
  const [showEMA20, setShowEMA20] = useState(true);
  const [showEMA50, setShowEMA50] = useState(true);
  const [showVWAP, setShowVWAP] = useState(true);

  const sym = symbol || stock?.symbol || 'RELIANCE.NS';
  const stName = name || stock?.name || 'Reliance Industries';
  const currentPrice = price ?? stock?.price ?? 2845.5;
  const currentChange = change ?? stock?.change ?? 0;
  const currentChangePct = changePercent ?? stock?.changePercent ?? 0;
  const isPos = currentChange >= 0;

  // Strict Candle Validation Rules
  const validCandles = (candles || []).filter((c) => {
    if (!c || typeof c.open !== 'number' || typeof c.close !== 'number') return false;
    const maxOC = Math.max(c.open, c.close);
    const minOC = Math.min(c.open, c.close);
    return c.high >= maxOC && c.low <= minOC && (c.volume || 0) >= 0;
  });

  const candleList = validCandles;
  const closes = candleList.map((c) => c.close);
  const ema20Values = calculateEMA(closes, 20);
  const ema50Values = calculateEMA(closes, 50);
  const currentVWAP = calculateVWAP(candleList);

  const lastCandle = candleList.length > 0 ? candleList[candleList.length - 1] : {
    open: currentPrice,
    high: currentPrice,
    low: currentPrice,
    close: currentPrice,
    volume: 5000,
  };

  // Chart coordinate calculations
  const minPrice = candleList.length > 0 ? Math.min(...candleList.map((c) => c.low)) * 0.998 : currentPrice * 0.98;
  const maxPrice = candleList.length > 0 ? Math.max(...candleList.map((c) => c.high)) * 1.002 : currentPrice * 1.02;
  const priceRange = maxPrice - minPrice || 1;

  const chartHeight = 280;
  const chartWidth = 800; // viewBox SVG scale width

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 flex flex-col justify-between h-full select-none">
      {/* Chart Top Header & Compact Metric Cards */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-stone-800/60">
        {/* Stock Title & Live Price */}
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center font-black text-amber-400 text-sm">
            ₹
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-black text-white text-sm font-mono tracking-wide">{sym}</span>
              <span className="text-[10px] text-stone-400 font-medium">{stName}</span>
            </div>
            <div className="flex items-center space-x-2 font-mono text-xs">
              <span className="font-extrabold text-white">
                ₹{currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className={`font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                {isPos ? '+' : ''}{currentChange.toFixed(2)} ({isPos ? '+' : ''}{currentChangePct.toFixed(2)}%)
              </span>
            </div>
          </div>
        </div>

        {/* Compact OHLC Metric Cards */}
        <div className="flex items-center space-x-2 font-mono text-[10px]">
          <div className="bg-[#14151b] border border-stone-800 px-2.5 py-1 rounded-xl flex flex-col items-center">
            <span className="text-stone-500 uppercase text-[8px] font-sans">Open</span>
            <span className="font-bold text-stone-200">₹{lastCandle.open.toFixed(2)}</span>
          </div>

          <div className="bg-[#14151b] border border-stone-800 px-2.5 py-1 rounded-xl flex flex-col items-center">
            <span className="text-stone-500 uppercase text-[8px] font-sans">High</span>
            <span className="font-bold text-emerald-400">₹{lastCandle.high.toFixed(2)}</span>
          </div>

          <div className="bg-[#14151b] border border-stone-800 px-2.5 py-1 rounded-xl flex flex-col items-center">
            <span className="text-stone-500 uppercase text-[8px] font-sans">Low</span>
            <span className="font-bold text-rose-400">₹{lastCandle.low.toFixed(2)}</span>
          </div>

          <div className="bg-[#14151b] border border-stone-800 px-2.5 py-1 rounded-xl flex flex-col items-center">
            <span className="text-stone-500 uppercase text-[8px] font-sans">Close</span>
            <span className="font-bold text-stone-200">₹{lastCandle.close.toFixed(2)}</span>
          </div>

          <div className="bg-[#14151b] border border-stone-800 px-2.5 py-1 rounded-xl flex flex-col items-center">
            <span className="text-stone-500 uppercase text-[8px] font-sans">Session VWAP</span>
            <span className="font-bold text-amber-400">₹{currentVWAP.toFixed(2)}</span>
          </div>
        </div>

        {/* Timeframe Selector & Indicators */}
        <div className="flex items-center space-x-2">
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

          <button
            onClick={() => setShowEMA20(!showEMA20)}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold border transition-colors cursor-pointer ${
              showEMA20 ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40' : 'bg-[#14151b] text-stone-500 border-stone-800'
            }`}
          >
            EMA20
          </button>

          <button
            onClick={() => setShowEMA50(!showEMA50)}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold border transition-colors cursor-pointer ${
              showEMA50 ? 'bg-rose-500/20 text-rose-300 border-rose-500/40' : 'bg-[#14151b] text-stone-500 border-stone-800'
            }`}
          >
            EMA50
          </button>

          <button
            onClick={() => setShowVWAP(!showVWAP)}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold border transition-colors cursor-pointer ${
              showVWAP ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' : 'bg-[#14151b] text-stone-500 border-stone-800'
            }`}
          >
            VWAP
          </button>
        </div>
      </div>

      {/* SVG Canvas for High Performance Candlesticks & Technical Overlays */}
      <div className="relative my-2 w-full h-[280px]">
        <svg className="w-full h-full overflow-visible" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none">
          {/* Background Grid Lines */}
          {[0.2, 0.4, 0.6, 0.8].map((ratio) => (
            <line
              key={ratio}
              x1="0"
              y1={chartHeight * ratio}
              x2={chartWidth}
              y2={chartHeight * ratio}
              stroke="#262730"
              strokeDasharray="4 4"
              strokeWidth="1"
            />
          ))}

          {/* Render Validated Candlesticks */}
          {candleList.map((c, i) => {
            const candleStep = chartWidth / Math.max(candleList.length, 1);
            const x = i * candleStep + candleStep / 2;
            const candleWidth = Math.max(candleStep * 0.65, 2);

            const yOpen = chartHeight - ((c.open - minPrice) / priceRange) * chartHeight;
            const yClose = chartHeight - ((c.close - minPrice) / priceRange) * chartHeight;
            const yHigh = chartHeight - ((c.high - minPrice) / priceRange) * chartHeight;
            const yLow = chartHeight - ((c.low - minPrice) / priceRange) * chartHeight;

            const isCandleGreen = c.close >= c.open;
            const candleColor = isCandleGreen ? '#10b981' : '#f43f5e';

            return (
              <g key={i}>
                <line x1={x} y1={yHigh} x2={x} y2={yLow} stroke={candleColor} strokeWidth="1.5" />
                <rect
                  x={x - candleWidth / 2}
                  y={Math.min(yOpen, yClose)}
                  width={candleWidth}
                  height={Math.max(Math.abs(yOpen - yClose), 1.5)}
                  fill={candleColor}
                  rx="1"
                />
              </g>
            );
          })}

          {/* EMA20 Polyline */}
          {showEMA20 && ema20Values.length > 0 && (
            <polyline
              fill="none"
              stroke="#818cf8"
              strokeWidth="1.5"
              points={ema20Values
                .map((val, idx) => {
                  const step = chartWidth / Math.max(candleList.length, 1);
                  const x = idx * step + step / 2;
                  const y = chartHeight - ((val - minPrice) / priceRange) * chartHeight;
                  return `${x},${y}`;
                })
                .join(' ')}
            />
          )}

          {/* EMA50 Polyline */}
          {showEMA50 && ema50Values.length > 0 && (
            <polyline
              fill="none"
              stroke="#f43f5e"
              strokeWidth="1.5"
              points={ema50Values
                .map((val, idx) => {
                  const step = chartWidth / Math.max(candleList.length, 1);
                  const x = idx * step + step / 2;
                  const y = chartHeight - ((val - minPrice) / priceRange) * chartHeight;
                  return `${x},${y}`;
                })
                .join(' ')}
            />
          )}

          {/* VWAP Constant Line */}
          {showVWAP && (
            <line
              x1="0"
              y1={chartHeight - ((currentVWAP - minPrice) / priceRange) * chartHeight}
              x2={chartWidth}
              y2={chartHeight - ((currentVWAP - minPrice) / priceRange) * chartHeight}
              stroke="#f59e0b"
              strokeWidth="1.5"
              strokeDasharray="3 3"
            />
          )}
        </svg>
      </div>

      {/* Chart Footer Indicator Readout & Data Source */}
      <div className="flex items-center justify-between font-mono text-[10px] text-stone-400 pt-2 border-t border-stone-800/60">
        <div className="flex items-center space-x-3">
          <span className="text-indigo-400 font-bold">EMA 20: ₹{ema20Values[ema20Values.length - 1]?.toFixed(2) || currentPrice}</span>
          <span className="text-rose-400 font-bold">EMA 50: ₹{ema50Values[ema50Values.length - 1]?.toFixed(2) || currentPrice}</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            SOURCE: UPSTOX REST
          </span>
        </div>
      </div>
    </div>
  );
};
