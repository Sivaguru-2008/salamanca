import React, { useState } from 'react';
import { WalletCards, Landmark, Plus, Trash2, X } from 'lucide-react';
import { Budget, Liability, Loan } from '../types';

interface TrackerPageProps {
  envelopes: Budget['category_budgets'];
  utilization: Budget['budget_utilization'];
  debts: Liability[];
  loans: Loan[];
  onUpdateEnvelope: (cat: string, field: 'allocated' | 'spent', value: number) => void;
  onAddEnvelope: (cat: string, allocated: number) => void;
  onDeleteEnvelope: (cat: string) => void;
  onUpdateDebt: (id: string, field: 'balance' | 'apr' | 'monthly', value: number) => void;
  onAddDebt: (name: string, balance: number, apr: number, monthly: number) => void;
  onDeleteDebt: (id: string) => void;
}

export const TrackerPage: React.FC<TrackerPageProps> = ({
  envelopes, utilization, debts, loans,
  onUpdateEnvelope, onAddEnvelope, onDeleteEnvelope,
  onUpdateDebt, onAddDebt, onDeleteDebt
}) => {
  const [showEnvModal, setShowEnvModal] = useState(false);
  const [showDebtModal, setShowDebtModal] = useState(false);

  // New Envelope Form State
  const [envName, setEnvName] = useState('');
  const [envAlloc, setEnvAlloc] = useState(500);

  // New Debt Form State
  const [debtName, setDebtName] = useState('');
  const [debtBal, setDebtBal] = useState(3000);
  const [debtApr, setDebtApr] = useState(12.5);
  const [debtMin, setDebtMin] = useState(150);

  const handleAddEnv = (e: React.FormEvent) => {
    e.preventDefault();
    if (!envName.trim()) return;
    onAddEnvelope(envName.trim(), envAlloc);
    setEnvName('');
    setEnvAlloc(500);
    setShowEnvModal(false);
  };

  const handleAddDebt = (e: React.FormEvent) => {
    e.preventDefault();
    if (!debtName.trim()) return;
    onAddDebt(debtName.trim(), debtBal, debtApr, debtMin);
    setDebtName('');
    setDebtBal(3000);
    setDebtApr(12.5);
    setDebtMin(150);
    setShowDebtModal(false);
  };

  return (
    <div className="space-y-8 select-none animate-in fade-in duration-300">
      {/* Title */}
      <div>
        <span className="text-[10px] font-bold text-[#c09a5f] uppercase tracking-wider block mb-1">Tracker</span>
        <h1 className="font-serif text-3xl font-medium text-brand-navy">Budget & debts</h1>
        <p className="text-xs text-brand-graphite/50">Track envelopes and payoff progress in one calm view.</p>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 items-start">
        
        {/* Left Column: Envelopes (3 Cols) */}
        <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium lg:col-span-3 space-y-6">
          <div className="flex justify-between items-center border-b border-black/5 pb-3">
            <div className="flex items-center gap-2">
              <WalletCards className="text-[#c09a5f]" size={16} />
              <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider">Envelopes</span>
            </div>
            <button 
              onClick={() => setShowEnvModal(true)}
              className="border border-brand-graphite hover:bg-black/5 px-3 py-1.5 rounded-full text-[10px] font-semibold flex items-center gap-1.5"
            >
              <Plus size={12} /> Add envelope
            </button>
          </div>

          <div className="space-y-6">
            {Object.keys(envelopes).map((cat) => {
              const allocated = envelopes[cat] || 0;
              const spent = utilization?.[cat] || 0;
              const pct = allocated > 0 ? Math.round((spent / allocated) * 100) : 0;
              return (
                <div key={cat} className="space-y-2 border-b border-black/[0.03] pb-4 last:border-b-0 last:pb-0">
                  <div className="flex justify-between items-center">
                    <span className="font-serif text-sm font-semibold text-brand-navy">{cat}</span>
                    <div className="flex items-center gap-4">
                      {/* Inputs */}
                      <div className="flex flex-col text-right">
                        <span className="text-[8px] font-bold uppercase tracking-wider text-brand-graphite/40">Allocated</span>
                        <input 
                          type="number" 
                          className="w-20 text-xs font-semibold text-right outline-none bg-black/5 border border-transparent rounded px-1.5 py-0.5 focus:bg-white focus:border-[#c09a5f]/40"
                          value={allocated} 
                          onChange={(e) => onUpdateEnvelope(cat, 'allocated', Number(e.target.value))}
                        />
                      </div>
                      <div className="flex flex-col text-right">
                        <span className="text-[8px] font-bold uppercase tracking-wider text-brand-graphite/40">Spent</span>
                        <input 
                          type="number" 
                          className="w-20 text-xs font-semibold text-right outline-none bg-black/5 border border-transparent rounded px-1.5 py-0.5 focus:bg-white focus:border-[#c09a5f]/40"
                          value={spent} 
                          onChange={(e) => onUpdateEnvelope(cat, 'spent', Number(e.target.value))}
                        />
                      </div>
                      <button 
                        onClick={() => onDeleteEnvelope(cat)}
                        className="text-brand-graphite/35 hover:text-red-500 p-1 mt-3"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                  {/* Progress bar */}
                  <div className="flex items-center gap-4">
                    <div className="flex-1 bg-black/5 h-1.5 rounded-full overflow-hidden">
                      <div 
                        className={`h-full rounded-full transition-all duration-300 ${pct > 90 ? 'bg-red-500' : 'bg-[#c09a5f]'}`}
                        style={{ width: `${Math.min(pct, 100)}%` }}
                      ></div>
                    </div>
                    <span className="text-[10px] font-semibold text-brand-graphite/50 w-8 text-right">{pct}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Debts (2 Cols) */}
        <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium lg:col-span-2 space-y-6">
          <div className="flex justify-between items-center border-b border-black/5 pb-3">
            <div className="flex items-center gap-2">
              <Landmark className="text-[#c09a5f]" size={16} />
              <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider">Outstanding Debts</span>
            </div>
            <button 
              onClick={() => setShowDebtModal(true)}
              className="border border-brand-graphite hover:bg-black/5 px-3 py-1.5 rounded-full text-[10px] font-semibold flex items-center gap-1.5"
            >
              <Plus size={12} /> Add debt
            </button>
          </div>

          <div className="space-y-4">
            {debts.map((d) => (
              <div key={d.id} className="border border-black/5 rounded-xl p-4 bg-[#faf8f5]/40 space-y-4 relative">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-brand-navy">{d.name}</span>
                  <button 
                    onClick={() => onDeleteDebt(d.id)}
                    className="text-brand-graphite/35 hover:text-red-500 p-1"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
                
                {/* Inputs Grid */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="flex flex-col gap-1">
                    <span className="text-[8px] font-bold uppercase tracking-wider text-brand-graphite/40">Balance</span>
                    <input 
                      type="number" 
                      className="w-full text-xs font-semibold bg-white border border-black/5 rounded px-2 py-1 outline-none focus:border-[#c09a5f]/40"
                      value={d.outstanding_balance} 
                      onChange={(e) => onUpdateDebt(d.id, 'balance', Number(e.target.value))}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[8px] font-bold uppercase tracking-wider text-brand-graphite/40">APR %</span>
                    <input 
                      type="number" 
                      className="w-full text-xs font-semibold bg-white border border-black/5 rounded px-2 py-1 outline-none focus:border-[#c09a5f]/40"
                      value={d.apr} 
                      onChange={(e) => onUpdateDebt(d.id, 'apr', Number(e.target.value))}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[8px] font-bold uppercase tracking-wider text-brand-graphite/40">Monthly</span>
                    <input 
                      type="number" 
                      className="w-full text-xs font-semibold bg-white border border-black/5 rounded px-2 py-1 outline-none focus:border-[#c09a5f]/40"
                      value={d.monthly_minimum_payment} 
                      onChange={(e) => onUpdateDebt(d.id, 'monthly', Number(e.target.value))}
                    />
                  </div>
                </div>
              </div>
            ))}

            {/* Static Loans display */}
            {loans.map(l => (
              <div key={l.id} className="border border-black/5 rounded-xl p-4 bg-black/[0.01] space-y-2 opacity-70">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-brand-navy">{l.lender} (Loan)</span>
                  <span className="text-[9px] bg-green-500/10 text-green-600 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">
                    {l.status}
                  </span>
                </div>
                <div className="grid grid-cols-3 text-center text-[10px] text-brand-graphite/60 font-semibold gap-2">
                  <div>
                    <span className="block text-[8px] text-brand-graphite/40">Balance</span>
                    ${l.outstanding_balance.toLocaleString()}
                  </div>
                  <div>
                    <span className="block text-[8px] text-brand-graphite/40">Interest</span>
                    {l.interest_rate}%
                  </div>
                  <div>
                    <span className="block text-[8px] text-brand-graphite/40">EMI</span>
                    ${l.emi}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* Envelope Modal Overlay */}
      {showEnvModal && (
        <div className="fixed inset-0 bg-[#0a1120]/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <form 
            onSubmit={handleAddEnv}
            className="bg-white rounded-2xl w-full max-w-sm border border-black/5 p-6 space-y-5 shadow-premium animate-in zoom-in-95 duration-200"
          >
            <div className="flex justify-between items-center border-b border-black/5 pb-3">
              <h3 className="font-serif text-base font-semibold text-brand-navy">Create Envelope</h3>
              <button type="button" onClick={() => setShowEnvModal(false)} className="text-brand-graphite/40 hover:text-brand-graphite">
                <X size={16} />
              </button>
            </div>
            
            <div className="space-y-4">
              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Category Name</label>
                <input 
                  type="text" required
                  className="bg-black/5 border border-transparent focus:bg-white focus:border-[#c09a5f]/40 outline-none rounded-lg px-3 py-2 text-xs font-semibold"
                  placeholder="e.g. Subscriptions"
                  value={envName} onChange={(e) => setEnvName(e.target.value)}
                />
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Allocated Budget ($)</label>
                <input 
                  type="number" required min="1"
                  className="bg-black/5 border border-transparent focus:bg-white focus:border-[#c09a5f]/40 outline-none rounded-lg px-3 py-2 text-xs font-semibold"
                  value={envAlloc} onChange={(e) => setEnvAlloc(Number(e.target.value))}
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button 
                type="button" onClick={() => setShowEnvModal(false)}
                className="bg-black/5 hover:bg-black/10 px-4 py-2 rounded-full text-xs font-semibold transition-colors"
              >
                Cancel
              </button>
              <button 
                type="submit"
                className="bg-brand-navy hover:bg-[#c09a5f] text-white px-5 py-2 rounded-full text-xs font-semibold transition-colors"
              >
                Create
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Debt Modal Overlay */}
      {showDebtModal && (
        <div className="fixed inset-0 bg-[#0a1120]/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <form 
            onSubmit={handleAddDebt}
            className="bg-white rounded-2xl w-full max-w-sm border border-black/5 p-6 space-y-5 shadow-premium animate-in zoom-in-95 duration-200"
          >
            <div className="flex justify-between items-center border-b border-black/5 pb-3">
              <h3 className="font-serif text-base font-semibold text-brand-navy">Create Debt</h3>
              <button type="button" onClick={() => setShowDebtModal(false)} className="text-brand-graphite/40 hover:text-brand-graphite">
                <X size={16} />
              </button>
            </div>

            <div className="space-y-4">
              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Debt Name</label>
                <input 
                  type="text" required
                  className="bg-black/5 border border-transparent focus:bg-white focus:border-[#c09a5f]/40 outline-none rounded-lg px-3 py-2 text-xs font-semibold"
                  placeholder="e.g. Chase Slate"
                  value={debtName} onChange={(e) => setDebtName(e.target.value)}
                />
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Outstanding Balance ($)</label>
                <input 
                  type="number" required
                  className="bg-black/5 border border-transparent focus:bg-white focus:border-[#c09a5f]/40 outline-none rounded-lg px-3 py-2 text-xs font-semibold"
                  value={debtBal} onChange={(e) => setDebtBal(Number(e.target.value))}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">APR (%)</label>
                  <input 
                    type="number" required step="0.1"
                    className="bg-black/5 border border-transparent focus:bg-white focus:border-[#c09a5f]/40 outline-none rounded-lg px-3 py-2 text-xs font-semibold"
                    value={debtApr} onChange={(e) => setDebtApr(Number(e.target.value))}
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Monthly Min ($)</label>
                  <input 
                    type="number" required
                    className="bg-black/5 border border-transparent focus:bg-white focus:border-[#c09a5f]/40 outline-none rounded-lg px-3 py-2 text-xs font-semibold"
                    value={debtMin} onChange={(e) => setDebtMin(Number(e.target.value))}
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button 
                type="button" onClick={() => setShowDebtModal(false)}
                className="bg-black/5 hover:bg-black/10 px-4 py-2 rounded-full text-xs font-semibold transition-colors"
              >
                Cancel
              </button>
              <button 
                type="submit"
                className="bg-brand-navy hover:bg-[#c09a5f] text-white px-5 py-2 rounded-full text-xs font-semibold transition-colors"
              >
                Create
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
