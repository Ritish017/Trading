import React, { useState, useEffect } from 'react';
import { IndexTickerBar } from './components/IndexTickerBar';
import { TerminalHeader } from './components/TerminalHeader';
import { NSEWatchlist } from './components/NSEWatchlist';
import { IndianCandleChart } from './components/IndianCandleChart';
import { FIIDIITracker } from './components/FIIDIITracker';
import { OptionChainSummary } from './components/OptionChainSummary';
import { SEBIAnnouncementsFeed } from './components/SEBIAnnouncementsFeed';
import { MarketIntelligenceModal } from './components/MarketIntelligenceModal';
import { PaperTradingModal } from './components/PaperTradingModal';

import { 
  NSEStock, 
  MarketIndex, 
  FIIDIINetFlow, 
  MarketBreadth, 
  OptionChainSummary as OptionChainType, 
  SEBIAnnouncement, 
  IndianMarketAIReport, 
  PaperPosition 
} from './types/indianMarket';

import { 
  INITIAL_INDICES, 
  INITIAL_NSE_STOCKS, 
  INITIAL_FII_DII_FLOWS, 
  INITIAL_MARKET_BREADTH, 
  INITIAL_OPTION_CHAIN, 
  INITIAL_SEBI_ANNOUNCEMENTS 
} from './data/indianMarketData';

import { 
  generateInitialIndianCandles, 
  IndianCandle, 
  generateLocalIndianAIReport 
} from './utils/indianTechnicalAnalysis';

export default function App() {
  // 1. Core State
  const [indices, setIndices] = useState<MarketIndex[]>(INITIAL_INDICES);
  const [stocks, setStocks] = useState<NSEStock[]>(() => {
    const saved = localStorage.getItem('apexnse_stocks');
    return saved ? JSON.parse(saved) : INITIAL_NSE_STOCKS;
  });

  const [selectedSymbol, setSelectedSymbol] = useState<string>('RELIANCE.NS');
  const selectedStock = stocks.find((s) => s.symbol === selectedSymbol) || stocks[0];

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [timeframe, setTimeframe] = useState<'1m' | '5m' | '15m' | '1h' | '1D'>('5m');

  // Chart Candle History
  const [candles, setCandles] = useState<Record<string, IndianCandle[]>>(() => {
    const initial: Record<string, IndianCandle[]> = {};
    INITIAL_NSE_STOCKS.forEach((s) => {
      initial[s.symbol] = generateInitialIndianCandles(s.price, 60, 300);
    });
    return initial;
  });

  // Paper Trading Account State
  const [paperBalance, setPaperBalance] = useState<number>(() => {
    const saved = localStorage.getItem('apexnse_balance');
    return saved ? Number(saved) : 1000000; // ₹10,00,000 (10 Lakhs INR starting paper capital)
  });

  const [paperPositions, setPaperPositions] = useState<PaperPosition[]>(() => {
    const saved = localStorage.getItem('apexnse_positions');
    return saved ? JSON.parse(saved) : [];
  });

  // Modals & AI State
  const [isAIModalOpen, setIsAIModalOpen] = useState<boolean>(false);
  const [aiReport, setAiReport] = useState<IndianMarketAIReport | null>(null);
  const [isAILoading, setIsAILoading] = useState<boolean>(false);
  const [isPaperModalOpen, setIsPaperModalOpen] = useState<boolean>(false);

  // Persistence Effects
  useEffect(() => {
    localStorage.setItem('apexnse_stocks', JSON.stringify(stocks));
  }, [stocks]);

  useEffect(() => {
    localStorage.setItem('apexnse_balance', paperBalance.toString());
  }, [paperBalance]);

  useEffect(() => {
    localStorage.setItem('apexnse_positions', JSON.stringify(paperPositions));
  }, [paperPositions]);

  // Real-time Tick Engine Loop (1.2s Interval)
  useEffect(() => {
    const interval = setInterval(() => {
      setStocks((prevStocks) =>
        prevStocks.map((stock) => {
          const volatility = stock.price * 0.0015;
          const delta = (Math.random() - 0.49) * volatility;
          const newPrice = Number(Math.max(stock.price + delta, 1.0).toFixed(2));

          const newHigh = Math.max(stock.high, newPrice);
          const newLow = Math.min(stock.low, newPrice);
          const priceDiff = newPrice - stock.prevClose;
          const newChangePercent = Number(((priceDiff / stock.prevClose) * 100).toFixed(2));
          const newChange = Number((newPrice - stock.prevClose).toFixed(2));

          return {
            ...stock,
            price: newPrice,
            change: newChange,
            changePercent: newChangePercent,
            high: newHigh,
            low: newLow,
            vwap: Number(((stock.vwap * 0.9 + newPrice * 0.1)).toFixed(2)),
          };
        })
      );

      // Tick Indices
      setIndices((prevIndices) =>
        prevIndices.map((idx) => {
          const delta = (Math.random() - 0.48) * (idx.value * 0.0008);
          const newValue = Number((idx.value + delta).toFixed(2));
          const newChangePercent = Number((((newValue - (idx.value - idx.change)) / (idx.value - idx.change)) * 100).toFixed(2));
          return {
            ...idx,
            value: newValue,
            changePercent: newChangePercent,
          };
        })
      );
    }, 1200);

    return () => clearInterval(interval);
  }, []);

  // Sync Candlestick History and Positions PnL on Tick
  useEffect(() => {
    const currentPrice = selectedStock.price;

    setCandles((prev) => {
      const currentCandles = prev[selectedSymbol] || [];
      if (currentCandles.length === 0) return prev;

      const lastCandle = currentCandles[currentCandles.length - 1];
      const nowSec = Math.floor(Date.now() / 1000);

      if (nowSec - lastCandle.time >= 300) {
        const newCandle: IndianCandle = {
          time: nowSec,
          open: currentPrice,
          high: currentPrice,
          low: currentPrice,
          close: currentPrice,
          volumeLakhs: Number((Math.random() * 5 + 1).toFixed(2)),
        };
        return {
          ...prev,
          [selectedSymbol]: [...currentCandles.slice(1), newCandle],
        };
      } else {
        const updatedCandle: IndianCandle = {
          ...lastCandle,
          high: Math.max(lastCandle.high, currentPrice),
          low: Math.min(lastCandle.low, currentPrice),
          close: currentPrice,
          volumeLakhs: Number((lastCandle.volumeLakhs + 0.05).toFixed(2)),
        };
        return {
          ...prev,
          [selectedSymbol]: [...currentCandles.slice(0, -1), updatedCandle],
        };
      }
    });

    // Update Paper Positions PnL
    setPaperPositions((prevPos) =>
      prevPos.map((pos) => {
        const stockObj = stocks.find((s) => s.symbol === pos.symbol);
        const curP = stockObj ? stockObj.price : pos.currentPrice;
        const diff = pos.side === 'BUY' ? curP - pos.entryPrice : pos.entryPrice - curP;
        const unrealizedPnL = diff * pos.quantity;
        const unrealizedPnLPercent = (diff / pos.entryPrice) * 100;

        return {
          ...pos,
          currentPrice: curP,
          unrealizedPnL,
          unrealizedPnLPercent,
        };
      })
    );
  }, [selectedStock.price]);

  // Toggle Stock Favorite
  const handleToggleFavorite = (symbol: string) => {
    setStocks((prev) =>
      prev.map((s) => (s.symbol === symbol ? { ...s, isFavorite: !s.isFavorite } : s))
    );
  };

  // Run Gemini AI Intelligence Analysis for Indian Market
  const handleGenerateAIReport = async (symbol: string) => {
    const stockObj = stocks.find((s) => s.symbol === symbol) || selectedStock;
    setIsAILoading(true);
    setIsAIModalOpen(true);

    try {
      const res = await fetch('/api/indian-market-intelligence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: stockObj.symbol,
          name: stockObj.name,
          sector: stockObj.sector,
          price: stockObj.price,
          change24h: stockObj.changePercent,
          niftyPrice: indices[0]?.value || 24580,
          fiiFlow: '+1,840.5',
          diiFlow: '+1,210.8',
          pcr: 1.18,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.error === 'GEMINI_API_KEY_NOT_SET') {
          setAiReport(generateLocalIndianAIReport(stockObj));
        } else {
          setAiReport(data);
        }
      } else {
        setAiReport(generateLocalIndianAIReport(stockObj));
      }
    } catch {
      setAiReport(generateLocalIndianAIReport(stockObj));
    } finally {
      setIsAILoading(false);
    }
  };

  // Place Paper Order
  const handlePlacePaperOrder = (order: {
    symbol: string;
    companyName: string;
    productType: 'CNC (Delivery)' | 'MIS (Intraday)';
    side: 'BUY' | 'SELL';
    quantity: number;
    price: number;
    targetPrice?: number;
    stopLoss?: number;
  }) => {
    const totalVal = order.quantity * order.price;
    const reqMargin = order.productType === 'MIS (Intraday)' ? totalVal * 0.20 : totalVal;

    if (reqMargin > paperBalance) return;

    setPaperBalance((prev) => prev - reqMargin);

    const newPosition: PaperPosition = {
      id: `paper-${Date.now()}`,
      symbol: order.symbol,
      companyName: order.companyName,
      productType: order.productType,
      side: order.side,
      quantity: order.quantity,
      entryPrice: order.price,
      currentPrice: order.price,
      unrealizedPnL: 0,
      unrealizedPnLPercent: 0,
      targetPrice: order.targetPrice,
      stopLoss: order.stopLoss,
      timestamp: Date.now(),
    };

    setPaperPositions((prev) => [newPosition, ...prev]);
  };

  // Close Paper Position
  const handleClosePaperPosition = (id: string) => {
    setPaperPositions((prev) => {
      const pos = prev.find((p) => p.id === id);
      if (!pos) return prev;

      const totalVal = pos.quantity * pos.currentPrice;
      const returnedMargin = pos.productType === 'MIS (Intraday)' ? (pos.quantity * pos.entryPrice * 0.20) : (pos.quantity * pos.entryPrice);
      const netCapitalReturned = returnedMargin + pos.unrealizedPnL;

      setPaperBalance((b) => b + netCapitalReturned);
      return prev.filter((p) => p.id !== id);
    });
  };

  const filteredStocks = searchQuery
    ? stocks.filter(
        (s) =>
          s.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
          s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          s.sector.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : stocks;

  return (
    <div className="min-h-screen bg-[#0f1015] text-stone-100 flex flex-col font-sans selection:bg-amber-900 selection:text-amber-100">
      {/* 1. Top Live NSE/BSE Index Ticker Bar */}
      <IndexTickerBar
        indices={indices}
        onSelectIndex={() => {}}
      />

      {/* 2. Main Terminal Header */}
      <TerminalHeader
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        fiiDiiFlow={INITIAL_FII_DII_FLOWS[0]}
        breadth={INITIAL_MARKET_BREADTH}
        onOpenAIIntelligence={() => handleGenerateAIReport(selectedSymbol)}
        onOpenPaperTrading={() => setIsPaperModalOpen(true)}
      />

      {/* 3. Primary Market Intelligence Workspace Layout */}
      <main className="flex-1 p-4 space-y-4 max-w-[1700px] w-full mx-auto overflow-x-hidden">
        {/* Top Workspace Grid: Candlestick Chart (8 cols) + FII/DII & Option Chain (4 cols) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <div className="lg:col-span-8 h-[420px]">
            <IndianCandleChart
              stock={selectedStock}
              candles={candles[selectedSymbol] || []}
              timeframe={timeframe}
              onTimeframeChange={setTimeframe}
            />
          </div>

          <div className="lg:col-span-4 flex flex-col space-y-4">
            <FIIDIITracker flows={INITIAL_FII_DII_FLOWS} />
            <OptionChainSummary optionSummary={INITIAL_OPTION_CHAIN} />
          </div>
        </div>

        {/* Middle Workspace: NSE Watchlist & Stock Screener */}
        <NSEWatchlist
          stocks={filteredStocks}
          selectedStock={selectedStock}
          onSelectStock={(stock) => setSelectedSymbol(stock.symbol)}
          onToggleFavorite={handleToggleFavorite}
          onOpenAIForStock={(stock) => handleGenerateAIReport(stock.symbol)}
        />

        {/* Bottom Workspace: SEBI Filings & Corporate Announcements Stream */}
        <SEBIAnnouncementsFeed announcements={INITIAL_SEBI_ANNOUNCEMENTS} />
      </main>

      {/* Modals */}
      <MarketIntelligenceModal
        isOpen={isAIModalOpen}
        onClose={() => setIsAIModalOpen(false)}
        stock={selectedStock}
        report={aiReport}
        isLoading={isAILoading}
        onReScan={handleGenerateAIReport}
      />

      <PaperTradingModal
        isOpen={isPaperModalOpen}
        onClose={() => setIsPaperModalOpen(false)}
        stock={selectedStock}
        availableBalance={paperBalance}
        positions={paperPositions}
        onPlacePaperOrder={handlePlacePaperOrder}
        onClosePosition={handleClosePaperPosition}
      />
    </div>
  );
}
