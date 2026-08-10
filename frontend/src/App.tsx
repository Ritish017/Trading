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
        }
      } catch {
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
          const quotes: Array<any> = await res.json();
          if (Array.isArray(quotes) && quotes.length > 0) {
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
                return {
                  ...idx,
                  value: q.ltp,
                  change: q.change ?? 0,
                  changePercent: q.change_percent ?? 0,
                };
              })
            );
          }
        }
      } catch {
        // quiet fallback
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
              volume: c.volume || Math.floor(Math.random() * 5000) + 1000,
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

  // Connect to FastAPI WebSocket `/ws/ticks` Feed
  useEffect(() => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    const wsUrl = `${wsProtocol}//${wsHost}/ws/ticks`;
    
    let ws: WebSocket | null = null;
    let fallbackInterval: any = null;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setWsConnected(true);
        if (fallbackInterval) clearInterval(fallbackInterval);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'TICK' && payload.data) {
            const tick = payload.data;
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

    // STRICT Fallback simulation rule: Only run client simulation if provider status is SIMULATED.
    // NEVER run simulation silently if backend reports LIVE or DISCONNECTED.
    fallbackInterval = setInterval(() => {
      if (feedStatus.status === 'SIMULATED') {
        setStocks((prevStocks) =>
          (prevStocks || []).map((stock) => {
            if (!stock || !stock.symbol) return stock;
            const volatility = stock.price * 0.0015;
            const delta = (Math.random() - 0.49) * volatility;
            const newPrice = Number(Math.max(stock.price + delta, 1.0).toFixed(2));
            const priceDiff = newPrice - stock.prevClose;
            return {
              ...stock,
              price: newPrice,
              change: Number((newPrice - stock.prevClose).toFixed(2)),
              changePercent: Number(((priceDiff / stock.prevClose) * 100).toFixed(2)),
              high: Math.max(stock.high, newPrice),
              low: Math.min(stock.low, newPrice),
              vwap: Number((stock.vwap * 0.9 + newPrice * 0.1).toFixed(2)),
            };
          })
        );
      }
    }, 1200);

    return () => {
      if (ws) ws.close();
      if (fallbackInterval) clearInterval(fallbackInterval);
    };
  }, [feedStatus.status]);

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
          volume: Math.floor(Math.random() * 5000) + 1000,
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
          vwap: Number(((lastCandle.vwap * 4 + currentPrice) / 5).toFixed(2)),
        };
        return {
          ...prev,
          [selectedSymbol]: [...currentCandles.slice(0, -1), updatedLast],
        };
      }
    });

    setPaperPositions((prev) =>
      (prev || []).map((pos) => {
        if (pos && pos.symbol === selectedSymbol) {
          const diff = currentPrice - pos.entryPrice;
          const pnl = pos.side === 'BUY' ? diff * pos.quantity : -diff * pos.quantity;
          const pnlPct = (pnl / (pos.entryPrice * pos.quantity)) * 100;
          return {
            ...pos,
            currentPrice,
            unrealizedPnL: Number(pnl.toFixed(2)),
            unrealizedPnLPct: Number(pnlPct.toFixed(2)),
          };
        }
        return pos;
      })
    );
  }, [selectedStock?.price, selectedSymbol]);

  const handleGenerateAIReport = async (symbol: string) => {
    const stockObj = (stocks && stocks.find((s) => s && s.symbol === symbol)) || selectedStock;
    if (!stockObj) return;
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
        setAiReport(data);
      } else {
        setAiReport(generateLocalIndianAIReport(stockObj));
      }
    } catch {
      setAiReport(generateLocalIndianAIReport(stockObj));
    } finally {
      setIsAILoading(false);
    }
  };

  const handlePlacePaperOrder = async (order: {
    symbol: string;
    companyName: string;
    productType: 'CNC (Delivery)' | 'MIS (Intraday)';
    side: 'BUY' | 'SELL';
    quantity: number;
    price: number;
    targetPrice?: number;
    stopLoss?: number;
  }) => {
    try {
      await fetch('/api/paper/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(order),
      });
    } catch {
      // Fallback local state handling
    }

    const marginRequired = order.productType === 'MIS (Intraday)' ? (order.quantity * order.price * 0.20) : (order.quantity * order.price);
    setPaperBalance((prev) => prev - marginRequired);

    const newPosition: PaperPosition = {
      id: `pos_${Date.now()}`,
      symbol: order.symbol,
      companyName: order.companyName,
      productType: order.productType,
      side: order.side,
      quantity: order.quantity,
      entryPrice: order.price,
      currentPrice: order.price,
      unrealizedPnL: 0,
      unrealizedPnLPct: 0,
      targetPrice: order.targetPrice,
      stopLoss: order.stopLoss,
      timestamp: Date.now(),
    };
    setPaperPositions((prev) => [newPosition, ...prev]);
  };

  const handleClosePaperPosition = async (id: string) => {
    setPaperPositions((prev) => {
      const pos = (prev || []).find((p) => p && p.id === id);
      if (!pos) return prev;

      const returnedMargin = pos.productType === 'MIS (Intraday)' ? (pos.quantity * pos.entryPrice * 0.20) : (pos.quantity * pos.entryPrice);
      const netCapitalReturned = returnedMargin + pos.unrealizedPnL;

      setPaperBalance((b) => b + netCapitalReturned);
      return prev.filter((p) => p && p.id !== id);
    });
  };

  const handleCommandPaletteAction = (actionId: string, payload?: any) => {
    if (actionId === 'TOGGLE_COMMAND_PALETTE') {
      setIsCommandPaletteOpen((prev) => !prev);
    } else if (actionId === 'SELECT_SYMBOL' && payload) {
      setSelectedSymbol(payload);
    } else if (actionId === 'ANALYZE_STOCK') {
      handleGenerateAIReport(selectedSymbol);
    } else if (actionId === 'OPEN_PAPER_TRADING') {
      setIsPaperModalOpen(true);
    } else if (actionId === 'OPEN_REPLAY') {
      setIsReplayOpen(true);
    } else if (actionId === 'OPEN_LEARN') {
      setIsLearnOpen(true);
    } else if (actionId === 'OPEN_COPILOT') {
      setIsCopilotOpen(true);
    }
  };

  const filteredStocks = searchQuery
    ? (stocks || []).filter(
        (s) =>
          s &&
          s.symbol &&
          (s.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (s.name && s.name.toLowerCase().includes(searchQuery.toLowerCase())) ||
            (s.sector && s.sector.toLowerCase().includes(searchQuery.toLowerCase())))
      )
    : stocks || [];

  return (
    <div className="min-h-screen bg-[#0f1015] text-stone-100 flex flex-col font-sans selection:bg-amber-900 selection:text-amber-100">
      {/* 1. Top Live NSE/BSE Index Ticker Bar with Live Data Badge */}
      <IndexTickerBar
        indices={indices}
        feedStatus={feedStatus}
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

      {/* Quick Action Navigation Bar */}
      <div className="bg-[#12131a] border-b border-stone-800 px-4 py-1.5 flex items-center justify-between font-mono text-xs text-stone-400">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => setIsCommandPaletteOpen(true)}
            className="flex items-center space-x-1.5 bg-stone-800 hover:bg-stone-700 px-2.5 py-1 rounded text-stone-200 transition-colors"
          >
            <span className="font-bold text-amber-400">⌘K</span>
            <span>Command Palette</span>
          </button>

          <button
            onClick={() => setIsReplayOpen(true)}
            className="flex items-center space-x-1 hover:text-stone-200 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5 text-sky-400" />
            <span>Market Replay Mode</span>
          </button>
        </div>

        <div className="flex items-center space-x-4">
          <button
            onClick={() => setIsLearnOpen(true)}
            className="flex items-center space-x-1 text-amber-400 hover:text-amber-300 transition-colors font-bold"
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Apex Quant Learn</span>
          </button>

          <button
            onClick={() => setIsCopilotOpen(true)}
            className="flex items-center space-x-1 text-indigo-400 hover:text-indigo-300 transition-colors font-bold"
          >
            <Bot className="w-3.5 h-3.5" />
            <span>AI Copilot</span>
          </button>
        </div>
      </div>

      {/* Main Terminal Grid Dashboard */}
      <div className="flex-1 p-3 grid grid-cols-1 xl:grid-cols-12 gap-3 overflow-hidden">
        {/* Left Panel: Watchlist */}
        <div className="xl:col-span-3 h-[calc(100vh-145px)] overflow-hidden">
          <NSEWatchlist
            stocks={filteredStocks}
            selectedStock={selectedStock}
            onSelectStock={setSelectedSymbol ? ((st) => setSelectedSymbol(st?.symbol || 'RELIANCE.NS')) : () => {}}
            onToggleFavorite={() => {}}
            onOpenAIForStock={(st) => handleGenerateAIReport(st?.symbol || selectedSymbol)}
          />
        </div>

        {/* Center Panel: Main Chart & Option Chain */}
        <div className="xl:col-span-6 flex flex-col space-y-3 h-[calc(100vh-145px)] overflow-y-auto scrollbar-none">
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
            optionChain={INITIAL_OPTION_CHAIN}
          />
        </div>

        {/* Right Panel: Institutional FII Flow & Market Intelligence Feeds */}
        <div className="xl:col-span-3 flex flex-col space-y-3 h-[calc(100vh-145px)] overflow-y-auto scrollbar-none">
          <FIIDIITracker flow={INITIAL_FII_DII_FLOWS[0]} />
          <SEBIAnnouncementsFeed announcements={INITIAL_SEBI_ANNOUNCEMENTS} />
        </div>
      </div>

      {/* Modals & Drawers */}
      <MarketIntelligenceModal
        isOpen={isAIModalOpen}
        onClose={() => setIsAIModalOpen(false)}
        report={aiReport}
        isLoading={isAILoading}
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
