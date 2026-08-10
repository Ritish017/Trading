import React, { useState, useRef, useMemo } from 'react';
import { 
  BarChart2, 
  LineChart, 
  Eye, 
  EyeOff, 
  Maximize2, 
  Sliders,
  TrendingUp,
  Info
} from 'lucide-react';
import { Candle, Timeframe, ChartIndicatorConfig, Asset } from '../types/trading';
import { 
  calculateSMA, 
  calculateRSI, 
  calculateBollingerBands 
} from '../utils/technicalAnalysis';

interface TradingChartProps {
  asset: Asset;
  candles: Candle[];
  timeframe: Timeframe;
  onTimeframeChange: (tf: Timeframe) => void;
}

export const TradingChart: React.FC<TradingChartProps> = ({
  asset,
  candles,
  timeframe,
  onTimeframeChange,
}) => {
  const [chartType, setChartType] = useState<'candlestick' | 'line'>('candlestick');
  const [hoveredCandleIndex, setHoveredCandleIndex] = useState<number | null>(null);
  const [indicators, setIndicators] = useState<ChartIndicatorConfig>({
    sma20: true,
    sma50: true,
    bollingerBands: false,
    rsi: true,
    macd: false,
    volume: true,
  });

  const chartRef = useRef<SVGSVGElement | null>(null);

  const timeframes: Timeframe[] = ['1m', '5m', '15m', '1h', '4h', '1D', '1W'];

  // Calculate Indicators
  const sma20 = useMemo(() => calculateSMA(candles, 20), [candles]);
  const sma50 = useMemo(() => calculateSMA(candles, 50), [candles]);
  const rsi = useMemo(() => calculateRSI(candles, 14), [candles]);
  const bollinger = useMemo(() => calculateBollingerBands(candles, 20, 2), [candles]);

  // Chart dimensions
  const svgWidth = 800;
  const svgHeight = 440;
  const paddingRight = 70; // space for y-axis labels
  const paddingLeft = 10;
  const paddingTop = 20;
  const paddingBottom = indicators.rsi ? 110 : 30; // space for RSI if active

  const chartAreaWidth = svgWidth - paddingLeft - paddingRight;
  const chartAreaHeight = svgHeight - paddingTop - paddingBottom;

  // Min and Max prices for scaling
  const priceMin = useMemo(() => {
    if (candles.length === 0) return 0;
    let min = Math.min(...candles.map((c) => c.low));
    if (indicators.bollingerBands) {
      const validBands = bollinger.lower.filter((v): v is number => v !== null);
      if (validBands.length) min = Math.min(min, ...validBands);
    }
    return min * 0.998;
  }, [candles, indicators.bollingerBands, bollinger]);

  const priceMax = useMemo(() => {
    if (candles.length === 0) return 100;
    let max = Math.max(...candles.map((c) => c.high));
    if (indicators.bollingerBands) {
      const validBands = bollinger.upper.filter((v): v is number => v !== null);
      if (validBands.length) max = Math.max(max, ...validBands);
    }
    return max * 1.002;
  }, [candles, indicators.bollingerBands, bollinger]);

  const maxVolume = useMemo(() => {
    if (candles.length === 0) return 1;
    return Math.max(...candles.map((c) => c.volume));
  }, [candles]);

  // Coordinate mappers
  const getY = (price: number) => {
    if (priceMax === priceMin) return paddingTop + chartAreaHeight / 2;
    return paddingTop + chartAreaHeight - ((price - priceMin) / (priceMax - priceMin)) * chartAreaHeight;
  };

  const candleWidth = chartAreaWidth / Math.max(candles.length, 1);
  const getX = (index: number) => paddingLeft + index * candleWidth + candleWidth / 2;

  // Y-axis grid ticks (5 levels)
  const priceTicks = useMemo(() => {
    const ticks = [];
    const count = 5;
    for (let i = 0; i <= count; i++) {
      const price = priceMin + (i * (priceMax - priceMin)) / count;
      ticks.push(price);
    }
    return ticks;
  }, [priceMin, priceMax]);

  // Active or hovered candle
  const displayCandle = hoveredCandleIndex !== null ? candles[hoveredCandleIndex] : candles[candles.length - 1];
  const displayRSI = hoveredCandleIndex !== null ? rsi[hoveredCandleIndex] : rsi[rsi.length - 1];

  const toggleIndicator = (key: keyof ChartIndicatorConfig) => {
    setIndicators((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-xl p-3 flex flex-col h-full text-stone-200 select-none">
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-800/80 pb-2.5 mb-2">
        {/* Left: Timeframe Switcher */}
        <div className="flex items-center space-x-1 bg-stone-950 p-1 rounded-lg border border-stone-800">
          {timeframes.map((tf) => (
            <button
              key={tf}
              onClick={() => onTimeframeChange(tf)}
              className={`px-2 py-0.5 rounded text-[11px] font-mono font-medium transition-colors ${
                timeframe === tf
                  ? 'bg-stone-700 text-white font-bold'
                  : 'text-stone-400 hover:text-stone-200 hover:bg-stone-800'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>

        {/* Center: Chart Type Toggle */}
        <div className="flex items-center space-x-1 bg-stone-950 p-1 rounded-lg border border-stone-800">
          <button
            onClick={() => setChartType('candlestick')}
            className={`p-1 rounded transition-colors ${
              chartType === 'candlestick' ? 'bg-stone-700 text-white' : 'text-stone-400 hover:text-stone-200'
            }`}
            title="Candlestick Chart"
          >
            <BarChart2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setChartType('line')}
            className={`p-1 rounded transition-colors ${
              chartType === 'line' ? 'bg-stone-700 text-white' : 'text-stone-400 hover:text-stone-200'
            }`}
            title="Line/Area Chart"
          >
            <LineChart className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Right: Technical Indicator Toggles */}
        <div className="flex items-center space-x-2 text-xs">
          <button
            onClick={() => toggleIndicator('sma20')}
            className={`px-2 py-0.5 rounded border text-[11px] font-mono font-medium transition-colors ${
              indicators.sma20
                ? 'bg-amber-500/20 border-amber-500/40 text-amber-400'
                : 'bg-stone-950 border-stone-800 text-stone-500 hover:text-stone-300'
            }`}
          >
            SMA 20
          </button>

          <button
            onClick={() => toggleIndicator('sma50')}
            className={`px-2 py-0.5 rounded border text-[11px] font-mono font-medium transition-colors ${
              indicators.sma50
                ? 'bg-sky-500/20 border-sky-500/40 text-sky-400'
                : 'bg-stone-950 border-stone-800 text-stone-500 hover:text-stone-300'
            }`}
          >
            SMA 50
          </button>

          <button
            onClick={() => toggleIndicator('bollingerBands')}
            className={`px-2 py-0.5 rounded border text-[11px] font-mono font-medium transition-colors ${
              indicators.bollingerBands
                ? 'bg-purple-500/20 border-purple-500/40 text-purple-400'
                : 'bg-stone-950 border-stone-800 text-stone-500 hover:text-stone-300'
            }`}
          >
            BB (20,2)
          </button>

          <button
            onClick={() => toggleIndicator('rsi')}
            className={`px-2 py-0.5 rounded border text-[11px] font-mono font-medium transition-colors ${
              indicators.rsi
                ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
                : 'bg-stone-950 border-stone-800 text-stone-500 hover:text-stone-300'
            }`}
          >
            RSI 14
          </button>
        </div>
      </div>

      {/* OHLCV Dynamic Data Bar */}
      {displayCandle && (
        <div className="flex flex-wrap items-center space-x-4 px-2 py-1 bg-stone-950/60 rounded-md text-[11px] font-mono text-stone-300 mb-2 border border-stone-800/40">
          <span className="text-stone-500 font-sans">O:</span>
          <span className="font-semibold text-white">${displayCandle.open.toFixed(asset.precision)}</span>
          <span className="text-stone-500 font-sans">H:</span>
          <span className="font-semibold text-emerald-400">${displayCandle.high.toFixed(asset.precision)}</span>
          <span className="text-stone-500 font-sans">L:</span>
          <span className="font-semibold text-rose-400">${displayCandle.low.toFixed(asset.precision)}</span>
          <span className="text-stone-500 font-sans">C:</span>
          <span className="font-semibold text-white">${displayCandle.close.toFixed(asset.precision)}</span>
          <span className="text-stone-500 font-sans">Vol:</span>
          <span className="font-semibold text-stone-300">{displayCandle.volume.toLocaleString()}</span>
          {indicators.rsi && displayRSI !== null && (
            <span className="ml-auto flex items-center space-x-1">
              <span className="text-stone-500">RSI(14):</span>
              <span className={`font-bold ${displayRSI > 70 ? 'text-rose-400' : displayRSI < 30 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {displayRSI.toFixed(1)}
              </span>
            </span>
          )}
        </div>
      )}

      {/* Main SVG Interactive Canvas */}
      <div className="relative flex-1 bg-stone-950 rounded-lg overflow-hidden border border-stone-800/80">
        <svg
          ref={chartRef}
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-full cursor-crosshair overflow-visible"
          onMouseLeave={() => setHoveredCandleIndex(null)}
          onMouseMove={(e) => {
            if (!chartRef.current || candles.length === 0) return;
            const rect = chartRef.current.getBoundingClientRect();
            const mouseX = ((e.clientX - rect.left) / rect.width) * svgWidth;
            const clampedX = Math.max(paddingLeft, Math.min(mouseX, svgWidth - paddingRight));
            const idx = Math.floor((clampedX - paddingLeft) / candleWidth);
            if (idx >= 0 && idx < candles.length) {
              setHoveredCandleIndex(idx);
            }
          }}
        >
          {/* Background Grid Lines */}
          {priceTicks.map((tick, i) => {
            const y = getY(tick);
            return (
              <g key={`grid-${i}`}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={svgWidth - paddingRight}
                  y2={y}
                  stroke="#27272a"
                  strokeDasharray="2 2"
                  strokeWidth="1"
                />
                {/* Y-Axis Price Labels */}
                <text
                  x={svgWidth - paddingRight + 6}
                  y={y + 4}
                  fill="#71717a"
                  fontSize="10"
                  fontFamily="monospace"
                >
                  ${tick.toFixed(asset.precision)}
                </text>
              </g>
            );
          })}

          {/* Current Market Price Dashline */}
          {candles.length > 0 && (
            <g>
              <line
                x1={paddingLeft}
                y1={getY(candles[candles.length - 1].close)}
                x2={svgWidth - paddingRight}
                y2={getY(candles[candles.length - 1].close)}
                stroke="#10b981"
                strokeDasharray="3 3"
                strokeWidth="1.2"
              />
              <rect
                x={svgWidth - paddingRight + 2}
                y={getY(candles[candles.length - 1].close) - 8}
                width={paddingRight - 4}
                height="16"
                fill="#10b981"
                rx="3"
              />
              <text
                x={svgWidth - paddingRight + 6}
                y={getY(candles[candles.length - 1].close) + 3}
                fill="#ffffff"
                fontSize="10"
                fontWeight="bold"
                fontFamily="monospace"
              >
                ${candles[candles.length - 1].close.toFixed(asset.precision)}
              </text>
            </g>
          )}

          {/* Bollinger Bands Fill & Lines */}
          {indicators.bollingerBands && (
            <g>
              <path
                d={candles.reduce((acc, _, i) => {
                  const upperVal = bollinger.upper[i];
                  if (upperVal === null) return acc;
                  const x = getX(i);
                  const y = getY(upperVal);
                  return acc + `${i === 20 ? 'M' : 'L'} ${x} ${y} `;
                }, '') +
                candles.reduceRight((acc, _, i) => {
                  const lowerVal = bollinger.lower[i];
                  if (lowerVal === null) return acc;
                  const x = getX(i);
                  const y = getY(lowerVal);
                  return acc + `L ${x} ${y} `;
                }, '') + 'Z'}
                fill="#a855f7"
                fillOpacity="0.08"
              />
            </g>
          )}

          {/* Volume Bars */}
          {indicators.volume && (
            <g>
              {candles.map((candle, i) => {
                const x = getX(i);
                const isGreen = candle.close >= candle.open;
                const volHeight = (candle.volume / maxVolume) * 40;
                const y = paddingTop + chartAreaHeight - volHeight;
                return (
                  <rect
                    key={`vol-${i}`}
                    x={x - candleWidth * 0.35}
                    y={y}
                    width={candleWidth * 0.7}
                    height={volHeight}
                    fill={isGreen ? '#10b981' : '#f43f5e'}
                    fillOpacity="0.2"
                  />
                );
              })}
            </g>
          )}

          {/* Candlesticks OR Line Chart */}
          {chartType === 'candlestick' ? (
            <g>
              {candles.map((candle, i) => {
                const x = getX(i);
                const isGreen = candle.close >= candle.open;
                const yOpen = getY(candle.open);
                const yClose = getY(candle.close);
                const yHigh = getY(candle.high);
                const yLow = getY(candle.low);

                const bodyY = Math.min(yOpen, yClose);
                const bodyHeight = Math.max(Math.abs(yOpen - yClose), 1.5);
                const color = isGreen ? '#10b981' : '#f43f5e';

                return (
                  <g key={`candle-${i}`}>
                    {/* Wick */}
                    <line
                      x1={x}
                      y1={yHigh}
                      x2={x}
                      y2={yLow}
                      stroke={color}
                      strokeWidth="1.2"
                    />
                    {/* Body */}
                    <rect
                      x={x - candleWidth * 0.38}
                      y={bodyY}
                      width={candleWidth * 0.76}
                      height={bodyHeight}
                      fill={color}
                      rx="1"
                    />
                  </g>
                );
              })}
            </g>
          ) : (
            <g>
              {/* Line Area Gradient */}
              <path
                d={
                  candles.reduce((acc, c, i) => {
                    const x = getX(i);
                    const y = getY(c.close);
                    return acc + `${i === 0 ? 'M' : 'L'} ${x} ${y} `;
                  }, '') +
                  `L ${getX(candles.length - 1)} ${paddingTop + chartAreaHeight} L ${getX(0)} ${paddingTop + chartAreaHeight} Z`
                }
                fill="url(#lineGradient)"
              />
              <path
                d={candles.reduce((acc, c, i) => {
                  const x = getX(i);
                  const y = getY(c.close);
                  return acc + `${i === 0 ? 'M' : 'L'} ${x} ${y} `;
                }, '')}
                fill="none"
                stroke="#10b981"
                strokeWidth="2"
              />
              <defs>
                <linearGradient id="lineGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                </linearGradient>
              </defs>
            </g>
          )}

          {/* SMA 20 Overlay Line */}
          {indicators.sma20 && (
            <path
              d={candles.reduce((acc, _, i) => {
                const val = sma20[i];
                if (val === null) return acc;
                const x = getX(i);
                const y = getY(val);
                return acc + `${acc === '' ? 'M' : 'L'} ${x} ${y} `;
              }, '')}
              fill="none"
              stroke="#f59e0b"
              strokeWidth="1.5"
            />
          )}

          {/* SMA 50 Overlay Line */}
          {indicators.sma50 && (
            <path
              d={candles.reduce((acc, _, i) => {
                const val = sma50[i];
                if (val === null) return acc;
                const x = getX(i);
                const y = getY(val);
                return acc + `${acc === '' ? 'M' : 'L'} ${x} ${y} `;
              }, '')}
              fill="none"
              stroke="#0ea5e9"
              strokeWidth="1.5"
            />
          )}

          {/* RSI Panel (Lower Chart Sub-Panel) */}
          {indicators.rsi && (
            <g transform={`translate(0, ${svgHeight - 90})`}>
              <line x1={paddingLeft} y1="0" x2={svgWidth - paddingRight} y2="0" stroke="#27272a" strokeWidth="1" />
              {/* Overbought 70 & Oversold 30 Dashlines */}
              <line x1={paddingLeft} y1="21" x2={svgWidth - paddingRight} y2="21" stroke="#3f3f46" strokeDasharray="2 2" />
              <line x1={paddingLeft} y1="49" x2={svgWidth - paddingRight} y2="49" stroke="#3f3f46" strokeDasharray="2 2" />
              <text x={svgWidth - paddingRight + 6} y="25" fill="#71717a" fontSize="9" fontFamily="monospace">70</text>
              <text x={svgWidth - paddingRight + 6} y="53" fill="#71717a" fontSize="9" fontFamily="monospace">30</text>

              {/* RSI Curve */}
              <path
                d={candles.reduce((acc, _, i) => {
                  const val = rsi[i];
                  if (val === null) return acc;
                  const x = getX(i);
                  // Scale RSI (0-100) to 70px panel height
                  const rsiY = 70 - (val / 100) * 70;
                  return acc + `${acc === '' ? 'M' : 'L'} ${x} ${rsiY} `;
                }, '')}
                fill="none"
                stroke="#10b981"
                strokeWidth="1.5"
              />
            </g>
          )}

          {/* Interactive Crosshair Tracker */}
          {hoveredCandleIndex !== null && (
            <g>
              {/* Vertical Crosshair line */}
              <line
                x1={getX(hoveredCandleIndex)}
                y1={paddingTop}
                x2={getX(hoveredCandleIndex)}
                y2={svgHeight - (indicators.rsi ? 90 : paddingBottom)}
                stroke="#a1a1aa"
                strokeDasharray="2 2"
                strokeWidth="1"
              />
              {/* Horizontal Crosshair line */}
              <line
                x1={paddingLeft}
                y1={getY(candles[hoveredCandleIndex].close)}
                x2={svgWidth - paddingRight}
                y2={getY(candles[hoveredCandleIndex].close)}
                stroke="#a1a1aa"
                strokeDasharray="2 2"
                strokeWidth="1"
              />
            </g>
          )}
        </svg>
      </div>
    </div>
  );
};
