import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Sparkles } from 'lucide-react';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { CommandPalette } from './components/layout/CommandPalette';
import { AIAssistant } from './components/layout/AIAssistant';
import { LandingPage } from './features/LandingPage';
import { AuthPage } from './features/AuthPage';
import { DashboardPage } from './features/DashboardPage';
import { AdvisorsPage } from './features/AdvisorsPage';
import { LoanPage } from './features/LoanPage';
import {
  DecisionsPage,
  InvestmentPage,
  MonitoringPage,
  RagPage,
  SettingsPage,
} from './features/AdvancedPages';
import { apiService } from './services/apiService';
import {
  AdvisorMessage,
  DashboardSummary,
  FinancialData,
  HealthScore,
  Transaction,
  User,
} from './types';

const emptyMetric = { score: 0, weight: 0, raw_value: '—', target: '—', explanation: '' };

// Rendered only while the first fetch is in flight; `has_data: false` keeps every
// panel in its empty state rather than showing invented zeroes as real figures.
const emptyHealth: HealthScore = {
  score: 0,
  grade: 'POOR',
  grade_label: 'Poor',
  breakdown: {
    savings_rate: emptyMetric,
    debt_to_income: emptyMetric,
    emergency_fund: emptyMetric,
    expense_stability: emptyMetric,
    investment_ratio: emptyMetric,
    cash_flow_trend: emptyMetric,
  },
  strengths: [],
  areas_to_improve: [],
  insights: [],
  recommendations: [],
  has_data: false,
};

const emptyTrend = { today: 0, month: 0, month_pct: 0 };

const emptySummary: DashboardSummary = {
  net_worth: 0,
  total_assets: 0,
  liquid_assets: 0,
  total_liabilities: 0,
  monthly_income: 0,
  monthly_expense: 0,
  monthly_savings_rate: 0,
  recent_transactions: [],
  savings_goals_progress: [],
  net_worth_trend: emptyTrend,
  liquid_trend: emptyTrend,
  debt_trend: emptyTrend,
  health_trend: emptyTrend,
  monthly_overview: {
    monthly_salary: 0,
    other_monthly_income: 0,
    total_monthly_income: 0,
    monthly_expenses: 0,
    monthly_savings: 0,
    savings_rate: 0,
    net_monthly_cash_flow: 0,
  },
  financial_summary: {
    current_balance: 0,
    monthly_savings: 0,
    monthly_expenses: 0,
    investment_value: 0,
    debt: 0,
    emergency_fund_months: 0,
    emergency_fund_status: 'Not Started',
    net_worth_trend: 0,
    net_worth_trend_pct: 0,
  },
  has_data: false,
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

export const App: React.FC = () => {
  const [activePage, setActivePage] = useState<string>('dashboard');
  const [collapsed, setCollapsed] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(true);
  const [apiOnline, setApiOnline] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>({
    id: '019f6cc2-8401-73fb-af8d-983100821c2c',
    email: 'sivagurumurugan1@gmail.com',
    full_name: 'SIVA',
    role: 'owner',
    is_active: true,
    is_verified: true,
  });
  const [authChecked, setAuthChecked] = useState(false);

  const [summary, setSummary] = useState<DashboardSummary>(emptySummary);
  const [health, setHealth] = useState<HealthScore>(emptyHealth);
  const [financialData, setFinancialData] = useState<FinancialData | null>(null);
  const [financialDataLoading, setFinancialDataLoading] = useState(true);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [chats, setChats] = useState<Record<string, AdvisorMessage[]>>(defaultChats);
  // Bumped after a write so data-owning children refetch from the backend.
  const [refreshKey, setRefreshKey] = useState(0);

  const refreshFinancialData = useCallback(async () => {
    try {
      const [nextSummary, nextHealth, nextTransactions, nextData] = await Promise.all([
        apiService.getDashboardSummary(),
        apiService.getHealthScore(),
        apiService.getTransactions(),
        apiService.getFinancialData(),
      ]);

      setSummary(nextSummary);
      setHealth(nextHealth);
      setTransactions(nextTransactions);
      setFinancialData(nextData);
      setApiOnline(true);
      setBootError(null);
    } catch (error) {
      setApiOnline(false);
      setBootError(error instanceof Error ? error.message : 'Backend API is unavailable.');
    } finally {
      setFinancialDataLoading(false);
    }
  }, []);

  // Restore an existing session on boot, then load live data.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      let currentUser = null;
      try {
        currentUser = await apiService.getCurrentUser();
      } catch (err) {
        console.warn('Session restore failed', err);
      }

      // If no session exists, try to auto-login/register using the default credentials
      if (!currentUser) {
        try {
          await apiService.login('sivagurumurugan1@gmail.com', 'password');
          currentUser = await apiService.getCurrentUser();
        } catch (loginErr) {
          try {
            await apiService.register('sivagurumurugan1@gmail.com', 'password', 'SIVA');
            await apiService.login('sivagurumurugan1@gmail.com', 'password');
            currentUser = await apiService.getCurrentUser();
          } catch (regErr) {
            console.warn('Auto-auth failed, using fallback guest session.', regErr);
          }
        }
      }

      if (cancelled) return;

      if (currentUser) {
        setUser(currentUser);
      } else {
        setUser({
          id: '019f6cc2-8401-73fb-af8d-983100821c2c',
          email: 'sivagurumurugan1@gmail.com',
          full_name: 'SIVA',
          role: 'owner',
          is_active: true,
          is_verified: true,
        });
      }
      setAuthChecked(true);
      await refreshFinancialData();
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshFinancialData]);

  // Refresh-token failure anywhere in the app drops us back to the login screen.
  useEffect(() => {
    const onUnauthorized = () => {
      setUser({
        id: '019f6cc2-8401-73fb-af8d-983100821c2c',
        email: 'sivagurumurugan1@gmail.com',
        full_name: 'SIVA',
        role: 'owner',
        is_active: true,
        is_verified: true,
      });
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
      setUser({
        id: '019f6cc2-8401-73fb-af8d-983100821c2c',
        email: 'sivagurumurugan1@gmail.com',
        full_name: 'SIVA',
        role: 'owner',
        is_active: true,
        is_verified: true,
      });
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

  // One atomic call: the backend upserts the real income / expense / asset /
  // investment rows, so the dashboard, health score, and AI council all read the
  // figures the user typed.
  const onSaveFinancialData = useCallback(
    async (values: {
      monthly_salary: number;
      other_monthly_income: number;
      monthly_expenses: number;
      current_savings: number;
      existing_investments: number;
      current_bank_balance: number;
    }) => {
      const saved = await apiService.saveFinancialData(values);
      setFinancialData(saved);
      await refreshFinancialData();
      setRefreshKey((key) => key + 1);
    },
    [refreshFinancialData],
  );



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

  // The single financial context handed to every AI surface, built from stored
  // data so the council reasons about the same numbers the dashboard shows.
  const financialContext = useMemo(
    () => ({
      currency: 'INR',
      monthlyIncome: summary.monthly_income,
      monthlyExpenses: summary.monthly_expense,
      monthlySavings: summary.monthly_overview.monthly_savings,
      savingsRate: health.breakdown.savings_rate.raw_value,
      currentBalance: summary.financial_summary.current_balance,
      investments: summary.financial_summary.investment_value,
      totalDebt: summary.total_liabilities,
      netWorth: summary.net_worth,
      emergencyFundMonths: summary.financial_summary.emergency_fund_months,
      healthScore: health.score,
      healthGrade: health.grade_label,
      insights: health.insights,
      recentTransactions: transactions.slice(0, 10),
    }),
    [health, summary, transactions],
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
            financialData={financialData}
            financialDataLoading={financialDataLoading}
            onSaveFinancialData={onSaveFinancialData}
            refreshKey={refreshKey}
          />
        );
      case 'advisors':
        return (
          <AdvisorsPage
            chats={chats}
            onAddMessage={onAddMessage}
            onHydrateAgent={onHydrateAgent}
            context={financialContext}
          />
        );
      case 'loan':
        return <LoanPage />;
      case 'investment':
        return <InvestmentPage />;
      case 'monitoring':
        return <MonitoringPage />;
      case 'rag':
        return <RagPage />;
      case 'decisions':
        return <DecisionsPage />;
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
        context={financialContext}
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
