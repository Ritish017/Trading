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

import { NavigationTabs, ActivePage } from './components/NavigationTabs';
import { TradingTerminalPage } from './components/pages/TradingTerminalPage';
import { IntelligenceDeskPage } from './components/pages/IntelligenceDeskPage';
import { DerivativesLabPage } from './components/pages/DerivativesLabPage';
import { InstitutionalDeskPage } from './components/pages/InstitutionalDeskPage';
import { PortfolioPage } from './components/pages/PortfolioPage';
import { BacktestReplayPage } from './components/pages/BacktestReplayPage';
import { QuantLearnPage } from './components/pages/QuantLearnPage';
import { StrategyLabPage } from './components/pages/StrategyLabPage';
import { FundamentalResearchPage } from './components/pages/FundamentalResearchPage';
import { ResearchFactoryPage } from './components/pages/ResearchFactoryPage';
import { CommandCenterPage } from './components/pages/CommandCenterPage';

import { MarketNarrativeBanner } from './components/intelligence/MarketNarrativeBanner';
import { IntelligenceTimeline } from './components/intelligence/IntelligenceTimeline';
import { SecurityIntelligencePanel } from './components/intelligence/SecurityIntelligencePanel';
import { AICommentary, MarketEvent, MarketNarrative } from './types/intelligence';
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

const STORAGE_VERSION = 'v2.3_corporate_action_aligned';

export default function App() {
  // 1. Core State with robust localStorage validation & cache busting
  const [indices, setIndices] = useState<MarketIndex[]>(INITIAL_INDICES);
  const [stocks, setStocks] = useState<NSEStock[]>(() => {
    try {
      const savedVersion = localStorage.getItem('apexnse_schema_version');
      if (savedVersion !== STORAGE_VERSION) {
        localStorage.setItem('apexnse_schema_version', STORAGE_VERSION);
        localStorage.removeItem('apexnse_stocks');
        return INITIAL_NSE_STOCKS;
      }
      const saved = localStorage.getItem('apexnse_stocks');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length >= INITIAL_NSE_STOCKS.length && parsed[0] && typeof parsed[0].symbol === 'string' && typeof parsed[0].price === 'number') {
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

  // Active Page Workspace State
  const [activePage, setActivePage] = useState<ActivePage>('terminal');

  // AI Market Intelligence Engine State
  const [marketNarrative, setMarketNarrative] = useState<MarketNarrative | undefined>(undefined);
  const [intelligenceEvents, setIntelligenceEvents] = useState<MarketEvent[]>([]);
  const [selectedSymbolIntelligence, setSelectedSymbolIntelligence] = useState<AICommentary | undefined>(undefined);
  const [isNarrativeLoading, setIsNarrativeLoading] = useState<boolean>(false);
  const [isSymbolIntelligenceLoading, setIsSymbolIntelligenceLoading] = useState<boolean>(false);

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
                  vwap: q.vwap ?? stock.vwap ?? 0,
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

  // Fetch AI Market Narrative on Mount
  const fetchMarketNarrative = async () => {
    try {
      setIsNarrativeLoading(true);
      const res = await fetch('/api/intelligence/market-narrative');
      if (res.ok) {
        const data: MarketNarrative = await res.json();
        setMarketNarrative(data);
      }
    } catch {
      // quiet fallback
    } finally {
      setIsNarrativeLoading(false);
    }
  };

  useEffect(() => {
    fetchMarketNarrative();
  }, []);

  // Fetch AI Intelligence Event Timeline Feed
  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const symbolsParam = (stocks || []).slice(0, 10).map((s) => s.symbol).join(',');
        const res = await fetch(`/api/intelligence/feed?symbols=${encodeURIComponent(symbolsParam)}`);
        if (res.ok) {
          const data: MarketEvent[] = await res.json();
          if (Array.isArray(data)) {
            setIntelligenceEvents(data);
          }
        }
      } catch {
        // quiet fallback
      }
    };
    fetchEvents();
    const interval = setInterval(fetchEvents, 12000);
    return () => clearInterval(interval);
  }, [stocks]);

  // Fetch AI Commentary for Active Selected Symbol
  const fetchSymbolIntelligence = async (symbol: string) => {
    try {
      setIsSymbolIntelligenceLoading(true);
      const res = await fetch(`/api/intelligence/symbol/${encodeURIComponent(symbol)}`);
      if (res.ok) {
        const data: AICommentary = await res.json();
        setSelectedSymbolIntelligence(data);
      }
    } catch {
      // quiet fallback
    } finally {
      setIsSymbolIntelligenceLoading(false);
    }
  };

  useEffect(() => {
    if (selectedSymbol) {
      fetchSymbolIntelligence(selectedSymbol);
    }
  }, [selectedSymbol]);

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
                    vwap: tick.vwap || s.vwap || newPrice,
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

  // Fetch initial Paper Trading State from Backend
  useEffect(() => {
    fetch('/api/paper/positions')
      .then((res) => res.json())
      .then((data) => {
        if (data && Array.isArray(data.positions)) {
          setPaperPositions(data.positions);
          if (data.available_capital !== undefined) setPaperBalance(data.available_capital);
        }
      })
      .catch(() => {});
  }, []);

  // Sync Candlestick History and Positions PnL on Tick
  useEffect(() => {
    if (!selectedStock || !selectedStock.price) return;
    const currentPrice = selectedStock.price;

    setCandles((prev) => {
      const currentCandles = prev[selectedSymbol] || [];
      const lastCandle = currentCandles.length > 0 ? currentCandles[currentCandles.length - 1] : null;

      // Discontinuity / Out-of-sync guard:
      // If candle history is empty OR price discrepancy between last synthetic candle and live price is > 18%,
      // smoothly re-seed the series to prevent chart compression / giant vertical distortion bars
      if (!lastCandle || Math.abs(currentPrice - lastCandle.close) / Math.max(lastCandle.close, 1) > 0.18) {
        return {
          ...prev,
          [selectedSymbol]: generateInitialIndianCandles(currentPrice, 60, 300),
        };
      }

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
          vwap: selectedStock.vwap || lastCandle.vwap || currentPrice,
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
      const res = await fetch(`/api/intelligence/symbol/${encodeURIComponent(targetStock.symbol)}`);
      if (res.ok) {
        const data = await res.json();
        setAiReport({
          symbol: targetStock.symbol,
          name: data.company_name || targetStock.name,
          sector: data.sector || targetStock.sector,
          marketStance: data.market_regime || data.classification || 'Neutral Consolidation',
          confidence: Math.round((data.confidence || 0) * 100),
          niftyCorrel: data.macro_context || 'Market Baseline',
          fiiDiiSentiment: data.why_it_matters || 'Neutral Settlement',
          executiveSummary: data.what_changed || data.headline || 'Quantitative market structure analysis.',
          supportLevels: data.bearish_confirmation || [],
          resistanceLevels: data.bullish_confirmation || [],
          technicalMetrics: {
            rsi14: undefined,
            ema20: undefined,
            ema50: undefined,
            vwap: targetStock.vwap,
            pcrSignal: data.likely_drivers?.[0] || 'Neutral',
          },
          catalysts: data.likely_drivers || [data.headline],
          tacticalTradeSetup: {
            action: data.importance || 'MONITOR',
            entryZone: `₹${targetStock.price.toFixed(2)}`,
            target1: data.bullish_confirmation?.[0] || `₹${targetStock.high.toFixed(2)}`,
            target2: `₹${targetStock.high.toFixed(2)}`,
            stopLoss: data.bearish_confirmation?.[0] || `₹${targetStock.low.toFixed(2)}`,
            riskReward: '1 : 2.0',
          },
        });
      } else {
        const fallback = generateLocalIndianAIReport(targetStock);
        setAiReport(fallback);
      }
    } catch {
      const targetStock = stocks.find((s) => s.symbol === symbol) || selectedStock;
      const fallback = generateLocalIndianAIReport(targetStock);
      setAiReport(fallback);
    } finally {
      setIsAILoading(false);
    }
  };

  const handlePlacePaperOrder = async (order: {
    symbol: string;
    productType: 'CNC (Delivery)' | 'MIS (Intraday)';
    side: 'BUY' | 'SELL';
    quantity: number;
    targetPrice?: number;
    stopLoss?: number;
  }) => {
    const targetStock = stocks.find((s) => s.symbol === order.symbol) || selectedStock;
    try {
      const res = await fetch('/api/paper/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: targetStock.symbol,
          companyName: targetStock.name,
          productType: order.productType,
          side: order.side,
          quantity: order.quantity,
          price: targetStock.price,
          targetPrice: order.targetPrice,
          stopLoss: order.stopLoss,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'FILLED' && data.position) {
          setPaperPositions((prev) => [data.position, ...prev]);
          if (data.available_capital !== undefined) setPaperBalance(data.available_capital);
        } else if (data.status === 'REJECTED') {
          alert(`Order Rejected: ${data.reason}`);
        }
      }
    } catch {
      // fallback
    }
  };

  const handleClosePaperPosition = async (id: string, closePrice?: number) => {
    const pos = paperPositions.find((p) => p.id === id);
    if (!pos) return;
    try {
      const res = await fetch(`/api/paper/close/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ close_price: closePrice || pos.currentPrice }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.available_capital !== undefined) setPaperBalance(data.available_capital);
      }
    } catch {
      // quiet
    }
    setPaperPositions((prev) => prev.filter((p) => p.id !== id));
  };

  const handleAddCustomStock = async (sym: string) => {
    const clean = sym.trim().toUpperCase();
    const fullSym = clean.endsWith('.NS') || clean.endsWith('.BO') ? clean : `${clean}.NS`;
    const exists = (stocks || []).find((s) => s.symbol === fullSym || s.symbol === clean);
    if (exists) {
      setSelectedSymbol(exists.symbol);
      return;
    }
    let quoteData: any = null;
    try {
      const res = await fetch(`/api/market/quote/${encodeURIComponent(fullSym)}`);
      if (res.ok) {
        quoteData = await res.json();
      }
    } catch {}

    const price = quoteData?.ltp || 1000.0;
    const prevClose = quoteData?.previous_close || price;
    const newStock: NSEStock = {
      symbol: fullSym,
      bseCode: quoteData?.bse_code || '000000',
      name: quoteData?.company_name || `${clean} Limited`,
      sector: quoteData?.sector || 'NSE Equities',
      price: price,
      change: quoteData?.change || 0,
      changePercent: quoteData?.change_percent || 0,
      open: quoteData?.open || price,
      high: quoteData?.high || price,
      low: quoteData?.low || price,
      prevClose: prevClose,
      volumeLakhs: quoteData?.volume ? Number((quoteData.volume / 100000).toFixed(2)) : 10.0,
      turnoverCr: 50.0,
      marketCapCr: 10000,
      peRatio: 20.0,
      pbRatio: 2.0,
      week52High: quoteData?.week_52_high || Number((price * 1.2).toFixed(2)),
      week52Low: quoteData?.week_52_low || Number((price * 0.8).toFixed(2)),
      vwap: quoteData?.vwap || price,
      upperCircuit: Number((prevClose * 1.1).toFixed(2)),
      lowerCircuit: Number((prevClose * 0.9).toFixed(2)),
      isNifty50: false,
      isFavorite: true,
      sparkline: [price, price, price, price, price, price, price],
    };
    setStocks((prev) => [newStock, ...(prev || [])]);
    setSelectedSymbol(fullSym);
  };

  const handleCommandPaletteAction = (action: string, payload?: any) => {
    if ((action === 'SELECT_STOCK' || action === 'SELECT_SYMBOL') && payload) {
      const sym = typeof payload === 'string' ? payload : (payload.symbol || selectedSymbol);
      handleAddCustomStock(sym);
      setActivePage('terminal');
    } else if (action === 'ANALYZE_STOCK' || action === 'AI_REPORT') {
      if (payload) {
        const sym = typeof payload === 'string' ? payload : payload.symbol;
        setSelectedSymbol(sym);
      }
      setActivePage('intelligence');
    } else if (action === 'OPEN_PAPER_TRADING' || action === 'PAPER_TRADE') {
      setActivePage('portfolio');
    } else if (action === 'RUN_BACKTEST') {
      setActivePage('backtest');
    } else if (action === 'OPEN_REPLAY') {
      setIsReplayOpen(true);
    } else if (action === 'OPEN_LEARN') {
      setActivePage('learn');
    }
  };

  // Typo-tolerant and fuzzy filtering
  const stripVowels = (s: string) => s.replace(/[aeiou\s\-_.]/g, '');

  const filteredStocks = (stocks || []).filter((s) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase().trim();
    const sym = (s.symbol || '').toLowerCase();
    const cleanSym = sym.replace('.ns', '').replace('.bo', '');
    const name = (s.name || '').toLowerCase();
    const sector = (s.sector || '').toLowerCase();

    if (sym.includes(q) || cleanSym.includes(q) || name.includes(q) || sector.includes(q)) return true;
    const qStripped = stripVowels(q);
    const symStripped = stripVowels(cleanSym);
    const nameStripped = stripVowels(name);
    if (qStripped.length >= 2 && (symStripped.includes(qStripped) || nameStripped.includes(qStripped) || qStripped.includes(symStripped))) return true;
    return false;
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
        onOpenAIIntelligence={() => setActivePage('intelligence')}
        onOpenPaperTrading={() => setActivePage('portfolio')}
      />

      {/* 3. Navigation Workspaces Tab Bar */}
      <NavigationTabs
        activePage={activePage}
        onSelectPage={setActivePage}
        eventCount={intelligenceEvents.length}
        openPositionsCount={paperPositions.length}
      />

      {/* 4. Dynamic Modular Workspaces */}
      {activePage === 'terminal' && (
        <TradingTerminalPage
          stocks={filteredStocks}
          selectedStock={selectedStock}
          selectedSymbol={selectedSymbol}
          onSelectStock={(st) => setSelectedSymbol(st?.symbol || 'RELIANCE.NS')}
          onToggleFavorite={(sym) => setStocks((prev) => (prev || []).map((s) => s.symbol === sym ? { ...s, isFavorite: !s.isFavorite } : s))}
          onOpenAIForStock={(st) => {
            setSelectedSymbol(st?.symbol || selectedSymbol);
            setActivePage('intelligence');
          }}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onAddCustomStock={handleAddCustomStock}
          candles={candles[selectedSymbol] || []}
          timeframe={timeframe}
          onTimeframeChange={setTimeframe}
          onQuickBuy={() => setIsPaperModalOpen(true)}
          onQuickSell={() => setIsPaperModalOpen(true)}
        />
      )}

      {activePage === 'intelligence' && (
        <IntelligenceDeskPage
          narrative={marketNarrative}
          isNarrativeLoading={isNarrativeLoading}
          onRefreshNarrative={fetchMarketNarrative}
          events={intelligenceEvents}
          selectedSymbol={selectedSymbol}
          onSelectSymbol={(sym) => setSelectedSymbol(sym)}
          selectedStock={selectedStock}
          commentary={selectedSymbolIntelligence}
          isCommentaryLoading={isSymbolIntelligenceLoading}
          onRefreshCommentary={() => fetchSymbolIntelligence(selectedSymbol)}
        />
      )}

      {activePage === 'derivatives' && (
        <DerivativesLabPage
          stocks={filteredStocks}
          selectedStock={selectedStock}
          onSelectStock={(st) => setSelectedSymbol(st?.symbol || 'RELIANCE.NS')}
          onToggleFavorite={(sym) => setStocks((prev) => (prev || []).map((s) => s.symbol === sym ? { ...s, isFavorite: !s.isFavorite } : s))}
          onOpenAIForStock={(st) => {
            setSelectedSymbol(st?.symbol || selectedSymbol);
            setActivePage('intelligence');
          }}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onAddCustomStock={handleAddCustomStock}
          optionSummary={optionChainData || INITIAL_OPTION_CHAIN}
        />
      )}

      {activePage === 'institutional' && (
        <InstitutionalDeskPage
          fiiDiiFlow={fiiDiiData || INITIAL_FII_DII_FLOWS[0]}
          breadth={marketBreadthData || INITIAL_MARKET_BREADTH}
          announcements={sebiAnnouncements.length > 0 ? sebiAnnouncements : INITIAL_SEBI_ANNOUNCEMENTS}
        />
      )}

      {activePage === 'portfolio' && (
        <PortfolioPage
          balance={paperBalance}
          positions={paperPositions}
          stocks={stocks}
          onOpenOrderModal={() => setIsPaperModalOpen(true)}
          onClosePosition={handleClosePaperPosition}
        />
      )}

      {activePage === 'backtest' && (
        <BacktestReplayPage
          stocks={stocks}
          selectedSymbol={selectedSymbol}
          onOpenReplayModal={() => setIsReplayOpen(true)}
        />
      )}

      {activePage === 'learn' && (
        <QuantLearnPage />
      )}

      {activePage === 'strategylab' && (
        <StrategyLabPage
          stocks={stocks}
          selectedSymbol={selectedSymbol}
          onSelectSymbol={(sym) => setSelectedSymbol(sym)}
        />
      )}

      {activePage === 'fundamentals' && (
        <FundamentalResearchPage
          stocks={stocks}
          selectedSymbol={selectedSymbol}
          onSelectSymbol={(sym) => setSelectedSymbol(sym)}
        />
      )}

      {activePage === 'researchfactory' && (
        <ResearchFactoryPage
          stocks={stocks}
          selectedSymbol={selectedSymbol}
          onSelectSymbol={(sym) => setSelectedSymbol(sym)}
        />
      )}

      {activePage === 'commandcenter' && (
        <CommandCenterPage
          stocks={stocks}
          selectedSymbol={selectedSymbol}
          onSelectSymbol={(sym) => setSelectedSymbol(sym)}
        />
      )}

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
