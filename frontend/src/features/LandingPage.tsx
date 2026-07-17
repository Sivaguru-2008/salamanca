import React from 'react';
import { Sparkles, FileText } from 'lucide-react';

interface LandingPageProps {
  onNavigate: (page: string) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigate }) => {
  return (
    <div className="max-w-5xl mx-auto space-y-24 py-8 select-none">
      {/* Hero Section */}
      <div className="text-center space-y-6 pt-12 animate-in fade-in slide-in-from-top-4 duration-300">
        <span className="text-[11px] font-bold tracking-widest text-[#c09a5f] uppercase bg-[#c09a5f]/10 px-3 py-1 rounded-full">
          Enterprise Financial Intelligence Operating System
        </span>
        <h1 className="font-serif text-6xl md:text-7xl font-light text-brand-navy leading-none tracking-tight">
          Wealth intelligence, <br />
          <span className="italic text-[#c09a5f]">fully unified.</span>
        </h1>
        <p className="text-brand-graphite/60 max-w-xl mx-auto text-base leading-relaxed">
          An agentic operating system that debates, plans, and stress-tests your assets, loans, and cash flows using structured multi-agent graphs.
        </p>
        <div className="flex justify-center gap-4 pt-4">
          <button 
            onClick={() => onNavigate('dashboard')}
            className="bg-brand-navy text-white hover:bg-brand-graphite px-8 py-3 rounded-full font-medium text-sm transition-all shadow-subtle hover:translate-y-[-1px]"
          >
            Enter Studio Dashboard
          </button>
          <button 
            onClick={() => onNavigate('advisors')}
            className="border border-brand-graphite text-brand-graphite hover:bg-black/5 px-8 py-3 rounded-full font-medium text-sm transition-all hover:translate-y-[-1px]"
          >
            Consult AI Council
          </button>
        </div>
      </div>

      {/* Grid Features */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        <div className="bg-white border border-black/5 rounded-xl p-6 space-y-3 shadow-subtle hover:border-[#c09a5f]/30 transition-all">
          <Sparkles className="text-[#c09a5f]" size={20} />
          <h3 className="font-serif text-base font-semibold text-brand-navy">AI Council</h3>
          <p className="text-xs text-brand-graphite/60 leading-relaxed">
            Consult a multi-agent council of specialists debating wealth risk, retirement, taxes, and loan optimizations.
          </p>
        </div>

        <div className="bg-white border border-black/5 rounded-xl p-6 space-y-3 shadow-subtle hover:border-[#c09a5f]/30 transition-all">
          <Brain className="text-[#c09a5f]" size={20} />
          <h3 className="font-serif text-base font-semibold text-brand-navy">RAG Explorer</h3>
          <p className="text-xs text-brand-graphite/60 leading-relaxed">
            Inspect chunked database embeddings, retrieval scores, and hallucination grounding checks to verify AI reliability.
          </p>
        </div>

        <div className="bg-white border border-black/5 rounded-xl p-6 space-y-3 shadow-subtle hover:border-[#c09a5f]/30 transition-all">
          <FileText className="text-[#c09a5f]" size={20} />
          <h3 className="font-serif text-base font-semibold text-brand-navy">Loan Intelligence</h3>
          <p className="text-xs text-brand-graphite/60 leading-relaxed">
            Upload complex loan document PDFs to analyze terms, calculate true amortization costs, and evaluate refinancing alternatives.
          </p>
        </div>
      </div>
    </div>
  );
};

const Brain = ({ className, size }: { className?: string; size?: number }) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1 0-3.12 3 3 0 0 1 0-4.88 2.5 2.5 0 0 1 0-3.12A2.5 2.5 0 0 1 9.5 2z"/>
    <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 0-3.12 3 3 0 0 0 0-4.88 2.5 2.5 0 0 0 0-3.12A2.5 2.5 0 0 0 14.5 2z"/>
  </svg>
);
