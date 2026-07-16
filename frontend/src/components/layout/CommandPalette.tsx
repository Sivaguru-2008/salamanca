import React, { useState, useEffect, useRef } from 'react';
import { Search, Compass, Terminal, Shield, Sparkles, X } from 'lucide-react';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (page: string) => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen, onClose, onNavigate
}) => {
  const [search, setSearch] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus Input on Open
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Bind Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!isOpen) return null;

  const items = [
    { id: 'dashboard', label: 'Go to Dashboard Summary', category: 'Pages', icon: Compass },
    { id: 'twin', label: 'Go to Financial Twin Projections', category: 'Pages', icon: Compass },
    { id: 'advisors', label: 'Talk to the AI Advisor Council', category: 'Pages', icon: Sparkles },
    { id: 'loan', label: 'Open Loan Document Analyzer', category: 'Pages', icon: Compass },
    { id: 'tracker', label: 'Open Budget Envelope Tracker', category: 'Pages', icon: Compass },
    { id: 'goals', label: 'Open Goal Planner', category: 'Pages', icon: Compass },
    { id: 'investment', label: 'Check Investment Portfolios', category: 'Pages', icon: Compass },
    { id: 'monitoring', label: 'Check Live Alert Monitors', category: 'Pages', icon: Compass },
    { id: 'graph', label: 'Check Interactive Knowledge Graph', category: 'Pages', icon: Compass },
    { id: 'rag', label: 'Open RAG Context Explorer', category: 'Pages', icon: Compass },
    { id: 'decisions', label: 'Replay Council Decision Log', category: 'Pages', icon: Terminal },
    { id: 'memory', label: 'Inspect Financial Memory Store', category: 'Pages', icon: Compass },
    { id: 'simulator', label: 'Run Monte Carlo Simulator', category: 'Pages', icon: Compass },
    { id: 'observability', label: 'Open Agent execution traces', category: 'Pages', icon: Terminal },
    { id: 'console', label: 'Open Developer Playground Console', category: 'Pages', icon: Terminal },
    { id: 'admin', label: 'Open Administration Panels', category: 'Pages', icon: Shield },
    { id: 'settings', label: 'Open System Settings', category: 'Pages', icon: Shield }
  ];

  const filteredItems = items.filter(item => 
    item.label.toLowerCase().includes(search.toLowerCase()) || 
    item.category.toLowerCase().includes(search.toLowerCase())
  );

  const handleSelect = (id: string) => {
    onNavigate(id);
    setSearch('');
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-[#0a1120]/40 backdrop-blur-sm z-50 flex items-start justify-center pt-24 px-4 select-none">
      <div className="bg-white rounded-2xl w-full max-w-lg border border-black/5 shadow-premium overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Search Header */}
        <div className="flex items-center gap-3 px-4 border-b border-black/5">
          <Search size={18} className="text-brand-graphite/40" />
          <input
            ref={inputRef}
            type="text"
            className="w-full py-4 text-sm bg-transparent outline-none text-brand-graphite placeholder-brand-graphite/40"
            placeholder="Type a page, metric or developer command..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button 
            onClick={onClose}
            className="text-brand-graphite/40 hover:text-brand-graphite p-1 rounded-md hover:bg-black/5"
          >
            <X size={14} />
          </button>
        </div>

        {/* Items List */}
        <div className="max-h-72 overflow-y-auto p-2">
          {filteredItems.length === 0 ? (
            <div className="py-6 text-center text-xs text-brand-graphite/40 italic">
              No pages or actions found matching "{search}"
            </div>
          ) : (
            filteredItems.map((item, idx) => {
              const Icon = item.icon;
              return (
                <button
                  key={idx}
                  onClick={() => handleSelect(item.id)}
                  className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-black/5 transition-colors text-left"
                >
                  <div className="flex items-center gap-3">
                    <Icon size={14} className="text-[#c09a5f]" />
                    <span className="text-xs font-semibold text-brand-graphite/85">{item.label}</span>
                  </div>
                  <span className="text-[10px] text-brand-graphite/35 font-bold uppercase tracking-wider bg-black/5 px-2 py-0.5 rounded">
                    {item.category}
                  </span>
                </button>
              );
            })
          )}
        </div>

        {/* Footer shortcuts */}
        <div className="bg-black/[0.02] border-t border-black/5 px-4 py-2 flex justify-between items-center text-[10px] text-brand-graphite/40">
          <span>Navigate with mouse or scroll</span>
          <span>Esc to Close</span>
        </div>
      </div>
    </div>
  );
};
