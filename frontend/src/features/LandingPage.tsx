import React from 'react';
import { Compass, Sparkles, Shield, Cpu, GitBranch, Terminal } from 'lucide-react';

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

      {/* Agents Debate Simulation Widget */}
      <div className="bg-white border border-black/5 rounded-2xl p-8 shadow-premium space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="flex items-center justify-between border-b border-black/5 pb-4">
          <div className="flex items-center gap-3">
            <Cpu className="text-[#c09a5f]" size={18} />
            <span className="font-serif font-semibold text-brand-navy">Active Agent Debate Fabric</span>
          </div>
          <span className="text-[10px] bg-green-500/10 text-green-600 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">
            Consensus Engine Online
          </span>
        </div>

        {/* Debate graph visualization */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="border border-black/5 rounded-xl p-4 space-y-3 bg-[#faf8f5]/50 hover:border-[#c09a5f]/40 transition-colors">
            <span className="text-[10px] text-brand-graphite/40 font-bold uppercase tracking-wider">1. Perception Phase</span>
            <div className="text-xs font-semibold text-brand-navy">Twin-Keeper Agent</div>
            <p className="text-[11px] text-brand-graphite/60">Loads your live financial snapshot, scans memory logs, and pulls twin facts (incomes, debts, balances).</p>
          </div>
          <div className="border border-[#c09a5f]/30 rounded-xl p-4 space-y-3 bg-white hover:border-[#c09a5f] transition-all glow-gold">
            <span className="text-[10px] text-[#c09a5f] font-bold uppercase tracking-wider">2. Debate Phase</span>
            <div className="text-xs font-semibold text-brand-navy">Specialist Debaters</div>
            <p className="text-[11px] text-brand-graphite/60">Budget Agent disputes Lifestyle leaks. Debt Agent pushes Avalanche paydown. Risk Sentinel stresses default scenarios.</p>
          </div>
          <div className="border border-black/5 rounded-xl p-4 space-y-3 bg-[#faf8f5]/50 hover:border-[#c09a5f]/40 transition-colors">
            <span className="text-[10px] text-brand-graphite/40 font-bold uppercase tracking-wider">3. Consensus Phase</span>
            <div className="text-xs font-semibold text-brand-navy">Verifier & Explainer</div>
            <p className="text-[11px] text-brand-graphite/60">Verifier tests suggestions. Explainer compiles opinion consensus report for the dashboard.</p>
          </div>
        </div>
      </div>

      {/* Grid Features */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        <div className="bg-white border border-black/5 rounded-xl p-6 space-y-3 shadow-subtle hover:border-[#c09a5f]/30 transition-all">
          <GitBranch className="text-[#c09a5f]" size={20} />
          <h3 className="font-serif text-base font-semibold text-brand-navy">Knowledge Graph</h3>
          <p className="text-xs text-brand-graphite/60 leading-relaxed">
            Every transaction, account, loan, and financial goal is mapped as a node, illustrating relationships and cashflows dynamically.
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
          <Terminal className="text-[#c09a5f]" size={20} />
          <h3 className="font-serif text-base font-semibold text-brand-navy">Developer Console</h3>
          <p className="text-xs text-brand-graphite/60 leading-relaxed">
            Inspect real-time execution times, API latency metrics, feature flags, Swagger frames, and system health checks.
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
