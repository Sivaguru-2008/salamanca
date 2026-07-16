import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, BrainCircuit, ChevronDown, ChevronUp, MessageSquare } from 'lucide-react';
import { apiService } from '../services/apiService';
import { AdvisorMessage } from '../types';

const ADVISORS = {
  advisor: { name: 'Advisor', role: 'Chief Financial Advisor' },
  budget: { name: 'Budget Agent', role: 'Budgeting Specialist' },
  debt: { name: 'Debt Agent', role: 'Debt Management Specialist' },
  savings: { name: 'Savings Agent', role: 'Savings Strategist' },
  investment: { name: 'Investment Agent', role: 'Investment Guide' },
  insurance: { name: 'Insurance Agent', role: 'Insurance Advisor' },
  tax: { name: 'Tax Agent', role: 'Tax Planner' },
  loan: { name: 'Loan Agent', role: 'Loan Evaluator' }
};

interface AdvisorsPageProps {
  chats: Record<string, AdvisorMessage[]>;
  onAddMessage: (agentId: string, msg: AdvisorMessage) => void;
  onHydrateAgent: (agentId: string) => void;
  snapshot: any;
  health: any;
}

export const AdvisorsPage: React.FC<AdvisorsPageProps> = ({
  chats, onAddMessage, onHydrateAgent, snapshot, health
}) => {
  const [activeId, setActiveId] = useState<string>('advisor');
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showTraceId, setShowTraceId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chats, activeId]);

  // Pull persisted conversation memory for the selected agent.
  useEffect(() => {
    onHydrateAgent(activeId);
  }, [activeId, onHydrateAgent]);

  const activeAdv = ADVISORS[activeId as keyof typeof ADVISORS];
  const history = chats[activeId] || [];

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userText = input.trim();
    setInput('');
    setLoading(true);

    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

    const userMsg: AdvisorMessage = {
      id: 'usr-' + Date.now(),
      sender: 'user',
      text: userText,
      time: timeStr,
      agentId: activeId
    };
    onAddMessage(activeId, userMsg);

    try {
      const context = {
        savingsRate: health.savingsRate,
        totalDebt: snapshot.totalDebt,
        totalSavings: snapshot.totalSavings,
        monthlyIncome: snapshot.monthlyIncome,
        monthlyExpenses: snapshot.monthlyExpenses,
        housing: snapshot.housing,
        lifestyle: snapshot.lifestyle,
        healthScore: health.score,
        healthGrade: health.grade
      };
      const response = await apiService.sendAdvisorMessage(activeId, userText, context);
      onAddMessage(activeId, response);
    } catch (e) {
      onAddMessage(activeId, {
        id: 'err-' + Date.now(),
        sender: 'agent',
        text: e instanceof Error
          ? `Council error: ${e.message}`
          : 'The council backend is unreachable. Check that the API server is running.',
        time: timeStr,
        agentId: activeId
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 select-none animate-in fade-in duration-300">
      {/* Title */}
      <div>
        <span className="text-[10px] font-bold text-[#c09a5f] uppercase tracking-wider block mb-1">Council Room</span>
        <h1 className="font-serif text-3xl font-medium text-brand-navy">Talk to the council</h1>
        <p className="text-xs text-brand-graphite/50">Choose a specialist or start with the Advisor to coordinate the team.</p>
      </div>

      {/* Main Layout */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-8 items-stretch h-[560px]">
        {/* Sidebar */}
        <aside className="bg-white border border-black/5 rounded-2xl py-3 flex flex-col overflow-y-auto shadow-subtle md:col-span-1">
          {Object.keys(ADVISORS).map((id) => {
            const adv = ADVISORS[id as keyof typeof ADVISORS];
            const isActive = activeId === id;
            return (
              <button
                key={id}
                onClick={() => setActiveId(id)}
                className={`w-full text-left px-5 py-3.5 border-l-2 flex flex-col gap-1 transition-all ${
                  isActive 
                    ? 'bg-brand-gold-light/20 border-[#c09a5f]' 
                    : 'border-transparent hover:bg-black/[0.01]'
                }`}
              >
                <span className="text-xs font-semibold text-brand-navy">{adv.name}</span>
                <span className="text-[9px] font-bold uppercase tracking-wider text-brand-graphite/40">{adv.role}</span>
              </button>
            );
          })}
        </aside>

        {/* Chat Workspaces */}
        <div className="bg-white border border-black/5 rounded-2xl flex flex-col overflow-hidden shadow-premium md:col-span-3">
          {/* Header */}
          <header className="px-6 py-4 border-b border-black/5 bg-white shrink-0">
            <span className="text-[9px] font-bold uppercase tracking-wider text-[#c09a5f]">{activeAdv.role}</span>
            <h3 className="font-serif text-base font-semibold text-brand-navy">{activeAdv.name}</h3>
          </header>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-black/[0.005]">
            {history.length === 0 && !loading && (
              <div className="h-full flex flex-col items-center justify-center gap-3 text-center text-brand-graphite/40">
                <MessageSquare size={24} className="text-[#c09a5f]/60" />
                <p className="text-xs max-w-xs leading-relaxed">
                  Start a conversation with the {activeAdv.name}. Replies are generated from your
                  live financial data and remembered between sessions.
                </p>
              </div>
            )}
            {history.map((msg) => (
              <div key={msg.id} className="space-y-2">
                <div className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div 
                    className={`max-w-[75%] rounded-2xl px-5 py-3 text-xs leading-relaxed shadow-subtle ${
                      msg.sender === 'user' 
                        ? 'bg-brand-navy text-white rounded-tr-sm' 
                        : 'bg-white border border-black/5 text-brand-graphite rounded-tl-sm'
                    }`}
                  >
                    <div>{msg.text}</div>
                    <span className="block text-[8px] opacity-40 text-right mt-1.5">{msg.time}</span>
                  </div>
                </div>

                {/* Reasoning trace / citations */}
                {msg.sender === 'agent' && (msg.citations || msg.reasoningSteps) && (
                  <div className="pl-3 space-y-1.5">
                    {/* Trace Toggle */}
                    {msg.reasoningSteps && (
                      <button 
                        onClick={() => setShowTraceId(showTraceId === msg.id ? null : msg.id)}
                        className="flex items-center gap-1.5 text-[9px] font-bold text-[#c09a5f] hover:text-[#ad8449]"
                      >
                        <BrainCircuit size={11} />
                        <span>{showTraceId === msg.id ? 'Hide planning trace' : 'View agent planning trace'}</span>
                        {showTraceId === msg.id ? <ChevronUp size={9} /> : <ChevronDown size={9} />}
                      </button>
                    )}

                    {/* Trace Content */}
                    {showTraceId === msg.id && msg.reasoningSteps && (
                      <div className="bg-white border border-black/5 rounded-xl p-3 space-y-1.5 max-w-[80%] animate-in slide-in-from-top-1 duration-200">
                        <div className="flex justify-between text-[8px] text-brand-graphite/40 font-bold border-b border-black/5 pb-1 uppercase tracking-wider">
                          <span>Graph Execution Trace</span>
                          <span>Latency: {msg.latencyMs || 480}ms</span>
                        </div>
                        {msg.reasoningSteps.map((step, sIdx) => (
                          <div key={sIdx} className="text-[9px] text-brand-graphite/70 flex gap-2">
                            <span className="text-[#c09a5f] font-bold">{sIdx + 1}.</span>
                            <span>{step}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Citations references */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {msg.citations.map((cite, cIdx) => (
                          <span 
                            key={cIdx} 
                            className="text-[8px] bg-white border border-[#c09a5f]/20 text-brand-graphite/50 px-2 py-0.5 rounded-full hover:border-[#c09a5f]/40 cursor-pointer"
                            title={cite.content}
                          >
                            📚 {cite.title} ({Math.round(cite.score * 100)}%)
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border border-black/5 rounded-2xl px-5 py-3 rounded-tl-sm text-xs text-brand-graphite/50 animate-pulse">
                  Advisor is compiling recommendation...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Footer */}
          <footer className="px-6 py-4 border-t border-black/5 bg-white flex gap-3 items-center shrink-0">
            <input
              type="text"
              className="flex-1 text-xs bg-black/5 border border-transparent rounded-full px-4 py-3 outline-none focus:bg-white focus:border-[#c09a5f]/40 transition-all"
              placeholder={`Ask ${activeAdv.name} a question...`}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => { if (e.key === 'Enter') handleSend(); }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              className="bg-brand-navy hover:bg-[#c09a5f] text-white p-3 rounded-full transition-colors flex items-center justify-center disabled:opacity-40"
            >
              <Send size={12} />
            </button>
          </footer>
        </div>
      </div>
    </div>
  );
};
