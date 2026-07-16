import React, { useEffect, useMemo, useState } from 'react';
import { TrendingDown, Landmark, Activity, Wallet } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { apiService } from '../services/apiService';
import { AnalyticsData, DashboardSummary, HealthScore } from '../types';

interface DashboardPageProps {
  summary: DashboardSummary;
  health: HealthScore;
  snapshot: any;
  onSnapshotChange: (field: string, value: number) => void;
  onSaveSnapshot: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  summary, health, snapshot, onSnapshotChange, onSaveSnapshot
}) => {
  const [saveStatus, setSaveStatus] = useState('Save snapshot');
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);

  useEffect(() => {
    apiService.getAnalytics()
      .then(setAnalytics)
      .catch(() => setAnalytics(null))
      .finally(() => setAnalyticsLoading(false));
  }, [summary]);

  // Live cash-flow history from transaction analytics (last 12 months present in the data).
  const chartData = useMemo(() => {
    const monthly = analytics?.monthly_cash_flow || {};
    const points = Object.entries(monthly)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-12)
      .map(([month, flow]) => ({
        name: new Date(`${month}-01T00:00:00`).toLocaleDateString(undefined, { month: 'short', year: '2-digit' }),
        Income: Math.round(flow.income),
        Expenses: Math.round(flow.expense),
      }));
    if (points.length === 0) {
      // No transactions recorded yet: show the current recurring snapshot as a single point.
      const now = new Date().toLocaleDateString(undefined, { month: 'short', year: '2-digit' });
      return [{ name: now, Income: summary.monthly_income, Expenses: summary.monthly_expense }];
    }
    return points;
  }, [analytics, summary]);

  const handleSave = () => {
    setSaveStatus('Saving...');
    onSaveSnapshot();
    setTimeout(() => {
      setSaveStatus('Saved to DB');
      setTimeout(() => setSaveStatus('Save snapshot'), 1200);
    }, 600);
  };

  const getGradeColor = (grade: string) => {
    if (grade === 'EXCELLENT') return 'text-emerald-500';
    if (grade === 'GOOD') return 'text-green-500';
    if (grade === 'FAIR') return 'text-amber-500';
    return 'text-rose-500';
  };

  return (
    <div className="space-y-8 select-none animate-in fade-in duration-300">
      {/* Title */}
      <div className="flex justify-between items-start">
        <div>
          <span className="text-[10px] font-bold text-[#c09a5f] uppercase tracking-wider block mb-1">Overview</span>
          <h1 className="font-serif text-3xl font-medium text-brand-navy">Your Financial Studio</h1>
          <p className="text-xs text-brand-graphite/50">An editorial, real-time snapshot of your net worth and cash balances.</p>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white border border-black/5 rounded-xl p-5 shadow-subtle flex items-center justify-between">
          <div>
            <span className="text-[10px] text-brand-graphite/40 font-bold uppercase tracking-wider block mb-1">Net Worth</span>
            <span className="text-2xl font-semibold text-brand-navy">${summary.net_worth.toLocaleString()}</span>
          </div>
          <div className="p-3 bg-green-500/10 rounded-lg text-green-600">
            <Landmark size={20} />
          </div>
        </div>

        <div className="bg-white border border-black/5 rounded-xl p-5 shadow-subtle flex items-center justify-between">
          <div>
            <span className="text-[10px] text-brand-graphite/40 font-bold uppercase tracking-wider block mb-1">Liquid Holdings</span>
            <span className="text-2xl font-semibold text-brand-navy">${summary.total_assets.toLocaleString()}</span>
          </div>
          <div className="p-3 bg-[#c09a5f]/10 rounded-lg text-[#c09a5f]">
            <Wallet size={20} />
          </div>
        </div>

        <div className="bg-white border border-black/5 rounded-xl p-5 shadow-subtle flex items-center justify-between">
          <div>
            <span className="text-[10px] text-brand-graphite/40 font-bold uppercase tracking-wider block mb-1">Total Outstanding Debt</span>
            <span className="text-2xl font-semibold text-brand-navy">${summary.total_liabilities.toLocaleString()}</span>
          </div>
          <div className="p-3 bg-red-500/10 rounded-lg text-red-600">
            <TrendingDown size={20} />
          </div>
        </div>

        <div className="bg-white border border-black/5 rounded-xl p-5 shadow-subtle flex items-center justify-between">
          <div>
            <span className="text-[10px] text-brand-graphite/40 font-bold uppercase tracking-wider block mb-1">Financial Health</span>
            <span className="text-2xl font-semibold text-brand-navy">{health.score}/100</span>
          </div>
          <div className={`p-3 rounded-lg bg-black/5 ${getGradeColor(health.grade)}`}>
            <Activity size={20} />
          </div>
        </div>
      </div>

      {/* Main Grid: Visuals & Input Snapshot */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left 2 Columns: Chart & Table */}
        <div className="lg:col-span-2 space-y-8">
          {/* Cashflow Chart */}
          <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium">
            <div className="flex justify-between items-center mb-4">
              <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider">Cash Flow History</span>
              {analyticsLoading && <span className="text-[9px] text-brand-graphite/40 font-bold uppercase tracking-wider animate-pulse">Loading…</span>}
            </div>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorInc" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#c09a5f" stopOpacity={0.15}/>
                      <stop offset="95%" stopColor="#c09a5f" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorExp" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0a1120" stopOpacity={0.1}/>
                      <stop offset="95%" stopColor="#0a1120" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.03)" />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} style={{ fontSize: 10, fill: 'rgba(0,0,0,0.4)' }} />
                  <YAxis tickLine={false} axisLine={false} style={{ fontSize: 10, fill: 'rgba(0,0,0,0.4)' }} />
                  <Tooltip contentStyle={{ background: '#fff', border: '1px solid rgba(0,0,0,0.05)', borderRadius: '8px', fontSize: 11 }} />
                  <Area type="monotone" dataKey="Income" stroke="#c09a5f" strokeWidth={2} fillOpacity={1} fill="url(#colorInc)" />
                  <Area type="monotone" dataKey="Expenses" stroke="#0a1120" strokeWidth={2} fillOpacity={1} fill="url(#colorExp)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Recent ledger transactions */}
          <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider">Recent Transactions</span>
              <span className="text-[10px] text-brand-graphite/40">Showing last 4 logs</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-black/5 text-brand-graphite/40 font-bold uppercase tracking-wider">
                    <th className="py-2.5">Description</th>
                    <th className="py-2.5">Category</th>
                    <th className="py-2.5">Date</th>
                    <th className="py-2.5 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-black/5 text-brand-graphite/85">
                  {summary.recent_transactions.map((tx) => (
                    <tr key={tx.id} className="hover:bg-black/[0.01]">
                      <td className="py-3 font-medium">{tx.description || 'System Allocation'}</td>
                      <td className="py-3">{tx.category}</td>
                      <td className="py-3">{new Date(tx.transaction_date).toLocaleDateString()}</td>
                      <td className={`py-3 text-right font-bold ${tx.type === 'Income' ? 'text-green-600' : 'text-brand-graphite'}`}>
                        {tx.type === 'Income' ? '+' : '-'}${tx.amount}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right 1 Column: Snapshot Input Panel */}
        <div className="space-y-8">
          {/* Health Details Panel */}
          <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-4">
            <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider block">Health Analysis</span>
            <div className="flex items-center gap-3">
              <span className="text-4xl font-light font-serif text-brand-navy">{health.score}</span>
              <div className="flex flex-col">
                <span className={`text-xs font-bold tracking-wider ${getGradeColor(health.grade)}`}>{health.grade}</span>
                <span className="text-[10px] text-brand-graphite/40">Consensus Rating</span>
              </div>
            </div>
            <div className="w-full bg-black/5 h-2 rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all duration-500 bg-emerald-500`} style={{ width: `${health.score}%` }}></div>
            </div>
            
            {/* Key Ratios */}
            <div className="grid grid-cols-2 gap-4 border-t border-black/5 pt-4">
              <div className="space-y-1">
                <span className="text-[9px] font-bold text-brand-graphite/40 uppercase tracking-widest block">Debt Service (DTI)</span>
                <span className="text-lg font-semibold font-serif text-brand-navy">{health.breakdown.debt_to_income.raw_value}</span>
              </div>
              <div className="space-y-1">
                <span className="text-[9px] font-bold text-brand-graphite/40 uppercase tracking-widest block">Savings Rate</span>
                <span className="text-lg font-semibold font-serif text-brand-navy">{health.breakdown.savings_rate.raw_value}</span>
              </div>
            </div>
          </div>

          {/* Snapshots editor */}
          <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-6">
            <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider block">Monthly Snapshot</span>
            
            <div className="space-y-4">
              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Monthly Income</label>
                <input 
                  type="number"
                  className="bg-black/5 border border-transparent focus:bg-white focus:border-[#c09a5f]/40 outline-none rounded-lg px-3 py-2 text-xs font-semibold"
                  value={snapshot.monthlyIncome} 
                  onChange={(e) => onSnapshotChange('monthlyIncome', Number(e.target.value))}
                />
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Monthly Expenses</label>
                <input 
                  type="number"
                  className="bg-black/5 border border-transparent focus:bg-white focus:border-[#c09a5f]/40 outline-none rounded-lg px-3 py-2 text-xs font-semibold"
                  value={snapshot.monthlyExpenses} 
                  onChange={(e) => onSnapshotChange('monthlyExpenses', Number(e.target.value))}
                />
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Total Savings Balance</label>
                <input 
                  type="number"
                  className="bg-black/5 border border-transparent focus:bg-white focus:border-[#c09a5f]/40 outline-none rounded-lg px-3 py-2 text-xs font-semibold"
                  value={snapshot.totalSavings} 
                  onChange={(e) => onSnapshotChange('totalSavings', Number(e.target.value))}
                />
              </div>
            </div>

            <button 
              onClick={handleSave}
              className="w-full bg-brand-navy hover:bg-[#c09a5f] text-white py-2.5 rounded-full text-xs font-semibold transition-colors shadow-subtle"
            >
              {saveStatus}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
