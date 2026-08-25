import { CanonicalQuote, MarketQuote } from '../types/marketQuote';

/**
 * Client-Side Canonical Quote Store
 * 
 * Reconciles incoming quotes from REST polls and WebSocket ticks.
 * Selection Rule: Newer provider_timestamp wins.
 */
class ClientCanonicalQuoteStore {
  private quotes: Map<string, CanonicalQuote> = new Map();
  private listeners: Set<() => void> = new Set();

  public getQuote(symbol: string): CanonicalQuote | undefined {
    return this.quotes.get(symbol);
  }

  public getAllQuotes(): Record<string, CanonicalQuote> {
    const result: Record<string, CanonicalQuote> = {};
    this.quotes.forEach((v, k) => {
      result[k] = v;
    });
    return result;
  }

  public updateFromREST(rawQuote: any): CanonicalQuote | null {
    if (!rawQuote || !rawQuote.symbol) return null;
    const ltp = rawQuote.ltp ?? rawQuote.price;
    if (ltp === null || ltp === undefined || ltp <= 0) return null;

    const symbol = rawQuote.symbol;
    const existing = this.quotes.get(symbol);
    const incomingTs = Number(rawQuote.provider_timestamp || rawQuote.timestamp || 0);

    // If existing quote has a newer provider timestamp, do not downgrade
    if (existing && existing.provider_timestamp > incomingTs && incomingTs > 0) {
      return existing;
    }

    const prevClose = rawQuote.previous_close ?? rawQuote.prevClose ?? ltp;
    const change = rawQuote.change ?? (prevClose > 0 ? Number((ltp - prevClose).toFixed(2)) : 0);
    const changePct = rawQuote.change_percent ?? rawQuote.changePercent ?? (prevClose > 0 ? Number((((ltp - prevClose) / prevClose) * 100).toFixed(2)) : 0);

    const canonical: CanonicalQuote = {
      symbol: symbol,
      instrument_key: rawQuote.instrument_key || rawQuote.instrumentKey || symbol,
      exchange: rawQuote.exchange || 'NSE',
      ltp: ltp,
      previous_close: prevClose,
      change: change,
      change_percent: changePct,
      open: rawQuote.open ?? ltp,
      high: rawQuote.high ?? ltp,
      low: rawQuote.low ?? ltp,
      volume: rawQuote.volume ?? 0,
      bid: rawQuote.bid ?? null,
      ask: rawQuote.ask ?? null,
      provider: rawQuote.provider || rawQuote.source || 'UPSTOX',
      provider_mode: rawQuote.provider_mode || 'AUTHENTIC_LIVE',
      provider_timestamp: incomingTs > 0 ? incomingTs : Math.floor(Date.now() / 1000),
      received_timestamp: Math.floor(Date.now() / 1000),
      data_age_seconds: rawQuote.data_age_seconds ?? 0,
      market_data_status: rawQuote.market_data_status || rawQuote.provenance_status || (rawQuote.is_live ? 'LIVE' : 'RECENT'),
      canonical_source: 'REST',
      quote_sequence_id: (existing?.quote_sequence_id || 0) + 1,
      is_live: Boolean(rawQuote.is_live),
      is_stale: Boolean(rawQuote.is_stale || rawQuote.stale),
      last_rest_ltp: ltp,
      last_rest_ts: incomingTs,
      last_ws_ltp: existing?.last_ws_ltp ?? null,
      last_ws_ts: existing?.last_ws_ts ?? null,
    };

    this.quotes.set(symbol, canonical);
    this.notify();
    return canonical;
  }

  public updateFromWS(tick: any): CanonicalQuote | null {
    if (!tick || !tick.symbol) return null;
    const ltp = tick.ltp ?? tick.price;
    if (ltp === null || ltp === undefined || ltp <= 0) return null;

    const symbol = tick.symbol;
    const existing = this.quotes.get(symbol);
    const incomingTs = Number(tick.timestamp || tick.provider_timestamp || 0);

    const prevClose = tick.previous_close ?? existing?.previous_close ?? ltp;
    const change = tick.change ?? (prevClose > 0 ? Number((ltp - prevClose).toFixed(2)) : 0);
    const changePct = tick.change_percent ?? tick.changePercent ?? (prevClose > 0 ? Number((((ltp - prevClose) / prevClose) * 100).toFixed(2)) : 0);

    const canonical: CanonicalQuote = {
      symbol: symbol,
      instrument_key: tick.instrument_key || existing?.instrument_key || symbol,
      exchange: tick.exchange || 'NSE',
      ltp: ltp,
      previous_close: prevClose,
      change: change,
      change_percent: changePct,
      open: tick.open ?? existing?.open ?? ltp,
      high: tick.high ?? Math.max(existing?.high || ltp, ltp),
      low: tick.low ?? Math.min(existing?.low || ltp, ltp),
      volume: tick.volume ?? existing?.volume ?? 0,
      bid: tick.bid ?? existing?.bid ?? null,
      ask: tick.ask ?? existing?.ask ?? null,
      provider: tick.provider || existing?.provider || 'UPSTOX',
      provider_mode: tick.provider_mode || existing?.provider_mode || 'AUTHENTIC_LIVE',
      provider_timestamp: incomingTs > 0 ? incomingTs : Math.floor(Date.now() / 1000),
      received_timestamp: Math.floor(Date.now() / 1000),
      data_age_seconds: 0,
      market_data_status: tick.market_status === 'SIMULATED' ? 'SIMULATED' : 'LIVE',
      canonical_source: 'WS',
      quote_sequence_id: (existing?.quote_sequence_id || 0) + 1,
      is_live: tick.provider_mode !== 'SIMULATED' && tick.provider !== 'MOCK',
      is_stale: false,
      last_rest_ltp: existing?.last_rest_ltp ?? null,
      last_rest_ts: existing?.last_rest_ts ?? null,
      last_ws_ltp: ltp,
      last_ws_ts: incomingTs,
    };

    this.quotes.set(symbol, canonical);
    this.notify();
    return canonical;
  }

  public toMarketQuote(symbol: string, displayName?: string, isIndex: boolean = false): MarketQuote {
    const q = this.quotes.get(symbol);
    if (!q || q.ltp === null || q.ltp <= 0) {
      return {
        symbol: symbol,
        displayName: displayName || symbol,
        exchange: 'NSE',
        instrumentKey: symbol,
        instrumentType: isIndex ? 'INDEX' : 'EQUITY',
        ltp: null,
        previousClose: null,
        change: null,
        changePercent: null,
        timestamp: 0,
        receivedAt: 0,
        dataAgeMs: 0,
        source: 'UPSTOX',
        marketStatus: 'UNAVAILABLE',
        isLive: false,
      };
    }

    return {
      symbol: q.symbol,
      displayName: displayName || q.symbol,
      exchange: (q.exchange as any) || 'NSE',
      instrumentKey: q.instrument_key,
      instrumentType: isIndex ? 'INDEX' : 'EQUITY',
      ltp: q.ltp,
      previousClose: q.previous_close,
      open: q.open,
      high: q.high,
      low: q.low,
      close: q.ltp,
      change: q.change,
      changePercent: q.change_percent,
      volume: q.volume,
      volumeLakhs: q.volume ? Number((q.volume / 100000).toFixed(2)) : undefined,
      timestamp: q.provider_timestamp,
      receivedAt: q.received_timestamp * 1000,
      dataAgeMs: Math.max(0, Date.now() - q.provider_timestamp * 1000),
      source: q.provider as any,
      providerMode: q.provider_mode,
      marketStatus: q.market_data_status,
      isLive: q.is_live,
      isStale: q.is_stale,
    };
  }

  public subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify() {
    this.listeners.forEach(fn => fn());
  }
}

export const canonicalQuoteStore = new ClientCanonicalQuoteStore();
