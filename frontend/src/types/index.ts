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

export interface Transaction {
  id: string;
  type: 'Income' | 'Expense' | 'Investment' | 'Transfer';
  category: string;
  amount: number;
  currency: string;
  description?: string;
  transaction_date: string;
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
  raw_value: string;
  target: string;
  explanation: string;
}

export interface HealthScore {
  score: number;
  grade: 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR';
  breakdown: {
    savings_rate: HealthScoreMetric;
    debt_to_income: HealthScoreMetric;
    emergency_fund: HealthScoreMetric;
    investment_ratio: HealthScoreMetric;
    insurance_coverage: HealthScoreMetric;
  };
  recommendations: string[];
}

export interface DashboardSummary {
  net_worth: number;
  total_assets: number;
  total_liabilities: number;
  monthly_income: number;
  monthly_expense: number;
  monthly_savings_rate: number;
  recent_transactions: Transaction[];
  savings_goals_progress: SavingsGoal[];
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
