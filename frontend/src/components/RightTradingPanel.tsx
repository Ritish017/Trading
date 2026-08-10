import React, { useState } from 'react';
import { Asset, TradeSide, OrderType } from '../types/trading';
import { MoreVertical, ChevronDown, ArrowUpRight, ArrowDownRight, Wallet, DollarSign } from 'lucide-react';

interface RightTradingPanelProps {
  userName?: string;
  activeAsset: Asset;
  balance: number;
  availableMargin: number;
  equity: number;
  onPlaceOrder: (order: {
    symbol: string;
    side: TradeSide;
    type: OrderType;
    price: number;
    amount: number;
    leverage: number;
    stopLoss?: number;
    takeProfit?: number;
  }) => void;
  onOpenDepositModal: () => void;
  selectedPrice?: number;
}

export const RightTradingPanel: React.FC<RightTradingPanelProps> = ({
  userName = 'John',
  activeAsset,
  balance,
  availableMargin,
  equity,
  onPlaceOrder,
  onOpenDepositModal,
  selectedPrice,
}) => {
  const [currency, setCurrency] = useState('USDT-BTC');
  const [side, setSide] = useState<TradeSide>('Buy');
  const [cryptoAmount, setCryptoAmount] = useState('786.55');
  const [fiatAmount, setFiatAmount] = useState('8156.67');
  const [leverage, setLeverage] = useState(10);
  const [orderType, setOrderType] = useState<OrderType>('Market');

  const baseSymbol = activeAsset.symbol.split('/')[0];
  const quoteSymbol = activeAsset.symbol.split('/')[1] || 'USDT';

  // Synchronize crypto / fiat calculation when crypto amount changes
  const handleCryptoChange = (val: string) => {
    setCryptoAmount(val);
    const num = Number(val) || 0;
    setFiatAmount((num * activeAsset.price).toFixed(2));
  };

  const handleFiatChange = (val: string) => {
    setFiatAmount(val);
    const num = Number(val) || 0;
    if (activeAsset.price > 0) {
      setCryptoAmount((num / activeAsset.price).toFixed(4));
    }
  };

  const numCrypto = Number(cryptoAmount) || 0;
  const positionValue = numCrypto * activeAsset.price;
  const requiredMargin = leverage > 0 ? positionValue / leverage : positionValue;

  const handleSubmitTrade = (e: React.FormEvent) => {
    e.preventDefault();
    if (numCrypto <= 0) return;

    onPlaceOrder({
      symbol: activeAsset.symbol,
      side,
      type: orderType,
      price: selectedPrice || activeAsset.price,
      amount: numCrypto,
      leverage,
    });
  };

  return (
    <div className="w-80 lg:w-88 bg-[#16171d] border-l border-stone-800/60 p-4 flex flex-col space-y-4 overflow-y-auto h-full select-none shrink-0">
      {/* 1. User Profile Greeting Box */}
      <div className="bg-[#1e2029] border border-stone-800/80 rounded-2xl p-3.5 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full overflow-hidden border-2 border-purple-500/40 shrink-0">
            <img
              src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=120"
              alt="Avatar"
              className="w-full h-full object-cover"
            />
          </div>
          <div>
            <div className="text-[10px] text-stone-400 font-medium">Welcome Back</div>
            <div className="text-sm font-bold text-white leading-none">{userName}</div>
          </div>
        </div>
        <button className="text-stone-400 hover:text-stone-200">
          <MoreVertical className="w-4 h-4" />
        </button>
      </div>

      {/* Default Currency Selector Dropdown */}
      <div>
        <label className="text-[10px] text-stone-400 font-medium block mb-1">Default Currency</label>
        <div className="relative">
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="w-full appearance-none bg-[#1e2029] border border-stone-800/80 rounded-xl px-3 py-2 text-xs font-bold text-white focus:outline-none cursor-pointer"
          >
            <option value="USDT-BTC">USDT-BTC</option>
            <option value="USD-ETH">USD-ETH</option>
            <option value="USDT-SOL">USDT-SOL</option>
          </select>
          <ChevronDown className="w-4 h-4 text-stone-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        </div>
      </div>

      {/* 2. My Balance Display Card */}
      <div className="bg-[#1e2029] border border-stone-800/80 rounded-2xl p-4 flex flex-col justify-between">
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-stone-400 font-medium">My Balance</span>
          <button
            onClick={onOpenDepositModal}
            className="text-[11px] text-purple-400 hover:text-purple-300 font-bold underline cursor-pointer"
          >
            Top Up
          </button>
        </div>

        <div className="text-2xl font-black text-white tracking-tight font-mono mb-1">
          ${balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          <span className="text-xs text-stone-400 font-sans ml-1">USDT</span>
        </div>

        <div className="text-[11px] text-stone-400 font-mono">
          Total Value: <span className="text-stone-200 font-bold">{(balance / (activeAsset.price || 40000)).toFixed(3)} {baseSymbol}</span>
        </div>
      </div>

      {/* 3. Quick Trade Execution Widget */}
      <div className="bg-[#1e2029] border border-stone-800/80 rounded-2xl p-4 flex flex-col space-y-3">
        {/* Buy / Sell Tabs */}
        <div className="grid grid-cols-2 gap-1.5 p-1 bg-[#16171d] rounded-xl border border-stone-800/60">
          <button
            onClick={() => setSide('Buy')}
            className={`py-2 rounded-lg font-bold text-xs transition-all cursor-pointer ${
              side === 'Buy'
                ? 'bg-emerald-500 text-stone-950 shadow-md'
                : 'text-stone-400 hover:text-stone-200'
            }`}
          >
            Buy
          </button>
          <button
            onClick={() => setSide('Sell')}
            className={`py-2 rounded-lg font-bold text-xs transition-all cursor-pointer ${
              side === 'Sell'
                ? 'bg-rose-500 text-stone-950 shadow-md'
                : 'text-stone-400 hover:text-stone-200'
            }`}
          >
            Sell
          </button>
        </div>

        {/* Live Asset Price Display */}
        <div className="text-center py-1 bg-[#16171d]/60 border border-stone-800/40 rounded-xl">
          <div className="text-[10px] text-stone-400 font-medium">{activeAsset.name} Price</div>
          <div className="text-lg font-black text-white font-mono">
            ${activeAsset.price.toLocaleString(undefined, { minimumFractionDigits: activeAsset.precision })}
          </div>
        </div>

        <form onSubmit={handleSubmitTrade} className="space-y-2.5">
          {/* Crypto Amount Input */}
          <div className="relative">
            <input
              type="number"
              step="any"
              value={cryptoAmount}
              onChange={(e) => handleCryptoChange(e.target.value)}
              className="w-full bg-[#16171d] border border-stone-800/80 rounded-xl pl-3 pr-16 py-2 text-xs font-mono font-bold text-white focus:outline-none focus:border-purple-500/60"
              placeholder="0.00"
            />
            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center space-x-1 bg-stone-800/80 px-2 py-0.5 rounded-lg text-[10px] font-bold text-amber-400">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              <span>{baseSymbol}</span>
            </div>
          </div>

          {/* Fiat Amount Input */}
          <div className="relative">
            <input
              type="number"
              step="any"
              value={fiatAmount}
              onChange={(e) => handleFiatChange(e.target.value)}
              className="w-full bg-[#16171d] border border-stone-800/80 rounded-xl pl-3 pr-16 py-2 text-xs font-mono font-bold text-white focus:outline-none focus:border-purple-500/60"
              placeholder="0.00"
            />
            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center space-x-1 bg-stone-800/80 px-2 py-0.5 rounded-lg text-[10px] font-bold text-sky-400">
              <span className="w-2 h-2 rounded-full bg-sky-400" />
              <span>{quoteSymbol}</span>
            </div>
          </div>

          {/* Leverage Selector */}
          <div className="flex justify-between items-center text-[11px] pt-1">
            <span className="text-stone-400">Leverage:</span>
            <div className="flex space-x-1">
              {[1, 5, 10, 20, 50].map((lev) => (
                <button
                  key={lev}
                  type="button"
                  onClick={() => setLeverage(lev)}
                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold transition-all ${
                    leverage === lev
                      ? 'bg-purple-500 text-white'
                      : 'bg-[#16171d] text-stone-400 hover:text-stone-200'
                  }`}
                >
                  {lev}x
                </button>
              ))}
            </div>
          </div>

          {/* Vibrant Action Button (Pink to Purple Gradient) */}
          <button
            type="submit"
            className={`w-full py-3 rounded-xl font-black text-xs uppercase tracking-wider text-white shadow-lg transition-all transform active:scale-95 cursor-pointer ${
              side === 'Buy'
                ? 'bg-gradient-to-r from-pink-500 via-purple-500 to-indigo-500 hover:from-pink-600 hover:to-indigo-600 shadow-purple-500/25'
                : 'bg-gradient-to-r from-rose-500 via-pink-600 to-purple-600 hover:from-rose-600 hover:to-purple-700 shadow-rose-500/25'
            }`}
          >
            {side === 'Buy' ? `Buy ${baseSymbol}` : `Sell ${baseSymbol}`}
          </button>
        </form>
      </div>

      {/* 4. My Portfolio Section */}
      <div className="bg-[#1e2029] border border-stone-800/80 rounded-2xl p-4 flex flex-col justify-between">
        <div className="flex justify-between items-center mb-3">
          <h4 className="text-xs font-bold text-white">My Portfolio</h4>
          <button className="text-[10px] text-stone-400 hover:text-stone-200 font-medium">View All</button>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-xs">
                ₿
              </div>
              <div>
                <div className="font-bold text-xs text-white">Bitcoin</div>
                <div className="text-[10px] text-stone-400">BTC</div>
              </div>
            </div>
            <div className="text-right font-mono">
              <div className="font-bold text-xs text-white">$15,585.95</div>
              <div className="text-[10px] text-stone-400">0.35 BTC</div>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-xl bg-sky-500/20 text-sky-400 flex items-center justify-center font-bold text-xs">
                Ξ
              </div>
              <div>
                <div className="font-bold text-xs text-white">Ethereum</div>
                <div className="text-[10px] text-stone-400">ETH</div>
              </div>
            </div>
            <div className="text-right font-mono">
              <div className="font-bold text-xs text-white">$12,546.26</div>
              <div className="text-[10px] text-stone-400">3.80 ETH</div>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center font-bold text-xs">
                ▲
              </div>
              <div>
                <div className="font-bold text-xs text-white">Avalanche</div>
                <div className="text-[10px] text-stone-400">AVAX</div>
              </div>
            </div>
            <div className="text-right font-mono">
              <div className="font-bold text-xs text-white">$10,213.24</div>
              <div className="text-[10px] text-stone-400">150 AVAX</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
