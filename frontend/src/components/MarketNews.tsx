import React from 'react';
import { NewsItem } from '../types/trading';
import { Newspaper, ExternalLink, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MarketNewsProps {
  news: NewsItem[];
  activeSymbol: string;
}

export const MarketNews: React.FC<MarketNewsProps> = ({ news, activeSymbol }) => {
  return (
    <div className="bg-stone-900 border border-stone-800 rounded-xl p-3 flex flex-col h-full text-stone-200 select-none">
      <div className="flex items-center justify-between border-b border-stone-800 pb-2 mb-2">
        <div className="flex items-center space-x-2">
          <Newspaper className="w-4 h-4 text-stone-400" />
          <span className="text-xs font-semibold uppercase tracking-wider text-stone-400">Market Insights & News</span>
        </div>
        <span className="text-[10px] text-stone-500 font-mono">Live Feed</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2.5 custom-scrollbar pr-1">
        {news.map((item) => {
          const isBullish = item.sentiment === 'Bullish';
          const isBearish = item.sentiment === 'Bearish';

          return (
            <div
              key={item.id}
              className="p-2.5 rounded-lg bg-stone-950 border border-stone-800/80 hover:border-stone-700 transition-all space-y-1"
            >
              <div className="flex items-center justify-between text-[10px] font-mono">
                <span className="text-stone-400 font-semibold">{item.source}</span>
                <span className="text-stone-500">{item.timeAgo}</span>
              </div>

              <h4 className="text-xs font-semibold text-stone-100 leading-snug hover:text-emerald-400 transition-colors cursor-pointer">
                {item.title}
              </h4>

              <p className="text-[11px] text-stone-400 leading-relaxed line-clamp-2">
                {item.summary}
              </p>

              <div className="flex items-center justify-between pt-1 text-[10px] font-mono">
                <span className="bg-stone-800 text-stone-300 px-1.5 py-0.5 rounded">
                  {item.relatedSymbol}
                </span>

                <span
                  className={`inline-flex items-center space-x-1 px-1.5 py-0.5 rounded font-bold ${
                    isBullish
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : isBearish
                      ? 'bg-rose-500/20 text-rose-400'
                      : 'bg-amber-500/20 text-amber-400'
                  }`}
                >
                  {isBullish ? <TrendingUp className="w-3 h-3" /> : isBearish ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                  <span>{item.sentiment}</span>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
