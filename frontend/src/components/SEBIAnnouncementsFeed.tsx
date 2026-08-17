import React from 'react';
import { SEBIAnnouncement } from '../types/indianMarket';
import { Newspaper, BellRing } from 'lucide-react';

interface SEBIAnnouncementsFeedProps {
  announcements?: SEBIAnnouncement[];
}

export const SEBIAnnouncementsFeed: React.FC<SEBIAnnouncementsFeedProps> = ({ announcements = [] }) => {
  return (
    <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 select-none flex flex-col justify-between">
      <div className="flex items-center justify-between mb-3 border-b border-stone-800/60 pb-2">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-xl bg-orange-500/20 text-orange-400 flex items-center justify-center font-bold">
            <Newspaper className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-white">NSE / BSE Corporate Filings</h3>
            <span className="text-[10px] text-stone-400">Regulatory Disclosures Feed</span>
          </div>
        </div>
        <span className="flex items-center space-x-1 text-[10px] font-mono text-stone-400">
          <span>FILINGS FEED</span>
        </span>
      </div>

      {announcements.length === 0 ? (
        <div className="p-4 bg-[#14151b] rounded-xl border border-stone-800 text-stone-400 text-xs font-mono text-center">
          No high-impact corporate announcements or SEBI filings in current session.
        </div>
      ) : (
        <div className="space-y-2.5 max-h-[220px] overflow-y-auto pr-1">
          {announcements.map((ann) => {
            if (!ann) return null;
            const symStr = ann.companySymbol ? ann.companySymbol.split('.')[0] : 'NSE';

            return (
              <div
                key={ann.id || ann.headline}
                className="p-2.5 bg-[#14151b] rounded-xl border border-stone-800 hover:border-amber-500/40 transition-all space-y-1"
              >
                <div className="flex items-center justify-between text-[10px]">
                  <div className="flex items-center space-x-1.5 font-mono">
                    <span className="font-bold text-amber-400">{symStr}</span>
                    <span className="px-1.5 py-0.2 rounded bg-stone-800 text-stone-300 text-[9px]">{ann.category || 'FILING'}</span>
                  </div>
                  <span className="text-stone-500 font-mono">{ann.timestamp || 'Just now'}</span>
                </div>

                <h4 className="text-xs font-semibold text-stone-100 leading-snug">
                  {ann.headline}
                </h4>

                <p className="text-[11px] text-stone-400 leading-tight">
                  {ann.details}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
