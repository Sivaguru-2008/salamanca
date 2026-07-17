import React from 'react';
import { Activity, Landmark, TrendingDown, Wallet } from 'lucide-react';
import { formatINR, formatINRSigned } from '../lib/currency';
import { DashboardSummary, FinancialData, HealthScore, TrendDelta } from '../types';
import { FinancialDataForm } from '../components/dashboard/FinancialDataForm';
import { HealthAnalysis } from '../components/dashboard/HealthAnalysis';
import { gradeTone } from '../components/dashboard/healthGrades';
import {
  FinancialSummarySection,
  MonthlyOverviewSection,
} from '../components/dashboard/OverviewSections';
import { TransactionsTable } from '../components/dashboard/TransactionsTable';
import { TrendIndicator } from '../components/dashboard/primitives';

interface MetricCardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  iconClass: string;
  trend: TrendDelta;
  /** True where a rise is bad news, so debt colours correctly. */
  invert?: boolean;
  /** Suffix for the today's-change line; scores are points, not rupees. */
  todayFormatter?: (value: number) => string;
  hasData: boolean;
}

const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  icon,
  iconClass,
  trend,
  invert = false,
  todayFormatter = formatINRSigned,
  hasData,
}) => (
  <div className="bg-white border border-black/5 rounded-xl p-5 shadow-subtle">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <span className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-brand-graphite/40">
          {label}
        </span>
        {/* Never clip the figure: a truncated amount is worse than a small one,
            so it steps down a size on narrow columns instead. */}
        <span className="block text-xl font-semibold leading-tight tabular-nums text-brand-navy xl:text-2xl">
          {value}
        </span>
      </div>
      <div className={`shrink-0 rounded-lg p-3 ${iconClass}`}>{icon}</div>
    </div>

    {hasData && (
      <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-black/5 pt-2.5">
        <TrendIndicator pct={trend.month_pct} invert={invert} />
        <span className="text-[10px] text-brand-graphite/45 tabular-nums">
          Today {todayFormatter(trend.today)}
        </span>
        <span className="text-[10px] text-brand-graphite/45 tabular-nums">
          Month {todayFormatter(trend.month)}
        </span>
      </div>
    )}
  </div>
);

interface DashboardPageProps {
  summary: DashboardSummary;
  health: HealthScore;
  financialData: FinancialData | null;
  financialDataLoading: boolean;
  onSaveFinancialData: (values: {
    monthly_salary: number;
    other_monthly_income: number;
    monthly_expenses: number;
    current_savings: number;
    existing_investments: number;
    current_bank_balance: number;
  }) => Promise<void>;
  /** Bumped after a save so the ledger refetches. */
  refreshKey: number;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  summary,
  health,
  financialData,
  financialDataLoading,
  onSaveFinancialData,
  refreshKey,
}) => {
  const hasData = summary.has_data;
  const formatPoints = (value: number) =>
    `${value >= 0 ? '+' : ''}${value.toFixed(1)} pts`;

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Title */}
      <div className="flex justify-between items-start">
        <div>
          <span className="text-[10px] font-bold text-[#c09a5f] uppercase tracking-wider block mb-1">
            Overview
          </span>
          <h1 className="font-serif text-3xl font-medium text-brand-navy">
            Your Financial Studio
          </h1>
          <p className="text-xs text-brand-graphite/50">
            An editorial, real-time view of your net worth and cash balances.
          </p>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Net Worth"
          value={formatINR(summary.net_worth)}
          icon={<Landmark size={20} />}
          iconClass="bg-green-500/10 text-green-600"
          trend={summary.net_worth_trend}
          hasData={hasData}
        />
        <MetricCard
          label="Liquid Holdings"
          value={formatINR(summary.liquid_assets)}
          icon={<Wallet size={20} />}
          iconClass="bg-[#c09a5f]/10 text-[#c09a5f]"
          trend={summary.liquid_trend}
          hasData={hasData}
        />
        <MetricCard
          label="Total Outstanding Debt"
          value={formatINR(summary.total_liabilities)}
          icon={<TrendingDown size={20} />}
          iconClass="bg-red-500/10 text-red-600"
          trend={summary.debt_trend}
          invert
          hasData={hasData}
        />
        <MetricCard
          label="Financial Health"
          value={`${health.score.toFixed(1)}/100`}
          icon={<Activity size={20} />}
          iconClass={`bg-black/5 ${gradeTone(health.grade).text}`}
          trend={summary.health_trend}
          todayFormatter={formatPoints}
          hasData={hasData}
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <div className="min-w-0 space-y-8 lg:col-span-2">
          <MonthlyOverviewSection overview={summary.monthly_overview} hasData={hasData} />
          <FinancialSummarySection summary={summary.financial_summary} hasData={hasData} />
          <TransactionsTable refreshKey={refreshKey} />
        </div>

        <div className="min-w-0 space-y-8">
          <HealthAnalysis health={health} />
          <FinancialDataForm
            data={financialData}
            loading={financialDataLoading}
            onSubmit={onSaveFinancialData}
          />
        </div>
      </div>
    </div>
  );
};
