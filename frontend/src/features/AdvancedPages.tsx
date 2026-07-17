import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Key, Plus, Trash2, FileText, Search, Upload, Loader2, RefreshCw, ShieldCheck,
} from 'lucide-react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
} from 'recharts';
import { apiService } from '../services/apiService';
import { CURRENCY_SYMBOL, formatINR, formatINRSigned } from '../lib/currency';
import {
  RAGDocument, Investment, DecisionTrace, MonitorAlert, DocumentChunk,
  User, FinancialProfile,
} from '../types';

const CHART_COLORS = ['#c09a5f', '#0a1120', '#7b8493', '#ad8449', '#4a5568', '#8b6f47'];

const relativeTime = (iso: string | undefined) => {
  if (!iso) return 'unknown';
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days > 1 ? 's' : ''} ago`;
  return new Date(iso).toLocaleDateString();
};

// ==========================================================================
// 1. INVESTMENT PAGE (live /financial/investments + /financial/analytics)
// ==========================================================================
export const InvestmentPage: React.FC = () => {
  const [investments, setInvestments] = useState<Investment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: '', type: 'Equity', amount_invested: 1000, current_value: 1000, ticker: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setInvestments(await apiService.getInvestments());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load investments.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const allocation = useMemo(() => {
    const byType: Record<string, number> = {};
    investments.forEach(inv => {
      byType[inv.type] = (byType[inv.type] || 0) + inv.current_value;
    });
    return Object.entries(byType).map(([name, value]) => ({ name, value: Math.round(value) }));
  }, [investments]);

  const totals = useMemo(() => {
    const invested = investments.reduce((s, i) => s + i.amount_invested, 0);
    const current = investments.reduce((s, i) => s + i.current_value, 0);
    const returnPct = invested > 0 ? ((current - invested) / invested) * 100 : 0;
    return { invested, current, returnPct };
  }, [investments]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiService.createInvestment({
        name: form.name,
        type: form.type,
        amount_invested: form.amount_invested,
        current_value: form.current_value,
        ticker: form.ticker || undefined,
      });
      setShowAdd(false);
      setForm({ name: '', type: 'Equity', amount_invested: 1000, current_value: 1000, ticker: '' });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create investment.');
    }
  };

  const handleDelete = async (id: string) => {
    await apiService.deleteInvestment(id);
    await load();
  };

  return (
    <div className="space-y-6 select-none animate-in fade-in duration-300">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="font-serif text-2xl font-medium text-brand-navy">Investment Portfolio</h2>
          <p className="text-xs text-brand-graphite/50">Live holdings from your database: allocations, cost basis, and unrealized return.</p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="bg-brand-navy hover:bg-[#c09a5f] text-white px-4 py-2 rounded-full text-xs font-semibold flex items-center gap-1.5 transition-colors"
        >
          <Plus size={14} /> Add Holding
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-500/5 px-4 py-3 text-xs font-semibold text-rose-600">{error}</div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {[0, 1, 2].map(i => <div key={i} className="bg-white border border-black/5 rounded-2xl h-56 animate-pulse" />)}
        </div>
      ) : investments.length === 0 ? (
        <div className="bg-white border border-black/5 rounded-2xl p-10 text-center text-xs text-brand-graphite/40">
          No investments recorded yet. Add your first holding to see live allocation analytics.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium md:col-span-2 space-y-4">
            <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider">Asset Distribution</span>
            <div className="h-56 w-full flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={allocation} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={4} dataKey="value">
                    {allocation.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-2 pl-4 text-xs font-semibold text-brand-graphite/80">
                {allocation.map((item, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] }}></span>
                    <span>{item.name}: {formatINR(item.value)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-6">
            <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider block">Portfolio Metrics</span>
            <div className="space-y-4">
              <div className="border-b border-black/5 pb-3">
                <span className="text-[8px] font-bold text-brand-graphite/40 uppercase tracking-widest block">Cost Basis</span>
                <span className="text-xl font-bold font-serif text-brand-navy">{formatINR(totals.invested)}</span>
              </div>
              <div className="border-b border-black/5 pb-3">
                <span className="text-[8px] font-bold text-brand-graphite/40 uppercase tracking-widest block">Current Value</span>
                <span className="text-xl font-bold font-serif text-brand-navy">{formatINR(totals.current)}</span>
              </div>
              <div>
                <span className="text-[8px] font-bold text-brand-graphite/40 uppercase tracking-widest block">Unrealized Return</span>
                <span className={`text-xl font-bold font-serif ${totals.returnPct >= 0 ? 'text-green-600' : 'text-rose-600'}`}>
                  {totals.returnPct >= 0 ? '+' : ''}{totals.returnPct.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>

          {/* Holdings table */}
          <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium md:col-span-3 space-y-4">
            <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider block">Holdings</span>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-black/5 text-brand-graphite/40 font-bold uppercase tracking-wider">
                    <th className="py-2.5">Name</th>
                    <th className="py-2.5">Type</th>
                    <th className="py-2.5">Ticker</th>
                    <th className="py-2.5 text-right">Invested</th>
                    <th className="py-2.5 text-right">Current</th>
                    <th className="py-2.5 text-right">P/L</th>
                    <th className="py-2.5"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-black/5 text-brand-graphite/85">
                  {investments.map(inv => {
                    const pl = inv.current_value - inv.amount_invested;
                    return (
                      <tr key={inv.id} className="hover:bg-black/[0.01]">
                        <td className="py-3 font-semibold text-brand-navy">{inv.name}</td>
                        <td className="py-3">{inv.type}</td>
                        <td className="py-3 font-mono">{inv.ticker || '—'}</td>
                        <td className="py-3 text-right tabular-nums">{formatINR(inv.amount_invested)}</td>
                        <td className="py-3 text-right tabular-nums">{formatINR(inv.current_value)}</td>
                        <td className={`py-3 text-right font-bold ${pl >= 0 ? 'text-green-600' : 'text-rose-600'}`}>
                          {formatINRSigned(pl)}
                        </td>
                        <td className="py-3 text-right">
                          <button onClick={() => handleDelete(inv.id)} className="text-brand-graphite/30 hover:text-red-500">
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {showAdd && (
        <div className="fixed inset-0 bg-[#0a1120]/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <form onSubmit={handleAdd} className="bg-white rounded-2xl w-full max-w-sm border border-black/5 p-6 space-y-4 shadow-premium animate-in zoom-in-95 duration-200">
            <h3 className="font-serif text-base font-semibold text-brand-navy">Add Investment</h3>
            <div className="flex flex-col gap-2">
              <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Name</label>
              <input type="text" required className="bg-black/5 rounded-lg px-3 py-2 text-xs font-semibold outline-none focus:bg-white border border-transparent focus:border-[#c09a5f]/40" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Type</label>
                <select className="bg-black/5 rounded-lg px-3 py-2 text-xs font-semibold outline-none" value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))}>
                  {['Equity', 'Bonds', 'Mutual Fund', 'ETF', 'Gold', 'Crypto', 'Real Estate', 'Other'].map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Ticker</label>
                <input type="text" className="bg-black/5 rounded-lg px-3 py-2 text-xs font-semibold outline-none focus:bg-white border border-transparent focus:border-[#c09a5f]/40" value={form.ticker} onChange={e => setForm(f => ({ ...f, ticker: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Invested ($)</label>
                <input type="number" required min={0} className="bg-black/5 rounded-lg px-3 py-2 text-xs font-semibold outline-none focus:bg-white border border-transparent focus:border-[#c09a5f]/40" value={form.amount_invested} onChange={e => setForm(f => ({ ...f, amount_invested: Number(e.target.value) }))} />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider">Current ($)</label>
                <input type="number" required min={0} className="bg-black/5 rounded-lg px-3 py-2 text-xs font-semibold outline-none focus:bg-white border border-transparent focus:border-[#c09a5f]/40" value={form.current_value} onChange={e => setForm(f => ({ ...f, current_value: Number(e.target.value) }))} />
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => setShowAdd(false)} className="bg-black/5 px-4 py-2 rounded-full text-xs font-semibold">Cancel</button>
              <button type="submit" className="bg-brand-navy text-white px-5 py-2 rounded-full text-xs font-semibold">Add</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

// ==========================================================================
// 2. MONITORING PAGE (alerts derived from live backend data)
// ==========================================================================
export const MonitoringPage: React.FC = () => {
  const [alerts, setAlerts] = useState<MonitorAlert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [summary, budgets, loans, insurances] = await Promise.all([
          apiService.getDashboardSummary(),
          apiService.getBudgets(),
          apiService.getLoans(),
          apiService.getInsurances(),
        ]);

        const derived: MonitorAlert[] = [];
        const budget = budgets[0];

        // Backend-computed budget alerts (category overspend warnings).
        Object.entries((budget as any)?.budget_alerts || {}).forEach(([category, alert]: [string, any]) => {
          derived.push({
            level: alert.status === 'CRITICAL' ? 'high' : 'medium',
            title: `Budget ${alert.status === 'CRITICAL' ? 'exceeded' : 'warning'}: ${category}`,
            desc: alert.message,
            time: 'Current month',
          });
        });

        // Solvency: total debt vs total assets.
        if (summary.total_liabilities > summary.total_assets && summary.total_liabilities > 0) {
          derived.push({
            level: 'high',
            title: 'Solvency stress detected',
            desc: `Total debt (${formatINR(summary.total_liabilities)}) exceeds total assets (${formatINR(summary.total_assets)}). Consider prioritizing high-APR paydown.`,
            time: 'Live',
          });
        }

        // Negative monthly cash flow.
        if (summary.monthly_expense > summary.monthly_income && summary.monthly_income > 0) {
          derived.push({
            level: 'high',
            title: 'Negative monthly cash flow',
            desc: `Monthly expenses (${formatINR(summary.monthly_expense)}) exceed income (${formatINR(summary.monthly_income)}).`,
            time: 'Live',
          });
        }

        // Predatory-rate loans.
        loans.filter(l => l.interest_rate > 36 && l.status === 'ACTIVE').forEach(l => {
          derived.push({
            level: 'high',
            title: `High-interest loan: ${l.lender}`,
            desc: `Active loan carries ${l.interest_rate}% interest on a ${formatINR(l.outstanding_balance)} balance — above the 36% consumer guideline.`,
            time: 'Live',
          });
        });

        // Insurance renewals within 45 days.
        const soon = Date.now() + 45 * 24 * 3600 * 1000;
        insurances.filter(i => i.status === 'ACTIVE' && new Date(i.renewal_date).getTime() < soon).forEach(i => {
          derived.push({
            level: 'medium',
            title: `Insurance renewal approaching: ${i.provider}`,
            desc: `${i.type} policy ${i.policy_number} renews on ${new Date(i.renewal_date).toLocaleDateString()}.`,
            time: 'Upcoming',
          });
        });

        // Low savings rate advisory.
        if (summary.monthly_income > 0 && summary.monthly_savings_rate < 0.1 && summary.monthly_savings_rate >= 0) {
          derived.push({
            level: 'low',
            title: 'Savings rate below 10%',
            desc: `Current savings rate is ${(summary.monthly_savings_rate * 100).toFixed(1)}%. The council recommends targeting at least 20%.`,
            time: 'Live',
          });
        }

        setAlerts(derived);
      } catch {
        setAlerts([]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6 select-none animate-in fade-in duration-300">
      <div>
        <h2 className="font-serif text-2xl font-medium text-brand-navy">Continuous Monitor Alert Center</h2>
        <p className="text-xs text-brand-graphite/50">Alerts computed from your live budgets, loans, insurance, and cash flow.</p>
      </div>

      {loading ? (
        <div className="space-y-3">{[0, 1, 2].map(i => <div key={i} className="bg-white border border-black/5 rounded-2xl h-20 animate-pulse" />)}</div>
      ) : alerts.length === 0 ? (
        <div className="bg-white border border-black/5 rounded-2xl p-10 text-center space-y-2">
          <ShieldCheck size={28} className="mx-auto text-green-500" />
          <p className="text-xs text-brand-graphite/50 font-semibold">All clear — no risk conditions detected in your live financial data.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((item, idx) => (
            <div key={idx} className="bg-white border border-black/5 rounded-2xl p-5 shadow-premium flex gap-4 hover:translate-x-1 transition-all">
              <span className={`text-[8.5px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full shrink-0 h-fit ${
                item.level === 'high'
                  ? 'bg-red-500/10 text-red-600 border border-red-200'
                  : item.level === 'medium'
                    ? 'bg-amber-500/10 text-amber-600 border border-amber-200'
                    : 'bg-blue-500/10 text-blue-600 border border-blue-200'
              }`}>
                {item.level} priority
              </span>
              <div className="space-y-1.5 flex-1">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-brand-navy">{item.title}</span>
                  <span className="text-[10px] text-brand-graphite/40">{item.time}</span>
                </div>
                <p className="text-xs text-brand-graphite/60 leading-relaxed">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ==========================================================================
// 3. RAG EXPLORER PAGE (upload → extract → chunk → retrieve, all live)
// ==========================================================================
export const RagPage: React.FC = () => {
  const [docs, setDocs] = useState<RAGDocument[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<RAGDocument | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<DocumentChunk[] | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    const res = await apiService.getUploadedDocuments();
    setDocs(res);
    setSelectedDoc(prev => (prev ? res.find(d => d.id === prev.id) ?? res[0] ?? null : res[0] ?? null));
  }, []);

  useEffect(() => { load().catch(() => undefined); }, [load]);

  const handleFiles = async (files: FileList | File[]) => {
    setUploadError(null);
    for (const file of Array.from(files)) {
      const controller = new AbortController();
      abortRef.current = controller;
      setUploadPct(0);
      try {
        const doc = await apiService.uploadDocument(
          file,
          (event) => {
            if (event.total) setUploadPct(Math.round((event.loaded / event.total) * 100));
          },
          controller.signal,
        );
        await load();
        setSelectedDoc(doc);
        setSearchResults(null);
      } catch (e: any) {
        if (e?.code !== 'ERR_CANCELED') {
          setUploadError(e?.response?.data?.detail || e?.message || `Upload of ${file.name} failed.`);
        }
      } finally {
        setUploadPct(null);
        abortRef.current = null;
      }
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDoc || !query.trim()) return;
    setSearching(true);
    try {
      const res = await apiService.searchDocumentChunks(selectedDoc.id, query.trim());
      setSearchResults(res.results);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleDelete = async (docId: string) => {
    await apiService.deleteDocument(docId);
    setSearchResults(null);
    await load();
  };

  const chunksToShow = searchResults ?? selectedDoc?.chunks ?? [];

  return (
    <div className="space-y-6 select-none animate-in fade-in duration-300">
      <div>
        <h2 className="font-serif text-2xl font-medium text-brand-navy">RAG Embeddings Explorer</h2>
        <p className="text-xs text-brand-graphite/50">Upload documents, inspect extracted chunks, and run live similarity retrieval.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left: upload + index */}
        <div className="space-y-4">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files); }}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-all ${
              dragOver ? 'border-[#c09a5f] bg-[#c09a5f]/5' : 'border-black/10 bg-white hover:border-[#c09a5f]/40'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.txt,.csv,.md,.json,.log,.tsv"
              className="hidden"
              onChange={(e) => { if (e.target.files?.length) handleFiles(e.target.files); e.target.value = ''; }}
            />
            {uploadPct !== null ? (
              <div className="space-y-2">
                <Loader2 size={20} className="mx-auto animate-spin text-[#c09a5f]" />
                <div className="w-full bg-black/5 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-[#c09a5f] h-full rounded-full transition-all" style={{ width: `${uploadPct}%` }} />
                </div>
                <div className="flex items-center justify-center gap-3">
                  <span className="text-[10px] font-bold text-brand-graphite/50">{uploadPct}% uploaded</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); abortRef.current?.abort(); }}
                    className="text-[10px] font-bold text-red-500 hover:text-red-600 uppercase tracking-wider"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload size={20} className="mx-auto text-[#c09a5f]" />
                <p className="text-xs font-semibold text-brand-navy">Drop files or click to upload</p>
                <p className="text-[9px] text-brand-graphite/40 uppercase tracking-wider">PDF · TXT · CSV · MD (max 15 MB)</p>
              </div>
            )}
          </div>

          {uploadError && (
            <div className="rounded-lg border border-red-200 bg-red-500/5 px-3 py-2 text-[11px] font-semibold text-rose-600">{uploadError}</div>
          )}

          <div className="bg-white border border-black/5 rounded-2xl p-5 shadow-premium space-y-4">
            <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider block">Uploaded Index</span>
            {docs.length === 0 && (
              <p className="text-[11px] text-brand-graphite/40 italic">No documents yet — upload one to build the vector index.</p>
            )}
            <div className="space-y-2">
              {docs.map(doc => (
                <div
                  key={doc.id}
                  className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg border text-left transition-colors ${
                    selectedDoc?.id === doc.id
                      ? 'border-[#c09a5f] bg-[#c09a5f]/5'
                      : 'border-black/5 hover:bg-black/[0.01]'
                  }`}
                >
                  <button className="flex items-center gap-3 flex-1 overflow-hidden text-left" onClick={() => { setSelectedDoc(doc); setSearchResults(null); }}>
                    <FileText size={16} className="text-[#c09a5f] shrink-0" />
                    <div className="flex-1 overflow-hidden">
                      <span className="text-xs font-semibold text-brand-navy truncate block">{doc.name}</span>
                      <span className="text-[9px] text-brand-graphite/40 font-mono block">
                        {Math.max(1, Math.round(doc.size / 1024))} KB · {doc.chunks.length} chunks · {new Date(doc.uploaded_at).toLocaleDateString()}
                      </span>
                    </div>
                  </button>
                  <button onClick={() => handleDelete(doc.id)} className="text-brand-graphite/30 hover:text-red-500 shrink-0">
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: retrieval + chunk inspector */}
        <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium lg:col-span-2 space-y-5">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider">Retrieval & Embedding Chunks</span>
            {searchResults && (
              <button onClick={() => setSearchResults(null)} className="text-[10px] font-bold uppercase tracking-wider text-brand-graphite/40 hover:text-brand-graphite">
                Clear search — show all chunks
              </button>
            )}
          </div>

          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="flex-1 flex items-center gap-2 bg-black/5 rounded-full px-4 border border-transparent focus-within:bg-white focus-within:border-[#c09a5f]/40 transition-all">
              <Search size={13} className="text-brand-graphite/30 shrink-0" />
              <input
                type="text"
                className="flex-1 bg-transparent outline-none py-2.5 text-xs font-semibold"
                placeholder={selectedDoc ? `Similarity search inside ${selectedDoc.name}...` : 'Select a document first...'}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={!selectedDoc}
              />
            </div>
            <button
              type="submit"
              disabled={!selectedDoc || !query.trim() || searching}
              className="bg-brand-navy hover:bg-[#c09a5f] text-white px-5 rounded-full text-xs font-semibold transition-colors disabled:opacity-40"
            >
              {searching ? 'Scoring...' : 'Retrieve'}
            </button>
          </form>

          {selectedDoc ? (
            chunksToShow.length === 0 ? (
              <div className="text-xs text-brand-graphite/40 italic py-12 text-center">
                {searchResults
                  ? 'No chunks matched this query.'
                  : 'No text could be extracted from this document.'}
              </div>
            ) : (
              <div className="space-y-4 max-h-[480px] overflow-y-auto pr-1">
                {chunksToShow.map((chunk) => (
                  <div key={chunk.index} className="border border-black/5 rounded-xl p-4 space-y-2 bg-[#faf8f5]/30">
                    <div className="flex justify-between items-center border-b border-black/5 pb-2 text-[9px] text-brand-graphite/40 font-bold uppercase tracking-wider">
                      <span>Chunk #{chunk.index + 1} · {selectedDoc.name}</span>
                      {chunk.score !== undefined ? (
                        <span className="text-[#c09a5f]">Similarity: {(chunk.score * 100).toFixed(1)}%</span>
                      ) : (
                        <span>{chunk.text.length} chars</span>
                      )}
                    </div>
                    <p className="text-xs text-brand-graphite/75 leading-relaxed font-mono-code whitespace-pre-wrap">{chunk.text}</p>
                  </div>
                ))}
              </div>
            )
          ) : (
            <div className="text-xs text-brand-graphite/40 italic py-12 text-center">
              Upload and select a document to inspect its extracted chunks.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ==========================================================================
// 4. DECISIONS PAGE (real council decision log from Redis via /chat/decisions)
// ==========================================================================
export const DecisionsPage: React.FC = () => {
  const [trace, setTrace] = useState<DecisionTrace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setTrace(await apiService.getDecisions());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load the decision log.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-6 select-none animate-in fade-in duration-300">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="font-serif text-2xl font-medium text-brand-navy">Decision Replay Center</h2>
          <p className="text-xs text-brand-graphite/50">Every real council exchange, recorded as it happened: agent, model, latency, and verdict.</p>
        </div>
        <button onClick={load} className="border border-brand-graphite hover:bg-black/5 px-3 py-1.5 rounded-full text-[10px] font-semibold flex items-center gap-1.5">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-6">
        <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider block">Council Execution Log</span>

        {loading ? (
          <div className="space-y-4">{[0, 1, 2].map(i => <div key={i} className="h-14 bg-black/[0.02] rounded-xl animate-pulse" />)}</div>
        ) : error ? (
          <div className="text-xs text-rose-600 font-semibold">{error}</div>
        ) : trace.length === 0 ? (
          <div className="text-xs text-brand-graphite/40 italic py-8 text-center">
            No decisions recorded yet. Ask the AI council a question and the exchange will appear here.
          </div>
        ) : (
          <div className="relative pl-6 border-l border-black/5 space-y-6">
            {trace.map((item) => (
              <div key={item.id} className="relative">
                <span className="absolute -left-[30px] top-1 w-2 h-2 rounded-full bg-[#c09a5f] border-4 border-white box-content"></span>
                <div className="space-y-1">
                  <div className="flex justify-between items-center text-xs font-semibold gap-2 flex-wrap">
                    <span className="text-brand-navy">{item.agent_name} — {item.action.replace(/_/g, ' ')}</span>
                    <span className="flex items-center gap-2">
                      <span className="text-[9px] font-mono text-brand-graphite/40">{item.provider}:{item.model} · {item.latency_ms}ms</span>
                      <span className="text-[9px] text-brand-graphite/40">{relativeTime(item.timestamp)}</span>
                    </span>
                  </div>
                  <p className="text-[11.5px] text-brand-graphite/60 leading-relaxed"><strong>Q:</strong> {item.question}</p>
                  <p className="text-[11.5px] text-brand-graphite/60 leading-relaxed font-mono-code"><strong>A:</strong> {item.answer_preview}{item.answer_preview.length >= 300 ? '…' : ''}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// ==========================================================================
// 5. SETTINGS PAGE (live user account + financial profile + sessions)
// ==========================================================================
interface SettingsPageProps {
  user: User | null;
  onUserUpdated: (user: User) => void;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ user, onUserUpdated }) => {
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [nameStatus, setNameStatus] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [passwordStatus, setPasswordStatus] = useState<string | null>(null);
  const [profile, setProfile] = useState<FinancialProfile | null>(null);
  const [profileStatus, setProfileStatus] = useState<string | null>(null);
  const [sessionsStatus, setSessionsStatus] = useState<string | null>(null);

  useEffect(() => {
    apiService.getProfile().then(setProfile).catch(() => setProfile(null));
  }, []);

  const saveName = async (e: React.FormEvent) => {
    e.preventDefault();
    setNameStatus('Saving…');
    try {
      const updated = await apiService.updateMe({ full_name: fullName.trim() });
      onUserUpdated(updated);
      setNameStatus('Saved');
    } catch {
      setNameStatus('Save failed');
    }
  };

  const savePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      setPasswordStatus('Password must be at least 8 characters.');
      return;
    }
    setPasswordStatus('Saving…');
    try {
      await apiService.updateMe({ password: newPassword });
      setNewPassword('');
      setPasswordStatus('Password updated.');
    } catch (err: any) {
      setPasswordStatus(err?.response?.data?.detail || 'Update failed.');
    }
  };

  const saveProfileField = async (field: 'currency' | 'risk_profile', value: string) => {
    if (!profile) return;
    setProfile({ ...profile, [field]: value });
    setProfileStatus('Saving…');
    try {
      const updated = await apiService.updateProfile({ [field]: value });
      setProfile(updated);
      setProfileStatus('Saved');
    } catch {
      setProfileStatus('Save failed');
    }
  };

  const revokeAllSessions = async () => {
    setSessionsStatus('Revoking…');
    try {
      await apiService.logout(true);
      // Access token stays valid until expiry, but refresh sessions are gone;
      // the unauthorized event will route back to login on the next refresh.
      window.dispatchEvent(new CustomEvent('fios:unauthorized'));
    } catch {
      setSessionsStatus('Failed to revoke sessions.');
    }
  };

  return (
    <div className="space-y-6 select-none animate-in fade-in duration-300">
      <div>
        <h2 className="font-serif text-2xl font-medium text-brand-navy">System Settings</h2>
        <p className="text-xs text-brand-graphite/50">Account, security, and financial-profile preferences — all persisted to the backend.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Account */}
        <form onSubmit={saveName} className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-4">
          <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider block">Account</span>
          <div className="space-y-3 text-xs">
            <div className="flex flex-col gap-1.5">
              <span className="text-[9px] text-brand-graphite/40 uppercase font-bold tracking-wider">Account Email</span>
              <input type="email" disabled className="bg-black/5 border border-transparent rounded-lg px-3 py-2 font-semibold text-brand-graphite/60" value={user?.email || ''} />
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-[9px] text-brand-graphite/40 uppercase font-bold tracking-wider">Full Name</span>
              <input
                type="text"
                className="bg-black/5 border border-transparent focus:bg-white focus:border-[#c09a5f]/40 outline-none rounded-lg px-3 py-2 font-semibold"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
              />
            </div>
            <div className="flex items-center justify-between">
              <button type="submit" className="bg-brand-navy hover:bg-[#c09a5f] text-white px-4 py-2 rounded-full text-xs font-semibold transition-colors">
                Save name
              </button>
              {nameStatus && <span className="text-[10px] text-brand-graphite/40 font-semibold">{nameStatus}</span>}
            </div>
          </div>
        </form>

        {/* Security */}
        <form onSubmit={savePassword} className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-4">
          <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider block">Security</span>
          <div className="space-y-3 text-xs">
            <div className="flex flex-col gap-1.5">
              <span className="text-[9px] text-brand-graphite/40 uppercase font-bold tracking-wider">New Password</span>
              <input
                type="password"
                autoComplete="new-password"
                className="bg-black/5 border border-transparent focus:bg-white focus:border-[#c09a5f]/40 outline-none rounded-lg px-3 py-2 font-semibold"
                placeholder="At least 8 characters"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
              />
            </div>
            <div className="flex items-center justify-between">
              <button type="submit" className="bg-brand-navy hover:bg-[#c09a5f] text-white px-4 py-2 rounded-full text-xs font-semibold transition-colors flex items-center gap-1.5">
                <Key size={12} /> Update password
              </button>
              {passwordStatus && <span className="text-[10px] text-brand-graphite/40 font-semibold">{passwordStatus}</span>}
            </div>
          </div>
        </form>

        {/* Financial profile */}
        <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-4">
          <div className="flex justify-between items-center">
            <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider">Financial Profile</span>
            {profileStatus && <span className="text-[10px] text-brand-graphite/40 font-semibold">{profileStatus}</span>}
          </div>
          {profile ? (
            <div className="grid grid-cols-2 gap-4 text-xs">
              {/* Every amount in the app is rendered in rupees, so the base
                  currency is fixed rather than selectable. */}
              <div className="flex flex-col gap-1.5">
                <span className="text-[9px] text-brand-graphite/40 uppercase font-bold tracking-wider">Base Currency</span>
                <span className="rounded-lg bg-black/5 px-3 py-2 font-semibold text-brand-graphite/70">
                  Indian Rupee ({CURRENCY_SYMBOL})
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-[9px] text-brand-graphite/40 uppercase font-bold tracking-wider">Risk Profile</span>
                <select
                  className="bg-black/5 rounded-lg px-3 py-2 font-semibold outline-none"
                  value={profile.risk_profile}
                  onChange={e => saveProfileField('risk_profile', e.target.value)}
                >
                  {['LOW', 'MEDIUM', 'HIGH'].map(r => <option key={r}>{r}</option>)}
                </select>
              </div>
            </div>
          ) : (
            <div className="h-16 bg-black/[0.02] rounded-lg animate-pulse" />
          )}
        </div>

        {/* Sessions */}
        <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-4">
          <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider block">Active Sessions</span>
          <p className="text-[11px] text-brand-graphite/50 leading-relaxed">
            Signing out everywhere revokes every refresh session issued to your account, on all devices.
          </p>
          <div className="flex items-center justify-between">
            <button
              onClick={revokeAllSessions}
              className="border border-red-200 text-red-600 hover:bg-red-500/5 px-4 py-2 rounded-full text-xs font-semibold transition-colors"
            >
              Sign out everywhere
            </button>
            {sessionsStatus && <span className="text-[10px] text-brand-graphite/40 font-semibold">{sessionsStatus}</span>}
          </div>
        </div>
      </div>
    </div>
  );
};
