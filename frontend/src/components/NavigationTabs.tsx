import React from 'react';
import { 
  BarChart2, 
  Brain, 
  Layers, 
  Landmark, 
  Briefcase, 
  RotateCcw, 
  BookOpen, 
  Sparkles,
  Zap,
  FlaskConical,
  Building2,
  Cpu
} from 'lucide-react';

export type ActivePage = 
  | 'terminal'
  | 'intelligence'
  | 'derivatives'
  | 'institutional'
  | 'portfolio'
  | 'backtest'
  | 'learn'
  | 'strategylab'
  | 'fundamentals'
  | 'researchfactory';

interface NavigationTabsProps {
  activePage: ActivePage;
  onSelectPage: (page: ActivePage) => void;
  eventCount?: number;
  openPositionsCount?: number;
}

export const NavigationTabs: React.FC<NavigationTabsProps> = ({
  activePage,
  onSelectPage,
  eventCount = 0,
  openPositionsCount = 0,
}) => {
  const tabs = [
    {
      id: 'terminal' as ActivePage,
      label: 'Trading Terminal',
      icon: BarChart2,
      badge: null,
      color: 'text-amber-400',
    },
    {
      id: 'intelligence' as ActivePage,
      label: 'AI Market Intelligence',
      icon: Brain,
      badge: eventCount > 0 ? `${eventCount} Events` : 'AI Live',
      badgeColor: 'bg-gradient-to-r from-orange-500/20 to-indigo-500/20 text-amber-300 border-amber-500/30',
      color: 'text-indigo-400',
    },
    {
      id: 'derivatives' as ActivePage,
      label: 'Option Chain & F&O',
      icon: Layers,
      badge: 'PCR & OI',
      badgeColor: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
      color: 'text-sky-400',
    },
    {
      id: 'institutional' as ActivePage,
      label: 'FII/DII & SEBI Desk',
      icon: Landmark,
      badge: 'Institutional',
      badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      color: 'text-emerald-400',
    },
    {
      id: 'portfolio' as ActivePage,
      label: 'Paper Portfolio',
      icon: Briefcase,
      badge: openPositionsCount > 0 ? `${openPositionsCount} Open` : null,
      badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
      color: 'text-amber-400',
    },
    {
      id: 'backtest' as ActivePage,
      label: 'Backtest & Replay',
      icon: RotateCcw,
      badge: null,
      color: 'text-rose-400',
    },
    {
      id: 'learn' as ActivePage,
      label: 'Quant Learn',
      icon: BookOpen,
      badge: 'Academy',
      badgeColor: 'bg-purple-500/10 text-purple-300 border-purple-500/20',
      color: 'text-purple-400',
    },
    {
      id: 'strategylab' as ActivePage,
      label: 'Strategy Lab',
      icon: FlaskConical,
      badge: 'V3',
      badgeColor: 'bg-violet-500/10 text-violet-300 border-violet-500/20',
      color: 'text-violet-400',
    },
    {
      id: 'fundamentals' as ActivePage,
      label: 'Fundamental Lab',
      icon: Building2,
      badge: 'NEW',
      badgeColor: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
      color: 'text-emerald-400',
    },
    {
      id: 'researchfactory' as ActivePage,
      label: 'Research Factory',
      icon: Cpu,
      badge: 'PRO',
      badgeColor: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/20',
      color: 'text-cyan-400',
    },
  ];

  return (
    <div className="bg-[#12131a] border-b border-stone-800 px-3 py-1 flex items-center justify-between overflow-x-auto custom-scrollbar select-none gap-2 shrink-0">
      <div className="flex items-center space-x-1.5 min-w-max">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activePage === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => onSelectPage(tab.id)}
              className={`flex items-center space-x-2 px-3 py-1.5 rounded-xl font-mono text-xs font-bold transition-all cursor-pointer border ${
                isActive
                  ? 'bg-amber-500 text-stone-950 border-amber-400 shadow-md font-extrabold transform scale-[1.02]'
                  : 'bg-[#181a24]/80 hover:bg-stone-800 text-stone-300 hover:text-white border-stone-800/80'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-stone-950' : tab.color}`} />
              <span>{tab.label}</span>
              {tab.badge && (
                <span
                  className={`px-1.5 py-0.2 rounded text-[9px] font-mono font-black border ${
                    isActive ? 'bg-stone-950/20 text-stone-950 border-stone-950/30' : tab.badgeColor
                  }`}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};
