import React, { useState } from 'react';
import { MarketEvent } from '../../types/intelligence';
import { Activity, Flame, ShieldAlert, Sparkles, Filter, ChevronDown, ChevronUp, Clock, ExternalLink } from 'lucide-react';

interface IntelligenceTimelineProps {
  events: MarketEvent[];
  selectedSymbol?: string;
  onSelectSymbol?: (symbol: string) => void;
  isLoading?: boolean;
}

export const IntelligenceTimeline: React.FC<IntelligenceTimelineProps> = ({
  events = [],
  selectedSymbol,
  onSelectSymbol,
  isLoading = false,
}) => {
  const [filterCategory, setFilterCategory] = useState<string>('All');
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  const categories = ['All', 'Critical (80+)', 'Important (65+)', 'Price & Vol', 'Derivatives', 'News'];

  const filteredEvents = (events || []).filter((ev) => {
    if (filterCategory === 'All') return true;
    if (filterCategory === 'Critical (80+)') return ev.attention_score >= 80;
    if (filterCategory === 'Important (65+)') return ev.attention_score >= 65;
    if (filterCategory === 'Price & Vol') return ev.event_type.includes('SELLING') || ev.event_type.includes('BUYING') || ev.event_type.includes('VWAP');
    if (filterCategory === 'Derivatives') return ev.event_type.includes('OI') || ev.event_type.includes('DERIVATIVE');
    if (filterCategory === 'News') return ev.event_type.includes('NEWS');
    return true;
  });

  const getBadgeColor = (classification: string, score: number) => {
    if (score >= 85 || classification === 'CRITICAL') return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
    if (score >= 70 || classification === 'IMPORTANT') return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
    if (score >= 50 || classification === 'INTERESTING') return 'bg-sky-500/20 text-sky-300 border-sky-500/40';
    return 'bg-stone-800 text-stone-400 border-stone-700';
  };

  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-3 h-full flex flex-col justify-between overflow-hidden shadow-sm">
      {/* Header & Filter Tabs */}
      <div className="pb-2 mb-2 border-b border-stone-800/60 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-amber-400" />
            <span className="font-extrabold text-xs text-white uppercase tracking-wider font-mono">
              Apex Intelligence Timeline
            </span>
            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
              {filteredEvents.length} Events
            </span>
          </div>

          <div className="flex items-center space-x-1 text-[10px] font-mono text-stone-500">
            <Clock className="w-3 h-3" />
            <span>Live Stream</span>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center space-x-1 overflow-x-auto custom-scrollbar pb-1">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setFilterCategory(cat)}
              className={`px-2 py-0.5 rounded-lg text-[10px] font-semibold whitespace-nowrap transition-all cursor-pointer ${
                filterCategory === cat
                  ? 'bg-amber-500 text-stone-950 font-bold shadow-sm'
                  : 'bg-[#14151b] text-stone-400 hover:text-stone-200 hover:bg-stone-800/60'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Events List Body */}
      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar space-y-2 pr-0.5">
        {isLoading && filteredEvents.length === 0 ? (
          <div className="p-6 text-center text-xs text-stone-400 font-mono animate-pulse">
            Scanning market anomaly streams...
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="p-6 text-center text-xs text-stone-500 font-mono">
            No events match the active filter criteria.
          </div>
        ) : (
          filteredEvents.map((ev) => {
            const isExpanded = expandedEventId === ev.event_id;
            const isSelected = selectedSymbol === ev.symbol;

            return (
              <div
                key={ev.event_id}
                onClick={() => onSelectSymbol && onSelectSymbol(ev.symbol)}
                className={`p-2.5 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-amber-500/10 border-amber-500/50 shadow-sm'
                    : 'bg-[#14151b]/80 hover:bg-stone-800/60 border-stone-800/60'
                }`}
              >
                {/* Top Row: Timestamp, Symbol, Attention Badge */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center space-x-2">
                    <span className="text-[10px] font-mono text-stone-400">{ev.timestamp}</span>
                    <span className="font-extrabold font-mono text-xs text-stone-100">{ev.symbol.split('.')[0]}</span>
                    {ev.affected_sector && (
                      <span className="px-1.5 py-0.2 rounded text-[8px] font-medium bg-[#1c1e27] text-stone-400 border border-stone-800 truncate max-w-[90px]">
                        {ev.affected_sector}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center space-x-1.5">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-black border ${getBadgeColor(ev.classification, ev.attention_score)}`}>
                      ATTN {ev.attention_score}
                    </span>
                  </div>
                </div>

                {/* Event Description */}
                <div className="text-xs font-semibold text-stone-200 mb-1.5 flex items-center justify-between">
                  <span>{ev.event_type.replace(/_/g, ' ')}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setExpandedEventId(isExpanded ? null : ev.event_id);
                    }}
                    className="text-stone-500 hover:text-stone-300 p-0.5"
                  >
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                </div>

                {/* Primary Evidence Line */}
                {ev.evidence.length > 0 && !isExpanded && (
                  <p className="text-[11px] text-stone-400 truncate font-mono">
                    • {ev.evidence[0].statement}
                  </p>
                )}

                {/* Expanded Detailed Evidence Breakdown */}
                {isExpanded && (
                  <div className="mt-2 pt-2 border-t border-stone-800/80 space-y-1.5 text-[11px] font-mono animate-in fade-in duration-100">
                    <div className="text-[9px] uppercase tracking-wider text-amber-400 font-bold">
                      Traceable Evidence ({ev.evidence.length} sources)
                    </div>
                    {ev.evidence.map((item, idx) => (
                      <div key={idx} className="flex items-start space-x-1.5 text-stone-300">
                        <span className="text-amber-400 shrink-0">✓</span>
                        <div className="flex-1">
                          <span>{item.statement}</span>
                          <span className="text-[9px] text-stone-500 ml-1.5 font-sans">[{item.source}]</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
