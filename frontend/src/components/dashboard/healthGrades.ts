import { HealthGrade, HealthMetricKey } from '../../types';

/**
 * Grade colours, kept out of the component module so Fast Refresh can still
 * hot-swap the components that use them.
 */
const GRADE_TONE: Record<HealthGrade, { text: string; bar: string }> = {
  EXCELLENT: { text: 'text-emerald-600', bar: 'bg-emerald-500' },
  VERY_GOOD: { text: 'text-green-600', bar: 'bg-green-500' },
  GOOD: { text: 'text-[#c09a5f]', bar: 'bg-[#c09a5f]' },
  NEEDS_IMPROVEMENT: { text: 'text-amber-600', bar: 'bg-amber-500' },
  POOR: { text: 'text-rose-600', bar: 'bg-rose-500' },
};

export const gradeTone = (grade: HealthGrade) => GRADE_TONE[grade] ?? GRADE_TONE.POOR;

export const METRIC_LABELS: Record<HealthMetricKey, string> = {
  savings_rate: 'Savings Rate',
  debt_to_income: 'Debt-to-Income',
  emergency_fund: 'Emergency Fund',
  expense_stability: 'Expense Stability',
  investment_ratio: 'Investment Ratio',
  cash_flow_trend: 'Cash Flow Trend',
};

/** Display order matches the weighting order used by the scoring engine. */
export const METRIC_ORDER: HealthMetricKey[] = [
  'savings_rate',
  'debt_to_income',
  'emergency_fund',
  'expense_stability',
  'investment_ratio',
  'cash_flow_trend',
];
