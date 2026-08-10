import React, { useState, useEffect } from 'react';
import { RotateCcw, Play, Pause, FastForward, CheckCircle, X } from 'lucide-react';

interface MarketReplayModalProps {
  isOpen: boolean;
  onClose: () => void;
  symbol: string;
}

export const MarketReplayModal: React.FC<MarketReplayModalProps> = ({
  isOpen,
  onClose,
  symbol,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [replaySpeed, setReplaySpeed] = useState<number>(1);
  const [currentIndex, setCurrentIndex] = useState(10);
  const [totalCandles, setTotalCandles] = useState(60);

  useEffect(() => {
    let timer: any;
    if (isPlaying) {
      timer = setInterval(() => {
        setCurrentIndex((prev) => {
          if (prev >= totalCandles - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 1000 / replaySpeed);
    }
    return () => clearInterval(timer);
  }, [isPlaying, replaySpeed, totalCandles]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#161822] border border-stone-800 rounded-2xl w-full max-w-xl shadow-2xl p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-stone-800 pb-4">
          <div className="flex items-center space-x-3">
            <RotateCcw className="w-6 h-6 text-amber-500" />
            <div>
              <h2 className="font-mono font-bold text-lg text-stone-100">Market Replay Simulator</h2>
              <p className="text-xs text-stone-400 font-mono">Replay historical market candles without look-ahead bias</p>
            </div>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-100 transition-colors">
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="bg-[#0f1015] p-4 rounded-xl border border-stone-800 space-y-3 font-mono">
          <div className="flex justify-between text-xs text-stone-400">
            <span>Symbol: <strong className="text-amber-400">{symbol}</strong></span>
            <span>Progress: {currentIndex} / {totalCandles} Candles</span>
          </div>

          <div className="w-full bg-stone-800 h-2 rounded-full overflow-hidden">
            <div
              className="bg-amber-500 h-full transition-all duration-300"
              style={{ width: `${(currentIndex / totalCandles) * 100}%` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-center space-x-4">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="flex items-center space-x-2 bg-amber-500 hover:bg-amber-600 text-stone-950 font-bold px-6 py-2.5 rounded-lg transition-colors font-mono text-sm"
          >
            {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
            <span>{isPlaying ? 'Pause Replay' : 'Start Replay'}</span>
          </button>

          <div className="flex items-center space-x-1 bg-stone-900 border border-stone-800 rounded-lg p-1 font-mono text-xs text-stone-300">
            {[1, 2, 5].map((speed) => (
              <button
                key={speed}
                onClick={() => setReplaySpeed(speed)}
                className={`px-3 py-1 rounded ${
                  replaySpeed === speed ? 'bg-amber-500/20 text-amber-400 font-bold' : 'hover:text-stone-100'
                }`}
              >
                {speed}x
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-stone-800 pt-4 flex justify-between items-center text-xs font-mono text-stone-500">
          <span>Decision Quality Simulator</span>
          <button onClick={onClose} className="px-4 py-2 bg-stone-800 hover:bg-stone-700 text-stone-200 font-bold rounded-lg transition-colors">
            Close Simulator
          </button>
        </div>
      </div>
    </div>
  );
};
