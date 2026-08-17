import React from 'react';
import { IndianMarketAIReport, NSEStock } from '../types/indianMarket';
import { Sparkles, X, ShieldCheck, Activity, BarChart2 } from 'lucide-react';

interface MarketIntelligenceModalProps {
  isOpen: boolean;
  onClose: () => void;
  stock: NSEStock;
  report: IndianMarketAIReport | null;
  isLoading: boolean;
  onReScan: (symbol: string) => void;
  onApplySetup?: (setup: { entry: number; target: number; stopLoss: number }) => void;
}

export const MarketIntelligenceModal: React.FC<MarketIntelligenceModalProps> = ({
  isOpen,
  onClose,
  stock,
  report,
  isLoading,
  onReScan,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md select-none animate-fade-in">
      <div className="bg-[#1c1e27] border border-stone-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl p-6 text-stone-100 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-stone-800 pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 via-orange-500 to-indigo-600 flex items-center justify-center text-white font-bold shadow-lg shadow-orange-500/20">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-lg font-black text-white">{stock?.name || 'Stock'} ({stock?.symbol || 'NSE'})</h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                  {stock?.sector || 'EQUITY'}
                </span>
                <span className="px-2 py-0.5 rounded text-[9px] font-mono font-bold bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
                  PROVENANCE: GEMINI AI
                </span>
              </div>
              <p className="text-xs text-stone-400">Gemini 2.5 Quantitative Evidence & Market Structure Analysis</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl bg-[#14151b] text-stone-400 hover:text-white border border-stone-800 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {isLoading ? (
          <div className="py-16 text-center space-y-4">
            <div className="w-12 h-12 rounded-full border-4 border-amber-500 border-t-transparent animate-spin mx-auto" />
            <div className="text-sm font-bold text-white">Evaluating Market Regime & Technical Metrics...</div>
            <p className="text-xs text-stone-400">Processing order flow, RSI(14), EMA20/50 crossovers & PCR positioning...</p>
          </div>
        ) : report ? (
          <div className="space-y-4">
            {/* Quantitative Score Cards First */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 font-mono text-xs">
              <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800">
                <span className="text-[9px] text-stone-400 font-sans uppercase">Market Stance</span>
                <div className="font-extrabold text-amber-400 text-sm mt-0.5">{report.marketStance}</div>
                <div className="text-[9px] text-stone-500">{report.confidence}% Model Confidence</div>
              </div>

              <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800">
                <span className="text-[9px] text-stone-400 font-sans uppercase">Technical Momentum</span>
                <div className="font-extrabold text-emerald-400 text-sm mt-0.5">
                  {report.technicalMetrics.rsi14 ? `RSI ${report.technicalMetrics.rsi14}` : 'Price Action'}
                </div>
                <div className="text-[9px] text-stone-500">
                  {report.technicalMetrics.ema20 ? `EMA20: ₹${report.technicalMetrics.ema20}` : 'Active Session Trend'}
                </div>
              </div>

              <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800">
                <span className="text-[9px] text-stone-400 font-sans uppercase">Options Positioning</span>
                <div className="font-extrabold text-sky-400 text-sm mt-0.5 truncate">{report.technicalMetrics.pcrSignal || 'Balanced'}</div>
                <div className="text-[9px] text-stone-500">Derivatives Flow</div>
              </div>

              <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800">
                <span className="text-[9px] text-stone-400 font-sans uppercase">Volume Benchmark</span>
                <div className="font-extrabold text-indigo-400 text-sm mt-0.5">₹{report.technicalMetrics.vwap?.toLocaleString() || stock.vwap.toLocaleString()}</div>
                <div className="text-[9px] text-stone-500">Session VWAP Anchor</div>
              </div>

              <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800">
                <span className="text-[9px] text-stone-400 font-sans uppercase">Institutional Bias</span>
                <div className="font-extrabold text-purple-400 text-sm mt-0.5 truncate">{report.fiiDiiSentiment || 'Neutral'}</div>
                <div className="text-[9px] text-stone-500">Clearing Status</div>
              </div>

              <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800">
                <span className="text-[9px] text-stone-400 font-sans uppercase">Index Benchmark</span>
                <div className="font-extrabold text-orange-400 text-sm mt-0.5 truncate">{report.niftyCorrel || 'NSE Benchmark'}</div>
                <div className="text-[9px] text-stone-500">Market Correlation</div>
              </div>
            </div>

            {/* AI Reasoning Analysis */}
            <div className="bg-[#14151b] p-4 rounded-xl border border-stone-800 space-y-2">
              <h4 className="text-xs font-bold text-amber-400 uppercase font-mono">Quantitative AI Analysis & Evidence</h4>
              <p className="text-xs text-stone-200 leading-relaxed">{report.executiveSummary}</p>
            </div>

            {/* Catalysts List */}
            <div className="bg-[#14151b] p-4 rounded-xl border border-stone-800 space-y-2">
              <h4 className="text-xs font-bold text-stone-300 uppercase font-mono">Fundamental & Regulatory Drivers</h4>
              <ul className="space-y-1.5 text-xs text-stone-300">
                {report.catalysts.map((cat, i) => (
                  <li key={i} className="flex items-start space-x-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{cat}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Tactical Plan */}
            <div className="bg-[#14151b] p-4 rounded-xl border border-stone-800 space-y-3">
              <div className="flex justify-between items-center border-b border-stone-800 pb-2">
                <h4 className="text-xs font-bold text-emerald-400 uppercase font-mono">Tactical Price Levels</h4>
                <span className="text-xs font-bold text-amber-400">{report.tacticalTradeSetup.action}</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                <div>
                  <span className="text-[10px] text-stone-400">Entry Zone</span>
                  <div className="font-extrabold text-white">{report.tacticalTradeSetup.entryZone}</div>
                </div>
                <div>
                  <span className="text-[10px] text-stone-400">Target 1</span>
                  <div className="font-extrabold text-emerald-400">{report.tacticalTradeSetup.target1}</div>
                </div>
                <div>
                  <span className="text-[10px] text-stone-400">Target 2</span>
                  <div className="font-extrabold text-emerald-400">{report.tacticalTradeSetup.target2}</div>
                </div>
                <div>
                  <span className="text-[10px] text-stone-400">Stop Loss</span>
                  <div className="font-extrabold text-rose-400">{report.tacticalTradeSetup.stopLoss}</div>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-between items-center pt-2">
              <button
                onClick={() => onReScan(stock.symbol)}
                className="px-4 py-2 rounded-xl bg-[#14151b] hover:bg-stone-800 text-stone-300 text-xs font-bold border border-stone-800 cursor-pointer"
              >
                Re-Scan Market Structure
              </button>
              <button
                onClick={onClose}
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-stone-950 font-black text-xs cursor-pointer shadow-lg shadow-amber-500/20"
              >
                Done
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
