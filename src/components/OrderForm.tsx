import React, { useState, useEffect } from 'react';
import { 
  ArrowUpRight, 
  ArrowDownRight, 
  ShieldAlert, 
  Percent, 
  Sliders,
  DollarSign,
  AlertTriangle
} from 'lucide-react';
import { Asset, TradeSide, OrderType } from '../types/trading';

interface OrderFormProps {
  asset: Asset;
  availableMargin: number;
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
  selectedPrice?: number;
}

export const OrderForm: React.FC<OrderFormProps> = ({
  asset,
  availableMargin,
  onPlaceOrder,
  selectedPrice,
}) => {
  const [side, setSide] = useState<TradeSide>('Buy');
  const [orderType, setOrderType] = useState<OrderType>('Market');
  const [price, setPrice] = useState<string>(asset.price.toString());
  const [amount, setAmount] = useState<string>('0.1');
  const [leverage, setLeverage] = useState<number>(10);
  const [enableTP, setEnableTP] = useState<boolean>(false);
  const [takeProfit, setTakeProfit] = useState<string>('');
  const [enableSL, setEnableSL] = useState<boolean>(false);
  const [stopLoss, setStopLoss] = useState<string>('');

  useEffect(() => {
    if (orderType === 'Market') {
      setPrice(asset.price.toString());
    }
  }, [asset.price, orderType]);

  useEffect(() => {
    if (selectedPrice && orderType !== 'Market') {
      setPrice(selectedPrice.toString());
    }
  }, [selectedPrice, orderType]);

  const numPrice = Number(price) || asset.price;
  const numAmount = Number(amount) || 0;
  const positionValue = numPrice * numAmount;
  const requiredMargin = leverage > 0 ? positionValue / leverage : positionValue;

  // Percentage allocation shortcut buttons (25%, 50%, 75%, 100%)
  const handlePercentageSelect = (pct: number) => {
    const marginToUse = availableMargin * (pct / 100);
    const maxVal = marginToUse * leverage;
    const calcQty = numPrice > 0 ? maxVal / numPrice : 0;
    setAmount(Number(calcQty.toFixed(4)).toString());
  };

  // Liquidation calculation
  const isLong = side === 'Buy';
  const estLiqPrice = isLong
    ? numPrice * (1 - 0.90 / leverage)
    : numPrice * (1 + 0.90 / leverage);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (numAmount <= 0) return;

    onPlaceOrder({
      symbol: asset.symbol,
      side,
      type: orderType,
      price: numPrice,
      amount: numAmount,
      leverage,
      stopLoss: enableSL && Number(stopLoss) > 0 ? Number(stopLoss) : undefined,
      takeProfit: enableTP && Number(takeProfit) > 0 ? Number(takeProfit) : undefined,
    });
  };

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-xl p-3.5 flex flex-col h-full text-stone-200 select-none">
      {/* Side Switcher (Buy / Sell) */}
      <div className="grid grid-cols-2 gap-1.5 p-1 bg-stone-950 rounded-lg border border-stone-800 mb-3">
        <button
          onClick={() => setSide('Buy')}
          className={`py-2 rounded-md font-bold text-xs flex items-center justify-center space-x-1 transition-all ${
            side === 'Buy'
              ? 'bg-emerald-500 text-stone-950 shadow-sm'
              : 'text-stone-400 hover:text-stone-200'
          }`}
        >
          <ArrowUpRight className="w-4 h-4" />
          <span>BUY / LONG</span>
        </button>

        <button
          onClick={() => setSide('Sell')}
          className={`py-2 rounded-md font-bold text-xs flex items-center justify-center space-x-1 transition-all ${
            side === 'Sell'
              ? 'bg-rose-500 text-stone-950 shadow-sm'
              : 'text-stone-400 hover:text-stone-200'
          }`}
        >
          <ArrowDownRight className="w-4 h-4" />
          <span>SELL / SHORT</span>
        </button>
      </div>

      <form onSubmit={handleSubmit} className="flex-1 flex flex-col justify-between space-y-3">
        {/* Order Type Tabs */}
        <div className="flex border-b border-stone-800 text-xs">
          {(['Market', 'Limit', 'Stop'] as OrderType[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setOrderType(t)}
              className={`pb-1.5 px-3 font-medium transition-colors border-b-2 -mb-px ${
                orderType === t
                  ? 'border-emerald-400 text-stone-100 font-bold'
                  : 'border-transparent text-stone-500 hover:text-stone-300'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Price Input (if Limit/Stop) */}
        {orderType !== 'Market' && (
          <div>
            <label className="text-[11px] text-stone-400 font-medium block mb-1">
              {orderType} Price (USD)
            </label>
            <div className="relative">
              <input
                type="number"
                step="any"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-1.5 text-xs font-mono text-stone-100 focus:outline-none focus:border-stone-600"
              />
            </div>
          </div>
        )}

        {/* Quantity Amount Input */}
        <div>
          <div className="flex justify-between items-center mb-1">
            <label className="text-[11px] text-stone-400 font-medium">Quantity ({asset.symbol.split('/')[0]})</label>
            <span className="text-[10px] text-stone-500 font-mono">Val: ${positionValue.toFixed(2)}</span>
          </div>
          <input
            type="number"
            step="any"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-1.5 text-xs font-mono text-stone-100 focus:outline-none focus:border-stone-600"
            placeholder="0.00"
          />

          {/* Quick Percentage Allocation Buttons */}
          <div className="grid grid-cols-4 gap-1 mt-1.5 font-mono text-[10px]">
            {[25, 50, 75, 100].map((pct) => (
              <button
                key={pct}
                type="button"
                onClick={() => handlePercentageSelect(pct)}
                className="py-1 rounded bg-stone-950 border border-stone-800 hover:bg-stone-800 text-stone-400 hover:text-stone-100 transition-colors"
              >
                {pct}%
              </button>
            ))}
          </div>
        </div>

        {/* Leverage Slider */}
        <div>
          <div className="flex justify-between items-center mb-1 text-[11px]">
            <span className="text-stone-400 font-medium">Leverage</span>
            <span className="font-mono font-bold text-amber-400 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 rounded">
              {leverage}x
            </span>
          </div>
          <input
            type="range"
            min="1"
            max="50"
            value={leverage}
            onChange={(e) => setLeverage(Number(e.target.value))}
            className="w-full accent-amber-400 cursor-pointer h-1.5 bg-stone-950 rounded-lg"
          />
          <div className="flex justify-between text-[9px] font-mono text-stone-600 mt-0.5">
            <span>1x</span>
            <span>10x</span>
            <span>25x</span>
            <span>50x</span>
          </div>
        </div>

        {/* TP / SL Controls */}
        <div className="space-y-2 border-t border-stone-800/80 pt-2">
          <div className="flex items-center justify-between text-xs">
            <label className="flex items-center space-x-1.5 cursor-pointer text-stone-300 text-[11px]">
              <input
                type="checkbox"
                checked={enableTP}
                onChange={(e) => setEnableTP(e.target.checked)}
                className="rounded bg-stone-950 border-stone-700 text-emerald-500 focus:ring-0"
              />
              <span>Take Profit</span>
            </label>
            {enableTP && (
              <input
                type="number"
                step="any"
                placeholder="Target Price"
                value={takeProfit}
                onChange={(e) => setTakeProfit(e.target.value)}
                className="w-28 bg-stone-950 border border-stone-800 rounded px-2 py-0.5 text-xs font-mono text-emerald-400 focus:outline-none"
              />
            )}
          </div>

          <div className="flex items-center justify-between text-xs">
            <label className="flex items-center space-x-1.5 cursor-pointer text-stone-300 text-[11px]">
              <input
                type="checkbox"
                checked={enableSL}
                onChange={(e) => setEnableSL(e.target.checked)}
                className="rounded bg-stone-950 border-stone-700 text-rose-500 focus:ring-0"
              />
              <span>Stop Loss</span>
            </label>
            {enableSL && (
              <input
                type="number"
                step="any"
                placeholder="Stop Price"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
                className="w-28 bg-stone-950 border border-stone-800 rounded px-2 py-0.5 text-xs font-mono text-rose-400 focus:outline-none"
              />
            )}
          </div>
        </div>

        {/* Margin Summary */}
        <div className="bg-stone-950 p-2.5 rounded-lg border border-stone-800/80 text-[11px] font-mono space-y-1">
          <div className="flex justify-between text-stone-400">
            <span>Required Margin:</span>
            <span className="font-semibold text-stone-200">${requiredMargin.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-stone-400">
            <span>Est. Liquidation Price:</span>
            <span className="font-semibold text-amber-400">${estLiqPrice.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-stone-400">
            <span>Est. Trading Fee (0.05%):</span>
            <span className="text-stone-400">${(positionValue * 0.0005).toFixed(2)}</span>
          </div>
        </div>

        {/* Submit Order Button */}
        <button
          type="submit"
          disabled={requiredMargin > availableMargin || numAmount <= 0}
          className={`w-full py-2.5 rounded-lg font-bold text-xs uppercase tracking-wider transition-all flex items-center justify-center space-x-2 ${
            requiredMargin > availableMargin
              ? 'bg-stone-800 text-stone-500 cursor-not-allowed'
              : side === 'Buy'
              ? 'bg-emerald-500 hover:bg-emerald-400 text-stone-950 shadow-md cursor-pointer'
              : 'bg-rose-500 hover:bg-rose-400 text-stone-950 shadow-md cursor-pointer'
          }`}
        >
          {requiredMargin > availableMargin ? (
            <span>Insufficient Available Margin</span>
          ) : (
            <span>
              {side === 'Buy' ? 'Open Long Position' : 'Open Short Position'}
            </span>
          )}
        </button>
      </form>
    </div>
  );
};
