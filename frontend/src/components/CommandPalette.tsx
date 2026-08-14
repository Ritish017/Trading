import React, { useState, useEffect } from 'react';
import { Search, TrendingUp, BarChart2, BookOpen, RotateCcw, Brain, Briefcase, FileText, PlusCircle } from 'lucide-react';
import { NSEStock } from '../types/indianMarket';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectAction?: (action: string, payload?: any) => void;
  onExecuteAction?: (action: string, payload?: any) => void;
  stocks?: NSEStock[];
  symbols?: string[];
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectAction,
  onExecuteAction,
  stocks = [],
  symbols,
}) => {
  const [query, setQuery] = useState('');

  const triggerAction = (action: string, payload?: any) => {
    if (onExecuteAction) onExecuteAction(action, payload);
    else if (onSelectAction) onSelectAction(action, payload);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (isOpen) onClose();
        else triggerAction('TOGGLE_COMMAND_PALETTE');
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const actions = [
    { id: 'ANALYZE_STOCK', label: 'Run AI Market Intelligence Analyst', icon: Brain, category: 'AI Research' },
    { id: 'OPEN_PAPER_TRADING', label: 'Open Paper Trading Terminal', icon: Briefcase, category: 'Trading' },
    { id: 'RUN_BACKTEST', label: 'Launch Strategy Backtester', icon: BarChart2, category: 'Quant Lab' },
    { id: 'OPEN_REPLAY', label: 'Start Market Replay Simulator', icon: RotateCcw, category: 'Simulator' },
    { id: 'OPEN_LEARN', label: 'Open APEX Learn Center', icon: BookOpen, category: 'Education' },
    { id: 'OPEN_JOURNAL', label: 'View Trading Journal Analytics', icon: FileText, category: 'Analytics' },
  ];

  // Smart Typo-Tolerant & Fuzzy Match
  const q = query.toLowerCase().trim();
  const stripVowels = (s: string) => s.replace(/[aeiou\s\-_.]/g, '');
  const qStripped = stripVowels(q);

  const matchedStocks = stocks.filter((s) => {
    if (!q) return true;
    const sym = (s.symbol || '').toLowerCase();
    const cleanSym = sym.replace('.ns', '').replace('.bo', '');
    const name = (s.name || '').toLowerCase();
    const sector = (s.sector || '').toLowerCase();

    if (sym.includes(q) || cleanSym.includes(q) || name.includes(q) || sector.includes(q)) return true;
    const symStripped = stripVowels(cleanSym);
    const nameStripped = stripVowels(name);
    if (qStripped.length >= 2 && (symStripped.includes(qStripped) || nameStripped.includes(qStripped) || qStripped.includes(symStripped))) return true;
    return false;
  });

  const filteredActions = actions.filter((a) => a.label.toLowerCase().includes(q));

  const handleSelectSymbol = (sym: string) => {
    triggerAction('SELECT_STOCK', { symbol: sym });
    triggerAction('SELECT_SYMBOL', sym);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-start justify-center pt-20 p-4">
      <div className="bg-[#161822] border border-stone-800 rounded-xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in duration-150">
        <div className="flex items-center px-4 py-3 border-b border-stone-800 bg-[#12131a]">
          <Search className="w-5 h-5 text-stone-400 mr-3" />
          <input
            type="text"
            autoFocus
            placeholder="Search stock (e.g. MRF, TCS, RELIANCE) or terminal command..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="bg-transparent border-none text-stone-100 placeholder-stone-500 focus:outline-none w-full text-base font-mono"
          />
          <kbd className="hidden sm:inline-block px-2 py-0.5 text-xs font-mono bg-stone-800 text-stone-400 rounded">Esc</kbd>
        </div>

        <div className="max-h-96 overflow-y-auto p-2 space-y-3 custom-scrollbar">
          {/* Symbol Search Results */}
          {matchedStocks.length > 0 && (
            <div>
              <div className="text-[10px] font-mono font-semibold uppercase tracking-wider text-stone-500 px-3 py-1">
                Equities & Indices ({matchedStocks.length})
              </div>
              {matchedStocks.slice(0, 8).map((st) => (
                <button
                  key={st.symbol}
                  onClick={() => handleSelectSymbol(st.symbol)}
                  className="w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg hover:bg-amber-500/10 hover:text-amber-400 text-stone-200 transition-colors cursor-pointer"
                >
                  <span className="font-mono font-bold flex items-center space-x-2">
                    <TrendingUp className="w-4 h-4 text-amber-500 shrink-0" />
                    <span>{st.symbol.split('.')[0]}</span>
                    <span className="text-xs text-stone-400 font-normal font-sans truncate max-w-[200px]">{st.name}</span>
                  </span>
                  <div className="flex items-center space-x-2 font-mono text-xs">
                    <span className="text-stone-200 font-bold">₹{st.price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    <span className={st.change >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                      {st.change >= 0 ? '+' : ''}{st.changePercent.toFixed(2)}%
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Dynamic Search & Load Action if user types something specific */}
          {q && (
            <div>
              <button
                onClick={() => handleSelectSymbol(q.toUpperCase().endsWith('.NS') ? q.toUpperCase() : `${q.toUpperCase()}.NS`)}
                className="w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 transition-colors border border-amber-500/30 cursor-pointer"
              >
                <span className="flex items-center space-x-2 font-mono font-bold">
                  <PlusCircle className="w-4 h-4 text-amber-400" />
                  <span>Load &ldquo;{q.toUpperCase()}&rdquo; from Live NSE Market</span>
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500 text-stone-950 font-bold">LIVE QUERY</span>
              </button>
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
                    triggerAction(action.id);
                    onClose();
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg hover:bg-stone-800 text-stone-200 transition-colors cursor-pointer"
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

