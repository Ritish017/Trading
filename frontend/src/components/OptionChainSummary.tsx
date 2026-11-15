import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { OptionChainSummary as OptionChainType, OptionStrikeData } from '../types/indianMarket';
import { BarChart3, AlertCircle, RefreshCw, Calendar, Filter, Zap, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { getAuthHeaders } from '../utils/auth';

interface OptionChainSummaryProps {
  optionSummary?: OptionChainType | null;
  optionChain?: OptionChainType | null;
  symbol?: string;
  price?: number;
  onTradeOption?: (order: { symbol: string; side: 'BUY' | 'SELL'; price: number; strike: number; type: 'CE' | 'PE' }) => void;
}

export const OptionChainSummary: React.FC<OptionChainSummaryProps> = ({
  optionSummary,
  optionChain,
  symbol,
  price,
  onTradeOption,
}) => {
  const sym = symbol || optionSummary?.symbol || optionChain?.symbol || 'NIFTY 50';
  const [activeData, setActiveData] = useState<OptionChainType | null>(optionSummary || optionChain || null);
  const [selectedExpiry, setSelectedExpiry] = useState<string>('');
  const [strikeFilter, setStrikeFilter] = useState<'ATM_10' | 'ATM_20' | 'ALL'>('ATM_10');
  const [loading, setLoading] = useState<boolean>(false);
  const [strikeSearch, setStrikeSearch] = useState<string>('');

  // Fetch real option chain from backend
  const fetchChain = useCallback(async (targetSymbol: string, expiry?: string) => {
    setLoading(true);
    try {
      let url = `/api/market/option-chain/${encodeURIComponent(targetSymbol)}`;
      if (expiry) {
        url += `?expiry=${encodeURIComponent(expiry)}`;
      }
      const res = await fetch(url, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        if (data && data.status === 'AVAILABLE') {
          setActiveData(data);
          if (data.expiryDate && (!selectedExpiry || !expiry)) {
            setSelectedExpiry(data.expiryDate);
          }
        }
      }
    } catch (err) {
      console.warn('Failed to fetch option chain:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedExpiry]);

  // Refetch when symbol changes
  useEffect(() => {
    fetchChain(sym);
  }, [sym, fetchChain]);

  // Handle user picking a different expiry date
  const handleExpiryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newExp = e.target.value;
    setSelectedExpiry(newExp);
    fetchChain(sym, newExp);
  };

  const currentSummary = activeData || optionSummary || optionChain;
  const spotPrice = price ?? currentSummary?.spotPrice ?? 0;
  const atmStrike = currentSummary?.atmStrike ?? (spotPrice > 0 ? Math.round(spotPrice / 50) * 50 : 0);
  const pcr = currentSummary?.pcr ?? 1.0;
  const maxPainStrike = currentSummary?.maxPainStrike ?? atmStrike;
  const totalCallOI = currentSummary?.totalCallOI ?? 0;
  const totalPutOI = currentSummary?.totalPutOI ?? 0;
  const impliedVolatility = currentSummary?.impliedVolatility ?? 15.0;
  const expiryDate = selectedExpiry || currentSummary?.expiryDate || 'NEAR';
  const availableExpiries = currentSummary?.available_expiries || [];
  const rawStrikes: OptionStrikeData[] = currentSummary?.strikes || [];

  // Filter strikes based on range around ATM
  const filteredStrikes = useMemo(() => {
    if (!rawStrikes || rawStrikes.length === 0) return [];

    let list = [...rawStrikes].sort((a, b) => a.strike - b.strike);

    if (strikeSearch.trim()) {
      const q = strikeSearch.trim();
      return list.filter((s) => s.strike.toString().includes(q));
    }

    if (strikeFilter === 'ALL') {
      return list;
    }

    // Find index closest to ATM
    let closestIdx = 0;
    let minDiff = Infinity;
    list.forEach((s, idx) => {
      const diff = Math.abs(s.strike - (atmStrike || spotPrice));
      if (diff < minDiff) {
        minDiff = diff;
        closestIdx = idx;
      }
    });

    const window = strikeFilter === 'ATM_10' ? 10 : 20;
    const start = Math.max(0, closestIdx - window);
    const end = Math.min(list.length, closestIdx + window + 1);

    return list.slice(start, end);
  }, [rawStrikes, strikeFilter, strikeSearch, atmStrike, spotPrice]);

  // Format quantities
  const fmtOI = (oi: number) => {
    if (oi >= 100000) {
      return `${(oi / 100000).toFixed(2)}L`;
    }
    if (oi >= 1000) {
      return `${(oi / 1000).toFixed(1)}k`;
    }
    return oi.toString();
  };

  // PCR Signal interpretation
  let pcrSignal = 'Neutral';
  let pcrColor = 'text-amber-400 bg-amber-500/10 border-amber-500/30';
  if (pcr > 1.15) {
    pcrSignal = 'Bullish (Put Writing)';
    pcrColor = 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
  } else if (pcr < 0.85) {
    pcrSignal = 'Bearish (Call Writing)';
    pcrColor = 'text-rose-400 bg-rose-500/10 border-rose-500/30';
  }

  const callOIFmt = totalCallOI >= 100000 ? `${(totalCallOI / 100000).toFixed(1)} Lakhs` : totalCallOI.toLocaleString();
  const putOIFmt = totalPutOI >= 100000 ? `${(totalPutOI / 100000).toFixed(1)} Lakhs` : totalPutOI.toLocaleString();
  const totalOI = (totalPutOI + totalCallOI) || 1;

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 select-none flex flex-col space-y-4 shadow-2xl">
      {/* Top Header & Analytics */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-800/80 pb-3">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-amber-500/15 border border-amber-500/30 text-amber-400 flex items-center justify-center font-bold">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-extrabold text-white font-mono tracking-wide">
                {sym} Live Option Chain Matrix
              </h3>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                UPSTOX F&amp;O FEED
              </span>
            </div>
            <span className="text-xs text-stone-400">
              Complete strike matrix with live Bid/Ask, Greeks, and real-time LTPs
            </span>
          </div>
        </div>

        {/* Expiry Selector & Filter Controls */}
        <div className="flex items-center space-x-2 text-xs font-mono">
          {/* Expiry Dropdown */}
          <div className="flex items-center space-x-1.5 bg-[#14151b] border border-stone-700/80 px-2.5 py-1.5 rounded-lg">
            <Calendar className="w-3.5 h-3.5 text-stone-400" />
            <span className="text-[10px] text-stone-500 uppercase">Expiry:</span>
            {availableExpiries && availableExpiries.length > 0 ? (
              <select
                value={expiryDate}
                onChange={handleExpiryChange}
                className="bg-transparent text-amber-300 font-bold focus:outline-none cursor-pointer"
              >
                {availableExpiries.map((exp) => (
                  <option key={exp} value={exp} className="bg-stone-900 text-white">
                    {exp}
                  </option>
                ))}
              </select>
            ) : (
              <span className="text-amber-300 font-bold">{expiryDate}</span>
            )}
          </div>

          {/* Range Filter */}
          <div className="flex items-center bg-[#14151b] border border-stone-700/80 rounded-lg p-0.5">
            <button
              onClick={() => setStrikeFilter('ATM_10')}
              className={`px-2 py-1 rounded text-[10px] font-bold transition ${
                strikeFilter === 'ATM_10' ? 'bg-amber-500 text-black' : 'text-stone-400 hover:text-white'
              }`}
            >
              ±10 ATM
            </button>
            <button
              onClick={() => setStrikeFilter('ATM_20')}
              className={`px-2 py-1 rounded text-[10px] font-bold transition ${
                strikeFilter === 'ATM_20' ? 'bg-amber-500 text-black' : 'text-stone-400 hover:text-white'
              }`}
            >
              ±20 ATM
            </button>
            <button
              onClick={() => setStrikeFilter('ALL')}
              className={`px-2 py-1 rounded text-[10px] font-bold transition ${
                strikeFilter === 'ALL' ? 'bg-amber-500 text-black' : 'text-stone-400 hover:text-white'
              }`}
            >
              All Strikes
            </button>
          </div>

          {/* Refresh Button */}
          <button
            onClick={() => fetchChain(sym, expiryDate)}
            disabled={loading}
            className="p-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300 border border-stone-700 transition"
            title="Refresh option chain data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-amber-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Grid Key Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 text-xs font-mono">
        <div className="bg-[#14151b] p-2.5 rounded-xl border border-stone-800/80">
          <div className="text-[10px] text-stone-500 uppercase">Underlying Spot</div>
          <div className="font-black text-sm text-white">
            ₹{spotPrice ? spotPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '24,500.00'}
          </div>
        </div>
        <div className="bg-[#14151b] p-2.5 rounded-xl border border-stone-800/80">
          <div className="text-[10px] text-stone-500 uppercase">ATM Strike</div>
          <div className="font-black text-sm text-amber-400">
            ₹{atmStrike ? atmStrike.toLocaleString() : '24,500'}
          </div>
        </div>
        <div className="bg-[#14151b] p-2.5 rounded-xl border border-stone-800/80">
          <div className="text-[10px] text-stone-500 uppercase">Max Pain Strike</div>
          <div className="font-black text-sm text-sky-400">
            ₹{maxPainStrike ? maxPainStrike.toLocaleString() : '24,500'}
          </div>
        </div>
        <div className="bg-[#14151b] p-2.5 rounded-xl border border-stone-800/80">
          <div className="text-[10px] text-stone-500 uppercase">Put-Call Ratio (PCR)</div>
          <div className={`font-black text-sm ${pcr >= 1.0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {pcr.toFixed(2)} ({pcr >= 1.0 ? 'Bullish' : 'Bearish'})
          </div>
        </div>
        <div className="bg-[#14151b] p-2.5 rounded-xl border border-stone-800/80">
          <div className="text-[10px] text-stone-500 uppercase">Implied Volatility</div>
          <div className="font-black text-sm text-purple-400">
            {impliedVolatility}% IV
          </div>
        </div>
      </div>

      {/* Put vs Call Open Interest Bar */}
      <div className="bg-[#14151b] p-2.5 rounded-xl border border-stone-800/80 space-y-1 font-mono">
        <div className="flex justify-between text-[11px] font-bold">
          <span className="text-emerald-400 flex items-center space-x-1">
            <span>Total Put OI:</span>
            <span>{putOIFmt}</span>
          </span>
          <span className="text-stone-500 text-[10px]">TOTAL OI DISTRIBUTION</span>
          <span className="text-rose-400 flex items-center space-x-1">
            <span>Total Call OI:</span>
            <span>{callOIFmt}</span>
          </span>
        </div>
        <div className="w-full bg-stone-800 h-2 rounded-full overflow-hidden flex">
          <div
            className="bg-emerald-500 h-full transition-all duration-500"
            style={{ width: `${(totalPutOI / totalOI) * 100}%` }}
          />
          <div
            className="bg-rose-500 h-full transition-all duration-500"
            style={{ width: `${(totalCallOI / totalOI) * 100}%` }}
          />
        </div>
      </div>

      {/* The Full Option Chain Table */}
      <div className="bg-[#14151b] border border-stone-800/90 rounded-xl overflow-hidden flex flex-col">
        {/* Table Column Headers */}
        <div className="grid grid-cols-15 bg-[#0f1014] border-b border-stone-800 text-[10px] font-mono font-extrabold uppercase py-2 px-2 text-center select-none">
          {/* CALL HEADERS (7 cols) */}
          <div className="col-span-7 grid grid-cols-6 text-stone-400 border-r border-stone-800/80 pr-2">
            <span className="text-left">Call OI</span>
            <span>Volume</span>
            <span>IV%</span>
            <span>Delta</span>
            <span className="text-stone-500">Bid / Ask</span>
            <span className="text-emerald-400 font-black text-right">Call LTP</span>
          </div>

          {/* STRIKE (1 col) */}
          <div className="col-span-1 text-amber-300 font-black flex items-center justify-center">
            STRIKE
          </div>

          {/* PUT HEADERS (7 cols) */}
          <div className="col-span-7 grid grid-cols-6 text-stone-400 border-l border-stone-800/80 pl-2">
            <span className="text-rose-400 font-black text-left">Put LTP</span>
            <span className="text-stone-500">Bid / Ask</span>
            <span>Delta</span>
            <span>IV%</span>
            <span>Volume</span>
            <span className="text-right">Put OI</span>
          </div>
        </div>

        {/* Table Rows Body */}
        <div className="max-h-[520px] overflow-y-auto divide-y divide-stone-800/40 custom-scrollbar text-xs font-mono">
          {filteredStrikes && filteredStrikes.length > 0 ? (
            filteredStrikes.map((row) => {
              const isAtm = row.strike === atmStrike;
              const isCallItm = spotPrice > 0 && row.strike < spotPrice;
              const isPutItm = spotPrice > 0 && row.strike > spotPrice;

              return (
                <div
                  key={row.strike}
                  className={`grid grid-cols-15 py-1.5 px-2 text-center transition items-center hover:bg-stone-800/50 ${
                    isAtm ? 'bg-amber-500/10 border-y border-amber-500/40 font-bold' : ''
                  }`}
                >
                  {/* CALL SIDE (7 cols) */}
                  <div className={`col-span-7 grid grid-cols-6 items-center border-r border-stone-800/80 pr-2 ${
                    isCallItm ? 'bg-amber-500/5' : ''
                  }`}>
                    <span className="text-stone-400 text-left text-[11px] truncate">
                      {fmtOI(row.call.oi)}
                    </span>
                    <span className="text-stone-500 text-[11px] truncate">
                      {row.call.volume > 0 ? row.call.volume.toLocaleString() : '-'}
                    </span>
                    <span className="text-purple-300 text-[11px]">
                      {row.call.iv ? `${row.call.iv}%` : '-'}
                    </span>
                    <span className="text-stone-400 text-[11px]">
                      {row.call.delta !== undefined && row.call.delta !== null ? row.call.delta.toFixed(2) : '-'}
                    </span>
                    <span className="text-stone-500 text-[10px] truncate">
                      {row.call.bid > 0 ? `₹${row.call.bid.toFixed(1)} / ₹${row.call.ask.toFixed(1)}` : '-'}
                    </span>
                    <div className="text-right">
                      <button
                        onClick={() => {
                          if (onTradeOption && row.call.ltp > 0) {
                            onTradeOption({
                              symbol: `${sym}${row.strike}CE`,
                              side: 'BUY',
                              price: row.call.ltp,
                              strike: row.strike,
                              type: 'CE',
                            });
                          }
                        }}
                        className={`font-black text-xs px-1.5 py-0.5 rounded transition ${
                          row.call.ltp > 0
                            ? 'text-emerald-400 hover:bg-emerald-500/20'
                            : 'text-stone-600'
                        }`}
                        title="Click to trade Call"
                      >
                        ₹{row.call.ltp.toFixed(2)}
                      </button>
                    </div>
                  </div>

                  {/* CENTER STRIKE (1 col) */}
                  <div className={`col-span-1 flex items-center justify-center font-black text-xs ${
                    isAtm ? 'text-amber-300 font-extrabold' : 'text-stone-200'
                  }`}>
                    <span className={`px-2 py-0.5 rounded ${isAtm ? 'bg-amber-500/20 border border-amber-500/50 shadow' : ''}`}>
                      {row.strike.toLocaleString()}
                    </span>
                  </div>

                  {/* PUT SIDE (7 cols) */}
                  <div className={`col-span-7 grid grid-cols-6 items-center border-l border-stone-800/80 pl-2 ${
                    isPutItm ? 'bg-amber-500/5' : ''
                  }`}>
                    <div className="text-left">
                      <button
                        onClick={() => {
                          if (onTradeOption && row.put.ltp > 0) {
                            onTradeOption({
                              symbol: `${sym}${row.strike}PE`,
                              side: 'BUY',
                              price: row.put.ltp,
                              strike: row.strike,
                              type: 'PE',
                            });
                          }
                        }}
                        className={`font-black text-xs px-1.5 py-0.5 rounded transition ${
                          row.put.ltp > 0
                            ? 'text-rose-400 hover:bg-rose-500/20'
                            : 'text-stone-600'
                        }`}
                        title="Click to trade Put"
                      >
                        ₹{row.put.ltp.toFixed(2)}
                      </button>
                    </div>
                    <span className="text-stone-500 text-[10px] truncate">
                      {row.put.bid > 0 ? `₹${row.put.bid.toFixed(1)} / ₹${row.put.ask.toFixed(1)}` : '-'}
                    </span>
                    <span className="text-stone-400 text-[11px]">
                      {row.put.delta !== undefined && row.put.delta !== null ? row.put.delta.toFixed(2) : '-'}
                    </span>
                    <span className="text-purple-300 text-[11px]">
                      {row.put.iv ? `${row.put.iv}%` : '-'}
                    </span>
                    <span className="text-stone-500 text-[11px] truncate">
                      {row.put.volume > 0 ? row.put.volume.toLocaleString() : '-'}
                    </span>
                    <span className="text-stone-400 text-right text-[11px] truncate">
                      {fmtOI(row.put.oi)}
                    </span>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="py-12 flex flex-col items-center justify-center space-y-2 text-stone-500">
              <AlertCircle className="w-6 h-6 text-amber-500" />
              <span className="text-xs">
                {loading ? 'Loading live strikes and Greeks from exchange...' : 'No option strikes found for the selected expiry.'}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
