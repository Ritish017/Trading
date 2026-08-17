import React, { useState } from 'react';
import { Bot, Send, X, Sparkles, AlertCircle } from 'lucide-react';

interface AICopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  selectedSymbol: string;
}

export const AICopilotDrawer: React.FC<AICopilotDrawerProps> = ({
  isOpen,
  onClose,
  selectedSymbol,
}) => {
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string; data?: any }>>([
    {
      role: 'assistant',
      text: `Hello! I am your APEX AI Quant Specialist. Ask me anything about ${selectedSymbol}, option chain dynamics, regime changes, or backtest strategy hypotheses.`,
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userText = input;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: userText }]);
    setIsLoading(true);

    try {
      if (userText.toLowerCase().includes('strategy') || userText.toLowerCase().includes('hypothesis')) {
        const res = await fetch('/api/ai/strategy-hypothesis', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: userText }),
        });
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: `Generated Quantitative Hypothesis (${data.hypothesis_id}):\nName: ${data.name}\n\nEntry Conditions:\n${data.rules.entry.map((r: string) => `- ${r}`).join('\n')}\n\nExit Conditions:\n${data.rules.exit.map((r: string) => `- ${r}`).join('\n')}`,
          },
        ]);
      } else {
        const res = await fetch(`/api/intelligence/symbol/${encodeURIComponent(selectedSymbol)}`);
        if (res.ok) {
          const data = await res.json();
          const stance = data.market_regime || data.classification || 'Consolidation';
          const conf = Math.round((data.confidence || 0) * 100);
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              text: `Market Intelligence Report for ${selectedSymbol}:\nHeadline: ${data.headline || 'Quantitative Summary'}\nStance: ${stance} (${conf}% confidence)\nWhat Changed: ${data.what_changed || 'Price action within dynamic range.'}\nWhy It Matters: ${data.why_it_matters || 'N/A'}\nLikely Drivers:\n${(data.likely_drivers || []).map((d: string) => `- ${d}`).join('\n')}`,
            },
          ]);
        } else {
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              text: `Market intelligence feed offline or insufficient data for ${selectedSymbol}.`,
            },
          ]);
        }
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Quantitative intelligence service currently unavailable for ${selectedSymbol}. Please verify backend network connectivity.`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed right-0 top-0 bottom-0 w-96 bg-[#12131a] border-l border-stone-800 z-50 flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
      <div className="px-4 py-3 bg-[#161822] border-b border-stone-800 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Bot className="w-5 h-5 text-amber-500" />
          <span className="font-mono font-bold text-stone-100 text-sm">APEX AI Copilot</span>
        </div>
        <button onClick={onClose} className="text-stone-400 hover:text-stone-100 transition-colors">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 p-4 overflow-y-auto space-y-3 font-mono text-xs">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`p-3 rounded-lg border ${
              m.role === 'user'
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-200 ml-6'
                : 'bg-stone-900 border-stone-800 text-stone-200 mr-6'
            }`}
          >
            <div className="flex items-center space-x-1 mb-1 font-bold text-[10px] text-stone-400 uppercase">
              {m.role === 'user' ? <span>Trader</span> : <Sparkles className="w-3 h-3 text-amber-400" />}
            </div>
            <p className="whitespace-pre-line leading-relaxed">{m.text}</p>
          </div>
        ))}
        {isLoading && (
          <div className="p-3 rounded-lg bg-stone-900 border border-stone-800 text-stone-400 font-mono text-xs flex items-center space-x-2">
            <span className="animate-pulse">Analyzing quantitative features & market snapshot...</span>
          </div>
        )}
      </div>

      <div className="p-3 bg-[#161822] border-t border-stone-800">
        <div className="flex items-center space-x-2">
          <input
            type="text"
            placeholder="Ask AI analyst or request hypothesis..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            className="flex-1 bg-[#0f1015] border border-stone-800 rounded-lg px-3 py-2 text-stone-100 placeholder-stone-500 font-mono text-xs focus:outline-none focus:border-amber-500"
          />
          <button
            onClick={handleSend}
            disabled={isLoading}
            className="bg-amber-500 hover:bg-amber-600 text-stone-950 font-bold p-2 rounded-lg transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
