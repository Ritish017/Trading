import { MarketStatusCode, MarketProvenance } from '../types/marketQuote';

export interface MarketSessionInfo {
  status: MarketStatusCode;
  description: string;
  badgeText: string;
  badgeBg: string;
  badgeTextColor: string;
  badgeBorder: string;
  isSessionActive: boolean;
}

/**
 * Determine if current IST time falls within NSE/BSE market session hours (09:15 - 15:30 IST, Mon-Fri).
 */
export function getISTMarketSessionInfo(lastReceivedMs?: number, isSimulatedMode = false): MarketSessionInfo {
  if (isSimulatedMode) {
    return {
      status: 'SIMULATED',
      description: 'Development Mock Feed Active',
      badgeText: 'SIMULATED · DEV MOCK',
      badgeBg: 'bg-amber-500/10',
      badgeTextColor: 'text-amber-400',
      badgeBorder: 'border-amber-500/30',
      isSessionActive: true,
    };
  }

  // Get current time in Asia/Kolkata timezone (IST)
  const now = new Date();
  const istFormatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Kolkata',
    weekday: 'short',
    hour: 'numeric',
    minute: 'numeric',
    hour12: false,
  });

  const parts = istFormatter.formatToParts(now);
  let weekday = 'Mon';
  let hour = 10;
  let minute = 0;

  for (const part of parts) {
    if (part.type === 'weekday') weekday = part.value;
    if (part.type === 'hour') hour = parseInt(part.value, 10);
    if (part.type === 'minute') minute = parseInt(part.value, 10);
  }

  const isWeekend = weekday === 'Sat' || weekday === 'Sun';
  const minutesSinceMidnight = hour * 60 + minute;
  const preMarketStart = 9 * 60;        // 09:00 IST
  const marketOpen = 9 * 60 + 15;       // 09:15 IST
  const marketClose = 15 * 60 + 30;     // 15:30 IST

  let isSessionActive = false;
  let status: MarketStatusCode = 'MARKET_CLOSED';

  if (!isWeekend) {
    if (minutesSinceMidnight >= marketOpen && minutesSinceMidnight <= marketClose) {
      isSessionActive = true;
      status = 'LIVE';
    } else if (minutesSinceMidnight >= preMarketStart && minutesSinceMidnight < marketOpen) {
      status = 'PRE_MARKET';
    } else {
      status = 'MARKET_CLOSED';
    }
  } else {
    status = 'MARKET_CLOSED';
  }

  // Check tick freshness if tick timestamp is provided
  const dataAgeMs = lastReceivedMs ? Math.max(0, Date.now() - lastReceivedMs) : Infinity;
  if (isSessionActive && dataAgeMs > 15000) {
    status = 'STALE';
  }

  switch (status) {
    case 'LIVE':
      return {
        status: 'LIVE',
        description: 'NSE/BSE Live Trading Session',
        badgeText: 'LIVE · UPSTOX',
        badgeBg: 'bg-emerald-500/10',
        badgeTextColor: 'text-emerald-400',
        badgeBorder: 'border-emerald-500/30',
        isSessionActive: true,
      };
    case 'PRE_MARKET':
      return {
        status: 'PRE_MARKET',
        description: 'NSE Pre-Open Session (09:00 - 09:15 IST)',
        badgeText: 'PRE-MARKET · UPSTOX',
        badgeBg: 'bg-sky-500/10',
        badgeTextColor: 'text-sky-400',
        badgeBorder: 'border-sky-500/30',
        isSessionActive: false,
      };
    case 'STALE':
      return {
        status: 'STALE',
        description: 'Delayed or Stale Market Data',
        badgeText: 'STALE DATA',
        badgeBg: 'bg-yellow-500/10',
        badgeTextColor: 'text-yellow-400',
        badgeBorder: 'border-yellow-500/30',
        isSessionActive: false,
      };
    case 'DISCONNECTED':
      return {
        status: 'DISCONNECTED',
        description: 'WebSocket Connection Interrupted',
        badgeText: 'DATA DISCONNECTED',
        badgeBg: 'bg-rose-500/10',
        badgeTextColor: 'text-rose-400',
        badgeBorder: 'border-rose-500/30',
        isSessionActive: false,
      };
    case 'MARKET_CLOSED':
    default:
      return {
        status: 'MARKET_CLOSED',
        description: 'Market Closed (Regular Hours: 09:15 - 15:30 IST)',
        badgeText: 'MARKET CLOSED · UPSTOX',
        badgeBg: 'bg-sky-500/10',
        badgeTextColor: 'text-sky-400',
        badgeBorder: 'border-sky-500/30',
        isSessionActive: false,
      };
  }
}

/**
 * Format data age in human-readable string (e.g., "240 ms ago", "4.2 s ago", "2h 15m ago").
 */
export function formatDataAge(dataAgeMs: number): string {
  if (!isFinite(dataAgeMs) || dataAgeMs <= 0) return 'Just now';
  if (dataAgeMs < 1000) return `${Math.round(dataAgeMs)} ms ago`;
  if (dataAgeMs < 60000) return `${(dataAgeMs / 1000).toFixed(1)} s ago`;
  const minutes = Math.floor(dataAgeMs / 60000);
  if (minutes < 60) return `${minutes} m ago`;
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  return `${hours}h ${remMinutes}m ago`;
}

/**
 * Get provenance badge styling details.
 */
export function getProvenanceBadge(source: MarketProvenance): { text: string; color: string } {
  switch (source) {
    case 'UPSTOX':
      return { text: 'UPSTOX', color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' };
    case 'FYERS':
      return { text: 'FYERS', color: 'text-sky-400 border-sky-500/30 bg-sky-500/10' };
    case 'DERIVED':
      return { text: 'DERIVED', color: 'text-purple-400 border-purple-500/30 bg-purple-500/10' };
    case 'GEMINI_AI':
      return { text: 'GEMINI AI', color: 'text-amber-400 border-amber-500/30 bg-amber-500/10' };
    case 'DEV_MOCK':
    default:
      return { text: 'MOCK', color: 'text-orange-400 border-orange-500/30 bg-orange-500/10' };
  }
}
