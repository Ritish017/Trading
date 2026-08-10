import React, { useState } from 'react';
import { 
  Sparkles, 
  X, 
  TrendingUp, 
  TrendingDown, 
  CheckCircle2, 
  AlertCircle, 
  Zap, 
  ArrowRight,
  ShieldCheck,
  Target
} from 'lucide-react';
import { Asset, AIAnalysis, TradeSide } from '../types/trading';

interface AIAnalystModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeAsset: Asset;
  analysis: AIAnalysis | null;
  isLoading: boolean;
  onGenerateAnalysis: (symbol: string) => void;
  onApplyTradeSetup: (setup: {
    side: TradeSide;
    entry: number;
    takeProfit: number;
    stopLoss: number;
  }) => void;
}

export const AIAnalystModal: React.FC<AIAnalystModalProps> = ({
  isOpen,
  onClose,
  activeAsset,
  analysis,
  isLoading,
  onGenerateAnalysis,
  onApplyTradeSetup,
}) => {
  if (!isOpen) return null;

  const isBuy = analysis?.tradeSetup?.recommendedSide === 'Buy';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs select-none animate-fadeIn">
      <div className="bg-stone-900 border border-stone-800 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden text-stone-100">
        {/* Header */}
        <div className="p-4 border-b border-stone-800 bg-stone-950 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-stone-100 text-sm tracking-tight flex items-center space-x-2">
                <span>Gemini Technical AI Analyst</span>
                <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded font-mono">
                  {activeAsset.symbol}
                </span>
              </h3>
              <p className="text-xs text-stone-500">
                Pattern recognition, support/resistance detection & trade setups
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-stone-400 hover:text-stone-200 hover:bg-stone-800 rounded-lg transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 flex-1 overflow-y-auto space-y-5 custom-scrollbar font-sans">
          {/* Top Scan Bar */}
          <div className="flex items-center justify-between bg-stone-950 p-3 rounded-xl border border-stone-800">
            <div>
              <div className="text-xs font-semibold text-stone-300">Active Market Scanner</div>
              <div className="text-[11px] text-stone-500">
                Current Price: <strong className="text-stone-200">${activeAsset.price.toLocaleString()}</strong>
              </div>
            </div>

            <button
              onClick={() => onGenerateAnalysis(activeAsset.symbol)}
              disabled={isLoading}
              className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-stone-950 font-bold text-xs rounded-lg transition-all shadow-xs flex items-center space-x-2 cursor-pointer disabled:opacity-50"
            >
              <Zap className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>{isLoading ? 'Scanning Pattern...' : 'Re-Run Signal Scan'}</span>
            </button>
          </div>

          {isLoading ? (
            <div className="py-16 text-center space-y-3">
              <Sparkles className="w-8 h-8 text-emerald-400 animate-spin mx-auto" />
              <p className="text-sm font-semibold text-stone-300">Analyzing Technical Indicators & Candles...</p>
              <p className="text-xs text-stone-500">Evaluating RSI, MACD, Moving Averages and Order Book Depth</p>
            </div>
          ) : analysis ? (
            <>
              {/* Overall Signal Card */}
              <div className="bg-stone-950/80 rounded-xl p-4 border border-stone-800/80 flex items-center justify-between">
                <div>
                  <div className="text-xs text-stone-500 uppercase tracking-wider font-mono">Market Signal Bias</div>
                  <div className="text-xl font-black mt-1 flex items-center space-x-2">
                    <span
                      className={
                        analysis.overallSignal.includes('Buy')
                          ? 'text-emerald-400'
                          : analysis.overallSignal.includes('Sell')
                          ? 'text-rose-400'
                          : 'text-amber-400'
                      }
                    >
                      {analysis.overallSignal}
                    </span>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-xs text-stone-500 uppercase font-mono">Signal Confidence</div>
                  <div className="text-lg font-bold font-mono text-emerald-400 mt-1">
                    {analysis.confidence}%
                  </div>
                </div>
              </div>

              {/* Technical Summary Commentary */}
              <div className="bg-stone-950/40 p-3.5 rounded-xl border border-stone-800/60 text-xs text-stone-300 leading-relaxed">
                <span className="font-semibold text-stone-100 block mb-1">Analyst Insight:</span>
                {analysis.summary}
              </div>

              {/* Indicators Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 bg-stone-950 rounded-xl border border-stone-800/80">
                  <div className="text-[10px] text-stone-500 uppercase font-mono">RSI (14) Index</div>
                  <div className="text-sm font-bold text-stone-100 mt-1 font-mono">
                    {analysis.indicators.rsi.value.toFixed(1)}
                  </div>
                  <div className="text-[11px] text-stone-400 mt-0.5">{analysis.indicators.rsi.signal}</div>
                </div>

                <div className="p-3 bg-stone-950 rounded-xl border border-stone-800/80">
                  <div className="text-[10px] text-stone-500 uppercase font-mono">MACD Signal</div>
                  <div className="text-sm font-bold text-stone-100 mt-1 font-mono">
                    {analysis.indicators.macd.signal}
                  </div>
                  <div className="text-[11px] text-stone-400 mt-0.5">Hist: {analysis.indicators.macd.histogram}</div>
                </div>

                <div className="p-3 bg-stone-950 rounded-xl border border-stone-800/80">
                  <div className="text-[10px] text-stone-500 uppercase font-mono">Trend Structure</div>
                  <div className="text-sm font-bold text-stone-100 mt-1 font-mono truncate">
                    {analysis.indicators.trend}
                  </div>
                  <div className="text-[11px] text-emerald-400 mt-0.5">Bullish Alignment</div>
                </div>
              </div>

              {/* Key Price Levels */}
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
                  <span className="text-emerald-400 font-bold block mb-1">Key Support Levels</span>
                  <div className="space-y-0.5 text-stone-200">
                    {analysis.supportLevels.map((lvl, i) => (
                      <div key={i} className="flex justify-between">
                        <span className="text-stone-500">S{i + 1}:</span>
                        <span className="font-semibold">${lvl.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl">
                  <span className="text-rose-400 font-bold block mb-1">Key Resistance Levels</span>
                  <div className="space-y-0.5 text-stone-200">
                    {analysis.resistanceLevels.map((lvl, i) => (
                      <div key={i} className="flex justify-between">
                        <span className="text-stone-500">R{i + 1}:</span>
                        <span className="font-semibold">${lvl.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Strategic Trade Setup Recommendation */}
              {analysis.tradeSetup && (
                <div className="bg-stone-950 p-4 rounded-xl border border-stone-800 space-y-3">
                  <div className="flex items-center justify-between border-b border-stone-800 pb-2">
                    <div className="flex items-center space-x-2">
                      <Target className="w-4 h-4 text-emerald-400" />
                      <span className="font-bold text-xs text-stone-100 uppercase tracking-wider">
                        Suggested Strategic Setup
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-stone-400">
                      Risk/Reward: <strong className="text-emerald-400">{analysis.tradeSetup.riskRewardRatio}</strong>
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                    <div className="p-2 bg-stone-900 rounded border border-stone-800">
                      <div className="text-[10px] text-stone-500">Direction</div>
                      <div className={`font-bold mt-0.5 ${isBuy ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {analysis.tradeSetup.recommendedSide.toUpperCase()}
                      </div>
                    </div>

                    <div className="p-2 bg-stone-900 rounded border border-stone-800">
                      <div className="text-[10px] text-stone-500">Entry Target</div>
                      <div className="font-bold text-stone-100 mt-0.5">
                        ${analysis.tradeSetup.suggestedEntry.toLocaleString()}
                      </div>
                    </div>

                    <div className="p-2 bg-stone-900 rounded border border-stone-800">
                      <div className="text-[10px] text-stone-500">Take Profit 1</div>
                      <div className="font-bold text-emerald-400 mt-0.5">
                        ${analysis.tradeSetup.takeProfit1.toLocaleString()}
                      </div>
                    </div>

                    <div className="p-2 bg-stone-900 rounded border border-stone-800">
                      <div className="text-[10px] text-stone-500">Stop Loss</div>
                      <div className="font-bold text-rose-400 mt-0.5">
                        ${analysis.tradeSetup.stopLoss.toLocaleString()}
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      if (analysis.tradeSetup) {
                        onApplyTradeSetup({
                          side: analysis.tradeSetup.recommendedSide,
                          entry: analysis.tradeSetup.suggestedEntry,
                          takeProfit: analysis.tradeSetup.takeProfit1,
                          stopLoss: analysis.tradeSetup.stopLoss,
                        });
                        onClose();
                      }
                    }}
                    className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-400 text-stone-950 font-bold text-xs rounded-lg transition-colors flex items-center justify-center space-x-2 cursor-pointer shadow-md"
                  >
                    <span>Apply Setup Parameters to Order Terminal</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
};
