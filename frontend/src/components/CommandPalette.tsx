import React, { useState, useEffect } from 'react';
import { Search, TrendingUp, BarChart2, BookOpen, RotateCcw, Brain, Briefcase, FileText } from 'lucide-react';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectAction: (action: string, payload?: any) => void;
  symbols: string[];
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectAction,
  symbols,
}) => {
  const [query, setQuery] = useState('');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (isOpen) onClose();
        else onSelectAction('TOGGLE_COMMAND_PALETTE');
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, onSelectAction]);

  if (!isOpen) return null;

  const actions = [
    { id: 'ANALYZE_STOCK', label: 'Run AI Market Intelligence Analyst', icon: Brain, category: 'AI Research' },
    { id: 'OPEN_PAPER_TRADING', label: 'Open Paper Trading Terminal', icon: Briefcase, category: 'Trading' },
    { id: 'RUN_BACKTEST', label: 'Launch Strategy Backtester', icon: BarChart2, category: 'Quant Lab' },
    { id: 'OPEN_REPLAY', label: 'Start Market Replay Simulator', icon: RotateCcw, category: 'Simulator' },
    { id: 'OPEN_LEARN', label: 'Open APEX Learn Center', icon: BookOpen, category: 'Education' },
    { id: 'OPEN_JOURNAL', label: 'View Trading Journal Analytics', icon: FileText, category: 'Analytics' },
  ];

  const filteredSymbols = symbols.filter((s) => s.toLowerCase().includes(query.toLowerCase()));
  const filteredActions = actions.filter((a) => a.label.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-start justify-center pt-20 p-4">
      <div className="bg-[#161822] border border-stone-800 rounded-xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in duration-150">
        <div className="flex items-center px-4 py-3 border-b border-stone-800 bg-[#12131a]">
          <Search className="w-5 h-5 text-stone-400 mr-3" />
          <input
            type="text"
            autoFocus
            placeholder="Type a command or search symbol... (Press Esc to exit)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="bg-transparent border-none text-stone-100 placeholder-stone-500 focus:outline-none w-full text-base font-mono"
          />
          <kbd className="hidden sm:inline-block px-2 py-0.5 text-xs font-mono bg-stone-800 text-stone-400 rounded">Esc</kbd>
        </div>

        <div className="max-h-96 overflow-y-auto p-2 space-y-3">
          {/* Symbol Search Results */}
          {filteredSymbols.length > 0 && (
            <div>
              <div className="text-[10px] font-mono font-semibold uppercase tracking-wider text-stone-500 px-3 py-1">Equities & Indices</div>
              {filteredSymbols.slice(0, 5).map((symbol) => (
                <button
                  key={symbol}
                  onClick={() => {
                    onSelectAction('SELECT_SYMBOL', symbol);
                    onClose();
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg hover:bg-amber-500/10 hover:text-amber-400 text-stone-200 transition-colors"
                >
                  <span className="font-mono font-bold flex items-center">
                    <TrendingUp className="w-4 h-4 mr-2 text-amber-500" />
                    {symbol}
                  </span>
                  <span className="text-xs text-stone-500 font-mono">Select Symbol</span>
                </button>
              ))}
            </div>
          )}

          {/* Quick Command Actions */}
          <div>
            <div className="text-[10px] font-mono font-semibold uppercase tracking-wider text-stone-500 px-3 py-1">Terminal Commands</div>
            {filteredActions.map((action) => {
              const Icon = action.icon;
              return (
                <button
                  key={action.id}
                  onClick={() => {
                    onSelectAction(action.id);
                    onClose();
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg hover:bg-stone-800 text-stone-200 transition-colors"
                >
                  <span className="flex items-center">
                    <Icon className="w-4 h-4 mr-3 text-stone-400" />
                    {action.label}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-stone-800 text-stone-400">{action.category}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="px-4 py-2 bg-[#0f1015] border-t border-stone-800 flex justify-between text-xs text-stone-500 font-mono">
          <span>APEX Terminal Quick Actions</span>
          <span>Shortcut: <kbd className="text-stone-300">Ctrl + K</kbd></span>
        </div>
      </div>
    </div>
  );
};
