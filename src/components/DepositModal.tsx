import React, { useState } from 'react';
import { Wallet, X, RotateCcw, Plus, Check } from 'lucide-react';

interface DepositModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentBalance: number;
  onResetBalance: (newBalance: number) => void;
}

export const DepositModal: React.FC<DepositModalProps> = ({
  isOpen,
  onClose,
  currentBalance,
  onResetBalance,
}) => {
  const [customAmount, setCustomAmount] = useState<string>('50000');

  if (!isOpen) return null;

  const presets = [10000, 50000, 100000, 250000];

  const handleApplyPreset = (amt: number) => {
    onResetBalance(amt);
    onClose();
  };

  const handleApplyCustom = () => {
    const num = Number(customAmount);
    if (num > 0) {
      onResetBalance(num);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs select-none animate-fadeIn">
      <div className="bg-stone-900 border border-stone-800 rounded-2xl w-full max-w-md p-5 shadow-2xl text-stone-100">
        <div className="flex items-center justify-between border-b border-stone-800 pb-3 mb-4">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Wallet className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-stone-100">Demo Paper Capital</h3>
              <p className="text-xs text-stone-500">Reset or add simulated trading account funds</p>
            </div>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div className="bg-stone-950 p-3 rounded-xl border border-stone-800 flex justify-between items-center">
            <span className="text-xs text-stone-400">Current Balance</span>
            <span className="font-mono font-bold text-lg text-emerald-400">
              ${currentBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
          </div>

          <div>
            <label className="text-xs font-semibold text-stone-300 block mb-2">Select Preset Funds</label>
            <div className="grid grid-cols-2 gap-2 font-mono text-xs">
              {presets.map((amt) => (
                <button
                  key={amt}
                  onClick={() => handleApplyPreset(amt)}
                  className="py-2 px-3 bg-stone-950 hover:bg-stone-800 border border-stone-800 rounded-lg text-stone-200 font-bold transition-colors flex items-center justify-between cursor-pointer"
                >
                  <span>${amt.toLocaleString()}</span>
                  <Plus className="w-3.5 h-3.5 text-stone-500" />
                </button>
              ))}
            </div>
          </div>

          <div className="pt-2 border-t border-stone-800">
            <label className="text-xs font-semibold text-stone-300 block mb-1">Set Custom Capital</label>
            <div className="flex space-x-2">
              <input
                type="number"
                value={customAmount}
                onChange={(e) => setCustomAmount(e.target.value)}
                className="flex-1 bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-xs font-mono text-stone-100 focus:outline-none focus:border-stone-600"
              />
              <button
                onClick={handleApplyCustom}
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-stone-950 font-bold text-xs rounded-lg transition-colors cursor-pointer"
              >
                Set Funds
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
