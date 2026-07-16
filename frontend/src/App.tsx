import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Sparkles } from 'lucide-react';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { CommandPalette } from './components/layout/CommandPalette';
import { AIAssistant } from './components/layout/AIAssistant';
import { LandingPage } from './features/LandingPage';
import { AuthPage } from './features/AuthPage';
import { DashboardPage } from './features/DashboardPage';
import { TwinPage } from './features/TwinPage';
import { AdvisorsPage } from './features/AdvisorsPage';
import { LoanPage } from './features/LoanPage';
import { TrackerPage } from './features/TrackerPage';
import {
  AdminPage,
  ConsolePage,
  DecisionsPage,
  GoalsPage,
  GraphPage,
  InvestmentPage,
  MemoryPage,
  MonitoringPage,
  ObservabilityPage,
  RagPage,
  SettingsPage,
  SimulatorPage,
} from './features/AdvancedPages';
import { apiService } from './services/apiService';
import {
  AdvisorMessage,
  Budget,
  DashboardSummary,
  HealthScore,
  Liability,
  Loan,
  SavingsGoal,
  Transaction,
  User,
} from './types';

const emptyHealth: HealthScore = {
  score: 0,
  grade: 'POOR',
  breakdown: {
    savings_rate: { score: 0, raw_value: '0%', target: '>= 20%', explanation: '' },
    debt_to_income: { score: 0, raw_value: '0%', target: '<= 36%', explanation: '' },
    emergency_fund: { score: 0, raw_value: '0 months', target: '>= 6.0 mo', explanation: '' },
    investment_ratio: { score: 0, raw_value: '0%', target: '>= 15%', explanation: '' },
    insurance_coverage: { score: 0, raw_value: 'Unknown', target: 'Active policies', explanation: '' },
  },
  recommendations: [],
};

const emptySummary: DashboardSummary = {
  net_worth: 0,
  total_assets: 0,
  total_liabilities: 0,
  monthly_income: 0,
  monthly_expense: 0,
  monthly_savings_rate: 0,
  recent_transactions: [],
  savings_goals_progress: [],
};

const defaultChats: Record<string, AdvisorMessage[]> = {
  advisor: [],
  budget: [],
  debt: [],
  savings: [],
  investment: [],
  insurance: [],
  tax: [],
  loan: [],
};

const snapshotFromSummary = (summary: DashboardSummary) => ({
  monthlyIncome: summary.monthly_income,
  monthlyExpenses: summary.monthly_expense,
  totalSavings: summary.total_assets,
  totalDebt: summary.total_liabilities,
  housing: 0,
  food: 0,
  transport: 0,
  lifestyle: 0,
  other: 0,
});

export const App: React.FC = () => {
  const [activePage, setActivePage] = useState<string>('landing');
  const [collapsed, setCollapsed] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(true);
  const [apiOnline, setApiOnline] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  const [summary, setSummary] = useState<DashboardSummary>(emptySummary);
  const [health, setHealth] = useState<HealthScore>(emptyHealth);
  const [snapshot, setSnapshot] = useState(snapshotFromSummary(emptySummary));
  const [envelopes, setEnvelopes] = useState<Record<string, number>>({});
  const [utilization, setUtilization] = useState<Record<string, number>>({});
  const [debts, setDebts] = useState<Liability[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [goals, setGoals] = useState<SavingsGoal[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [chats, setChats] = useState<Record<string, AdvisorMessage[]>>(defaultChats);

  const refreshFinancialData = useCallback(async () => {
    try {
      const [
        nextSummary,
        nextHealth,
        budgets,
        liabilities,
        nextLoans,
        nextGoals,
        nextTransactions,
      ] = await Promise.all([
        apiService.getDashboardSummary(),
        apiService.getHealthScore(),
        apiService.getBudgets(),
        apiService.getLiabilities(),
        apiService.getLoans(),
        apiService.getGoals(),
        apiService.getTransactions(),
      ]);

      const currentBudget = budgets[0];
      setSummary(nextSummary);
      setHealth(nextHealth);
      setSnapshot((previous) => ({
        ...previous,
        ...snapshotFromSummary(nextSummary),
      }));
      setEnvelopes(currentBudget?.category_budgets || {});
      setUtilization(currentBudget?.budget_utilization || {});
      setDebts(liabilities);
      setLoans(nextLoans);
      setGoals(nextGoals);
      setTransactions(nextTransactions);
      setApiOnline(true);
      setBootError(null);
    } catch (error) {
      setApiOnline(false);
      setBootError(error instanceof Error ? error.message : 'Backend API is unavailable.');
    }
  }, []);

  // Restore an existing session on boot, then load live data.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const currentUser = await apiService.getCurrentUser();
      if (cancelled) return;
      setUser(currentUser);
      setAuthChecked(true);
      if (currentUser) await refreshFinancialData();
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshFinancialData]);

  // Refresh-token failure anywhere in the app drops us back to the login screen.
  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setChats(defaultChats);
    };
    window.addEventListener('fios:unauthorized', onUnauthorized);
    return () => window.removeEventListener('fios:unauthorized', onUnauthorized);
  }, []);

  const handleAuthenticated = useCallback(
    async (nextUser: User) => {
      setUser(nextUser);
      setActivePage('landing');
      await refreshFinancialData();
    },
    [refreshFinancialData],
  );

  const handleLogout = useCallback(async () => {
    try {
      await apiService.logout();
    } finally {
      setUser(null);
      setChats(defaultChats);
      setSummary(emptySummary);
      setHealth(emptyHealth);
      setActivePage('landing');
    }
  }, []);

  useEffect(() => {
    const handleKeys = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setCommandOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeys);
    return () => window.removeEventListener('keydown', handleKeys);
  }, []);

  const onSnapshotChange = (field: string, value: number) => {
    setSnapshot((prev) => ({ ...prev, [field]: value }));
  };

  // Saving the snapshot writes REAL domain records (income / expense / savings
  // asset), so the dashboard, health score, twin, and AI council all see the
  // numbers — not just a preferences blob.
  const SNAPSHOT_INCOME_SOURCE = 'Primary Income';
  const SNAPSHOT_EXPENSE_CATEGORY = 'Living Expenses';
  const SNAPSHOT_ASSET_NAME = 'Savings Balance';

  const onSaveSnapshot = async () => {
    const [incomes, expenses, assets] = await Promise.all([
      apiService.getIncomes(),
      apiService.getExpenses(),
      apiService.getAssets(),
    ]);

    const income = incomes.find((i) => i.source === SNAPSHOT_INCOME_SOURCE);
    if (snapshot.monthlyIncome > 0) {
      if (income) {
        await apiService.updateIncome(income.id, { amount: snapshot.monthlyIncome });
      } else {
        await apiService.createIncome({
          source: SNAPSHOT_INCOME_SOURCE,
          amount: snapshot.monthlyIncome,
          frequency: 'MONTHLY',
        } as any);
      }
    } else if (income) {
      await apiService.deleteIncome(income.id);
    }

    const expense = expenses.find((e) => e.category === SNAPSHOT_EXPENSE_CATEGORY);
    if (snapshot.monthlyExpenses > 0) {
      if (expense) {
        await apiService.updateExpense(expense.id, { amount: snapshot.monthlyExpenses });
      } else {
        await apiService.createExpense({
          category: SNAPSHOT_EXPENSE_CATEGORY,
          amount: snapshot.monthlyExpenses,
          frequency: 'MONTHLY',
        } as any);
      }
    } else if (expense) {
      await apiService.deleteExpense(expense.id);
    }

    const asset = assets.find((a) => a.name === SNAPSHOT_ASSET_NAME);
    if (snapshot.totalSavings > 0) {
      if (asset) {
        await apiService.updateAsset(asset.id, { current_value: snapshot.totalSavings });
      } else {
        await apiService.createAsset({
          name: SNAPSHOT_ASSET_NAME,
          type: 'Bank accounts',
          current_value: snapshot.totalSavings,
        });
      }
    } else if (asset) {
      await apiService.deleteAsset(asset.id);
    }

    await apiService.updateProfile({
      financial_preferences: { dashboard_snapshot: snapshot },
    });
    await refreshFinancialData();
  };

  const persistBudget = async (nextEnvelopes: Record<string, number>) => {
    const month = new Date().toISOString().slice(0, 7);
    await apiService.saveBudget({
      month,
      monthly_budget: Object.values(nextEnvelopes).reduce((sum, value) => sum + value, 0),
      category_budgets: nextEnvelopes,
      budget_utilization: utilization,
    } as Omit<Budget, 'id'>);
    await refreshFinancialData();
  };

  const onUpdateEnvelope = async (cat: string, field: 'allocated' | 'spent', value: number) => {
    if (field === 'allocated') {
      const next = { ...envelopes, [cat]: value };
      setEnvelopes(next);
      await persistBudget(next);
    } else {
      setUtilization((prev) => ({ ...prev, [cat]: value }));
    }
  };

  const onAddEnvelope = async (cat: string, allocated: number) => {
    const next = { ...envelopes, [cat]: allocated };
    setEnvelopes(next);
    await persistBudget(next);
  };

  const onDeleteEnvelope = async (cat: string) => {
    const next = { ...envelopes };
    delete next[cat];
    setEnvelopes(next);
    await persistBudget(next);
  };

  const onUpdateDebt = async (id: string, field: 'balance' | 'apr' | 'monthly', value: number) => {
    const current = debts.find((debt) => debt.id === id);
    if (!current) return;

    const payload: Liability = {
      ...current,
      outstanding_balance: field === 'balance' ? value : current.outstanding_balance,
      apr: field === 'apr' ? value : current.apr,
      monthly_minimum_payment: field === 'monthly' ? value : current.monthly_minimum_payment,
    };
    setDebts((prev) => prev.map((debt) => (debt.id === id ? payload : debt)));
    await apiService.updateLiability(id, payload);
    await refreshFinancialData();
  };

  const onAddDebt = async (name: string, balance: number, apr: number, monthly: number) => {
    await apiService.createLiability({
      name,
      type: 'Other',
      outstanding_balance: balance,
      apr,
      monthly_minimum_payment: monthly,
    });
    await refreshFinancialData();
  };

  const onDeleteDebt = async (id: string) => {
    await apiService.deleteLiability(id);
    await refreshFinancialData();
  };

  const onAddGoal = async (name: string, target: number) => {
    await apiService.createGoal({
      name,
      target_amount: target,
      current_amount: 0,
      status: 'IN_PROGRESS',
    });
    await refreshFinancialData();
  };

  const onDeleteGoal = async (id: string) => {
    await apiService.deleteGoal(id);
    await refreshFinancialData();
  };

  const onAddMessage = (agentId: string, msg: AdvisorMessage) => {
    setChats((prev) => ({
      ...prev,
      [agentId]: [...(prev[agentId] || []), msg],
    }));
  };

  // Restore persisted conversation memory from the backend the first time an
  // agent's chat is opened in this session.
  const onHydrateAgent = useCallback(async (agentId: string) => {
    try {
      const history = await apiService.getChatHistory(agentId);
      if (!history.messages.length) return;
      setChats((prev) => {
        if ((prev[agentId] || []).length > 0) return prev;
        return {
          ...prev,
          [agentId]: history.messages.map((m, idx) => ({
            id: `hist-${agentId}-${idx}`,
            sender: m.role === 'user' ? ('user' as const) : ('agent' as const),
            text: m.content,
            time: '',
            agentId,
          })),
        };
      });
    } catch {
      // History is best-effort; the chat still works without it.
    }
  }, []);

  const snapshotContext = useMemo(
    () => ({
      savingsRate: health.breakdown.savings_rate.raw_value,
      totalDebt: snapshot.totalDebt,
      totalSavings: snapshot.totalSavings,
      monthlyIncome: snapshot.monthlyIncome,
      monthlyExpenses: snapshot.monthlyExpenses,
      housing: snapshot.housing,
      lifestyle: snapshot.lifestyle,
      healthScore: health.score,
      healthGrade: health.grade,
      recentTransactions: transactions.slice(0, 10),
    }),
    [health, snapshot, transactions],
  );

  const renderActivePage = () => {
    switch (activePage) {
      case 'landing':
        return <LandingPage onNavigate={setActivePage} />;
      case 'dashboard':
        return (
          <DashboardPage
            summary={summary}
            health={health}
            snapshot={snapshot}
            onSnapshotChange={onSnapshotChange}
            onSaveSnapshot={onSaveSnapshot}
          />
        );
      case 'twin':
        return <TwinPage snapshot={snapshot} health={health} />;
      case 'advisors':
        return (
          <AdvisorsPage
            chats={chats}
            onAddMessage={onAddMessage}
            onHydrateAgent={onHydrateAgent}
            snapshot={snapshot}
            health={health}
          />
        );
      case 'loan':
        return <LoanPage />;
      case 'tracker':
        return (
          <TrackerPage
            envelopes={envelopes}
            utilization={utilization}
            debts={debts}
            loans={loans}
            onUpdateEnvelope={onUpdateEnvelope}
            onAddEnvelope={onAddEnvelope}
            onDeleteEnvelope={onDeleteEnvelope}
            onUpdateDebt={onUpdateDebt}
            onAddDebt={onAddDebt}
            onDeleteDebt={onDeleteDebt}
          />
        );
      case 'goals':
        return <GoalsPage goals={goals} onAddGoal={onAddGoal} onDeleteGoal={onDeleteGoal} />;
      case 'investment':
        return <InvestmentPage />;
      case 'monitoring':
        return <MonitoringPage />;
      case 'graph':
        return <GraphPage />;
      case 'rag':
        return <RagPage />;
      case 'decisions':
        return <DecisionsPage />;
      case 'memory':
        return <MemoryPage />;
      case 'simulator':
        return <SimulatorPage />;
      case 'observability':
        return <ObservabilityPage />;
      case 'console':
        return <ConsolePage />;
      case 'admin':
        return <AdminPage />;
      case 'settings':
        return <SettingsPage user={user} onUserUpdated={setUser} />;
      default:
        return <LandingPage onNavigate={setActivePage} />;
    }
  };

  if (!authChecked) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#faf8f5]">
        <div className="flex items-center gap-3 text-brand-graphite/50 text-sm animate-pulse">
          <Sparkles size={16} className="text-[#c09a5f]" />
          Restoring session...
        </div>
      </div>
    );
  }

  if (!user) {
    return <AuthPage onAuthenticated={handleAuthenticated} />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary text-brand-graphite font-sans">
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(!collapsed)}
        user={user}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        <Header
          activePage={activePage}
          onOpenCommand={() => setCommandOpen(true)}
          onNavigate={setActivePage}
          apiOnline={apiOnline}
          user={user}
          onLogout={handleLogout}
        />

        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          {bootError && (
            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-xs font-semibold text-amber-800">
              Backend Offline: {bootError}
            </div>
          )}
          {renderActivePage()}
        </main>
      </div>

      <AIAssistant
        isOpen={aiOpen}
        onClose={() => setAiOpen(false)}
        snapshotContext={snapshotContext}
      />

      {!aiOpen && (
        <button
          onClick={() => setAiOpen(true)}
          className="fixed bottom-6 right-6 bg-[#0a1120] text-white p-3 rounded-full shadow-premium hover:bg-[#c09a5f] transition-all hover:scale-105 z-40"
        >
          <Sparkles size={16} />
        </button>
      )}

      <CommandPalette
        isOpen={commandOpen}
        onClose={() => setCommandOpen(false)}
        onNavigate={setActivePage}
      />
    </div>
  );
};
