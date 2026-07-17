// FIOS TypeScript Interface Definitions

export interface User {
  id: string;
  email: string;
  full_name?: string;
  role?: string;
  is_active?: boolean;
  is_verified?: boolean;
  created_at?: string;
}

export interface FinancialProfile {
  id: string;
  user_id: string;
  currency: string;
  country: string;
  risk_profile: string;
  financial_literacy_level: string;
  personal_info?: Record<string, unknown> | null;
  financial_preferences?: Record<string, any> | null;
  updated_at?: string;
}

export interface Income {
  id: string;
  source: string;
  amount: number;
  frequency: 'ONCE' | 'WEEKLY' | 'BIWEEKLY' | 'MONTHLY' | 'QUARTERLY' | 'YEARLY';
  normalized_monthly_amount: number;
}

export interface Expense {
  id: string;
  category: string;
  amount: number;
  frequency: 'ONCE' | 'WEEKLY' | 'BIWEEKLY' | 'MONTHLY' | 'QUARTERLY' | 'YEARLY';
  normalized_monthly_amount: number;
}

export interface Asset {
  id: string;
  name: string;
  type: string; // 'Cash' | 'Bank accounts' | 'Real Estate' | 'Brokerage' | 'Other'
  current_value: number;
}

export interface Liability {
  id: string;
  name: string;
  type: string; // 'Credit Card' | 'Personal Loan' | 'Student Loan' | 'Car Loan' | 'Mortgage' | 'Other'
  outstanding_balance: number;
  apr: number;
  monthly_minimum_payment: number;
}

export interface Loan {
  id: string;
  lender: string;
  principal_amount: number;
  outstanding_balance: number;
  interest_rate: number;
  emi: number;
  start_date: string;
  end_date: string;
  status: 'ACTIVE' | 'PAID' | 'DEFAULT';
}

export interface Budget {
  id: string;
  month: string; // YYYY-MM
  monthly_budget: number;
  category_budgets: Record<string, number>;
  budget_utilization?: Record<string, number>;
  budget_alerts?: Record<string, any>;
}

export type TransactionType =
  | 'Income'
  | 'Expense'
  | 'Investment'
  | 'Transfer'
  | 'Loan Payment'
  | 'Insurance Premium'
  | 'Refund';

export type PaymentMethod =
  | 'UPI'
  | 'Bank Transfer'
  | 'Credit Card'
  | 'Debit Card'
  | 'Cash'
  | 'Net Banking'
  | 'Auto Debit';

export type TransactionStatus = 'Completed' | 'Pending' | 'Failed';

export interface Transaction {
  id: string;
  type: TransactionType;
  category: string;
  amount: number;
  currency: string;
  description?: string;
  payment_method: PaymentMethod | string;
  status: TransactionStatus | string;
  transaction_date: string;
}

export interface TransactionQuery {
  search?: string;
  category?: string;
  type?: string;
  sort_by?: 'transaction_date' | 'amount' | 'category' | 'status';
  sort_dir?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

export interface TransactionPage {
  items: Transaction[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  categories: string[];
}

/** The six figures behind the dashboard's Financial Data Upload form. */
export interface FinancialData {
  monthly_salary: number;
  other_monthly_income: number;
  monthly_expenses: number;
  current_savings: number;
  existing_investments: number;
  current_bank_balance: number;
  has_data: boolean;
  updated_at?: string | null;
}

export interface SavingsGoal {
  id: string;
  name: string;
  target_amount: number;
  current_amount: number;
  target_date?: string;
  status: 'IN_PROGRESS' | 'COMPLETED' | 'ABANDONED';
}

export interface HealthScoreMetric {
  score: number;
  /** 0 when the metric cannot be measured yet, so its weight is redistributed. */
  weight: number;
  raw_value: string;
  target: string;
  explanation: string;
}

export type HealthGrade =
  | 'EXCELLENT'
  | 'VERY_GOOD'
  | 'GOOD'
  | 'NEEDS_IMPROVEMENT'
  | 'POOR';

export type HealthMetricKey =
  | 'savings_rate'
  | 'debt_to_income'
  | 'emergency_fund'
  | 'expense_stability'
  | 'investment_ratio'
  | 'cash_flow_trend';

export interface HealthScore {
  score: number;
  grade: HealthGrade;
  grade_label: string;
  breakdown: Record<HealthMetricKey, HealthScoreMetric>;
  strengths: string[];
  areas_to_improve: string[];
  insights: string[];
  recommendations: string[];
  has_data: boolean;
}

export interface TrendDelta {
  today: number;
  month: number;
  month_pct: number;
}

export interface MonthlyOverview {
  monthly_salary: number;
  other_monthly_income: number;
  total_monthly_income: number;
  monthly_expenses: number;
  monthly_savings: number;
  savings_rate: number;
  net_monthly_cash_flow: number;
}

export interface FinancialSummary {
  current_balance: number;
  monthly_savings: number;
  monthly_expenses: number;
  investment_value: number;
  debt: number;
  emergency_fund_months: number;
  emergency_fund_status: string;
  net_worth_trend: number;
  net_worth_trend_pct: number;
}

export interface DashboardSummary {
  net_worth: number;
  /** Everything owned, investments included. */
  total_assets: number;
  /** Cash, bank and savings only. */
  liquid_assets: number;
  total_liabilities: number;
  monthly_income: number;
  monthly_expense: number;
  monthly_savings_rate: number;
  recent_transactions: Transaction[];
  savings_goals_progress: SavingsGoal[];
  net_worth_trend: TrendDelta;
  liquid_trend: TrendDelta;
  debt_trend: TrendDelta;
  health_trend: TrendDelta;
  monthly_overview: MonthlyOverview;
  financial_summary: FinancialSummary;
  has_data: boolean;
}

export interface AdvisorMessage {
  id: string;
  sender: 'agent' | 'user';
  text: string;
  time: string;
  agentId?: string;
  citations?: { title: string; content: string; score: number }[];
  reasoningSteps?: string[];
  latencyMs?: number;
}

export interface LoanClause {
  level: 'high' | 'medium' | 'low';
  title: string;
  desc: string;
}

export interface LoanAnalysis {
  apr: number;
  term: string;
  cost: string;
  flags: LoanClause[];
  recommendation: string;
  engine?: string;
}

export interface DocumentChunk {
  index: number;
  text: string;
  score?: number;
}

export interface RAGDocument {
  id: string;
  name: string;
  size: number;
  uploaded_at: string;
  chunks: DocumentChunk[];
}

export interface Investment {
  id: string;
  name: string;
  type: string;
  amount_invested: number;
  current_value: number;
  ticker?: string | null;
  currency: string;
}

export interface Insurance {
  id: string;
  policy_number: string;
  provider: string;
  type: string;
  coverage_amount: number;
  premium_amount: number;
  premium_frequency: string;
  renewal_date: string;
  status: string;
}

export interface CashFlowPoint {
  income: number;
  expense: number;
  net_cash_flow: number;
}

export interface AnalyticsData {
  monthly_cash_flow: Record<string, CashFlowPoint>;
  quarterly_cash_flow: Record<string, CashFlowPoint>;
  yearly_cash_flow: Record<string, CashFlowPoint>;
  asset_allocation: Record<string, number>;
  liability_allocation: Record<string, number>;
}

export interface DecisionTrace {
  id: string;
  agent: string;
  agent_name: string;
  action: string;
  question: string;
  answer_preview: string;
  provider: string;
  model: string;
  latency_ms: number;
  timestamp: string;
}

export interface MemoryFact {
  key: string;
  value: string;
  storageClass: 'Short-term' | 'Long-term';
  recordedAt: string;
}

export interface MonitorAlert {
  level: 'high' | 'medium' | 'low';
  title: string;
  desc: string;
  time: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: 'account' | 'loan' | 'goal' | 'transaction' | 'user';
  value?: number;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
}

export interface ObservabilityLog {
  id: string;
  timestamp: string;
  agentName: string;
  action: string;
  latencyMs: number;
  tokensUsed: number;
  reasoning: string;
  memoryRecall: string;
}
