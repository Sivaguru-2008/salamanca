import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, X, BrainCircuit, ChevronDown, ChevronUp } from 'lucide-react';
import { apiService } from '../../services/apiService';
import { AdvisorMessage } from '../../types';

interface AIAssistantProps {
  isOpen: boolean;
  onClose: () => void;
  /** The user's live financial figures, sent with every question. */
  context: Record<string, unknown>;
}

export const AIAssistant: React.FC<AIAssistantProps> = ({
  isOpen, onClose, context
}) => {
  const [messages, setMessages] = useState<AdvisorMessage[]>([
    { id: '1', sender: 'agent', text: 'Hello! I am the Chief Financial Advisor. I coordinate the council of 8 agents to analyze your variables. How can I help you with your finances today?', time: '12:00' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showTraceIdx, setShowTraceIdx] = useState<string | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (!isOpen) return null;

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    
    const userText = input.trim();
    setInput('');
    setLoading(true);

    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    
    // Add User Message
    const userMsg: AdvisorMessage = {
      id: 'usr-' + Date.now(),
      sender: 'user',
      text: userText,
      time: timeStr
    };
    setMessages(prev => [...prev, userMsg]);

    try {
      const response = await apiService.sendAdvisorMessage('advisor', userText, context);
      setMessages(prev => [...prev, response]);
    } catch(e) {
      setMessages(prev => [...prev, {
        id: 'err-' + Date.now(),
        sender: 'agent',
        text: e instanceof Error
          ? `Council error: ${e.message}`
          : 'The council backend is unreachable. Check that the API server is running.',
        time: timeStr
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-80 border-l border-black/5 bg-[#faf8f5] flex flex-col h-full select-none shadow-premium relative animate-in slide-in-from-right duration-300 z-30">
      {/* Title Header */}
      <div className="h-16 border-b border-black/5 px-4 flex items-center justify-between bg-white">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-[#c09a5f]" />
          <span className="font-serif text-sm font-semibold text-brand-graphite">AI Council Assistant</span>
        </div>
        <button 
          onClick={onClose}
          className="text-brand-graphite/40 hover:text-brand-graphite p-1 rounded-md hover:bg-black/5"
        >
          <X size={16} />
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className="space-y-2">
            {/* Bubble Row */}
            <div className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div 
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed shadow-subtle ${
                  msg.sender === 'user' 
                    ? 'bg-brand-navy text-white rounded-tr-sm' 
                    : 'bg-white border border-black/5 text-brand-graphite rounded-tl-sm'
                }`}
              >
                <div>{msg.text}</div>
                <span className="block text-[9px] opacity-40 text-right mt-1.5">{msg.time}</span>
              </div>
            </div>

            {/* Citations & Trace for Agent Messages */}
            {msg.sender === 'agent' && (msg.citations || msg.reasoningSteps) && (
              <div className="pl-2 space-y-1">
                {/* Agent Trace Toggle */}
                {msg.reasoningSteps && (
                  <button 
                    onClick={() => setShowTraceIdx(showTraceIdx === msg.id ? null : msg.id)}
                    className="flex items-center gap-1.5 text-[10px] font-bold text-[#c09a5f] hover:text-[#ad8449]"
                  >
                    <BrainCircuit size={12} />
                    <span>{showTraceIdx === msg.id ? 'Hide reasoning trace' : 'View reasoning trace'}</span>
                    {showTraceIdx === msg.id ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                  </button>
                )}

                {/* Agent Trace Content */}
                {showTraceIdx === msg.id && msg.reasoningSteps && (
                  <div className="bg-white/40 border border-black/5 rounded-lg p-2.5 space-y-1.5 animate-in slide-in-from-top-1 duration-200">
                    <div className="flex justify-between text-[9px] text-brand-graphite/40 font-bold border-b border-black/5 pb-1">
                      <span>Reasoning Chain</span>
                      <span>Latency: {msg.latencyMs || 420}ms</span>
                    </div>
                    {msg.reasoningSteps.map((step, sIdx) => (
                      <div key={sIdx} className="text-[10px] text-brand-graphite/70 flex gap-2">
                        <span className="text-[#c09a5f] font-bold">{sIdx + 1}.</span>
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Citations list */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {msg.citations.map((cite, cIdx) => (
                      <span 
                        key={cIdx} 
                        className="text-[9px] bg-white border border-[#c09a5f]/20 text-brand-graphite/60 px-2 py-0.5 rounded-full cursor-pointer hover:border-[#c09a5f]/50 transition-colors"
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
            <div className="bg-white border border-black/5 rounded-2xl px-4 py-2.5 rounded-tl-sm text-[13px] text-brand-graphite/50 animate-pulse">
              Coordinating agents...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="p-3 border-t border-black/5 bg-white flex gap-2 items-center">
        <input
          type="text"
          className="flex-1 text-xs bg-black/5 border border-transparent rounded-full px-4 py-2.5 outline-none focus:bg-white focus:border-[#c09a5f]/40 transition-colors"
          placeholder="Ask council about wealth..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => { if (e.key === 'Enter') handleSend(); }}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          className="bg-brand-navy hover:bg-[#c09a5f] text-white p-2.5 rounded-full transition-colors flex items-center justify-center disabled:opacity-40 disabled:hover:bg-brand-navy"
        >
          <Send size={12} />
        </button>
      </div>
    </div>
  );
};
