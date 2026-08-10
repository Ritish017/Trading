import React from 'react';
import { SEBIAnnouncement } from '../types/indianMarket';
import { Newspaper, BellRing, ArrowUpRight, ShieldAlert, CheckCircle2 } from 'lucide-react';

interface SEBIAnnouncementsFeedProps {
  announcements: SEBIAnnouncement[];
}

export const SEBIAnnouncementsFeed: React.FC<SEBIAnnouncementsFeedProps> = ({ announcements }) => {
  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 select-none flex flex-col justify-between">
      <div className="flex items-center justify-between mb-3 border-b border-stone-800/60 pb-2">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-xl bg-orange-500/20 text-orange-400 flex items-center justify-center font-bold">
            <Newspaper className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-white">NSE / BSE SEBI Corporate Filings</h3>
            <span className="text-[10px] text-stone-400">Real-time Regulatory Disclosures</span>
          </div>
        </div>
        <span className="flex items-center space-x-1 text-[10px] font-mono text-emerald-400">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>LIVE SEBI STREAM</span>
        </span>
      </div>

      <div className="space-y-2.5 max-h-[220px] overflow-y-auto pr-1">
        {announcements.map((ann) => (
          <div
            key={ann.id}
            className="p-2.5 bg-[#14151b] rounded-xl border border-stone-800 hover:border-amber-500/40 transition-all space-y-1"
          >
            <div className="flex items-center justify-between text-[10px]">
              <div className="flex items-center space-x-1.5 font-mono">
                <span className="font-bold text-amber-400">{ann.companySymbol.split('.')[0]}</span>
                <span className="px-1.5 py-0.2 rounded bg-stone-800 text-stone-300 text-[9px]">{ann.category}</span>
              </div>
              <span className="text-stone-500 font-mono">{ann.timestamp}</span>
            </div>

            <h4 className="text-xs font-semibold text-stone-100 leading-snug">
              {ann.headline}
            </h4>

            <p className="text-[11px] text-stone-400 leading-tight">
              {ann.details}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};
