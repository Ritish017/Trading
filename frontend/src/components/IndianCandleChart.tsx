import React, { useState, useRef } from 'react';
import { NSEStock } from '../types/indianMarket';
import { IndianCandle, calculateEMA, calculateVWAP } from '../utils/indianTechnicalAnalysis';
import { Layers, TrendingUp, BarChart2, Activity, Eye, Zap, ShieldCheck, AlertCircle } from 'lucide-react';

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
  provenanceStatus?: string;
  providerName?: string;
  marketStatus?: string;
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
  provenanceStatus = 'DEV_MOCK',
  providerName = 'UPSTOX',
  marketStatus = 'LIVE',
}) => {
  const [showEMA20, setShowEMA20] = useState(true);
  const [showEMA50, setShowEMA50] = useState(true);
  const [showVWAP, setShowVWAP] = useState(true);
  const [chartType, setChartType] = useState<'candlestick' | 'line'>('candlestick');
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const sym = symbol || stock?.symbol || 'RELIANCE.NS';
  const stName = name || stock?.name || 'Reliance Industries';
  const currentPrice = price ?? stock?.price;
  const currentChange = change ?? stock?.change ?? 0;
  const currentChangePct = changePercent ?? stock?.changePercent ?? 0;
  const isPos = currentChange >= 0;

  // Strict Candle Validation
  const validCandles = (candles || []).filter((c) => {
    if (!c || typeof c.open !== 'number' || typeof c.close !== 'number') return false;
    const maxOC = Math.max(c.open, c.close);
    const minOC = Math.min(c.open, c.close);
    return c.high >= maxOC && c.low <= minOC;
  });

  const candleList = validCandles.length > 0 ? validCandles : [];

  const closes = candleList.map((c) => c.close);
  const ema20Values = calculateEMA(closes, 20);
  const ema50Values = calculateEMA(closes, 50);
  const currentVWAP = calculateVWAP(candleList);

  // Active or Hovered Candle for Inspection Badge
  const activeIndex = hoverIndex !== null && hoverIndex >= 0 && hoverIndex < candleList.length ? hoverIndex : candleList.length - 1;
  const activeCandle = candleList[activeIndex] || candleList[candleList.length - 1];
  const activeCandleChange = activeCandle.close - activeCandle.open;
  const activeCandleChangePct = activeCandle.open > 0 ? (activeCandleChange / activeCandle.open) * 100 : 0;

  // Chart Layout Calculations
  const chartWidth = 900;
  const totalHeight = 360;
  const priceChartHeight = 260;
  const volumeChartHeight = 65;
  const volumeGap = 15;
  const volumeChartTop = priceChartHeight + volumeGap;

  const minPrice = Math.min(...candleList.map((c) => c.low)) * 0.999;
  const maxPrice = Math.max(...candleList.map((c) => c.high)) * 1.001;
  const priceRange = maxPrice - minPrice || 1;

  const maxVolume = Math.max(
    ...candleList.map((c) => c.volume ?? (c.volumeLakhs ? c.volumeLakhs * 100000 : 5000)),
    1000
  );

  // Format Timestamps for X-Axis Labels and Crosshairs
  const formatTimeLabel = (timestamp: number | string, tf: string) => {
    try {
      const ms = typeof timestamp === 'number' ? (timestamp > 1e11 ? timestamp : timestamp * 1000) : new Date(timestamp).getTime();
      const d = new Date(ms);
      if (isNaN(d.getTime())) return '';
      
      const day = d.getDate().toString().padStart(2, '0');
      const month = d.toLocaleString('en-US', { month: 'short' });
      const hours = d.getHours().toString().padStart(2, '0');
      const mins = d.getMinutes().toString().padStart(2, '0');

      if (tf === '1D') {
        return `${day} ${month}`;
      } else if (tf === '1h' || tf === '15m') {
        return `${day} ${month} ${hours}:${mins}`;
      } else {
        return `${hours}:${mins}`;
      }
    } catch {
      return '';
    }
  };

  // Mouse Interaction for Crosshair
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * chartWidth;
    const y = ((e.clientY - rect.top) / rect.height) * totalHeight;

    const candleStep = chartWidth / Math.max(candleList.length, 1);
    const idx = Math.min(Math.max(Math.floor(x / candleStep), 0), candleList.length - 1);
    setHoverIndex(idx);
    setMousePos({ x, y });
  };

  const handleMouseLeave = () => {
    setHoverIndex(null);
    setMousePos(null);
  };

  // Calculate Price Grid Levels (4 horizontal lines)
  const priceGridLevels = [0.15, 0.38, 0.62, 0.85].map((r) => {
    const val = maxPrice - r * priceRange;
    const y = r * priceChartHeight;
    return { val, y };
  });

  // Calculate Time Grid Indices
  const numTimeLabels = Math.min(candleList.length, 6);
  const timeIndices = Array.from({ length: numTimeLabels }, (_, i) =>
    Math.floor((i * (candleList.length - 1)) / (numTimeLabels - 1 || 1))
  );

  const isMarketClosed = marketStatus === 'MARKET_CLOSED';
  const isSimulated = provenanceStatus === 'DEV_MOCK' || providerName === 'MOCK';
  const isLiveAuthentic = provenanceStatus === 'AUTHENTIC_LIVE' && !isMarketClosed;

  const activeVolNumber = activeCandle?.volume ?? (activeCandle?.volumeLakhs ? activeCandle.volumeLakhs * 100000 : 5000);
  const activeVolFormatted = activeVolNumber >= 100000 
    ? `${(activeVolNumber / 100000).toFixed(1)}L` 
    : `${(activeVolNumber / 1000).toFixed(1)}k`;

  return (
    <div className="bg-[#181a20] border border-stone-800/90 rounded-2xl p-4 flex flex-col justify-between shadow-2xl select-none">
      {/* 1. Header: Stock Info, Price, OHLCV Inspector & Timeframe Selector */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-stone-800/70">
        {/* Stock Title & Live Price */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center font-black text-amber-400 text-base shadow-inner">
            ₹
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-black text-white text-base font-mono tracking-wide">{sym}</span>
              <span className="text-xs text-stone-400 font-medium hidden sm:inline">{stName}</span>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold border ${
                isMarketClosed
                  ? 'bg-stone-800 text-stone-400 border-stone-700'
                  : isSimulated
                  ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30'
                  : isLiveAuthentic
                  ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                  : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
              }`}>
                {isMarketClosed ? 'MARKET CLOSED' : (isSimulated ? 'SIMULATED • DEV MOCK' : (isLiveAuthentic ? 'NSE LIVE' : 'FEED: RECENT'))}
              </span>
            </div>
            <div className="flex items-center space-x-2 font-mono text-sm">
              <span className="font-extrabold text-white">
                {currentPrice !== undefined ? `₹${currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '---'}
              </span>
              <span className={`font-bold text-xs ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                {isPos ? '+' : ''}{currentChange.toFixed(2)} ({isPos ? '+' : ''}{currentChangePct.toFixed(2)}%)
              </span>
            </div>
          </div>
        </div>

        {/* Dynamic OHLCV Live / Hover Inspector Banner */}
        <div className="flex items-center space-x-2 font-mono text-[11px] bg-[#121318] px-3 py-1.5 rounded-xl border border-stone-800/80">
          <span className="text-stone-500 text-[10px]">
            {formatTimeLabel(activeCandle.time, timeframe) || 'Latest'}
          </span>
          <div className="h-3 w-[1px] bg-stone-800 mx-1" />
          <span className="text-stone-400">O: <strong className="text-stone-200">₹{activeCandle.open.toFixed(2)}</strong></span>
          <span className="text-stone-400">H: <strong className="text-emerald-400">₹{activeCandle.high.toFixed(2)}</strong></span>
          <span className="text-stone-400">L: <strong className="text-rose-400">₹{activeCandle.low.toFixed(2)}</strong></span>
          <span className="text-stone-400">C: <strong className="text-stone-200">₹{activeCandle.close.toFixed(2)}</strong></span>
          <span className="text-stone-400 hidden lg:inline">Vol: <strong className="text-amber-400">{activeVolFormatted}</strong></span>
        </div>

        {/* Timeframe Selector & Chart Controls */}
        <div className="flex items-center space-x-2">
          {/* Timeframe Buttons */}
          <div className="flex space-x-1 bg-[#121318] p-1 rounded-xl border border-stone-800/80">
            {(['1m', '5m', '15m', '1h', '1D'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => onTimeframeChange(tf)}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
                  timeframe === tf ? 'bg-amber-500 text-stone-950 shadow-md font-black' : 'text-stone-400 hover:text-stone-200'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Chart Type Toggle */}
          <button
            onClick={() => setChartType(chartType === 'candlestick' ? 'line' : 'candlestick')}
            className="p-1.5 rounded-lg bg-[#121318] border border-stone-800 text-stone-300 hover:text-white transition-colors"
            title={chartType === 'candlestick' ? 'Switch to Line Chart' : 'Switch to Candlestick Chart'}
          >
            {chartType === 'candlestick' ? <BarChart2 className="w-4 h-4 text-amber-400" /> : <Activity className="w-4 h-4 text-cyan-400" />}
          </button>
        </div>
      </div>

      {/* 2. Main Professional SVG Candlestick & Volume Sub-Chart */}
      <div className="relative my-2 w-full h-[360px] bg-[#14151b]/70 rounded-xl overflow-hidden border border-stone-800/40">
        <svg
          ref={svgRef}
          className="w-full h-full cursor-crosshair overflow-visible"
          viewBox={`0 0 ${chartWidth} ${totalHeight}`}
          preserveAspectRatio="none"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            {/* Area chart gradient */}
            <linearGradient id="chartAreaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Price Grid Horizontal Lines & Price Y-Axis Labels */}
          {priceGridLevels.map((lvl, idx) => (
            <g key={idx}>
              <line
                x1="0"
                y1={lvl.y}
                x2={chartWidth - 65}
                y2={lvl.y}
                stroke="#232530"
                strokeDasharray="3 3"
                strokeWidth="1"
              />
              <text
                x={chartWidth - 5}
                y={lvl.y + 3}
                fill="#71717a"
                fontSize="10"
                fontFamily="monospace"
                textAnchor="end"
              >
                ₹{lvl.val.toFixed(2)}
              </text>
            </g>
          ))}

          {/* Volume Sub-Chart Separator Line */}
          <line
            x1="0"
            y1={volumeChartTop - 5}
            x2={chartWidth}
            y2={volumeChartTop - 5}
            stroke="#272a37"
            strokeWidth="1"
          />
          <text
            x="8"
            y={volumeChartTop + 8}
            fill="#52525b"
            fontSize="9"
            fontFamily="monospace"
            fontWeight="bold"
          >
            VOL ({(maxVolume / 1000).toFixed(0)}K max)
          </text>

          {/* Render Candlesticks or Area Line */}
          {chartType === 'candlestick' ? (
            candleList.map((c, i) => {
              const candleStep = (chartWidth - 70) / Math.max(candleList.length, 1);
              const x = i * candleStep + candleStep / 2;
              const candleWidth = Math.max(candleStep * 0.7, 2);

              const yOpen = priceChartHeight - ((c.open - minPrice) / priceRange) * priceChartHeight;
              const yClose = priceChartHeight - ((c.close - minPrice) / priceRange) * priceChartHeight;
              const yHigh = priceChartHeight - ((c.high - minPrice) / priceRange) * priceChartHeight;
              const yLow = priceChartHeight - ((c.low - minPrice) / priceRange) * priceChartHeight;

              const isGreen = c.close >= c.open;
              const color = isGreen ? '#10b981' : '#f43f5e';

              // Volume Bar
              const cVol = c.volume ?? (c.volumeLakhs ? c.volumeLakhs * 100000 : 5000);
              const volRatio = cVol / maxVolume;
              const volBarHeight = Math.max(volRatio * volumeChartHeight, 2);
              const volY = totalHeight - 20 - volBarHeight;

              return (
                <g key={i}>
                  {/* Candlestick Wick */}
                  <line x1={x} y1={yHigh} x2={x} y2={yLow} stroke={color} strokeWidth="1.5" />
                  {/* Candlestick Body */}
                  <rect
                    x={x - candleWidth / 2}
                    y={Math.min(yOpen, yClose)}
                    width={candleWidth}
                    height={Math.max(Math.abs(yOpen - yClose), 1.5)}
                    fill={color}
                    rx="1"
                  />
                  {/* Volume Sub-Bar */}
                  <rect
                    x={x - candleWidth / 2}
                    y={volY}
                    width={candleWidth}
                    height={volBarHeight}
                    fill={color}
                    opacity={0.65}
                    rx="0.5"
                  />
                </g>
              );
            })
          ) : (
            // Smooth Area/Line Chart
            <g>
              <polygon
                points={`0,${priceChartHeight} ${candleList
                  .map((c, i) => {
                    const candleStep = (chartWidth - 70) / Math.max(candleList.length, 1);
                    const x = i * candleStep + candleStep / 2;
                    const y = priceChartHeight - ((c.close - minPrice) / priceRange) * priceChartHeight;
                    return `${x},${y}`;
                  })
                  .join(' ')} ${chartWidth - 70},${priceChartHeight}`}
                fill="url(#chartAreaGradient)"
              />
              <polyline
                fill="none"
                stroke="#10b981"
                strokeWidth="2"
                points={candleList
                  .map((c, i) => {
                    const candleStep = (chartWidth - 70) / Math.max(candleList.length, 1);
                    const x = i * candleStep + candleStep / 2;
                    const y = priceChartHeight - ((c.close - minPrice) / priceRange) * priceChartHeight;
                    return `${x},${y}`;
                  })
                  .join(' ')}
              />
            </g>
          )}

          {/* EMA20 Polyline */}
          {showEMA20 && ema20Values.length > 0 && (
            <polyline
              fill="none"
              stroke="#818cf8"
              strokeWidth="1.5"
              points={ema20Values
                .map((val, idx) => {
                  const step = (chartWidth - 70) / Math.max(candleList.length, 1);
                  const x = idx * step + step / 2;
                  const y = priceChartHeight - ((val - minPrice) / priceRange) * priceChartHeight;
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
                  const step = (chartWidth - 70) / Math.max(candleList.length, 1);
                  const x = idx * step + step / 2;
                  const y = priceChartHeight - ((val - minPrice) / priceRange) * priceChartHeight;
                  return `${x},${y}`;
                })
                .join(' ')}
            />
          )}

          {/* VWAP Horizontal / Polyline */}
          {showVWAP && (
            <line
              x1="0"
              y1={priceChartHeight - ((currentVWAP - minPrice) / priceRange) * priceChartHeight}
              x2={chartWidth - 70}
              y2={priceChartHeight - ((currentVWAP - minPrice) / priceRange) * priceChartHeight}
              stroke="#f59e0b"
              strokeWidth="1.5"
              strokeDasharray="4 4"
            />
          )}

          {/* Current Live Price Tag on Right Y-Axis */}
          {currentPrice && currentPrice > 0 && minPrice > 0 && priceRange > 0 && (() => {
            const currentY = priceChartHeight - ((currentPrice - minPrice) / priceRange) * priceChartHeight;
            if (isNaN(currentY)) return null;
            return (
              <g>
                <line
                  x1="0"
                  y1={currentY}
                  x2={chartWidth - 65}
                  y2={currentY}
                  stroke={isPos ? '#10b981' : '#f43f5e'}
                  strokeDasharray="2 2"
                  strokeWidth="1"
                />
                <rect
                  x={chartWidth - 62}
                  y={currentY - 9}
                  width="60"
                  height="18"
                  fill={isPos ? '#10b981' : '#f43f5e'}
                  rx="3"
                />
                <text
                  x={chartWidth - 32}
                  y={currentY + 4}
                  fill="#ffffff"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                  textAnchor="middle"
                >
                  ₹{currentPrice.toFixed(1)}
                </text>
              </g>
            );
          })()}

          {/* Time X-Axis Grid Labels at Bottom */}
          {timeIndices.map((idx) => {
            const candleStep = (chartWidth - 70) / Math.max(candleList.length, 1);
            const x = idx * candleStep + candleStep / 2;
            const candle = candleList[idx];
            if (!candle) return null;
            return (
              <g key={idx}>
                <line x1={x} y1={totalHeight - 20} x2={x} y2={totalHeight - 16} stroke="#3f3f46" strokeWidth="1" />
                <text
                  x={x}
                  y={totalHeight - 5}
                  fill="#71717a"
                  fontSize="9"
                  fontFamily="monospace"
                  textAnchor="middle"
                >
                  {formatTimeLabel(candle.time, timeframe)}
                </text>
              </g>
            );
          })}

          {/* Interactive Crosshair Lines & Inspection Pills */}
          {hoverIndex !== null && mousePos && (
            <g>
              {/* Vertical Crosshair Line */}
              {(() => {
                const candleStep = (chartWidth - 70) / Math.max(candleList.length, 1);
                const x = hoverIndex * candleStep + candleStep / 2;
                return (
                  <g>
                    <line
                      x1={x}
                      y1="0"
                      x2={x}
                      y2={totalHeight - 20}
                      stroke="#94a3b8"
                      strokeDasharray="3 3"
                      strokeWidth="1"
                      opacity="0.8"
                    />
                    {/* Bottom Time Pill */}
                    <rect
                      x={x - 45}
                      y={totalHeight - 18}
                      width="90"
                      height="16"
                      fill="#1e293b"
                      stroke="#475569"
                      rx="3"
                    />
                    <text
                      x={x}
                      y={totalHeight - 6}
                      fill="#f8fafc"
                      fontSize="9"
                      fontFamily="monospace"
                      fontWeight="bold"
                      textAnchor="middle"
                    >
                      {formatTimeLabel(activeCandle.time, timeframe)}
                    </text>
                  </g>
                );
              })()}

              {/* Horizontal Crosshair Line */}
              {mousePos.y <= priceChartHeight && (
                <g>
                  <line
                    x1="0"
                    y1={mousePos.y}
                    x2={chartWidth - 65}
                    y2={mousePos.y}
                    stroke="#94a3b8"
                    strokeDasharray="3 3"
                    strokeWidth="1"
                    opacity="0.8"
                  />
                  {/* Right Price Pill */}
                  <rect
                    x={chartWidth - 65}
                    y={mousePos.y - 9}
                    width="62"
                    height="18"
                    fill="#1e293b"
                    stroke="#475569"
                    rx="3"
                  />
                  <text
                    x={chartWidth - 34}
                    y={mousePos.y + 4}
                    fill="#f8fafc"
                    fontSize="10"
                    fontFamily="monospace"
                    fontWeight="bold"
                    textAnchor="middle"
                  >
                    ₹{(maxPrice - (mousePos.y / priceChartHeight) * priceRange).toFixed(2)}
                  </text>
                </g>
              )}
            </g>
          )}
        </svg>

        {candleList.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#14151b]/85 backdrop-blur-xs text-stone-400 font-mono text-xs space-y-2 select-none">
            <AlertCircle className="w-8 h-8 text-amber-400 opacity-60 animate-pulse" />
            <span className="font-bold text-stone-200 text-sm">NO MARKET CANDLE DATA</span>
            <span className="text-[11px] text-stone-500">Awaiting canonical exchange candle feed for {sym} ({timeframe})</span>
          </div>
        )}
      </div>

      {/* 3. Bottom Indicator Toggles & Provenance Status */}
      <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-xs text-stone-400 pt-2 border-t border-stone-800/70">
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowEMA20(!showEMA20)}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors cursor-pointer flex items-center space-x-1.5 ${
              showEMA20 ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40 shadow-sm' : 'bg-[#121318] text-stone-500 border-stone-800'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-indigo-400" />
            <span>EMA 20 ({ema20Values.length > 0 ? `₹${ema20Values[ema20Values.length - 1]?.toFixed(1)}` : '---'})</span>
          </button>

          <button
            onClick={() => setShowEMA50(!showEMA50)}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors cursor-pointer flex items-center space-x-1.5 ${
              showEMA50 ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-sm' : 'bg-[#121318] text-stone-500 border-stone-800'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-rose-400" />
            <span>EMA 50 ({ema50Values.length > 0 ? `₹${ema50Values[ema50Values.length - 1]?.toFixed(1)}` : '---'})</span>
          </button>

          <button
            onClick={() => setShowVWAP(!showVWAP)}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors cursor-pointer flex items-center space-x-1.5 ${
              showVWAP ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm' : 'bg-[#121318] text-stone-500 border-stone-800'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span>VWAP ({candleList.length > 0 ? `₹${currentVWAP.toFixed(1)}` : '---'})</span>
          </button>
        </div>

        <div className="flex items-center space-x-2">
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-stone-800/80 text-stone-300 border border-stone-700">
            {candleList.length} Candles
          </span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border flex items-center space-x-1 ${
            isMarketClosed
              ? 'bg-stone-800 text-stone-400 border-stone-700'
              : isSimulated
              ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30'
              : isLiveAuthentic
              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
              : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isMarketClosed ? 'bg-stone-500' : (isLiveAuthentic ? 'bg-emerald-400 animate-pulse' : 'bg-cyan-400')}`} />
            <span>PROVENANCE: {isMarketClosed ? 'MARKET CLOSED' : (isSimulated ? 'SIMULATED • DEV MOCK' : (isLiveAuthentic ? `${providerName.toUpperCase()} LIVE CANONICAL` : 'FEED: RECENT'))}</span>
          </span>
        </div>
      </div>
    </div>
  );
};

