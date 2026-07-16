from __future__ import annotations

from app.infra.db.models.asset import Asset
from app.infra.db.models.budget import Budget
from app.infra.db.models.expense import Expense
from app.infra.db.models.financial_document import FinancialDocument
from app.infra.db.models.financial_profile import FinancialProfile
from app.infra.db.models.income import Income
from app.infra.db.models.insurance import Insurance
from app.infra.db.models.investment import Investment
from app.infra.db.models.liability import Liability
from app.infra.db.models.loan import Loan
from app.infra.db.models.savings_goal import SavingsGoal
from app.infra.db.models.transaction import Transaction
from app.infra.db.repository import BaseRepository


class FinancialProfileRepository(BaseRepository[FinancialProfile]):
    model = FinancialProfile


class IncomeRepository(BaseRepository[Income]):
    model = Income


class ExpenseRepository(BaseRepository[Expense]):
    model = Expense


class AssetRepository(BaseRepository[Asset]):
    model = Asset


class LiabilityRepository(BaseRepository[Liability]):
    model = Liability


class LoanRepository(BaseRepository[Loan]):
    model = Loan


class InsuranceRepository(BaseRepository[Insurance]):
    model = Insurance


class InvestmentRepository(BaseRepository[Investment]):
    model = Investment


class SavingsGoalRepository(BaseRepository[SavingsGoal]):
    model = SavingsGoal


class FinancialDocumentRepository(BaseRepository[FinancialDocument]):
    model = FinancialDocument


class TransactionRepository(BaseRepository[Transaction]):
    model = Transaction


class BudgetRepository(BaseRepository[Budget]):
    model = Budget
