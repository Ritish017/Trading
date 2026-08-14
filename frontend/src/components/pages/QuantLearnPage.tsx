import React, { useState } from 'react';
import { BookOpen, Bot, Sparkles, CheckCircle2, ChevronRight, Send, User } from 'lucide-react';

export const QuantLearnPage: React.FC = () => {
  const [selectedTopic, setSelectedTopic] = useState('VWAP_INSTITUTIONAL');
  const [messages, setMessages] = useState<Array<{ sender: 'user' | 'bot'; text: string }>>([
    {
      sender: 'bot',
      text: 'Hello! I am your APEX Quant Copilot. Ask me anything about Indian equity technicals, option chain analysis (PCR, Max Pain), FII/DII flows, or quantitative trading strategies.',
    },
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  const topics = [
    {
      id: 'VWAP_INSTITUTIONAL',
      title: 'VWAP & Institutional Order Flow',
      level: 'Core',
      summary: 'Why institutional algos anchor execution to Volume Weighted Average Price.',
      content: 'Institutions cannot enter entire positions in a single market order without moving the price adverse to their execution. VWAP represents the benchmark execution price for mutual funds and foreign institutional investors. When price is above VWAP with high RVOL, buyers are paying a premium above average traded price, confirming strong demand.',
    },
    {
      id: 'PCR_OI_INTERPRETATION',
      title: 'Option Put-Call Ratio (PCR) & Max Pain',
      level: 'Derivatives',
      summary: 'Decoding smart money positioning from Put and Call Open Interest.',
      content: 'PCR (Put OI / Call OI) measures the balance between option sellers. A PCR > 1.2 indicates heavy Put writing by institutional option sellers creating strong underlying support. Max Pain is the strike price where option buyers collectively lose the maximum amount of premium at expiry.',
    },
    {
      id: 'FII_DII_FLOW_DYNAMICS',
      title: 'FII & DII Net Cash Flow Cycles',
      level: 'Macro',
      summary: 'Tracking foreign institutional accumulation vs domestic mutual fund SIP flows.',
      content: 'Foreign Institutional Investors (FIIs) trade with global macro risk appetite (influenced by US 10-Year yields, DXY, and Crude). Domestic Institutional Investors (DIIs) provide steady liquidity through Indian domestic SIPs. When both FII and DII are net buyers simultaneously, the market exhibits high-conviction trend days.',
    },
    {
      id: 'RVOL_BREAKOUTS',
      title: 'Relative Volume (RVOL) Confirmation',
      level: 'Execution',
      summary: 'Filtering false breakouts using multi-period volume anomalies.',
      content: 'A price breakout without relative volume (RVOL < 1.2x) has a statistically high failure rate. When price breaks resistance with RVOL > 2.0x, it signifies large-block institutional participation, significantly increasing the probability of follow-through.',
    },
  ];

  const currentTopic = topics.find((t) => t.id === selectedTopic) || topics[0];

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuery.trim() || isTyping) return;

    const userText = inputQuery.trim();
    setInputQuery('');
    setMessages((prev) => [...prev, { sender: 'user', text: userText }]);
    setIsTyping(true);

    try {
      const res = await fetch('/api/ai/strategy-hypothesis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userText }),
      });
      if (res.ok) {
        const data = await res.json();
        const reply = typeof data === 'string' ? data : (data.hypothesis || data.executiveSummary || JSON.stringify(data));
        setMessages((prev) => [...prev, { sender: 'bot', text: reply }]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            sender: 'bot',
            text: `Analyzing "${userText}" in the context of NSE equities: Institutional flow and derivatives positioning (PCR & RVOL) are the primary confirmation pillars. Keep risk capped at 1-2% per trade.`,
          },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: `Analyzing "${userText}" in the context of NSE equities: Institutional flow and derivatives positioning (PCR & RVOL) are the primary confirmation pillars. Keep risk capped at 1-2% per trade.`,
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex-1 p-3 flex flex-col space-y-3 h-[calc(100vh-175px)] overflow-y-auto custom-scrollbar">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 flex-1 min-h-[500px]">
        {/* Left Column (Col 4): Curriculum & Topics */}
        <div className="md:col-span-4 bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 flex flex-col space-y-3">
          <div className="flex items-center space-x-2 border-b border-stone-800/60 pb-2">
            <BookOpen className="w-4 h-4 text-purple-400" />
            <span className="font-extrabold font-mono text-xs text-white uppercase">Quant Trading Academy</span>
          </div>

          <div className="space-y-2 flex-1 overflow-y-auto custom-scrollbar pr-0.5">
            {topics.map((t) => {
              const isSelected = selectedTopic === t.id;
              return (
                <div
                  key={t.id}
                  onClick={() => setSelectedTopic(t.id)}
                  className={`p-3 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-purple-500/10 border-purple-500/50 shadow-sm'
                      : 'bg-[#14151b] hover:bg-stone-800/60 border-stone-800/60'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-stone-800 text-purple-300">
                      {t.level}
                    </span>
                    <ChevronRight className="w-3.5 h-3.5 text-stone-500" />
                  </div>
                  <h4 className="text-xs font-bold text-white mb-1">{t.title}</h4>
                  <p className="text-[11px] text-stone-400">{t.summary}</p>
                </div>
              );
            })}
          </div>

          {/* Active Lesson Display */}
          <div className="p-3.5 bg-[#14151b] rounded-xl border border-stone-800 text-xs font-mono">
            <div className="font-bold text-purple-300 mb-1.5">{currentTopic.title}</div>
            <p className="text-[11px] text-stone-300 leading-relaxed font-sans">{currentTopic.content}</p>
          </div>
        </div>

        {/* Right Column (Col 8): Interactive AI Copilot Terminal */}
        <div className="md:col-span-8 bg-[#1c1e27] border border-stone-800/80 rounded-2xl p-4 flex flex-col h-full">
          <div className="flex items-center justify-between border-b border-stone-800/60 pb-2 mb-3">
            <div className="flex items-center space-x-2">
              <Bot className="w-4 h-4 text-indigo-400" />
              <span className="font-extrabold font-mono text-xs text-white uppercase">APEX AI Copilot Chat</span>
            </div>
            <span className="text-[10px] font-mono text-emerald-400 flex items-center space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>ONLINE</span>
            </span>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto custom-scrollbar space-y-3 pr-1 mb-3">
            {messages.map((m, idx) => {
              const isBot = m.sender === 'bot';
              return (
                <div key={idx} className={`flex items-start space-x-2.5 ${isBot ? '' : 'flex-row-reverse space-x-reverse'}`}>
                  <div className={`p-1.5 rounded-xl text-white shrink-0 ${isBot ? 'bg-indigo-600' : 'bg-amber-600'}`}>
                    {isBot ? <Sparkles className="w-3.5 h-3.5" /> : <User className="w-3.5 h-3.5" />}
                  </div>
                  <div className={`p-3 rounded-2xl text-xs max-w-[85%] font-sans leading-relaxed ${
                    isBot ? 'bg-[#14151b] border border-stone-800 text-stone-200' : 'bg-amber-500/10 border border-amber-500/30 text-amber-200'
                  }`}>
                    {m.text}
                  </div>
                </div>
              );
            })}
            {isTyping && (
              <div className="flex items-center space-x-2 text-xs font-mono text-stone-500 animate-pulse">
                <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                <span>Copilot is formulating quantitative analysis...</span>
              </div>
            )}
          </div>

          {/* Input Form */}
          <form onSubmit={handleSendMessage} className="flex items-center space-x-2 pt-2 border-t border-stone-800/80">
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Ask Copilot about VWAP setups, PCR, FII flow, or risk rules..."
              className="flex-1 bg-[#14151b] border border-stone-800 rounded-xl px-4 py-2 text-xs font-mono text-stone-100 placeholder-stone-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={isTyping || !inputQuery.trim()}
              className="p-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl cursor-pointer disabled:opacity-50 transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
