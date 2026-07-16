import React, { useState } from 'react';
import { Sparkles, AlertCircle } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { HealthScore } from '../types';

interface TwinPageProps {
  snapshot: any;
  health: HealthScore;
}

export const TwinPage: React.FC<TwinPageProps> = ({ snapshot, health: _health }) => {
  const [salaryInc, setSalaryInc] = useState(5); // % annual increase
  const [returnRate, setReturnRate] = useState(7); // % investment returns
  const [emergShock, setEmergShock] = useState(0); // $ cash emergency

  // Compute Wealth Projections over 30 years
  const generateProjectionData = () => {
    const data = [];
    let baselineWealth = snapshot.totalSavings;
    let scenarioWealth = snapshot.totalSavings;
    
    const monthlySurplus = snapshot.monthlyIncome - snapshot.monthlyExpenses;
    
    for (let year = 0; year <= 30; year += 5) {
      if (year === 0) {
        data.push({ name: `Yr ${year}`, Baseline: Math.round(baselineWealth), 'What-If': Math.round(scenarioWealth) });
        continue;
      }

      // Baseline compounding standard 4% return
      const baseMonthlyRate = 0.04 / 12;
      let tempBase = baselineWealth;
      for (let m = 0; m < 5 * 12; m++) {
        tempBase = tempBase * (1 + baseMonthlyRate) + monthlySurplus;
      }
      baselineWealth = tempBase;

      // Scenario compounding returnRate + salaryInc
      const scenMonthlyRate = (returnRate / 100) / 12;
      let tempScen = scenarioWealth;
      
      // Inject emergency shock in year 1
      if (year === 5) {
        tempScen = Math.max(0, tempScen - emergShock);
      }

      for (let m = 0; m < 5 * 12; m++) {
        // Compound salary growth annually
        const currentYearSalaryMultiplier = Math.pow(1 + (salaryInc / 100), Math.floor((year - 5) + (m / 12)));
        const adjustedIncome = snapshot.monthlyIncome * currentYearSalaryMultiplier;
        const adjustedSurplus = adjustedIncome - snapshot.monthlyExpenses;
        tempScen = tempScen * (1 + scenMonthlyRate) + adjustedSurplus;
      }
      scenarioWealth = tempScen;

      data.push({
        name: `Yr ${year}`,
        Baseline: Math.round(baselineWealth),
        'What-If': Math.round(scenarioWealth)
      });
    }
    return data;
  };

  const projectionData = generateProjectionData();

  return (
    <div className="space-y-8 select-none animate-in fade-in duration-300">
      {/* Title */}
      <div>
        <span className="text-[10px] font-bold text-[#c09a5f] uppercase tracking-wider block mb-1">Financial Twin</span>
        <h1 className="font-serif text-3xl font-medium text-brand-navy">Wealth Projection & Simulator</h1>
        <p className="text-xs text-brand-graphite/50">Stochastic counterfactual models forecasting your capital path over 30 years.</p>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Sliders */}
        <div className="space-y-6 bg-white border border-black/5 rounded-2xl p-6 shadow-premium">
          <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider block mb-2">Simulated Scenarios</span>
          
          {/* Slider A */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs font-semibold text-brand-navy">
              <span>Annual Salary Increase</span>
              <span className="text-[#c09a5f] font-mono">{salaryInc}%</span>
            </div>
            <input 
              type="range" min="0" max="25" step="1" 
              className="w-full accent-brand-gold bg-black/5 rounded-lg h-1"
              value={salaryInc} 
              onChange={(e) => setSalaryInc(Number(e.target.value))}
            />
            <span className="text-[10px] text-brand-graphite/40 leading-tight block">Simulates raises or promotion intervals compounding inflows.</span>
          </div>

          {/* Slider B */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs font-semibold text-brand-navy">
              <span>Investment Return Rate (APR)</span>
              <span className="text-[#c09a5f] font-mono">{returnRate}%</span>
            </div>
            <input 
              type="range" min="2" max="15" step="0.5" 
              className="w-full accent-brand-gold bg-black/5 rounded-lg h-1"
              value={returnRate} 
              onChange={(e) => setReturnRate(Number(e.target.value))}
            />
            <span className="text-[10px] text-brand-graphite/40 leading-tight block">Custom rate compounding surplus cash flow into equity funds.</span>
          </div>

          {/* Slider C */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs font-semibold text-brand-navy">
              <span>Immediate Cash Emergency Shock</span>
              <span className="text-[#c09a5f] font-mono">${emergShock.toLocaleString()}</span>
            </div>
            <input 
              type="range" min="0" max="30000" step="1000" 
              className="w-full accent-brand-gold bg-black/5 rounded-lg h-1"
              value={emergShock} 
              onChange={(e) => setEmergShock(Number(e.target.value))}
            />
            <span className="text-[10px] text-brand-graphite/40 leading-tight block">Simulates immediate cash reserves drain (medical shock, vehicle failure).</span>
          </div>

          {/* Alert check */}
          {emergShock > snapshot.totalSavings && (
            <div className="border border-red-200 bg-red-500/5 text-rose-600 rounded-lg p-3 flex gap-2.5 items-start">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <div className="text-[10px] leading-relaxed">
                <span className="font-bold">Liquidity Warning:</span> Emergency shock exceeds your savings of <strong>${snapshot.totalSavings}</strong>. Your twin model triggers immediate solvency stress.
              </div>
            </div>
          )}
        </div>

        {/* Right 2 Columns: Chart */}
        <div className="lg:col-span-2 space-y-6">
          {/* Line Chart */}
          <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium">
            <span className="text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider block mb-4">Capital Growth Comparison</span>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={projectionData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.03)" />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} style={{ fontSize: 10, fill: 'rgba(0,0,0,0.4)' }} />
                  <YAxis tickLine={false} axisLine={false} style={{ fontSize: 10, fill: 'rgba(0,0,0,0.4)' }} />
                  <Tooltip contentStyle={{ background: '#fff', border: '1px solid rgba(0,0,0,0.05)', borderRadius: '8px', fontSize: 11 }} />
                  <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="Baseline" stroke="rgba(10, 17, 32, 0.4)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="What-If" stroke="#c09a5f" strokeWidth={3} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Twin Explainability Card */}
          <div className="bg-white border border-black/5 rounded-xl p-5 shadow-subtle flex gap-4 items-start">
            <div className="p-3 bg-[#c09a5f]/15 rounded-lg text-[#c09a5f] shrink-0">
              <Sparkles size={20} />
            </div>
            <div className="space-y-1">
              <h3 className="font-serif text-sm font-semibold text-brand-navy">AI Counterfactual Insights</h3>
              <p className="text-xs text-brand-graphite/60 leading-relaxed">
                By compounding your raises at **{salaryInc}%** and pushing surplus allocations to a **{returnRate}%** asset pool, your simulated wealth reaches **${projectionData[projectionData.length-1]['What-If'].toLocaleString()}** in Year 30, outperforming the baseline projection by **${(projectionData[projectionData.length-1]['What-If'] / (projectionData[projectionData.length-1]['Baseline'] || 1) * 100 - 100).toFixed(0)}%**.
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
