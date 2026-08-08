import React, { useState } from 'react';
import { Position, PendingOrder, ClosedTrade } from '../types/trading';
import { 
  X, 
  ArrowUpRight, 
  ArrowDownRight, 
  Trash2, 
  Percent, 
  History, 
  Briefcase, 
  TrendingUp,
  Clock,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';

interface PositionsPanelProps {
  positions: Position[];
  pendingOrders: PendingOrder[];
  closedTrades: ClosedTrade[];
  equityHistory: { time: string; equity: number }[];
  onClosePosition: (id: string, ratio?: number) => void;
  onCancelPendingOrder: (id: string) => void;
}

export const PositionsPanel: React.FC<PositionsPanelProps> = ({
  positions,
  pendingOrders,
  closedTrades,
  equityHistory,
  onClosePosition,
  onCancelPendingOrder,
}) => {
  const [activeTab, setActiveTab] = useState<'positions' | 'orders' | 'history' | 'analytics'>('positions');

  const totalUnrealizedPnL = positions.reduce((acc, p) => acc + p.unrealizedPnL, 0);
  const totalRealizedPnL = closedTrades.reduce((acc, t) => acc + t.realizedPnL, 0);
  const winCount = closedTrades.filter((t) => t.realizedPnL > 0).length;
  const winRate = closedTrades.length > 0 ? (winCount / closedTrades.length) * 100 : 0;

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-xl p-3 flex flex-col h-full text-stone-200 select-none">
      {/* Tab Navigation Bar */}
      <div className="flex flex-wrap items-center justify-between border-b border-stone-800 pb-2 mb-3 gap-2">
        <div className="flex items-center space-x-1 bg-stone-950 p-1 rounded-lg border border-stone-800 text-xs font-mono">
          <button
            onClick={() => setActiveTab('positions')}
            className={`px-3 py-1 rounded transition-all flex items-center space-x-1.5 ${
              activeTab === 'positions'
                ? 'bg-stone-700 text-white font-bold'
                : 'text-stone-400 hover:text-stone-200'
            }`}
          >
            <Briefcase className="w-3.5 h-3.5" />
            <span>Open Positions ({positions.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('orders')}
            className={`px-3 py-1 rounded transition-all flex items-center space-x-1.5 ${
              activeTab === 'orders'
                ? 'bg-stone-700 text-white font-bold'
                : 'text-stone-400 hover:text-stone-200'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Pending Orders ({pendingOrders.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`px-3 py-1 rounded transition-all flex items-center space-x-1.5 ${
              activeTab === 'history'
                ? 'bg-stone-700 text-white font-bold'
                : 'text-stone-400 hover:text-stone-200'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>Closed History ({closedTrades.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('analytics')}
            className={`px-3 py-1 rounded transition-all flex items-center space-x-1.5 ${
              activeTab === 'analytics'
                ? 'bg-stone-700 text-white font-bold'
                : 'text-stone-400 hover:text-stone-200'
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span>Performance</span>
          </button>
        </div>

        {/* Tab Metrics Summary */}
        <div className="flex items-center space-x-4 text-xs font-mono text-stone-400">
          <div>
            <span>Total UnPnL: </span>
            <span className={`font-bold ${totalUnrealizedPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {totalUnrealizedPnL >= 0 ? '+' : ''}${totalUnrealizedPnL.toFixed(2)}
            </span>
          </div>
          <div>
            <span>Realized PnL: </span>
            <span className={`font-bold ${totalRealizedPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {totalRealizedPnL >= 0 ? '+' : ''}${totalRealizedPnL.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* Content Body */}
      <div className="flex-1 overflow-x-auto overflow-y-auto custom-scrollbar">
        {activeTab === 'positions' && (
          <div>
            {positions.length === 0 ? (
              <div className="text-center py-12 text-stone-500 text-xs">
                No active open positions. Select a market and place an order above.
              </div>
            ) : (
              <table className="w-full text-left text-xs font-mono border-collapse">
                <thead>
                  <tr className="border-b border-stone-800 text-[10px] text-stone-500 uppercase tracking-wider">
                    <th className="pb-2">Market</th>
                    <th className="pb-2">Side</th>
                    <th className="pb-2">Size / Leverage</th>
                    <th className="pb-2">Entry Price</th>
                    <th className="pb-2">Mark Price</th>
                    <th className="pb-2">Margin</th>
                    <th className="pb-2">Unrealized PnL</th>
                    <th className="pb-2">Liq. Price</th>
                    <th className="pb-2 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-800/50">
                  {positions.map((pos) => {
                    const isLong = pos.side === 'Buy';
                    const isProfit = pos.unrealizedPnL >= 0;

                    return (
                      <tr key={pos.id} className="hover:bg-stone-800/40 transition-colors">
                        <td className="py-2.5 font-bold text-stone-100">{pos.symbol}</td>
                        <td className="py-2.5">
                          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            isLong ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                          }`}>
                            {isLong ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
                            {isLong ? 'LONG' : 'SHORT'}
                          </span>
                        </td>
                        <td className="py-2.5 text-stone-300">
                          {pos.amount.toFixed(3)} <span className="text-amber-400 font-bold">({pos.leverage}x)</span>
                        </td>
                        <td className="py-2.5 text-stone-300">${pos.entryPrice.toLocaleString()}</td>
                        <td className="py-2.5 font-semibold text-stone-100">${pos.markPrice.toLocaleString()}</td>
                        <td className="py-2.5 text-stone-400">${pos.margin.toFixed(2)}</td>
                        <td className="py-2.5">
                          <div className={`font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {isProfit ? '+' : ''}${pos.unrealizedPnL.toFixed(2)}
                          </div>
                          <div className={`text-[10px] ${isProfit ? 'text-emerald-500' : 'text-rose-500'}`}>
                            ({isProfit ? '+' : ''}{pos.unrealizedPnLPercent.toFixed(2)}%)
                          </div>
                        </td>
                        <td className="py-2.5 text-amber-400 font-semibold">${pos.liquidationPrice.toLocaleString()}</td>
                        <td className="py-2.5 text-right space-x-1.5">
                          <button
                            onClick={() => onClosePosition(pos.id, 0.5)}
                            className="px-2 py-1 rounded bg-stone-800 hover:bg-stone-700 text-stone-300 text-[10px] font-medium transition-colors"
                            title="Close 50% of position"
                          >
                            Close 50%
                          </button>
                          <button
                            onClick={() => onClosePosition(pos.id, 1)}
                            className="px-2 py-1 rounded bg-rose-500/20 border border-rose-500/40 hover:bg-rose-500/30 text-rose-300 text-[10px] font-bold transition-colors"
                          >
                            Market Close
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}

        {activeTab === 'orders' && (
          <div>
            {pendingOrders.length === 0 ? (
              <div className="text-center py-12 text-stone-500 text-xs">
                No active pending limit or stop orders.
              </div>
            ) : (
              <table className="w-full text-left text-xs font-mono border-collapse">
                <thead>
                  <tr className="border-b border-stone-800 text-[10px] text-stone-500 uppercase">
                    <th className="pb-2">Market</th>
                    <th className="pb-2">Type</th>
                    <th className="pb-2">Side</th>
                    <th className="pb-2">Target Price</th>
                    <th className="pb-2">Amount</th>
                    <th className="pb-2 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-800/50">
                  {pendingOrders.map((order) => (
                    <tr key={order.id} className="hover:bg-stone-800/40 transition-colors">
                      <td className="py-2 font-bold text-stone-100">{order.symbol}</td>
                      <td className="py-2 text-stone-400">{order.type}</td>
                      <td className="py-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          order.side === 'Buy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                        }`}>
                          {order.side}
                        </span>
                      </td>
                      <td className="py-2 text-stone-200">${order.price.toLocaleString()}</td>
                      <td className="py-2 text-stone-300">{order.amount}</td>
                      <td className="py-2 text-right">
                        <button
                          onClick={() => onCancelPendingOrder(order.id)}
                          className="px-2 py-1 rounded bg-stone-800 hover:bg-stone-700 text-stone-400 hover:text-stone-200 text-[10px]"
                        >
                          Cancel
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div>
            {closedTrades.length === 0 ? (
              <div className="text-center py-12 text-stone-500 text-xs">
                No closed trade history yet.
              </div>
            ) : (
              <table className="w-full text-left text-xs font-mono border-collapse">
                <thead>
                  <tr className="border-b border-stone-800 text-[10px] text-stone-500 uppercase">
                    <th className="pb-2">Market</th>
                    <th className="pb-2">Side</th>
                    <th className="pb-2">Entry / Exit</th>
                    <th className="pb-2">Realized PnL</th>
                    <th className="pb-2">Fee Paid</th>
                    <th className="pb-2">Close Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-800/50">
                  {closedTrades.map((trade) => {
                    const isProfit = trade.realizedPnL >= 0;
                    return (
                      <tr key={trade.id} className="hover:bg-stone-800/40 transition-colors">
                        <td className="py-2 font-bold text-stone-100">{trade.symbol}</td>
                        <td className="py-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            trade.side === 'Buy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                          }`}>
                            {trade.side}
                          </span>
                        </td>
                        <td className="py-2 text-stone-300">
                          ${trade.entryPrice.toLocaleString()} → ${trade.exitPrice.toLocaleString()}
                        </td>
                        <td className="py-2 font-bold">
                          <span className={isProfit ? 'text-emerald-400' : 'text-rose-400'}>
                            {isProfit ? '+' : ''}${trade.realizedPnL.toFixed(2)} ({isProfit ? '+' : ''}{trade.realizedPnLPercent.toFixed(2)}%)
                          </span>
                        </td>
                        <td className="py-2 text-stone-500">${trade.fee.toFixed(2)}</td>
                        <td className="py-2 text-stone-400 text-[11px]">{trade.reason}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}

        {activeTab === 'analytics' && (
          <div className="h-48 w-full pt-2">
            <div className="flex justify-between items-center mb-2 text-xs font-mono text-stone-400">
              <span>Account Equity Growth History</span>
              <span>Win Rate: <strong className="text-emerald-400">{winRate.toFixed(1)}%</strong> ({winCount}/{closedTrades.length} Trades)</span>
            </div>
            <ResponsiveContainer width="100%" height="85%">
              <AreaChart data={equityHistory}>
                <XAxis dataKey="time" stroke="#52525b" fontSize={10} />
                <YAxis stroke="#52525b" fontSize={10} domain={['dataMin - 100', 'dataMax + 100']} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', borderRadius: '8px', fontSize: '11px' }}
                  itemStyle={{ color: '#10b981' }}
                />
                <Area type="monotone" dataKey="equity" stroke="#10b981" fill="#10b981" fillOpacity={0.15} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
};
