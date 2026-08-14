import React from 'react';
import { FIIDIITracker } from '../FIIDIITracker';
import { SEBIAnnouncementsFeed } from '../SEBIAnnouncementsFeed';
import { FIIDIINetFlow, MarketBreadth, SEBIAnnouncement } from '../../types/indianMarket';
import { Landmark, Globe, Activity, ArrowUpRight, ArrowDownRight, ShieldCheck } from 'lucide-react';

interface InstitutionalDeskPageProps {
  fiiDiiFlow?: FIIDIINetFlow;
  breadth?: MarketBreadth;
  announcements?: SEBIAnnouncement[];
}

export const InstitutionalDeskPage: React.FC<InstitutionalDeskPageProps> = ({
  fiiDiiFlow,
  breadth,
  announcements = [],
}) => {
  const adv = breadth?.advances ?? 1482;
  const dec = breadth?.declines ?? 840;
  const unch = breadth?.unchanged ?? 128;
  const ratio = breadth?.ratio ?? 1.76;

  return (
    <div className="flex-1 p-3 flex flex-col space-y-3 h-[calc(100vh-175px)] overflow-y-auto custom-scrollbar">
      {/* Top Header & Market Breadth Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Card 1: FII Cash */}
        <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-mono text-stone-400">FII Net Cash (Today)</span>
            <div className="text-base font-black font-mono text-emerald-400">
              +₹{(fiiDiiFlow?.fiiCashNetCr ?? 1840.5).toLocaleString()} Cr
            </div>
          </div>
          <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <Globe className="w-4 h-4" />
          </div>
        </div>

        {/* Card 2: DII Cash */}
        <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-mono text-stone-400">DII Net Cash (Today)</span>
            <div className="text-base font-black font-mono text-emerald-400">
              +₹{(fiiDiiFlow?.diiCashNetCr ?? 1210.8).toLocaleString()} Cr
            </div>
          </div>
          <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400">
            <Landmark className="w-4 h-4" />
          </div>
        </div>

        {/* Card 3: Market Breadth */}
        <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-mono text-stone-400">Market Breadth (A : D)</span>
            <div className="text-base font-black font-mono text-sky-400">
              {adv} A : {dec} D ({ratio}x)
            </div>
          </div>
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400">
            <Activity className="w-4 h-4" />
          </div>
        </div>

        {/* Card 4: 52W Highs / Lows */}
        <div className="bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-mono text-stone-400">52-Week High / Low</span>
            <div className="text-base font-black font-mono text-stone-100 flex items-center space-x-2">
              <span className="text-emerald-400">{breadth?.new52WeekHighs ?? 142}H</span>
              <span>/</span>
              <span className="text-rose-400">{breadth?.new52WeekLows ?? 18}L</span>
            </div>
          </div>
          <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
            <ShieldCheck className="w-4 h-4" />
          </div>
        </div>
      </div>

      {/* Main Grid: FII/DII Tracker (Left Col 6) + SEBI Disclosures Feed (Right Col 6) */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 flex-1 min-h-[450px]">
        <div className="md:col-span-6 flex flex-col h-full">
          <FIIDIITracker flow={fiiDiiFlow} />
        </div>

        <div className="md:col-span-6 flex flex-col h-full">
          <SEBIAnnouncementsFeed announcements={announcements} />
        </div>
      </div>
    </div>
  );
};
