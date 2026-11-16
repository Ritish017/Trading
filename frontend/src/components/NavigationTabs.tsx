import React from 'react';
import { 
  BarChart2, 
  Brain, 
  Layers, 
  Landmark, 
  ShieldCheck, 
  RotateCcw, 
  BookOpen, 
  FlaskConical,
  Building2,
  Cpu,
  Radio,
  Radar,
  Globe,
  Sliders,
  Sparkles,
  ChevronRight
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
  | 'researchfactory'
  | 'commandcenter'
  | 'signalcenter';

export type PrimaryTabId = 'terminal' | 'intelligence' | 'derivatives' | 'portfolio' | 'quantlab';

interface NavigationTabsProps {
  activePage: ActivePage;
  onSelectPage: (page: ActivePage) => void;
  eventCount?: number;
  openPositionsCount?: number;
  activeSignalCount?: number;
}

export const getPrimaryTab = (page: ActivePage): PrimaryTabId => {
  if (page === 'terminal') return 'terminal';
  if (page === 'intelligence' || page === 'institutional' || page === 'signalcenter') return 'intelligence';
  if (page === 'derivatives') return 'derivatives';
  if (page === 'portfolio') return 'portfolio';
  return 'quantlab'; // 'strategylab' | 'backtest' | 'learn' | 'fundamentals' | 'researchfactory' | 'commandcenter'
};

export const NavigationTabs: React.FC<NavigationTabsProps> = ({
  activePage,
  onSelectPage,
  eventCount = 0,
  openPositionsCount = 0,
  activeSignalCount = 0,
}) => {
  const currentPrimary = getPrimaryTab(activePage);

  const primaryTabs = [
    {
      id: 'terminal' as PrimaryTabId,
      defaultPage: 'terminal' as ActivePage,
      label: 'Trading Terminal',
      icon: BarChart2,
      badge: null,
      badgeColor: '',
      color: 'text-amber-400',
    },
    {
      id: 'intelligence' as PrimaryTabId,
      defaultPage: 'intelligence' as ActivePage,
      label: 'Market Intelligence',
      icon: Brain,
      badge: eventCount > 0 ? `${eventCount} Events` : 'AI Core',
      badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
      color: 'text-indigo-400',
    },
    {
      id: 'derivatives' as PrimaryTabId,
      defaultPage: 'derivatives' as ActivePage,
      label: 'Autonomous Bot & F&O',
      icon: Layers,
      badge: 'InstaBox 24/7',
      badgeColor: 'bg-sky-500/20 text-sky-300 border-sky-500/40 font-bold',
      color: 'text-sky-400',
    },
    {
      id: 'portfolio' as PrimaryTabId,
      defaultPage: 'portfolio' as ActivePage,
      label: 'Portfolio & Risk',
      icon: ShieldCheck,
      badge: openPositionsCount > 0 ? `${openPositionsCount} Open` : 'Protected',
      badgeColor: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
      color: 'text-emerald-400',
    },
    {
      id: 'quantlab' as PrimaryTabId,
      defaultPage: 'strategylab' as ActivePage,
      label: 'Quant Research Lab',
      icon: FlaskConical,
      badge: 'Suite (6 Tools)',
      badgeColor: 'bg-purple-500/10 text-purple-300 border-purple-500/20',
      color: 'text-purple-400',
    },
  ];

  const intelligenceSubTabs = [
    {
      id: 'intelligence' as ActivePage,
      label: 'Global Macro & Commodities',
      shortLabel: 'Commodities & Macro',
      icon: Globe,
      badge: 'Chief Reasoner',
    },
    {
      id: 'institutional' as ActivePage,
      label: 'FII/DII & SEBI Desk',
      shortLabel: 'Institutional Flow',
      icon: Landmark,
      badge: null,
    },
    {
      id: 'signalcenter' as ActivePage,
      label: 'Signal Center & Multi-TF Consensus',
      shortLabel: 'Signal Center',
      icon: Radar,
      badge: activeSignalCount > 0 ? `${activeSignalCount} Signals` : null,
    },
  ];

  const quantLabSubTabs = [
    {
      id: 'strategylab' as ActivePage,
      label: 'Strategy Hypothesis Lab',
      shortLabel: 'Strategy Lab',
      icon: FlaskConical,
      badge: 'V3',
    },
    {
      id: 'backtest' as ActivePage,
      label: 'Backtest & Market Replay',
      shortLabel: 'Backtest & Replay',
      icon: RotateCcw,
      badge: null,
    },
    {
      id: 'researchfactory' as ActivePage,
      label: 'Alpha Research Factory',
      shortLabel: 'Research Factory',
      icon: Cpu,
      badge: 'Quant',
    },
    {
      id: 'fundamentals' as ActivePage,
      label: 'Fundamental Valuation Lab',
      shortLabel: 'Fundamentals',
      icon: Building2,
      badge: null,
    },
    {
      id: 'learn' as ActivePage,
      label: 'Quant Academy',
      shortLabel: 'Academy',
      icon: BookOpen,
      badge: null,
    },
    {
      id: 'commandcenter' as ActivePage,
      label: 'Mission Command Center',
      shortLabel: 'Telemetry',
      icon: Radio,
      badge: 'Health',
    },
  ];

  const handlePrimaryClick = (primary: typeof primaryTabs[0]) => {
    if (primary.id === currentPrimary) return;
    
    if (primary.id === 'quantlab') {
      // If already in a quantlab sub-page, keep it, else go to default
      if (['strategylab', 'backtest', 'learn', 'fundamentals', 'researchfactory', 'commandcenter'].includes(activePage)) {
        // already in lab
      } else {
        onSelectPage(primary.defaultPage);
      }
    } else if (primary.id === 'intelligence') {
      if (['intelligence', 'institutional', 'signalcenter'].includes(activePage)) {
        // already in intelligence
      } else {
        onSelectPage(primary.defaultPage);
      }
    } else {
      onSelectPage(primary.defaultPage);
    }
  };

  return (
    <div className="bg-[#101117] border-b border-stone-800/90 select-none shrink-0 shadow-lg">
      {/* 1. Primary Clean Workspaces Bar (5 Unified Hubs) */}
      <div className="px-4 py-2 flex items-center justify-between overflow-x-auto custom-scrollbar gap-3 border-b border-stone-900/50">
        <div className="flex items-center space-x-2 min-w-max">
          {primaryTabs.map((tab) => {
            const Icon = tab.icon;
            const isTabActive = currentPrimary === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => handlePrimaryClick(tab)}
                className={`flex items-center space-x-2.5 px-4 py-2 rounded-xl font-mono text-xs font-bold transition-all cursor-pointer border ${
                  isTabActive
                    ? 'bg-amber-500 text-stone-950 border-amber-400 shadow-md shadow-amber-500/20 font-extrabold transform scale-[1.01]'
                    : 'bg-[#161822]/90 hover:bg-stone-800/90 text-stone-300 hover:text-white border-stone-800'
                }`}
              >
                <Icon className={`w-4 h-4 ${isTabActive ? 'text-stone-950 stroke-[2.5]' : tab.color}`} />
                <span className="tracking-tight text-[13px]">{tab.label}</span>
                {tab.badge && (
                  <span
                    className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-black border ${
                      isTabActive
                        ? 'bg-stone-950/20 text-stone-950 border-stone-950/30'
                        : tab.badgeColor
                    }`}
                  >
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Workspace Breadcrumb Hint */}
        <div className="hidden lg:flex items-center space-x-1.5 text-xs font-mono text-stone-500 pr-2">
          <span className="text-stone-400 capitalize">{currentPrimary}</span>
          <ChevronRight className="w-3 h-3 text-stone-600" />
          <span className="text-amber-400 font-semibold">{activePage}</span>
        </div>
      </div>

      {/* 2. Contextual Sub-Navigation Pill Bar (Only visible when Intelligence or Quant Lab is selected) */}
      {currentPrimary === 'intelligence' && (
        <div className="bg-[#141620] px-4 py-1.5 flex items-center space-x-2 overflow-x-auto custom-scrollbar border-t border-stone-800/40">
          <span className="text-[10px] font-mono font-bold text-stone-400 uppercase tracking-wider mr-1 shrink-0 flex items-center space-x-1">
            <Brain className="w-3 h-3 text-indigo-400" />
            <span>Modules:</span>
          </span>
          {intelligenceSubTabs.map((sub) => {
            const Icon = sub.icon;
            const isSubActive = activePage === sub.id;

            return (
              <button
                key={sub.id}
                onClick={() => onSelectPage(sub.id)}
                className={`flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-mono transition-all cursor-pointer border ${
                  isSubActive
                    ? 'bg-indigo-600/30 text-indigo-200 border-indigo-500/50 font-bold shadow-sm'
                    : 'bg-[#1a1c28]/60 hover:bg-stone-800/80 text-stone-400 hover:text-stone-200 border-stone-800/60'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isSubActive ? 'text-indigo-300' : 'text-stone-400'}`} />
                <span>{sub.shortLabel}</span>
                {sub.badge && (
                  <span className="px-1 py-0.2 rounded text-[9px] bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-bold">
                    {sub.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {currentPrimary === 'quantlab' && (
        <div className="bg-[#141620] px-4 py-1.5 flex items-center space-x-2 overflow-x-auto custom-scrollbar border-t border-stone-800/40">
          <span className="text-[10px] font-mono font-bold text-stone-400 uppercase tracking-wider mr-1 shrink-0 flex items-center space-x-1">
            <FlaskConical className="w-3 h-3 text-purple-400" />
            <span>Lab Tools:</span>
          </span>
          {quantLabSubTabs.map((sub) => {
            const Icon = sub.icon;
            const isSubActive = activePage === sub.id;

            return (
              <button
                key={sub.id}
                onClick={() => onSelectPage(sub.id)}
                className={`flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-mono transition-all cursor-pointer border ${
                  isSubActive
                    ? 'bg-purple-600/30 text-purple-200 border-purple-500/50 font-bold shadow-sm'
                    : 'bg-[#1a1c28]/60 hover:bg-stone-800/80 text-stone-400 hover:text-stone-200 border-stone-800/60'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isSubActive ? 'text-purple-300' : 'text-stone-400'}`} />
                <span>{sub.shortLabel}</span>
                {sub.badge && (
                  <span className="px-1 py-0.2 rounded text-[9px] bg-purple-500/20 text-purple-300 border border-purple-500/30 font-bold">
                    {sub.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
