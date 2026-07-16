import React, { useState } from 'react';
import { AlertTriangle, ShieldAlert, CheckCircle, Upload } from 'lucide-react';
import { apiService } from '../services/apiService';
import { LoanAnalysis } from '../types';

export const LoanPage: React.FC = () => {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<LoanAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleLoadSample = () => {
    setText(`LOAN AGREEMENT AND TERM SHEET
Lender: QuickCapital Payday Services
Borrower: Guest User
Principal Loan Amount: $1,200.00
Disbursement Date: 2026-07-16
Maturity Date: 2026-08-16 (1 Month term)
Interest Details: Flat interest charge of $288.00 due at maturity.
Equivalent annual percentage rate (APR): 240.0%
Late Payment Terms: A penalty fee of $50.00 plus an additional 15% interest accrues weekly on any outstanding balances.
Prepayment Penalty: Borrower may NOT pay back early unless the full contract interest of $288 is satisfied in full.
Arbitration: Borrower agrees to settle any dispute via binding arbitration, waiving all rights to class action lawsuits.`);
  };

  const handleAnalyze = async () => {
    if (!text.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiService.analyzeLoanDocument(text);
      setAnalysis(result);
    } catch (e) {
      setAnalysis(null);
      setError(e instanceof Error ? e.message : 'Loan analysis failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 select-none animate-in fade-in duration-300">
      {/* Title */}
      <div>
        <span className="text-[10px] font-bold text-[#c09a5f] uppercase tracking-wider block mb-1">Consumer Protection</span>
        <h1 className="font-serif text-3xl font-medium text-brand-navy">Loan Document Analyzer</h1>
        <p className="text-xs text-brand-graphite/50">Paste any loan agreement, term sheet, or offer letter. We'll flag what to watch for.</p>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        {/* Input Panel */}
        <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium flex flex-col min-h-[460px]">
          <div className="flex justify-between items-center mb-4">
            <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider">Loan Agreement Text</span>
            <button 
              onClick={handleLoadSample}
              className="text-[10px] font-bold uppercase tracking-wider text-[#c09a5f] hover:text-[#ad8449]"
            >
              Load Sample Document
            </button>
          </div>
          <textarea
            className="flex-1 w-full min-h-[280px] text-xs bg-black/5 border border-transparent rounded-lg p-4 outline-none focus:bg-white focus:border-[#c09a5f]/45 resize-none leading-relaxed transition-all"
            placeholder="Paste the full text of the agreement here..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="flex justify-between items-center mt-5">
            <span className="text-[10px] text-brand-graphite/40">{text.length} characters</span>
            <button
              onClick={handleAnalyze}
              disabled={!text.trim() || loading}
              className="bg-brand-navy hover:bg-[#c09a5f] text-white px-5 py-2.5 rounded-full text-xs font-semibold transition-colors disabled:opacity-40"
            >
              {loading ? 'Analyzing Clauses...' : 'Analyze document'}
            </button>
          </div>
        </div>

        {/* Results Panel */}
        <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium min-h-[460px] flex flex-col">
          {error ? (
            <div className="m-auto text-center max-w-[300px] space-y-4">
              <AlertTriangle size={32} className="mx-auto text-rose-500" />
              <h3 className="font-serif text-base text-brand-navy font-semibold">Analysis failed</h3>
              <p className="text-xs leading-relaxed text-rose-600 font-semibold">{error}</p>
            </div>
          ) : !analysis ? (
            <div className="m-auto text-center max-w-[280px] space-y-4 text-brand-graphite/40">
              <Upload size={32} className="mx-auto text-[#c09a5f]/70" />
              <h3 className="font-serif text-base text-brand-navy font-semibold">Your analysis will appear here.</h3>
              <p className="text-xs leading-relaxed">Paste your loan agreement or click Load Sample, then trigger the scanner to extract interest terms and warning flags.</p>
            </div>
          ) : (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div className="flex justify-between items-center">
                <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider">Scan Findings</span>
                {analysis.engine && (
                  <span className="text-[9px] font-mono text-brand-graphite/40" title="Analysis engine">
                    {analysis.engine === 'heuristic' ? 'rule-based scan' : analysis.engine}
                  </span>
                )}
              </div>

              {/* Risk Banner */}
              <div className={`p-4 rounded-xl flex gap-3 items-start border ${
                analysis.apr > 36 
                  ? 'bg-red-500/5 border-red-200 text-rose-600' 
                  : 'bg-emerald-500/5 border-emerald-200 text-emerald-600'
              }`}>
                {analysis.apr > 36 ? <ShieldAlert size={20} className="shrink-0" /> : <CheckCircle size={20} className="shrink-0" />}
                <div className="space-y-1">
                  <span className="text-xs font-bold uppercase tracking-wider">
                    {analysis.apr > 36 ? 'High Risk Assessment' : 'Standard Risk Assessment'}
                  </span>
                  <p className="text-[11px] leading-relaxed opacity-90">{analysis.recommendation}</p>
                </div>
              </div>

              {/* Scorecard */}
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-black/5 border border-transparent rounded-lg p-3 text-center">
                  <span className="text-[8px] font-bold uppercase tracking-wider text-brand-graphite/40 block mb-1">Est. APR</span>
                  <span className="text-base font-semibold text-brand-navy">{analysis.apr}%</span>
                </div>
                <div className="bg-black/5 border border-transparent rounded-lg p-3 text-center">
                  <span className="text-[8px] font-bold uppercase tracking-wider text-brand-graphite/40 block mb-1">Term Length</span>
                  <span className="text-base font-semibold text-[#c09a5f]">{analysis.term}</span>
                </div>
                <div className="bg-black/5 border border-transparent rounded-lg p-3 text-center">
                  <span className="text-[8px] font-bold uppercase tracking-wider text-brand-graphite/40 block mb-1">Total Payback</span>
                  <span className="text-base font-semibold text-brand-navy">{analysis.cost}</span>
                </div>
              </div>

              {/* Warning Flags */}
              <div className="space-y-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-brand-graphite/40 block">Extracted Caveat Flags</span>
                <div className="space-y-2">
                  {analysis.flags.map((flag, idx) => (
                    <div key={idx} className="border border-black/5 rounded-xl p-3 flex gap-3 hover:translate-x-1 transition-transform bg-white shadow-subtle">
                      <span className={`text-[8px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full shrink-0 h-fit ${
                        flag.level === 'high' 
                          ? 'bg-red-500/10 text-red-600 border border-red-200' 
                          : flag.level === 'medium'
                            ? 'bg-amber-500/10 text-amber-600 border border-amber-200'
                            : 'bg-blue-500/10 text-blue-600 border border-blue-200'
                      }`}>
                        {flag.level}
                      </span>
                      <div className="space-y-1">
                        <span className="text-xs font-semibold text-brand-navy block">{flag.title}</span>
                        <p className="text-[10px] text-brand-graphite/60 leading-relaxed">{flag.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
