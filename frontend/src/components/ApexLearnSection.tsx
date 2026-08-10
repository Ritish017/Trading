import React, { useState } from 'react';
import { BookOpen, CheckCircle, Code, Play, ArrowRight, X } from 'lucide-react';

interface ApexLearnSectionProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ApexLearnSection: React.FC<ApexLearnSectionProps> = ({ isOpen, onClose }) => {
  const [selectedTopic, setSelectedTopic] = useState(0);

  if (!isOpen) return null;

  const topics = [
    {
      title: "1. Volume-Weighted Average Price (VWAP)",
      what: "VWAP calculates the average price an equity traded at throughout the day, based on both volume and price.",
      why: "Institutional algorithms use VWAP to gauge whether an order was executed at a favorable price.",
      how: "Typical Price = (High + Low + Close) / 3. VWAP = Cumulative(Typical Price * Volume) / Cumulative(Volume).",
      codeLocation: "backend/app/quant_engine/indicators.py",
      codeSnippet: `def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (df['high'] + df['low'] + df['close']) / 3.0
    return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()`,
    },
    {
      title: "2. Exponential Moving Average (EMA20 vs EMA50)",
      what: "EMA applies more weight to recent prices, reducing lag compared to Simple Moving Average.",
      why: "Bullish trend continuation occurs when price > EMA20 > EMA50 with rising slope.",
      how: "Multiplier = 2 / (Period + 1). EMA = (Price * Multiplier) + (Previous EMA * (1 - Multiplier)).",
      codeLocation: "backend/app/quant_engine/indicators.py",
      codeSnippet: `def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()`,
    },
    {
      title: "3. Put-Call Ratio (PCR) & Derivatives Max Pain",
      what: "PCR measures Total Put Open Interest divided by Total Call Open Interest. Max Pain strike is where option writers lose minimum capital.",
      why: "PCR > 1.2 indicates put writing (bullish floor); PCR < 0.7 indicates call writing (bearish ceiling).",
      how: "Calculated across active expiry option chains.",
      codeLocation: "backend/app/quant_engine/options.py",
      codeSnippet: `def calculate_pcr(total_put_oi: int, total_call_oi: int) -> float:
    return round(total_put_oi / total_call_oi, 2)`,
    },
    {
      title: "4. Walk-Forward Backtesting Validation",
      what: "Splits historical data into 70% In-Sample training and 30% Out-of-Sample testing to prevent curve fitting.",
      why: "Single backtests often overfit noise. Walk-Forward ensures out-of-sample edge stability.",
      how: "If Out-Of-Sample return collapses negative while In-Sample is positive, status = OVERFIT_REJECTED.",
      codeLocation: "backend/app/backtesting/event_driven.py",
      codeSnippet: `split_idx = int(len(df) * 0.70)
in_sample = df.iloc[:split_idx]
out_sample = df.iloc[split_idx:]`,
    },
  ];

  const current = topics[selectedTopic];

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
      <div className="bg-[#12131a] border border-stone-800 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden shadow-2xl">
        <div className="px-6 py-4 bg-[#161822] border-b border-stone-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <BookOpen className="w-6 h-6 text-amber-500" />
            <div>
              <h2 className="font-mono font-bold text-lg text-stone-100">APEX LEARN — Personal Quantitative Engineering Guide</h2>
              <p className="text-xs text-stone-400 font-mono">Master trading mechanics through real financial implementation code</p>
            </div>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-100 transition-colors">
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Topic Selector Sidebar */}
          <div className="w-1/3 border-r border-stone-800 bg-[#0f1015] p-3 space-y-2 overflow-y-auto">
            {topics.map((t, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedTopic(idx)}
                className={`w-full text-left p-3 rounded-lg font-mono text-xs font-semibold transition-all flex items-center justify-between ${
                  selectedTopic === idx
                    ? 'bg-amber-500/15 border border-amber-500/40 text-amber-400'
                    : 'text-stone-300 hover:bg-stone-800'
                }`}
              >
                <span>{t.title}</span>
                {selectedTopic === idx && <ArrowRight className="w-4 h-4" />}
              </button>
            ))}
          </div>

          {/* Topic Detail Content */}
          <div className="flex-1 p-6 overflow-y-auto space-y-6 text-stone-200 font-sans text-sm">
            <div>
              <h3 className="text-lg font-mono font-bold text-amber-400 mb-2">{current.title}</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
              <div className="p-3 bg-stone-900 border border-stone-800 rounded-lg">
                <span className="text-amber-500 font-bold uppercase block mb-1">What It Does</span>
                <p className="text-stone-300">{current.what}</p>
              </div>
              <div className="p-3 bg-stone-900 border border-stone-800 rounded-lg">
                <span className="text-amber-500 font-bold uppercase block mb-1">Why It Matters</span>
                <p className="text-stone-300">{current.why}</p>
              </div>
              <div className="p-3 bg-stone-900 border border-stone-800 rounded-lg">
                <span className="text-amber-500 font-bold uppercase block mb-1">How It Works</span>
                <p className="text-stone-300">{current.how}</p>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-xs font-bold text-stone-400 flex items-center">
                  <Code className="w-4 h-4 mr-2 text-amber-500" />
                  Apex Code Location: <code className="text-amber-300 ml-2">{current.codeLocation}</code>
                </span>
              </div>
              <pre className="p-4 bg-[#0a0b0e] border border-stone-800 rounded-lg text-emerald-400 font-mono text-xs overflow-x-auto leading-relaxed">
                {current.codeSnippet}
              </pre>
            </div>
          </div>
        </div>

        <div className="px-6 py-3 bg-[#161822] border-t border-stone-800 flex justify-between items-center text-xs font-mono text-stone-500">
          <span>APEX Lab Learning System</span>
          <button onClick={onClose} className="px-4 py-1.5 bg-amber-500 hover:bg-amber-600 text-stone-950 font-bold rounded-lg transition-colors">
            Got It
          </button>
        </div>
      </div>
    </div>
  );
};
