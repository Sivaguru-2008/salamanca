import { AxiosProgressEvent } from 'axios';
import { apiRequest, client, tokenStore, API_ROOT_URL } from '../lib/api';
import {
  AnalyticsData,
  Asset,
  Budget,
  DashboardSummary,
  DecisionTrace,
  DocumentChunk,
  Expense,
  FinancialProfile,
  GraphEdge,
  GraphNode,
  HealthScore,
  Income,
  Insurance,
  Investment,
  Liability,
  Loan,
  LoanAnalysis,
  ObservabilityLog,
  RAGDocument,
  SavingsGoal,
  Transaction,
  User,
} from '../types';

const unwrapError = (error: unknown, fallback: string) => {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = (error as any).response;
    return response?.data?.detail || response?.data?.message || fallback;
  }
  if (error instanceof Error) return error.message;
  return fallback;
};

const toNumber = (value: unknown, fallback = 0) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

const today = () => new Date().toISOString().slice(0, 10);

const normalizeGoal = (goal: any): SavingsGoal => ({
  id: String(goal.id),
  name: goal.name,
  target_amount: toNumber(goal.target_amount),
  current_amount: toNumber(goal.current_amount ?? goal.current_progress),
  target_date: goal.target_date,
  status: goal.status || 'IN_PROGRESS',
});

const normalizeLoan = (loan: any): Loan => ({
  id: String(loan.id),
  lender: loan.lender || loan.name,
  principal_amount: toNumber(loan.principal_amount ?? loan.outstanding_balance),
  outstanding_balance: toNumber(loan.outstanding_balance),
  interest_rate: toNumber(loan.interest_rate),
  emi: toNumber(loan.emi),
  start_date: loan.start_date || loan.created_at || today(),
  end_date: loan.end_date || loan.updated_at || today(),
  status: loan.status || 'ACTIVE',
});

const normalizeLiability = (liability: any): Liability => ({
  id: String(liability.id),
  name: liability.name,
  type: liability.type,
  outstanding_balance: toNumber(liability.outstanding_balance),
  apr: toNumber(liability.apr ?? liability.details?.apr),
  monthly_minimum_payment: toNumber(
    liability.monthly_minimum_payment ?? liability.details?.monthly_minimum_payment,
  ),
});

const normalizeDocument = (doc: any): RAGDocument => ({
  id: String(doc.id),
  name: doc.name,
  size: toNumber(doc.size ?? doc.metadata_json?.size_bytes),
  uploaded_at: doc.uploaded_at || doc.created_at,
  chunks: ((doc.chunks || doc.metadata_json?.chunks || []) as any[]).map((chunk, idx) => ({
    index: toNumber(chunk.index, idx),
    text: chunk.text || '',
    score: chunk.score === undefined ? undefined : toNumber(chunk.score),
  })),
});

const normalizeCashFlowMap = (flow: Record<string, any> | undefined) => {
  const result: AnalyticsData['monthly_cash_flow'] = {};
  Object.entries(flow || {}).forEach(([period, value]) => {
    result[period] = {
      income: toNumber(value.income),
      expense: toNumber(value.expense),
      net_cash_flow: toNumber(value.net_cash_flow),
    };
  });
  return result;
};

const normalizeAllocation = (allocation: Record<string, any> | undefined) => {
  const result: Record<string, number> = {};
  Object.entries(allocation || {}).forEach(([key, value]) => {
    result[key] = toNumber(value);
  });
  return result;
};

const normalizeSummary = (summary: any): DashboardSummary => ({
  net_worth: toNumber(summary.net_worth),
  total_assets: toNumber(summary.total_assets),
  total_liabilities: toNumber(summary.total_liabilities),
  monthly_income: toNumber(summary.monthly_income),
  monthly_expense: toNumber(summary.monthly_expense),
  monthly_savings_rate: toNumber(summary.monthly_savings_rate),
  recent_transactions: (summary.recent_transactions || []).map((tx: any) => ({
    ...tx,
    id: String(tx.id),
    amount: toNumber(tx.amount),
  })),
  savings_goals_progress: (summary.savings_goals_progress || []).map(normalizeGoal),
});

const graphFromFinancialData = async (): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> => {
  const [incomes, assets, liabilities, loans, transactions, goals] = await Promise.all([
    apiService.getIncomes(),
    apiService.getAssets(),
    apiService.getLiabilities(),
    apiService.getLoans(),
    apiService.getTransactions(),
    apiService.getGoals(),
  ]);

  const nodes: GraphNode[] = [{ id: 'user', label: 'Financial Twin', type: 'user' }];
  const edges: GraphEdge[] = [];

  incomes.forEach((income) => {
    nodes.push({
      id: income.id,
      label: `${income.source} ($${income.amount})`,
      type: 'account',
      value: income.amount,
    });
    edges.push({ source: income.id, target: 'user', label: 'INFLOW' });
  });

  assets.forEach((asset) => {
    nodes.push({
      id: asset.id,
      label: `${asset.name} ($${asset.current_value})`,
      type: 'account',
      value: asset.current_value,
    });
    edges.push({ source: 'user', target: asset.id, label: 'HOLDS' });
  });

  liabilities.forEach((liability) => {
    nodes.push({
      id: liability.id,
      label: `${liability.name} ($${liability.outstanding_balance})`,
      type: 'loan',
      value: liability.outstanding_balance,
    });
    edges.push({ source: 'user', target: liability.id, label: 'OWES' });
  });

  loans.forEach((loan) => {
    nodes.push({
      id: loan.id,
      label: `${loan.lender} ($${loan.outstanding_balance})`,
      type: 'loan',
      value: loan.outstanding_balance,
    });
    edges.push({ source: 'user', target: loan.id, label: 'LOAN' });
  });

  goals.forEach((goal) => {
    nodes.push({
      id: goal.id,
      label: `${goal.name} ($${goal.target_amount})`,
      type: 'goal',
      value: goal.target_amount,
    });
    edges.push({ source: 'user', target: goal.id, label: 'TARGETS' });
  });

  transactions.slice(0, 25).forEach((tx) => {
    nodes.push({
      id: tx.id,
      label: `${tx.category} ($${tx.amount})`,
      type: 'transaction',
      value: tx.amount,
    });
    edges.push({ source: 'user', target: tx.id, label: tx.type.toUpperCase() });
  });

  return { nodes, edges };
};

export const apiService = {
  register: async (email: string, password: string, fullName: string): Promise<User> =>
    apiRequest<User>({
      method: 'POST',
      url: '/auth/register',
      data: { email, password, full_name: fullName },
    }),

  login: async (email: string, password: string) => {
    const tokens = await apiRequest<{ access_token: string; refresh_token: string; expires_in: number }>(
      {
        method: 'POST',
        url: '/auth/login',
        data: { email, password },
      },
    );
    tokenStore.setTokens(tokens.access_token, tokens.refresh_token);
    return tokens;
  },

  logout: async (everywhere = false) => {
    const refreshToken = tokenStore.getRefreshToken();
    try {
      if (refreshToken) {
        await apiRequest({
          method: 'POST',
          url: '/auth/logout',
          data: { refresh_token: refreshToken, everywhere },
        });
      }
    } finally {
      tokenStore.clear();
    }
  },

  updateMe: (payload: { full_name?: string; password?: string }) =>
    apiRequest<User>({ method: 'PATCH', url: '/users/me', data: payload }),

  getCurrentUser: async (): Promise<User | null> => {
    if (!tokenStore.getAccessToken()) return null;
    try {
      return await apiRequest<User>({ method: 'GET', url: '/users/me' });
    } catch {
      return null;
    }
  },

  getProfile: () =>
    apiRequest<FinancialProfile>({ method: 'GET', url: '/financial/profile' }),

  updateProfile: (payload: Record<string, unknown>) =>
    apiRequest<FinancialProfile>({ method: 'PUT', url: '/financial/profile', data: payload }),

  getHealthScore: () =>
    apiRequest<HealthScore>({ method: 'GET', url: '/financial/health-score' }),

  getDashboardSummary: async () =>
    normalizeSummary(await apiRequest({ method: 'GET', url: '/financial/summary' })),

  getIncomes: async (): Promise<Income[]> =>
    (await apiRequest<any[]>({ method: 'GET', url: '/financial/incomes' })).map((income) => ({
      ...income,
      id: String(income.id),
      amount: toNumber(income.amount),
      normalized_monthly_amount: toNumber(income.normalized_monthly_amount),
    })),

  createIncome: (payload: Omit<Income, 'id' | 'normalized_monthly_amount'>) =>
    apiRequest<Income>({
      method: 'POST',
      url: '/financial/incomes',
      data: {
        ...payload,
        start_date: (payload as any).start_date || today(),
      },
    }),

  updateIncome: (id: string, payload: Record<string, unknown>) =>
    apiRequest<Income>({ method: 'PUT', url: `/financial/incomes/${id}`, data: payload }),

  deleteIncome: (id: string) =>
    apiRequest<void>({ method: 'DELETE', url: `/financial/incomes/${id}` }),

  getExpenses: async (): Promise<Expense[]> =>
    (await apiRequest<any[]>({ method: 'GET', url: '/financial/expenses' })).map((expense) => ({
      ...expense,
      id: String(expense.id),
      amount: toNumber(expense.amount),
      frequency: expense.frequency || (expense.is_recurring ? 'MONTHLY' : 'ONCE'),
      normalized_monthly_amount: toNumber(expense.normalized_monthly_amount),
    })),

  createExpense: (payload: Omit<Expense, 'id' | 'normalized_monthly_amount'>) =>
    apiRequest<Expense>({
      method: 'POST',
      url: '/financial/expenses',
      data: {
        category: payload.category,
        expense_type: (payload as any).expense_type || 'VARIABLE',
        amount: payload.amount,
        currency: (payload as any).currency || 'USD',
        is_recurring: payload.frequency === 'MONTHLY',
        description: (payload as any).description,
      },
    }),

  updateExpense: (id: string, payload: Record<string, unknown>) =>
    apiRequest<Expense>({ method: 'PUT', url: `/financial/expenses/${id}`, data: payload }),

  deleteExpense: (id: string) =>
    apiRequest<void>({ method: 'DELETE', url: `/financial/expenses/${id}` }),

  getAssets: async (): Promise<Asset[]> =>
    (await apiRequest<any[]>({ method: 'GET', url: '/financial/assets' })).map((asset) => ({
      ...asset,
      id: String(asset.id),
      current_value: toNumber(asset.current_value),
    })),

  createAsset: (payload: Omit<Asset, 'id'>) =>
    apiRequest<Asset>({ method: 'POST', url: '/financial/assets', data: payload }),

  updateAsset: (id: string, payload: Record<string, unknown>) =>
    apiRequest<Asset>({ method: 'PUT', url: `/financial/assets/${id}`, data: payload }),

  deleteAsset: (id: string) =>
    apiRequest<void>({ method: 'DELETE', url: `/financial/assets/${id}` }),

  getLiabilities: async (): Promise<Liability[]> =>
    (await apiRequest<any[]>({ method: 'GET', url: '/financial/liabilities' })).map(
      normalizeLiability,
    ),

  createLiability: (payload: Omit<Liability, 'id'>) =>
    apiRequest<Liability>({
      method: 'POST',
      url: '/financial/liabilities',
      data: {
        name: payload.name,
        type: payload.type,
        outstanding_balance: payload.outstanding_balance,
        currency: 'USD',
        details: {
          apr: payload.apr,
          monthly_minimum_payment: payload.monthly_minimum_payment,
        },
      },
    }),

  updateLiability: (id: string, payload: Partial<Liability>) =>
    apiRequest<Liability>({
      method: 'PUT',
      url: `/financial/liabilities/${id}`,
      data: {
        name: payload.name,
        type: payload.type,
        outstanding_balance: payload.outstanding_balance,
        details: {
          apr: payload.apr,
          monthly_minimum_payment: payload.monthly_minimum_payment,
        },
      },
    }),

  deleteLiability: (id: string) =>
    apiRequest<void>({ method: 'DELETE', url: `/financial/liabilities/${id}` }),

  getLoans: async (): Promise<Loan[]> =>
    (await apiRequest<any[]>({ method: 'GET', url: '/financial/loans' })).map(normalizeLoan),

  createLoan: (payload: Omit<Loan, 'id'>) =>
    apiRequest<Loan>({
      method: 'POST',
      url: '/financial/loans',
      data: {
        name: payload.lender,
        type: 'Loan',
        interest_rate: payload.interest_rate,
        apr: payload.interest_rate,
        emi: payload.emi,
        remaining_tenure: 0,
        outstanding_balance: payload.outstanding_balance,
        status: payload.status,
      },
    }),

  deleteLoan: (id: string) =>
    apiRequest<void>({ method: 'DELETE', url: `/financial/loans/${id}` }),

  getBudgets: async (): Promise<Budget[]> => [
    await apiRequest<Budget>({ method: 'GET', url: '/financial/budgets/current' }),
  ],

  saveBudget: (payload: Omit<Budget, 'id'>) =>
    apiRequest<Budget>({ method: 'POST', url: '/financial/budgets', data: payload }),

  getGoals: async (): Promise<SavingsGoal[]> =>
    (await apiRequest<any[]>({ method: 'GET', url: '/financial/savings-goals' })).map(
      normalizeGoal,
    ),

  createGoal: async (payload: Omit<SavingsGoal, 'id'>) =>
    normalizeGoal(
      await apiRequest({
        method: 'POST',
        url: '/financial/savings-goals',
        data: {
          name: payload.name,
          category: 'General',
          target_amount: payload.target_amount,
          target_date:
            payload.target_date ||
            new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
          current_progress: payload.current_amount,
          currency: 'USD',
        },
      }),
    ),

  deleteGoal: (id: string) =>
    apiRequest<void>({ method: 'DELETE', url: `/financial/savings-goals/${id}` }),

  getTransactions: async (): Promise<Transaction[]> =>
    (await apiRequest<any[]>({ method: 'GET', url: '/financial/transactions' })).map((tx) => ({
      ...tx,
      id: String(tx.id),
      amount: toNumber(tx.amount),
    })),

  createTransaction: (payload: Omit<Transaction, 'id' | 'transaction_date'>) =>
    apiRequest<Transaction>({
      method: 'POST',
      url: '/financial/transactions',
      data: { ...payload, transaction_date: new Date().toISOString() },
    }),

  getInvestments: async (): Promise<Investment[]> =>
    (await apiRequest<any[]>({ method: 'GET', url: '/financial/investments' })).map((inv) => ({
      ...inv,
      id: String(inv.id),
      amount_invested: toNumber(inv.amount_invested),
      current_value: toNumber(inv.current_value),
    })),

  createInvestment: (payload: {
    name: string;
    type: string;
    amount_invested: number;
    current_value: number;
    ticker?: string;
  }) =>
    apiRequest<Investment>({
      method: 'POST',
      url: '/financial/investments',
      data: { currency: 'USD', ...payload },
    }),

  deleteInvestment: (id: string) =>
    apiRequest<void>({ method: 'DELETE', url: `/financial/investments/${id}` }),

  getInsurances: async (): Promise<Insurance[]> =>
    (await apiRequest<any[]>({ method: 'GET', url: '/financial/insurances' })).map((ins) => ({
      ...ins,
      id: String(ins.id),
      coverage_amount: toNumber(ins.coverage_amount),
      premium_amount: toNumber(ins.premium_amount),
    })),

  getIncomesRaw: () => apiRequest<any[]>({ method: 'GET', url: '/financial/incomes' }),

  getDecisions: () => apiRequest<DecisionTrace[]>({ method: 'GET', url: '/chat/decisions' }),

  getChatHistory: (agent: string, conversationId = 'default') =>
    apiRequest<{ agent: string; conversation_id: string; messages: { role: string; content: string }[] }>({
      method: 'GET',
      url: `/chat/${agent}/history`,
      params: { conversation_id: conversationId },
    }),

  searchDocumentChunks: (docId: string, query: string, limit = 5) =>
    apiRequest<{ document_id: string; document_name: string; query: string; results: DocumentChunk[] }>({
      method: 'GET',
      url: `/documents/${docId}/search`,
      params: { query, limit },
    }),

  deleteDocument: (docId: string) =>
    apiRequest<void>({ method: 'DELETE', url: `/documents/${docId}` }),

  buildDocumentDownloadUrl: (docId: string) => `/documents/${docId}/download`,

  analyzeLoanDocument: async (text: string): Promise<LoanAnalysis> => {
    try {
      return await apiRequest<LoanAnalysis>({
        method: 'POST',
        url: '/loan-analysis/analyze',
        data: { text },
      });
    } catch (error) {
      throw new Error(
        unwrapError(error, 'Loan analysis endpoint is unavailable. Connect the OCR/LLM backend first.'),
      );
    }
  },

  sendAdvisorMessage: async (
    agentId: string,
    message: string,
    contextSnapshot: Record<string, unknown>,
    conversationId = 'default',
  ) => {
    try {
      const startedAt = performance.now();
      const response = await apiRequest<any>({
        method: 'POST',
        url: '/chat',
        data: {
          agent: agentId,
          message,
          conversation_id: conversationId,
          context: contextSnapshot,
        },
      });

      return {
        id: response.id || `msg-${Date.now()}`,
        sender: 'agent' as const,
        text: response.text || response.message || response.content,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        agentId,
        citations: response.citations,
        reasoningSteps: response.reasoning_steps || response.reasoningSteps,
        latencyMs: response.latency_ms || Math.round(performance.now() - startedAt),
      };
    } catch (error) {
      throw new Error(
        unwrapError(error, 'AI council backend is unavailable. Configure the /api/v1/chat service.'),
      );
    }
  },

  getUploadedDocuments: async (): Promise<RAGDocument[]> =>
    (await apiRequest<any[]>({ method: 'GET', url: '/financial/documents' })).map(
      normalizeDocument,
    ),

  uploadDocument: async (
    file: File,
    onUploadProgress?: (event: AxiosProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<RAGDocument> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await client.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress,
      signal,
    });

    return normalizeDocument(response.data);
  },

  getKnowledgeGraph: async () => {
    try {
      return await apiRequest<{ nodes: GraphNode[]; edges: GraphEdge[] }>({
        method: 'GET',
        url: '/financial/knowledge-graph',
      });
    } catch {
      return graphFromFinancialData();
    }
  },

  getAnalytics: async (): Promise<AnalyticsData> => {
    const raw = await apiRequest<any>({ method: 'GET', url: '/financial/analytics' });
    return {
      monthly_cash_flow: normalizeCashFlowMap(raw.monthly_cash_flow),
      quarterly_cash_flow: normalizeCashFlowMap(raw.quarterly_cash_flow),
      yearly_cash_flow: normalizeCashFlowMap(raw.yearly_cash_flow),
      asset_allocation: normalizeAllocation(raw.asset_allocation),
      liability_allocation: normalizeAllocation(raw.liability_allocation),
    };
  },

  getObservabilityLogs: async (): Promise<ObservabilityLog[]> => {
    const response = await client.get(`${API_ROOT_URL}/readyz`);
    const checks = response.data.checks || [];
    return checks.map((check: any, index: number) => ({
      id: `${check.name}-${index}`,
      timestamp: new Date().toISOString(),
      agentName: check.name,
      action: check.healthy ? 'dependency_ready' : 'dependency_degraded',
      latencyMs: Math.round(check.latency_ms || 0),
      tokensUsed: 0,
      reasoning: check.error || 'Health check completed successfully.',
      memoryRecall: check.critical ? 'critical dependency' : 'optional dependency',
    }));
  },
};
