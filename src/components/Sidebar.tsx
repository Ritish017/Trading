import React from 'react';
import { 
  LayoutDashboard, 
  BarChart2, 
  TrendingUp, 
  BookOpen, 
  Calendar, 
  CreditCard, 
  Settings, 
  HelpCircle, 
  LogOut,
  Sparkles,
  Layers
} from 'lucide-react';

export type NavTab = 
  | 'Dashboard' 
  | 'Statistics' 
  | 'Market' 
  | 'Library' 
  | 'Schedule' 
  | 'Payout' 
  | 'Settings';

interface SidebarProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  onOpenAIAnalyst?: () => void;
  onOpenDepositModal?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onTabChange,
  onOpenAIAnalyst,
  onOpenDepositModal,
}) => {
  const navItems: { id: NavTab; label: string; icon: React.FC<{ className?: string }> }[] = [
    { id: 'Dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'Statistics', label: 'Statistics', icon: BarChart2 },
    { id: 'Market', label: 'Market', icon: TrendingUp },
    { id: 'Library', label: 'Library', icon: BookOpen },
    { id: 'Schedule', label: 'Schedule', icon: Calendar },
    { id: 'Payout', label: 'Payout', icon: CreditCard },
    { id: 'Settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-60 bg-[#16171d] border-r border-stone-800/60 flex flex-col justify-between p-4 h-full select-none shrink-0">
      <div>
        {/* Logo Section */}
        <div className="flex items-center space-x-3 px-2 py-2 mb-8">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-pink-500 via-purple-500 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-purple-500/20 font-black">
            <Layers className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="font-extrabold text-lg text-white tracking-tight block leading-tight">
              Apex<span className="text-purple-400">Crypto</span>
            </span>
            <span className="text-[10px] text-stone-400 tracking-wider uppercase font-semibold">Trading Suite</span>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${
                  isActive
                    ? 'bg-gradient-to-r from-pink-500 via-purple-500 to-indigo-500 text-white shadow-lg shadow-purple-500/25 font-semibold'
                    : 'text-stone-400 hover:text-stone-200 hover:bg-stone-800/50'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-stone-400'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* AI Analyst Trigger Banner */}
      <div className="my-4 bg-gradient-to-br from-purple-900/40 via-indigo-900/30 to-stone-900 border border-purple-500/30 rounded-2xl p-3.5 text-center">
        <div className="w-8 h-8 rounded-full bg-purple-500/20 text-purple-300 flex items-center justify-center mx-auto mb-2">
          <Sparkles className="w-4 h-4 animate-pulse text-purple-400" />
        </div>
        <div className="text-xs font-bold text-white mb-1">Gemini AI Signals</div>
        <p className="text-[11px] text-stone-400 mb-2.5 leading-tight">
          Real-time technical scans & trade setups.
        </p>
        <button
          onClick={onOpenAIAnalyst}
          className="w-full py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs transition-all shadow-md shadow-purple-500/20 cursor-pointer"
        >
          Run AI Scan
        </button>
      </div>

      {/* Bottom Actions */}
      <div className="pt-3 border-t border-stone-800/60 space-y-1 text-stone-400 text-xs font-medium">
        <button 
          onClick={onOpenDepositModal}
          className="w-full flex items-center space-x-3 px-3 py-2 rounded-xl hover:text-stone-200 hover:bg-stone-800/40 transition-colors"
        >
          <HelpCircle className="w-4 h-4" />
          <span>Help Centre</span>
        </button>
        <button 
          onClick={onOpenDepositModal}
          className="w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span>Reset Balance</span>
        </button>
      </div>
    </aside>
  );
};
