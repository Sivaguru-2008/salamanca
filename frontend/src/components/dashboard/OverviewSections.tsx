import React from 'react';
import { formatINR, formatINRSigned, formatPercent } from '../../lib/currency';
import { FinancialSummary, MonthlyOverview } from '../../types';
import { EmptyState, SectionLabel, StatCard, TrendIndicator } from './primitives';

/** Premium statistic tiles replacing the old grey input boxes. */
export const MonthlyOverviewSection: React.FC<{
  overview: MonthlyOverview;
  hasData: boolean;
}> = ({ overview, hasData }) => (
  <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-4">
    <SectionLabel className="block">Monthly Overview</SectionLabel>

    {!hasData ? (
      <EmptyState message="Upload your financial data to see your monthly overview." />
    ) : (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="Monthly Salary" value={formatINR(overview.monthly_salary)} />
        <StatCard
          label="Other Income"
          value={formatINR(overview.other_monthly_income)}
          hint={`Total income ${formatINR(overview.total_monthly_income)}`}
        />
        <StatCard label="Monthly Expenses" value={formatINR(overview.monthly_expenses)} />
        <StatCard
          label="Monthly Savings"
          value={formatINR(overview.monthly_savings)}
          tone={overview.monthly_savings >= 0 ? 'positive' : 'negative'}
        />
        <StatCard
          label="Savings Rate"
          value={formatPercent(overview.savings_rate)}
          hint={overview.savings_rate >= 20 ? 'At or above target' : 'Target is 20%'}
          tone={overview.savings_rate >= 20 ? 'positive' : 'default'}
        />
        <StatCard
          label="Net Monthly Cash Flow"
          value={formatINRSigned(overview.net_monthly_cash_flow)}
          tone={overview.net_monthly_cash_flow >= 0 ? 'positive' : 'negative'}
        />
      </div>
    )}
  </div>
);

const EMERGENCY_TONE: Record<string, 'positive' | 'negative' | 'default'> = {
  'Fully Funded': 'positive',
  Adequate: 'positive',
  Building: 'default',
  'Not Started': 'negative',
};

/** KPI cards that took the place of the cash-flow history graph. */
export const FinancialSummarySection: React.FC<{
  summary: FinancialSummary;
  hasData: boolean;
}> = ({ summary, hasData }) => (
  <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <SectionLabel>Financial Summary</SectionLabel>
      {hasData && (
        <TrendIndicator pct={summary.net_worth_trend_pct} amount={summary.net_worth_trend} />
      )}
    </div>

    {!hasData ? (
      <EmptyState message="Upload your financial data to see your summary." />
    ) : (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="Current Balance" value={formatINR(summary.current_balance)} />
        <StatCard
          label="Monthly Savings"
          value={formatINR(summary.monthly_savings)}
          tone={summary.monthly_savings >= 0 ? 'positive' : 'negative'}
        />
        <StatCard label="Monthly Expenses" value={formatINR(summary.monthly_expenses)} />
        <StatCard label="Investment Value" value={formatINR(summary.investment_value)} />
        <StatCard
          label="Debt"
          value={formatINR(summary.debt)}
          tone={summary.debt > 0 ? 'negative' : 'positive'}
          hint={summary.debt > 0 ? undefined : 'Debt free'}
        />
        <StatCard
          label="Emergency Fund"
          value={summary.emergency_fund_status}
          hint={`${summary.emergency_fund_months.toFixed(1)} months of expenses`}
          tone={EMERGENCY_TONE[summary.emergency_fund_status] || 'default'}
        />
        <StatCard
          label="Net Worth Trend"
          value={formatINRSigned(summary.net_worth_trend)}
          hint="This month"
          tone={summary.net_worth_trend >= 0 ? 'positive' : 'negative'}
          className="sm:col-span-2 lg:col-span-3"
        />
      </div>
    )}
  </div>
);
