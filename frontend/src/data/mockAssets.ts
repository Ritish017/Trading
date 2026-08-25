import { Asset, NewsItem } from '../types/trading';

// NOTE: Test fixture only. Not used in production live price path.
export const INITIAL_ASSETS: Asset[] = [
  {
    symbol: 'BTC/USD',
    name: 'Bitcoin',
    category: 'Crypto',
    price: 0,
    change24h: 0,
    high24h: 0,
    low24h: 0,
    volume24h: 0,
    precision: 2,
    sparkline: [],
    isFavorite: true,
  },
  {
    symbol: 'ETH/USD',
    name: 'Ethereum',
    category: 'Crypto',
    price: 0,
    change24h: 0,
    high24h: 0,
    low24h: 0,
    volume24h: 0,
    precision: 2,
    sparkline: [],
    isFavorite: true,
  }
];

export const MOCK_NEWS: NewsItem[] = [];
