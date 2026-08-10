import React, { useState } from 'react';
import { NSEStock, PaperPosition } from '../types/indianMarket';
import { X, ShoppingCart, DollarSign, ArrowUpRight, ArrowDownRight, Layers, Trash2 } from 'lucide-react';

interface PaperTradingModalProps {
  isOpen: boolean;
  onClose: () => void;
  stock: NSEStock;
  availableBalance: number;
  positions: PaperPosition[];
  onPlacePaperOrder: (order: {
    symbol: string;
    companyName: string;
    productType: 'CNC (Delivery)' | 'MIS (Intraday)';
    side: 'BUY' | 'SELL';
    quantity: number;
    price: number;
    targetPrice?: number;
    stopLoss?: number;
  }) => void;
  onClosePosition: (id: string) => void;
}

export const PaperTradingModal: React.FC<PaperTradingModalProps> = ({
  isOpen,
  onClose,
  stock,
  availableBalance,
  positions,
  onPlacePaperOrder,
  onClosePosition,
}) => {
  const [productType, setProductType] = useState<'CNC (Delivery)' | 'MIS (Intraday)'>('CNC (Delivery)');
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [quantity, setQuantity] = useState<number>(100);

  if (!isOpen) return null;

  const totalOrderValue = quantity * stock.price;
  // Intraday MIS requires 20% margin (5x leverage), CNC requires 100% margin
  const requiredMargin = productType === 'MIS (Intraday)' ? totalOrderValue * 0.20 : totalOrderValue;

  const handleSubmitOrder = (e: React.FormEvent) => {
    e.preventDefault();
    if (quantity <= 0 || requiredMargin > availableBalance) return;

    onPlacePaperOrder({
      symbol: stock.symbol,
      companyName: stock.name,
      productType,
      side,
      quantity,
      price: stock.price,
      targetPrice: Number((stock.price * (side === 'BUY' ? 1.05 : 0.95)).toFixed(2)),
      stopLoss: Number((stock.price * (side === 'BUY' ? 0.97 : 1.03)).toFixed(2)),
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md select-none animate-fade-in">
      <div className="bg-[#1c1e27] border border-stone-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl p-6 text-stone-100 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-stone-800 pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center font-bold text-amber-400">
              <ShoppingCart className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-black text-white">NSE Paper Order Terminal</h3>
              <p className="text-xs text-stone-400">Simulated Equity Order Execution for Indian Markets</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl bg-[#14151b] text-stone-400 hover:text-white border border-stone-800 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Selected Stock Info Banner */}
        <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800 flex items-center justify-between font-mono text-xs">
          <div>
            <div className="font-bold text-white">{stock.name} ({stock.symbol})</div>
            <div className="text-[10px] text-stone-400">{stock.sector}</div>
          </div>
          <div className="text-right">
            <div className="font-extrabold text-amber-400">₹{stock.price.toFixed(2)}</div>
            <div className="text-[10px] text-stone-400">Available Capital: ₹{availableBalance.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
          </div>
        </div>

        {/* Order Form */}
        <form onSubmit={handleSubmitOrder} className="space-y-4">
          {/* BUY / SELL Switch */}
          <div className="grid grid-cols-2 gap-2 bg-[#14151b] p-1 rounded-xl border border-stone-800">
            <button
              type="button"
              onClick={() => setSide('BUY')}
              className={`py-2 rounded-lg font-bold text-xs transition-all cursor-pointer ${
                side === 'BUY' ? 'bg-emerald-500 text-stone-950 font-black shadow' : 'text-stone-400 hover:text-white'
              }`}
            >
              BUY (Long)
            </button>
            <button
              type="button"
              onClick={() => setSide('SELL')}
              className={`py-2 rounded-lg font-bold text-xs transition-all cursor-pointer ${
                side === 'SELL' ? 'bg-rose-500 text-stone-950 font-black shadow' : 'text-stone-400 hover:text-white'
              }`}
            >
              SELL (Short / MIS)
            </button>
          </div>

          {/* Product Type (CNC Delivery vs MIS Intraday) */}
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setProductType('CNC (Delivery)')}
              className={`p-3 rounded-xl border text-left cursor-pointer transition-all ${
                productType === 'CNC (Delivery)'
                  ? 'bg-amber-500/10 border-amber-500/60 text-white'
                  : 'bg-[#14151b] border-stone-800 text-stone-400'
              }`}
            >
              <div className="text-xs font-bold">CNC (Equity Delivery)</div>
              <div className="text-[10px] text-stone-400">100% Margin required • Hold overnight</div>
            </button>
            <button
              type="button"
              onClick={() => setProductType('MIS (Intraday)')}
              className={`p-3 rounded-xl border text-left cursor-pointer transition-all ${
                productType === 'MIS (Intraday)'
                  ? 'bg-amber-500/10 border-amber-500/60 text-white'
                  : 'bg-[#14151b] border-stone-800 text-stone-400'
              }`}
            >
              <div className="text-xs font-bold">MIS (Intraday Trading)</div>
              <div className="text-[10px] text-stone-400">5x Leverage (20% Margin) • Auto squared off</div>
            </button>
          </div>

          {/* Quantity Selector */}
          <div>
            <label className="text-xs font-bold text-stone-300 block mb-1 font-mono">
              Order Quantity (Shares):
            </label>
            <input
              type="number"
              min="1"
              max="50000"
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value) || 1)}
              className="w-full bg-[#14151b] border border-stone-800 rounded-xl px-4 py-2.5 text-xs font-mono font-bold text-white focus:outline-none focus:border-amber-500/60"
            />
          </div>

          {/* Order Summary Calculations */}
          <div className="bg-[#14151b] p-3 rounded-xl border border-stone-800 space-y-1 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-stone-400">Total Order Value:</span>
              <span className="font-bold text-white">₹{totalOrderValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-stone-400">Required Margin ({productType}):</span>
              <span className="font-extrabold text-amber-400">₹{requiredMargin.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
            </div>
          </div>

          <button
            type="submit"
            disabled={requiredMargin > availableBalance}
            className={`w-full py-3 rounded-xl font-black text-xs uppercase tracking-wider text-stone-950 transition-all cursor-pointer shadow-lg ${
              side === 'BUY'
                ? 'bg-emerald-400 hover:bg-emerald-300 shadow-emerald-500/20'
                : 'bg-rose-400 hover:bg-rose-300 shadow-rose-500/20'
            } ${requiredMargin > availableBalance ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            Execute {side} Order ({quantity} Shares)
          </button>
        </form>

        {/* Existing Open Positions */}
        {positions.length > 0 && (
          <div className="border-t border-stone-800 pt-4 space-y-2">
            <h4 className="text-xs font-bold text-white uppercase font-mono">Active Paper Positions</h4>
            <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
              {positions.map((pos) => (
                <div key={pos.id} className="p-2.5 bg-[#14151b] rounded-xl border border-stone-800 flex items-center justify-between text-xs font-mono">
                  <div>
                    <div className="font-bold text-white">{pos.symbol.split('.')[0]} ({pos.productType})</div>
                    <div className="text-[10px] text-stone-400">{pos.side} • {pos.quantity} Qty @ ₹{pos.entryPrice}</div>
                  </div>
                  <div className="text-right flex items-center space-x-3">
                    <div>
                      <div className={`font-bold ${pos.unrealizedPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {pos.unrealizedPnL >= 0 ? '+' : ''}₹{pos.unrealizedPnL.toFixed(2)}
                      </div>
                      <div className="text-[10px] text-stone-500">{pos.unrealizedPnLPercent.toFixed(2)}%</div>
                    </div>
                    <button
                      onClick={() => onClosePosition(pos.id)}
                      className="p-1.5 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 border border-rose-500/30 cursor-pointer"
                      title="Exit Position"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
