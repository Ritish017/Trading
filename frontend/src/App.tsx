import React, { useState, useEffect } from 'react';
import { IndexTickerBar, FeedStatusInfo } from './components/IndexTickerBar';
import { TerminalHeader } from './components/TerminalHeader';
import { NSEWatchlist } from './components/NSEWatchlist';
import { IndianCandleChart } from './components/IndianCandleChart';
import { FIIDIITracker } from './components/FIIDIITracker';
import { OptionChainSummary } from './components/OptionChainSummary';
import { SEBIAnnouncementsFeed } from './components/SEBIAnnouncementsFeed';
import { MarketIntelligenceModal } from './components/MarketIntelligenceModal';
import { PaperTradingModal } from './components/PaperTradingModal';
import { CommandPalette } from './components/CommandPalette';
import { AICopilotDrawer } from './components/AICopilotDrawer';
import { ApexLearnSection } from './components/ApexLearnSection';
import { MarketReplayModal } from './components/MarketReplayModal';
import { DataHealthBar } from './components/DataHealthBar';
import { BookOpen, Bot, RotateCcw } from 'lucide-react';

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

import { MarketQuote, MarketProvenance } from './types/marketQuote';

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

function toMarketQuote(raw: any, isIndex = false): MarketQuote {
  const ltp = raw.price ?? raw.value ?? raw.ltp ?? 0;
  const prevClose = raw.prevClose ?? raw.previousClose ?? raw.previous_close ?? ltp;
  const change = raw.change ?? Number((ltp - prevClose).toFixed(2));
  const changePercent = raw.changePercent ?? raw.change_percent ?? (prevClose > 0 ? Number((((ltp - prevClose) / prevClose) * 100).toFixed(2)) : 0);

  return {
    symbol: raw.symbol,
    displayName: raw.name || raw.displayName || raw.symbol,
    exchange: raw.exchange || 'NSE',
    instrumentKey: raw.instrumentKey || raw.instrument_key || raw.symbol,
    instrumentType: isIndex ? 'INDEX' : 'EQUITY',
    ltp: ltp,
    previousClose: prevClose,
    open: raw.open || ltp,
    high: raw.high || ltp,
    low: raw.low || ltp,
    close: ltp,
    change: change,
    changePercent: changePercent,
    volume: raw.volume || 0,
    timestamp: Math.floor(Date.now() / 1000),
    receivedAt: raw.receivedAt || Date.now(),
    dataAgeMs: raw.receivedAt ? Math.max(0, Date.now() - raw.receivedAt) : 0,
    source: (raw.source as MarketProvenance) || 'UPSTOX',
    marketStatus: raw.marketStatus || 'LIVE'
  };
}

export default function App() {
  // 1. Core State with robust localStorage validation
  const [indices, setIndices] = useState<MarketIndex[]>(INITIAL_INDICES);
  const [stocks, setStocks] = useState<NSEStock[]>(() => {
    try {
      const saved = localStorage.getItem('apexnse_stocks');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0 && parsed[0] && typeof parsed[0].symbol === 'string') {
          return parsed;
        }
      }
    } catch {
      // fallback
    }
    return INITIAL_NSE_STOCKS;
  });

  const [selectedSymbol, setSelectedSymbol] = useState<string>('RELIANCE.NS');
  const selectedStock = (stocks && stocks.find((s) => s && s.symbol === selectedSymbol)) || (stocks && stocks[0]) || INITIAL_NSE_STOCKS[0];

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [timeframe, setTimeframe] = useState<'1m' | '5m' | '15m' | '1h' | '1D'>('5m');
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [restHealthy, setRestHealthy] = useState<boolean>(true);
  const [lastTickTimeMs, setLastTickTimeMs] = useState<number>(Date.now());
  const [feedStatus, setFeedStatus] = useState<FeedStatusInfo>({
    status: 'INITIALIZING',
    mode: 'LIVE',
    active_provider: 'UPSTOX',
    is_live: false,
  });

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
    try {
      const saved = localStorage.getItem('apexnse_balance');
      return saved ? Number(saved) : 1000000;
    } catch {
      return 1000000;
    }
  });

  const [paperPositions, setPaperPositions] = useState<PaperPosition[]>(() => {
    try {
      const saved = localStorage.getItem('apexnse_positions');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Modals & Auxiliary Views State
  const [isAIModalOpen, setIsAIModalOpen] = useState<boolean>(false);
  const [aiReport, setAiReport] = useState<IndianMarketAIReport | null>(null);
  const [isAILoading, setIsAILoading] = useState<boolean>(false);
  const [isPaperModalOpen, setIsPaperModalOpen] = useState<boolean>(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState<boolean>(false);
  const [isCopilotOpen, setIsCopilotOpen] = useState<boolean>(false);
  const [isLearnOpen, setIsLearnOpen] = useState<boolean>(false);
  const [isReplayOpen, setIsReplayOpen] = useState<boolean>(false);

  // Persistence Effects
  useEffect(() => {
    if (stocks && stocks.length > 0) {
      localStorage.setItem('apexnse_stocks', JSON.stringify(stocks));
    }
  }, [stocks]);

  useEffect(() => {
    localStorage.setItem('apexnse_balance', paperBalance.toString());
  }, [paperBalance]);

  useEffect(() => {
    localStorage.setItem('apexnse_positions', JSON.stringify(paperPositions));
  }, [paperPositions]);

  // Poll /health/data-feed to track Provider Status (LIVE vs SIMULATED vs DISCONNECTED)
  useEffect(() => {
    const checkFeedHealth = async () => {
      try {
        const res = await fetch('/health/data-feed');
        if (res.ok) {
          const data = await res.json();
          setFeedStatus(data);
          setRestHealthy(true);
        } else {
          setRestHealthy(false);
        }
      } catch {
        setRestHealthy(false);
        setFeedStatus((prev) => ({
          ...prev,
          status: 'DISCONNECTED',
          is_live: false,
        }));
      }
    };
    checkFeedHealth();
    const interval = setInterval(checkFeedHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch real market quotes from Upstox REST endpoint on load and periodically
  useEffect(() => {
    const fetchRealQuotes = async () => {
      try {
        const symbolList = (stocks || [])
          .map((s) => s.symbol)
          .concat(['NIFTY 50', 'BANKNIFTY', 'INDIA VIX', 'SENSEX', 'NIFTY IT'])
          .join(',');
        const res = await fetch(`/api/market/quotes?symbols=${encodeURIComponent(symbolList)}`);
        if (res.ok) {
          setRestHealthy(true);
          const quotes: Array<any> = await res.json();
          if (Array.isArray(quotes) && quotes.length > 0) {
            const now = Date.now();
            setLastTickTimeMs(now);

            setStocks((prev) =>
              (prev || []).map((stock) => {
                const q = quotes.find((item) => item && (item.symbol === stock.symbol || item.instrument_key === stock.symbol));
                if (!q || !q.ltp) return stock;
                const newPrice = q.ltp;
                const prevClose = q.previous_close || stock.prevClose || newPrice;
                const priceDiff = newPrice - prevClose;
                return {
                  ...stock,
                  price: newPrice,
                  change: q.change ?? Number((newPrice - prevClose).toFixed(2)),
                  changePercent: q.change_percent ?? Number(((priceDiff / prevClose) * 100).toFixed(2)),
                  high: q.high ? Math.max(q.high, newPrice) : stock.high,
                  low: q.low ? Math.min(q.low, newPrice) : stock.low,
                  open: q.open || stock.open,
                  prevClose: prevClose,
                  vwap: Number((stock.vwap * 0.9 + newPrice * 0.1).toFixed(2)),
                };
              })
            );

            setIndices((prev) =>
              (prev || []).map((idx) => {
                const q = quotes.find((item) => item && (item.symbol === idx.symbol || item.instrument_key === idx.symbol));
                if (!q || !q.ltp) return idx;
                const newLtp = q.ltp;
                const pClose = q.previous_close || idx.value || newLtp;
                return {
                  ...idx,
                  value: newLtp,
                  change: q.change ?? Number((newLtp - pClose).toFixed(2)),
                  changePercent: q.change_percent ?? Number((((newLtp - pClose) / pClose) * 100).toFixed(2)),
                };
              })
            );
          }
        } else {
          setRestHealthy(false);
        }
      } catch {
        setRestHealthy(false);
      }
    };
    fetchRealQuotes();
    const interval = setInterval(fetchRealQuotes, 6000);
    return () => clearInterval(interval);
  }, []);

  // Fetch real candles for selected stock from Upstox REST endpoint
  useEffect(() => {
    const fetchRealCandles = async () => {
      try {
        const res = await fetch(`/api/market/candles/${encodeURIComponent(selectedSymbol)}?interval=${timeframe}&count=100`);
        if (res.ok) {
          const data = await res.json();
          if (data && Array.isArray(data.candles) && data.candles.length > 0) {
            const formattedCandles: IndianCandle[] = data.candles.map((c: any) => ({
              time: typeof c.timestamp === 'number' ? c.timestamp : Math.floor(new Date(c.timestamp || c.time).getTime() / 1000),
              open: c.open,
              high: c.high,
              low: c.low,
              close: c.close,
              volume: c.volume || 5000,
              vwap: c.vwap || c.close,
            }));
            setCandles((prev) => ({
              ...prev,
              [selectedSymbol]: formattedCandles,
            }));
          }
        }
      } catch {
        // quiet fallback
      }
    };
    fetchRealCandles();
  }, [selectedSymbol, timeframe]);

  // Option Chain, FII/DII, Market Breadth, and Announcements Data Hooks
  const [optionChainData, setOptionChainData] = useState<OptionChainType | null>(null);
  const [fiiDiiData, setFiiDiiData] = useState<FIIDIINetFlow | null>(null);
  const [marketBreadthData, setMarketBreadthData] = useState<MarketBreadth | null>(null);
  const [sebiAnnouncements, setSebiAnnouncements] = useState<SEBIAnnouncement[]>([]);

  useEffect(() => {
    const fetchRealOptionChain = async () => {
      try {
        const res = await fetch(`/api/market/option-chain/${encodeURIComponent(selectedSymbol)}`);
        if (res.ok) {
          const data = await res.json();
          if (data && data.spotPrice) {
            setOptionChainData(data);
          }
        }
      } catch {
        // quiet fallback
      }
    };
    fetchRealOptionChain();
  }, [selectedSymbol]);

  useEffect(() => {
    const fetchMarketInfo = async () => {
      try {
        const fiiRes = await fetch('/api/market/fii-dii');
        if (fiiRes.ok) {
          const fiiData = await fiiRes.json();
          if (fiiData && fiiData.fiiCashNetCr !== undefined) {
            setFiiDiiData(fiiData);
          }
        }

        const breadthRes = await fetch('/api/market/breadth');
        if (breadthRes.ok) {
          const bData = await breadthRes.json();
          if (bData && bData.advances !== undefined) {
            setMarketBreadthData(bData);
          }
        }

        const annRes = await fetch('/api/market/announcements');
        if (annRes.ok) {
          const annData = await annRes.json();
          if (Array.isArray(annData) && annData.length > 0) {
            setSebiAnnouncements(annData);
          }
        }
      } catch {
        // quiet fallback
      }
    };
    fetchMarketInfo();
  }, []);

  // Connect to FastAPI WebSocket `/ws/ticks` Feed
  useEffect(() => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    const wsUrl = `${wsProtocol}//${wsHost}/ws/ticks`;
    
    let ws: WebSocket | null = null;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'TICK' && payload.data) {
            const tick = payload.data;
            setLastTickTimeMs(Date.now());

            setStocks((prev) =>
              (prev || []).map((s) => {
                if (!s || !s.symbol) return s;
                if (s.symbol === tick.symbol || s.symbol === tick.instrument_key) {
                  const newPrice = tick.ltp;
                  const prevClose = tick.previous_close || s.prevClose || newPrice;
                  const priceDiff = newPrice - prevClose;
                  return {
                    ...s,
                    price: newPrice,
                    change: Number((newPrice - prevClose).toFixed(2)),
                    changePercent: Number(((priceDiff / prevClose) * 100).toFixed(2)),
                    high: Math.max(s.high, newPrice),
                    low: Math.min(s.low, newPrice),
                    vwap: Number((s.vwap * 0.9 + newPrice * 0.1).toFixed(2)),
                  };
                }
                return s;
              })
            );
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onerror = () => {
        setWsConnected(false);
      };

      ws.onclose = () => {
        setWsConnected(false);
      };
    } catch {
      setWsConnected(false);
    }

    return () => {
      if (ws) ws.close();
    };
  }, []);

  // Sync Candlestick History and Positions PnL on Tick
  useEffect(() => {
    if (!selectedStock || !selectedStock.price) return;
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
          volume: 5000,
          vwap: currentPrice,
        };
        return {
          ...prev,
          [selectedSymbol]: [...currentCandles.slice(-199), newCandle],
        };
      } else {
        const updatedLast: IndianCandle = {
          ...lastCandle,
          high: Math.max(lastCandle.high, currentPrice),
          low: Math.min(lastCandle.low, currentPrice),
          close: currentPrice,
          vwap: Number((lastCandle.vwap * 0.95 + currentPrice * 0.05).toFixed(2)),
        };
        return {
          ...prev,
          [selectedSymbol]: [...currentCandles.slice(0, -1), updatedLast],
        };
      }
    });

    setPaperPositions((prev) =>
      prev.map((pos) => {
        if (pos.symbol === selectedSymbol) {
          const priceDiff = pos.side === 'BUY' ? currentPrice - pos.entryPrice : pos.entryPrice - currentPrice;
          const unPnL = Number((priceDiff * pos.quantity).toFixed(2));
          const unPnLPct = Number(((priceDiff / pos.entryPrice) * 100).toFixed(2));
          return {
            ...pos,
            currentPrice: currentPrice,
            unrealizedPnL: unPnL,
            unrealizedPnLPercent: unPnLPct,
          };
        }
        return pos;
      })
    );
  }, [selectedStock?.price, selectedSymbol]);

  // Handlers for AI, Paper Trading & Command Palette
  const handleGenerateAIReport = async (symbol: string) => {
    setIsAILoading(true);
    setIsAIModalOpen(true);
    try {
      const targetStock = stocks.find((s) => s.symbol === symbol) || selectedStock;
      const report = generateLocalIndianAIReport(targetStock);
      setAiReport(report);
    } catch {
      // quiet fallback
    } finally {
      setIsAILoading(false);
    }
  };

  const handlePlacePaperOrder = (order: {
    symbol: string;
    productType: 'CNC (Delivery)' | 'MIS (Intraday)';
    side: 'BUY' | 'SELL';
    quantity: number;
    targetPrice?: number;
    stopLoss?: number;
  }) => {
    const targetStock = stocks.find((s) => s.symbol === order.symbol) || selectedStock;
    const requiredCapital = targetStock.price * order.quantity;

    if (order.side === 'BUY' && paperBalance < requiredCapital) {
      alert('Insufficient Paper Trading Margin Balance!');
      return;
    }

    const newPos: PaperPosition = {
      id: 'pos_' + Date.now(),
      symbol: targetStock.symbol,
      companyName: targetStock.name,
      productType: order.productType,
      side: order.side,
      quantity: order.quantity,
      entryPrice: targetStock.price,
      currentPrice: targetStock.price,
      unrealizedPnL: 0,
      unrealizedPnLPercent: 0,
      targetPrice: order.targetPrice,
      stopLoss: order.stopLoss,
      timestamp: Date.now(),
    };

    if (order.side === 'BUY') {
      setPaperBalance((prev) => prev - requiredCapital);
    }
    setPaperPositions((prev) => [newPos, ...prev]);
  };

  const handleClosePaperPosition = (id: string) => {
    const pos = paperPositions.find((p) => p.id === id);
    if (!pos) return;

    const returnAmount = pos.quantity * pos.currentPrice + pos.unrealizedPnL;
    setPaperBalance((prev) => prev + returnAmount);
    setPaperPositions((prev) => prev.filter((p) => p.id !== id));
  };

  const handleCommandPaletteAction = (action: string, payload?: any) => {
    if (action === 'SELECT_STOCK' && payload) {
      setSelectedSymbol(payload.symbol);
    } else if (action === 'AI_REPORT' && payload) {
      handleGenerateAIReport(payload.symbol);
    } else if (action === 'PAPER_TRADE') {
      setIsPaperModalOpen(true);
    }
  };

  const filteredStocks = (stocks || []).filter((s) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q) || s.sector.toLowerCase().includes(q);
  });

  const indexQuotes: MarketQuote[] = (indices || []).map((idx) => toMarketQuote(idx, true));

  return (
    <div className="min-h-screen bg-[#0f1015] text-stone-100 flex flex-col font-sans selection:bg-amber-900 selection:text-amber-100">
      {/* 1. Top Live NSE/BSE Index Ticker Bar with Live Data Badge */}
      <IndexTickerBar
        indices={indexQuotes}
        feedStatus={feedStatus}
        onSelectIndex={() => {}}
      />

      {/* 2. Main Terminal Header */}
      <TerminalHeader
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        fiiDiiFlow={fiiDiiData || INITIAL_FII_DII_FLOWS[0]}
        breadth={marketBreadthData || INITIAL_MARKET_BREADTH}
        onOpenAIIntelligence={() => handleGenerateAIReport(selectedSymbol)}
        onOpenPaperTrading={() => setIsPaperModalOpen(true)}
      />

      {/* Quick Action Navigation Bar */}
      <div className="bg-[#12131a] border-b border-stone-800 px-4 py-1.5 flex flex-wrap items-center justify-between gap-y-1.5 font-mono text-xs text-stone-400">
        <div className="flex items-center space-x-3 flex-wrap gap-y-1">
          <button
            onClick={() => setIsCommandPaletteOpen(true)}
            className="flex items-center space-x-1.5 bg-stone-800 hover:bg-stone-700 px-2.5 py-1 rounded text-stone-200 transition-colors"
          >
            <span className="font-bold text-amber-400">⌘K</span>
            <span className="hidden sm:inline">Command Palette</span>
          </button>

          <button
            onClick={() => setIsReplayOpen(true)}
            className="flex items-center space-x-1 hover:text-stone-200 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5 text-sky-400" />
            <span className="hidden sm:inline">Market Replay Mode</span>
          </button>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setIsLearnOpen(true)}
            className="flex items-center space-x-1 text-amber-400 hover:text-amber-300 transition-colors font-bold"
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Apex Quant Learn</span>
          </button>

          <button
            onClick={() => setIsCopilotOpen(true)}
            className="flex items-center space-x-1 text-indigo-400 hover:text-indigo-300 transition-colors font-bold"
          >
            <Bot className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">AI Copilot</span>
          </button>
        </div>
      </div>

      {/* Main Terminal Grid Dashboard */}
      <div className="flex-1 p-3 grid grid-cols-1 md:grid-cols-12 gap-3">
        {/* Left Panel: Watchlist */}
        <div className="md:col-span-3 md:h-[calc(100vh-170px)] flex flex-col min-h-0">
          <NSEWatchlist
            stocks={filteredStocks}
            selectedStock={selectedStock}
            onSelectStock={(st) => setSelectedSymbol(st?.symbol || 'RELIANCE.NS')}
            onToggleFavorite={(sym) => setStocks((prev) => (prev || []).map((s) => s.symbol === sym ? { ...s, isFavorite: !s.isFavorite } : s))}
            onOpenAIForStock={(st) => handleGenerateAIReport(st?.symbol || selectedSymbol)}
          />
        </div>

        {/* Center Panel: Main Chart & Option Chain */}
        <div className="md:col-span-6 flex flex-col space-y-3 md:h-[calc(100vh-170px)] md:overflow-y-auto custom-scrollbar pr-0.5">
          <IndianCandleChart
            symbol={selectedStock?.symbol || 'RELIANCE.NS'}
            name={selectedStock?.name || 'Reliance Industries'}
            price={selectedStock?.price || 2845.5}
            change={selectedStock?.change || 0}
            changePercent={selectedStock?.changePercent || 0}
            candles={candles[selectedSymbol] || []}
            timeframe={timeframe}
            onTimeframeChange={setTimeframe}
          />

          <OptionChainSummary
            symbol={selectedStock?.symbol || 'RELIANCE.NS'}
            price={selectedStock?.price || 2845.5}
            optionSummary={optionChainData || INITIAL_OPTION_CHAIN}
          />
        </div>

        {/* Right Panel: Institutional FII Flow & Market Intelligence Feeds */}
        <div className="md:col-span-3 flex flex-col space-y-3 md:h-[calc(100vh-170px)] md:overflow-y-auto custom-scrollbar pr-0.5">
          <FIIDIITracker flow={fiiDiiData || INITIAL_FII_DII_FLOWS[0]} />
          <SEBIAnnouncementsFeed announcements={sebiAnnouncements.length > 0 ? sebiAnnouncements : INITIAL_SEBI_ANNOUNCEMENTS} />
        </div>
      </div>

      {/* Data Health & Latency Bottom Status Bar */}
      <DataHealthBar
        provider={(feedStatus.active_provider as MarketProvenance) || 'UPSTOX'}
        status={feedStatus.status === 'SIMULATED' ? 'SIMULATED' : 'LIVE'}
        wsConnected={wsConnected}
        restConnected={restHealthy}
        lastTickTimeMs={lastTickTimeMs}
        subscribedCount={stocks.length}
      />

      {/* Modals & Drawers */}
      <MarketIntelligenceModal
        isOpen={isAIModalOpen}
        onClose={() => setIsAIModalOpen(false)}
        stock={selectedStock}
        report={aiReport}
        isLoading={isAILoading}
        onReScan={(sym) => handleGenerateAIReport(sym)}
      />

      {selectedStock && (
        <PaperTradingModal
          isOpen={isPaperModalOpen}
          onClose={() => setIsPaperModalOpen(false)}
          selectedStock={selectedStock}
          paperBalance={paperBalance}
          positions={paperPositions}
          onPlaceOrder={handlePlacePaperOrder}
          onClosePosition={handleClosePaperPosition}
        />
      )}

      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        stocks={stocks}
        onExecuteAction={handleCommandPaletteAction}
      />

      <AICopilotDrawer
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
        selectedSymbol={selectedSymbol}
      />

      <ApexLearnSection
        isOpen={isLearnOpen}
        onClose={() => setIsLearnOpen(false)}
      />

      <MarketReplayModal
        isOpen={isReplayOpen}
        onClose={() => setIsReplayOpen(false)}
        symbol={selectedSymbol}
      />
    </div>
  );
}
