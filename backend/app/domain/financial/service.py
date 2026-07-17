from __future__ import annotations

import itertools
import statistics
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationAppError
from app.core.filtering import FieldFilter, FilterOperator, SortField
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
from app.infra.db.repositories.financial import (
    AssetRepository,
    BudgetRepository,
    ExpenseRepository,
    FinancialDocumentRepository,
    FinancialProfileRepository,
    IncomeRepository,
    InsuranceRepository,
    InvestmentRepository,
    LiabilityRepository,
    LoanRepository,
    SavingsGoalRepository,
    TransactionRepository,
)
from app.utils.datetime import utc_now

# Canonical record identities behind the dashboard's Financial Data Upload form.
# The form is a view over real domain rows, so the summary, health score, and AI
# council all read the same numbers the user typed.
SALARY_SOURCE = "Monthly Salary"
OTHER_INCOME_SOURCE = "Other Monthly Income"
UPLOAD_EXPENSE_CATEGORY = "Monthly Expenses"
SAVINGS_ASSET_NAME = "Current Savings"
SAVINGS_ASSET_TYPE = "Savings"
BANK_ASSET_NAME = "Current Bank Balance"
BANK_ASSET_TYPE = "Bank accounts"
INVESTMENT_NAME = "Existing Investments"
INVESTMENT_TYPE = "Portfolio"

# Assets that can be drawn on within days — the emergency-fund denominator.
LIQUID_ASSET_TYPES = ("Cash", "Bank accounts", "Savings")
# Assets held as spendable balance rather than earmarked savings.
BALANCE_ASSET_TYPES = ("Cash", "Bank accounts")

INFLOW_TX_TYPES = ("Income", "Refund")
OUTFLOW_TX_TYPES = ("Expense", "Investment", "Loan Payment", "Insurance Premium")

ZERO = Decimal("0.00")

GRADE_LABELS = {
    "EXCELLENT": "Excellent",
    "VERY_GOOD": "Very Good",
    "GOOD": "Good",
    "NEEDS_IMPROVEMENT": "Needs Improvement",
    "POOR": "Poor",
}

# Weights sum to 100. A metric that cannot be measured yet (no transaction
# history) drops out and the remainder is renormalised, so a new account is not
# punished for data it has had no chance to produce.
METRIC_WEIGHTS = {
    "savings_rate": 30.0,
    "debt_to_income": 25.0,
    "emergency_fund": 15.0,
    "expense_stability": 10.0,
    "investment_ratio": 10.0,
    "cash_flow_trend": 10.0,
}

METRIC_LABELS = {
    "savings_rate": "Savings rate",
    "debt_to_income": "Debt-to-income ratio",
    "emergency_fund": "Emergency fund",
    "expense_stability": "Expense stability",
    "investment_ratio": "Investment allocation",
    "cash_flow_trend": "Cash flow trend",
}


def _rupees(value: Decimal | float) -> str:
    """₹1,25,000 — Indian digit grouping for figures embedded in generated text.

    Python's locale support cannot be relied on inside a container, so the
    lakh/crore grouping is applied directly.
    """
    num = round(float(value))
    sign = "-" if num < 0 else ""
    digits = str(abs(num))
    if len(digits) <= 3:
        return f"{sign}₹{digits}"
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return f"{sign}₹{','.join(groups)},{tail}"


def _band(value: float, points: list[tuple[float, float]]) -> float:
    """Piecewise-linear score from ``points`` given as ascending (value, score).

    Interpolating instead of using fixed buckets means a small real improvement
    always moves the score, rather than the user sitting on a cliff edge.
    """
    if value <= points[0][0]:
        return points[0][1]
    if value >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in itertools.pairwise(points):
        if x0 <= value <= x1:
            if x1 == x0:
                return y1
            return y0 + (value - x0) / (x1 - x0) * (y1 - y0)
    return points[-1][1]


def _pct_change(current: Decimal, previous: Decimal) -> float:
    """Percentage movement, guarding the divide-by-zero opening balance."""
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return float((current - previous) / abs(previous) * 100)


class FinancialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.profiles = FinancialProfileRepository(session)
        self.incomes = IncomeRepository(session)
        self.expenses = ExpenseRepository(session)
        self.assets = AssetRepository(session)
        self.liabilities = LiabilityRepository(session)
        self.loans = LoanRepository(session)
        self.insurances = InsuranceRepository(session)
        self.investments = InvestmentRepository(session)
        self.savings_goals = SavingsGoalRepository(session)
        self.documents = FinancialDocumentRepository(session)
        self.transactions = TransactionRepository(session)
        self.budgets = BudgetRepository(session)

    # --- Financial Profile ---
    async def get_profile(self, user_id: uuid.UUID) -> FinancialProfile:
        profile = await self.profiles.get_by(user_id=user_id)
        if profile is None:
            # Create default profile
            profile = FinancialProfile(
                user_id=user_id,
                currency="INR",
                country="",
                risk_profile="MEDIUM",
                financial_literacy_level="BEGINNER",
                personal_info={},
                financial_preferences={},
            )
            await self.profiles.add(profile)
            await self.session.refresh(profile)
        return profile

    async def update_profile(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> FinancialProfile:
        profile = await self.get_profile(user_id)
        values = {k: v for k, v in data.items() if v is not None}
        if values:
            values["updated_by"] = actor_id or user_id
            await self.profiles.update(profile, **values)
            await self.session.refresh(profile)
        return profile

    # --- Financial Data Upload ---
    # The six figures the user types on the dashboard are stored as ordinary
    # Income / Expense / Asset / Investment rows rather than a preferences blob,
    # so there is exactly one source of truth to calculate from.
    def _uf(self, user_id: uuid.UUID) -> list[FieldFilter]:
        return [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user_id))]

    async def _upsert_income(
        self, user_id: uuid.UUID, source: str, amount: Decimal, actor_id: uuid.UUID | None
    ) -> None:
        existing = await self.incomes.get_by(user_id=user_id, source=source)
        if amount > 0:
            if existing is not None:
                await self.incomes.update(
                    existing,
                    amount=amount,
                    frequency="MONTHLY",
                    is_recurring=True,
                    normalized_monthly_amount=amount,
                    updated_by=actor_id or user_id,
                )
            else:
                await self.incomes.add(
                    Income(
                        user_id=user_id,
                        source=source,
                        amount=amount,
                        currency="INR",
                        frequency="MONTHLY",
                        is_recurring=True,
                        start_date=utc_now().date(),
                        normalized_monthly_amount=amount,
                        created_by=actor_id or user_id,
                    )
                )
        elif existing is not None:
            # Entering 0 means "I don't have this" — retire the row so it stops
            # counting toward monthly income.
            await self.incomes.soft_delete(existing)

    async def _upsert_expense(
        self, user_id: uuid.UUID, category: str, amount: Decimal, actor_id: uuid.UUID | None
    ) -> None:
        existing = await self.expenses.get_by(user_id=user_id, category=category)
        if amount > 0:
            if existing is not None:
                await self.expenses.update(
                    existing,
                    amount=amount,
                    normalized_monthly_amount=amount,
                    is_recurring=True,
                    updated_by=actor_id or user_id,
                )
            else:
                await self.expenses.add(
                    Expense(
                        user_id=user_id,
                        category=category,
                        expense_type="RECURRING",
                        amount=amount,
                        currency="INR",
                        is_recurring=True,
                        normalized_monthly_amount=amount,
                        description="Declared monthly expenses",
                        created_by=actor_id or user_id,
                    )
                )
        elif existing is not None:
            await self.expenses.soft_delete(existing)

    async def _upsert_asset(
        self,
        user_id: uuid.UUID,
        name: str,
        asset_type: str,
        value: Decimal,
        actor_id: uuid.UUID | None,
    ) -> None:
        existing = await self.assets.get_by(user_id=user_id, name=name)
        if value > 0:
            if existing is not None:
                await self.assets.update(
                    existing, current_value=value, type=asset_type, updated_by=actor_id or user_id
                )
            else:
                await self.assets.add(
                    Asset(
                        user_id=user_id,
                        name=name,
                        type=asset_type,
                        current_value=value,
                        currency="INR",
                        created_by=actor_id or user_id,
                    )
                )
        elif existing is not None:
            await self.assets.soft_delete(existing)

    async def _upsert_investment(
        self, user_id: uuid.UUID, name: str, value: Decimal, actor_id: uuid.UUID | None
    ) -> None:
        existing = await self.investments.get_by(user_id=user_id, name=name)
        if value > 0:
            if existing is not None:
                await self.investments.update(
                    existing,
                    current_value=value,
                    amount_invested=value,
                    last_updated_at=utc_now(),
                    updated_by=actor_id or user_id,
                )
            else:
                await self.investments.add(
                    Investment(
                        user_id=user_id,
                        name=name,
                        type=INVESTMENT_TYPE,
                        amount_invested=value,
                        current_value=value,
                        currency="INR",
                        last_updated_at=utc_now(),
                        created_by=actor_id or user_id,
                    )
                )
        elif existing is not None:
            await self.investments.soft_delete(existing)

    async def get_financial_data(self, user_id: uuid.UUID) -> dict[str, Any]:
        salary = await self.incomes.get_by(user_id=user_id, source=SALARY_SOURCE)
        other = await self.incomes.get_by(user_id=user_id, source=OTHER_INCOME_SOURCE)
        expense = await self.expenses.get_by(user_id=user_id, category=UPLOAD_EXPENSE_CATEGORY)
        savings = await self.assets.get_by(user_id=user_id, name=SAVINGS_ASSET_NAME)
        bank = await self.assets.get_by(user_id=user_id, name=BANK_ASSET_NAME)
        investments = await self.investments.get_by(user_id=user_id, name=INVESTMENT_NAME)

        rows = [r for r in (salary, other, expense, savings, bank, investments) if r is not None]
        updated_at = max((r.updated_at for r in rows), default=None)

        return {
            "monthly_salary": salary.amount if salary else ZERO,
            "other_monthly_income": other.amount if other else ZERO,
            "monthly_expenses": expense.amount if expense else ZERO,
            "current_savings": savings.current_value if savings else ZERO,
            "existing_investments": investments.current_value if investments else ZERO,
            "current_bank_balance": bank.current_value if bank else ZERO,
            "has_data": salary is not None,
            "updated_at": updated_at,
        }

    async def save_financial_data(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        fields = (
            "monthly_salary",
            "other_monthly_income",
            "monthly_expenses",
            "current_savings",
            "existing_investments",
            "current_bank_balance",
        )
        values: dict[str, Decimal] = {}
        for field in fields:
            raw = data.get(field)
            if raw is None or raw == "":
                raise ValidationAppError(f"'{field.replace('_', ' ')}' is required.")
            try:
                amount = Decimal(str(raw))
            except (ArithmeticError, ValueError) as exc:
                raise ValidationAppError(f"'{field.replace('_', ' ')}' must be a number.") from exc
            if not amount.is_finite():
                raise ValidationAppError(f"'{field.replace('_', ' ')}' must be a number.")
            if amount < 0:
                raise ValidationAppError(f"'{field.replace('_', ' ')}' cannot be negative.")
            values[field] = amount

        if values["monthly_salary"] <= 0:
            raise ValidationAppError("Monthly salary must be greater than zero.")

        await self._upsert_income(user_id, SALARY_SOURCE, values["monthly_salary"], actor_id)
        await self._upsert_income(
            user_id, OTHER_INCOME_SOURCE, values["other_monthly_income"], actor_id
        )
        await self._upsert_expense(
            user_id, UPLOAD_EXPENSE_CATEGORY, values["monthly_expenses"], actor_id
        )
        await self._upsert_asset(
            user_id, SAVINGS_ASSET_NAME, SAVINGS_ASSET_TYPE, values["current_savings"], actor_id
        )
        await self._upsert_asset(
            user_id, BANK_ASSET_NAME, BANK_ASSET_TYPE, values["current_bank_balance"], actor_id
        )
        await self._upsert_investment(
            user_id, INVESTMENT_NAME, values["existing_investments"], actor_id
        )

        # Snapshot the resulting score so the health card has a baseline to
        # measure tomorrow's movement against.
        await self._record_health_snapshot(user_id)

        return await self.get_financial_data(user_id)

    # --- Income ---
    def normalize_income(self, amount: Decimal, frequency: str) -> Decimal:
        if amount <= 0:
            raise ValidationAppError("Income amount must be positive.")
        freq = frequency.upper()
        if freq == "WEEKLY":
            return amount * Decimal("4.3333")
        elif freq == "BI_WEEKLY":
            return amount * Decimal("2.1667")
        elif freq == "MONTHLY":
            return amount
        elif freq == "YEARLY":
            return amount / Decimal("12.0")
        elif freq == "ONE_TIME":
            return amount / Decimal("12.0")  # Amortize over 12 months
        else:
            return amount

    async def create_income(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> Income:
        amount = Decimal(str(data["amount"]))
        if amount <= 0:
            raise ValidationAppError("Income amount must be positive.")
        freq = data["frequency"]
        norm_amt = self.normalize_income(amount, freq)

        income = Income(
            user_id=user_id,
            source=data["source"],
            amount=amount,
            currency=data.get("currency", "INR"),
            frequency=freq,
            is_recurring=data.get("is_recurring", True),
            start_date=data["start_date"],
            end_date=data.get("end_date"),
            normalized_monthly_amount=norm_amt,
            created_by=actor_id or user_id,
        )
        await self.incomes.add(income)
        await self.session.refresh(income)
        return income

    async def update_income(
        self,
        user_id: uuid.UUID,
        income_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> Income:
        income = await self.incomes.get(income_id)
        if income is None or income.user_id != user_id:
            raise NotFoundError("Income not found.")

        values = {k: v for k, v in data.items() if v is not None}
        if "amount" in values or "frequency" in values:
            amount = Decimal(str(values.get("amount", income.amount)))
            if amount <= 0:
                raise ValidationAppError("Income amount must be positive.")
            freq = values.get("frequency", income.frequency)
            values["normalized_monthly_amount"] = self.normalize_income(amount, freq)

        if values:
            values["updated_by"] = actor_id or user_id
            await self.incomes.update(income, **values)
            await self.session.refresh(income)
        return income

    async def delete_income(self, user_id: uuid.UUID, income_id: uuid.UUID) -> None:
        income = await self.incomes.get(income_id)
        if income is None or income.user_id != user_id:
            raise NotFoundError("Income not found.")
        await self.incomes.soft_delete(income)

    # --- Expense ---
    async def create_expense(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> Expense:
        amount = Decimal(str(data["amount"]))
        if amount <= 0:
            raise ValidationAppError("Expense amount must be positive.")

        norm_amt = amount

        expense = Expense(
            user_id=user_id,
            category=data["category"],
            expense_type=data["expense_type"],
            amount=amount,
            currency=data.get("currency", "INR"),
            is_recurring=data.get("is_recurring", False),
            due_date=data.get("due_date"),
            normalized_monthly_amount=norm_amt,
            description=data.get("description"),
            created_by=actor_id or user_id,
        )
        saved_expense = await self.expenses.add(expense)
        await self.session.refresh(saved_expense)

        # Trigger budget utilization check
        month_str = utc_now().strftime("%Y-%m")
        await self.check_budget_utilization(user_id, data["category"], amount, month_str)

        return saved_expense

    async def update_expense(
        self,
        user_id: uuid.UUID,
        expense_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> Expense:
        expense = await self.expenses.get(expense_id)
        if expense is None or expense.user_id != user_id:
            raise NotFoundError("Expense not found.")

        values = {k: v for k, v in data.items() if v is not None}
        if "amount" in values:
            amount = Decimal(str(values["amount"]))
            if amount <= 0:
                raise ValidationAppError("Expense amount must be positive.")
            values["normalized_monthly_amount"] = amount

        if values:
            values["updated_by"] = actor_id or user_id
            await self.expenses.update(expense, **values)
            await self.session.refresh(expense)

        return expense

    async def delete_expense(self, user_id: uuid.UUID, expense_id: uuid.UUID) -> None:
        expense = await self.expenses.get(expense_id)
        if expense is None or expense.user_id != user_id:
            raise NotFoundError("Expense not found.")
        await self.expenses.soft_delete(expense)

    # --- Asset ---
    async def create_asset(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> Asset:
        val = Decimal(str(data["current_value"]))
        if val < 0:
            raise ValidationAppError("Asset value cannot be negative.")
        asset = Asset(
            user_id=user_id,
            name=data["name"],
            type=data["type"],
            current_value=val,
            currency=data.get("currency", "INR"),
            details=data.get("details"),
            created_by=actor_id or user_id,
        )
        await self.assets.add(asset)
        await self.session.refresh(asset)
        return asset

    async def update_asset(
        self,
        user_id: uuid.UUID,
        asset_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> Asset:
        asset = await self.assets.get(asset_id)
        if asset is None or asset.user_id != user_id:
            raise NotFoundError("Asset not found.")
        values = {k: v for k, v in data.items() if v is not None}
        if "current_value" in values:
            val = Decimal(str(values["current_value"]))
            if val < 0:
                raise ValidationAppError("Asset value cannot be negative.")
        if values:
            values["updated_by"] = actor_id or user_id
            await self.assets.update(asset, **values)
            await self.session.refresh(asset)
        return asset

    async def delete_asset(self, user_id: uuid.UUID, asset_id: uuid.UUID) -> None:
        asset = await self.assets.get(asset_id)
        if asset is None or asset.user_id != user_id:
            raise NotFoundError("Asset not found.")
        await self.assets.soft_delete(asset)

    # --- Liability ---
    async def create_liability(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> Liability:
        bal = Decimal(str(data["outstanding_balance"]))
        if bal < 0:
            raise ValidationAppError("Liability outstanding balance cannot be negative.")
        liability = Liability(
            user_id=user_id,
            name=data["name"],
            type=data["type"],
            outstanding_balance=bal,
            currency=data.get("currency", "INR"),
            details=data.get("details"),
            created_by=actor_id or user_id,
        )
        await self.liabilities.add(liability)
        await self.session.refresh(liability)
        return liability

    async def update_liability(
        self,
        user_id: uuid.UUID,
        liability_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> Liability:
        liability = await self.liabilities.get(liability_id)
        if liability is None or liability.user_id != user_id:
            raise NotFoundError("Liability not found.")
        values = {k: v for k, v in data.items() if v is not None}
        if "outstanding_balance" in values:
            bal = Decimal(str(values["outstanding_balance"]))
            if bal < 0:
                raise ValidationAppError("Liability outstanding balance cannot be negative.")
        if values:
            values["updated_by"] = actor_id or user_id
            await self.liabilities.update(liability, **values)
            await self.session.refresh(liability)
        return liability

    async def delete_liability(self, user_id: uuid.UUID, liability_id: uuid.UUID) -> None:
        liability = await self.liabilities.get(liability_id)
        if liability is None or liability.user_id != user_id:
            raise NotFoundError("Liability not found.")
        await self.liabilities.soft_delete(liability)

    # --- Loan ---
    async def create_loan(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> Loan:
        bal = Decimal(str(data["outstanding_balance"]))
        emi = Decimal(str(data["emi"]))
        rate = Decimal(str(data["interest_rate"]))
        apr = Decimal(str(data["apr"]))
        processing = Decimal(str(data.get("processing_fees", 0)))

        if bal < 0:
            raise ValidationAppError("Loan outstanding balance cannot be negative.")
        if emi <= 0:
            raise ValidationAppError("Loan EMI must be positive.")
        if rate < 0 or apr < 0 or processing < 0:
            raise ValidationAppError("Rates and fees cannot be negative.")

        loan = Loan(
            user_id=user_id,
            name=data["name"],
            type=data["type"],
            interest_rate=rate,
            apr=apr,
            processing_fees=processing,
            emi=emi,
            remaining_tenure=data["remaining_tenure"],
            outstanding_balance=bal,
            collateral=data.get("collateral"),
            status=data.get("status", "ACTIVE"),
            payment_history=data.get("payment_history") or [],
            created_by=actor_id or user_id,
        )
        await self.loans.add(loan)
        await self.session.refresh(loan)
        return loan

    async def update_loan(
        self,
        user_id: uuid.UUID,
        loan_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> Loan:
        loan = await self.loans.get(loan_id)
        if loan is None or loan.user_id != user_id:
            raise NotFoundError("Loan not found.")

        values = {k: v for k, v in data.items() if v is not None}
        if "outstanding_balance" in values:
            bal = Decimal(str(values["outstanding_balance"]))
            if bal < 0:
                raise ValidationAppError("Loan outstanding balance cannot be negative.")
        if "emi" in values:
            emi = Decimal(str(values["emi"]))
            if emi <= 0:
                raise ValidationAppError("Loan EMI must be positive.")

        if values:
            values["updated_by"] = actor_id or user_id
            await self.loans.update(loan, **values)
            await self.session.refresh(loan)
        return loan

    async def delete_loan(self, user_id: uuid.UUID, loan_id: uuid.UUID) -> None:
        loan = await self.loans.get(loan_id)
        if loan is None or loan.user_id != user_id:
            raise NotFoundError("Loan not found.")
        await self.loans.soft_delete(loan)

    # --- Insurance ---
    async def create_insurance(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> Insurance:
        cov = Decimal(str(data["coverage_amount"]))
        prem = Decimal(str(data["premium_amount"]))

        if cov <= 0 or prem <= 0:
            raise ValidationAppError("Insurance amounts must be positive.")

        ins = Insurance(
            user_id=user_id,
            policy_number=data["policy_number"],
            provider=data["provider"],
            type=data["type"],
            coverage_amount=cov,
            premium_amount=prem,
            premium_frequency=data["premium_frequency"],
            renewal_date=data["renewal_date"],
            beneficiaries=data.get("beneficiaries") or [],
            status=data.get("status", "ACTIVE"),
            created_by=actor_id or user_id,
        )
        await self.insurances.add(ins)
        await self.session.refresh(ins)
        return ins

    async def update_insurance(
        self,
        user_id: uuid.UUID,
        insurance_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> Insurance:
        ins = await self.insurances.get(insurance_id)
        if ins is None or ins.user_id != user_id:
            raise NotFoundError("Insurance not found.")

        values = {k: v for k, v in data.items() if v is not None}
        if "coverage_amount" in values:
            cov = Decimal(str(values["coverage_amount"]))
            if cov <= 0:
                raise ValidationAppError("Coverage amount must be positive.")
        if "premium_amount" in values:
            prem = Decimal(str(values["premium_amount"]))
            if prem <= 0:
                raise ValidationAppError("Premium amount must be positive.")

        if values:
            values["updated_by"] = actor_id or user_id
            await self.insurances.update(ins, **values)
            await self.session.refresh(ins)
        return ins

    async def delete_insurance(self, user_id: uuid.UUID, insurance_id: uuid.UUID) -> None:
        ins = await self.insurances.get(insurance_id)
        if ins is None or ins.user_id != user_id:
            raise NotFoundError("Insurance not found.")
        await self.insurances.soft_delete(ins)

    # --- Investment ---
    async def create_investment(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> Investment:
        amt = Decimal(str(data["amount_invested"]))
        val = Decimal(str(data["current_value"]))

        if amt < 0 or val < 0:
            raise ValidationAppError("Investment values cannot be negative.")

        inv = Investment(
            user_id=user_id,
            name=data["name"],
            type=data["type"],
            amount_invested=amt,
            current_value=val,
            quantity=Decimal(str(data["quantity"])) if data.get("quantity") is not None else None,
            purchase_price=(
                Decimal(str(data["purchase_price"]))
                if data.get("purchase_price") is not None
                else None
            ),
            ticker=data.get("ticker"),
            currency=data.get("currency", "INR"),
            last_updated_at=data.get("last_updated_at") or utc_now(),
            created_by=actor_id or user_id,
        )
        await self.investments.add(inv)
        await self.session.refresh(inv)
        return inv

    async def update_investment(
        self,
        user_id: uuid.UUID,
        investment_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> Investment:
        inv = await self.investments.get(investment_id)
        if inv is None or inv.user_id != user_id:
            raise NotFoundError("Investment not found.")

        values = {k: v for k, v in data.items() if v is not None}
        if "amount_invested" in values:
            amt = Decimal(str(values["amount_invested"]))
            if amt < 0:
                raise ValidationAppError("Investment values cannot be negative.")
        if "current_value" in values:
            val = Decimal(str(values["current_value"]))
            if val < 0:
                raise ValidationAppError("Investment values cannot be negative.")

        if values:
            values["updated_by"] = actor_id or user_id
            await self.investments.update(inv, **values)
            await self.session.refresh(inv)
        return inv

    async def delete_investment(self, user_id: uuid.UUID, investment_id: uuid.UUID) -> None:
        inv = await self.investments.get(investment_id)
        if inv is None or inv.user_id != user_id:
            raise NotFoundError("Investment not found.")
        await self.investments.soft_delete(inv)

    # --- Savings Goal ---
    async def create_savings_goal(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> SavingsGoal:
        target = Decimal(str(data["target_amount"]))
        prog = Decimal(str(data.get("current_progress", 0)))

        if target <= 0:
            raise ValidationAppError("Target amount must be positive.")
        if prog < 0:
            raise ValidationAppError("Current progress cannot be negative.")

        sg = SavingsGoal(
            user_id=user_id,
            name=data["name"],
            category=data["category"],
            target_amount=target,
            target_date=data["target_date"],
            current_progress=prog,
            currency=data.get("currency", "INR"),
            created_by=actor_id or user_id,
        )
        await self.savings_goals.add(sg)
        await self.session.refresh(sg)
        return sg

    async def update_savings_goal(
        self,
        user_id: uuid.UUID,
        goal_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> SavingsGoal:
        sg = await self.savings_goals.get(goal_id)
        if sg is None or sg.user_id != user_id:
            raise NotFoundError("Savings goal not found.")

        values = {k: v for k, v in data.items() if v is not None}
        if "target_amount" in values:
            target = Decimal(str(values["target_amount"]))
            if target <= 0:
                raise ValidationAppError("Target amount must be positive.")
        if "current_progress" in values:
            prog = Decimal(str(values["current_progress"]))
            if prog < 0:
                raise ValidationAppError("Current progress cannot be negative.")

        if values:
            values["updated_by"] = actor_id or user_id
            await self.savings_goals.update(sg, **values)
            await self.session.refresh(sg)
        return sg

    async def delete_savings_goal(self, user_id: uuid.UUID, goal_id: uuid.UUID) -> None:
        sg = await self.savings_goals.get(goal_id)
        if sg is None or sg.user_id != user_id:
            raise NotFoundError("Savings goal not found.")
        await self.savings_goals.soft_delete(sg)

    # --- Financial Document ---
    async def create_document(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> FinancialDocument:
        doc = FinancialDocument(
            user_id=user_id,
            name=data["name"],
            type=data["type"],
            file_path=data["file_path"],
            uploaded_at=utc_now(),
            metadata_json=data.get("metadata_json") or {},
            created_by=actor_id or user_id,
        )
        await self.documents.add(doc)
        await self.session.refresh(doc)
        return doc

    async def update_document(
        self,
        user_id: uuid.UUID,
        doc_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> FinancialDocument:
        doc = await self.documents.get(doc_id)
        if doc is None or doc.user_id != user_id:
            raise NotFoundError("Financial document not found.")

        values = {k: v for k, v in data.items() if v is not None}
        if values:
            values["updated_by"] = actor_id or user_id
            await self.documents.update(doc, **values)
            await self.session.refresh(doc)
        return doc

    async def delete_document(self, user_id: uuid.UUID, doc_id: uuid.UUID) -> None:
        doc = await self.documents.get(doc_id)
        if doc is None or doc.user_id != user_id:
            raise NotFoundError("Financial document not found.")
        await self.documents.soft_delete(doc)

    # --- Transaction & Side-Effects ---
    async def create_transaction(
        self, user_id: uuid.UUID, data: dict[str, Any], actor_id: uuid.UUID | None = None
    ) -> Transaction:
        amount = Decimal(str(data["amount"]))
        if amount <= 0:
            raise ValidationAppError("Transaction amount must be positive.")

        tx_type = data["type"].title()
        tx = Transaction(
            user_id=user_id,
            type=tx_type,
            category=data["category"],
            amount=amount,
            currency=data.get("currency", "INR"),
            transaction_date=data.get("transaction_date") or utc_now(),
            description=data.get("description"),
            reference_id=data.get("reference_id"),
            created_by=actor_id or user_id,
        )
        saved_tx = await self.transactions.add(tx)
        await self.session.refresh(saved_tx)

        # TRIGGER SIDE-EFFECTS
        # 1. Update general Cash asset balance
        cash_asset = await self.assets.get_by(user_id=user_id, type="Cash")
        if cash_asset is None:
            # Create default Cash asset
            cash_asset = Asset(
                user_id=user_id,
                name="Cash Wallet",
                type="Cash",
                current_value=Decimal("0.00"),
                currency=data.get("currency", "INR"),
            )
            await self.assets.add(cash_asset)

        if tx_type in ("Income", "Refund"):
            new_val = cash_asset.current_value + amount
            await self.assets.update(cash_asset, current_value=new_val)
        elif tx_type in ("Expense", "Insurance Premium"):
            new_val = cash_asset.current_value - amount
            if new_val < 0:
                raise ValidationAppError("Insufficient cash balance for this expense.")
            await self.assets.update(cash_asset, current_value=new_val)

        # 2. Loan Payment Side-Effects
        if tx_type == "Loan Payment" and data.get("reference_id"):
            try:
                loan_uuid = uuid.UUID(data["reference_id"])
                loan = await self.loans.get(loan_uuid)
                if loan and loan.user_id == user_id:
                    new_bal = loan.outstanding_balance - amount
                    if new_bal < 0:
                        new_bal = Decimal("0.00")
                    status = "PAID_OFF" if new_bal == 0 else loan.status
                    history = list(loan.payment_history or [])
                    history.append(
                        {
                            "date": utc_now().isoformat(),
                            "amount": float(amount),
                            "transaction_id": str(saved_tx.id),
                        }
                    )
                    await self.loans.update(
                        loan,
                        outstanding_balance=new_bal,
                        status=status,
                        payment_history=history,
                    )
                    # Subtract payment from cash
                    new_cash_val = cash_asset.current_value - amount
                    if new_cash_val < 0:
                        new_cash_val = Decimal("0.00")
                    await self.assets.update(cash_asset, current_value=new_cash_val)
            except ValueError:
                pass

        # 3. Investment Side-Effects
        if tx_type == "Investment" and data.get("reference_id"):
            try:
                inv_uuid = uuid.UUID(data["reference_id"])
                investment = await self.investments.get(inv_uuid)
                if investment and investment.user_id == user_id:
                    new_invested = investment.amount_invested + amount
                    new_val = investment.current_value + amount
                    await self.investments.update(
                        investment,
                        amount_invested=new_invested,
                        current_value=new_val,
                        last_updated_at=utc_now(),
                    )
                    # Subtract from cash
                    new_cash_val = cash_asset.current_value - amount
                    if new_cash_val < 0:
                        new_cash_val = Decimal("0.00")
                    await self.assets.update(cash_asset, current_value=new_cash_val)
            except ValueError:
                pass

        # 4. Expense Side-Effects on Budgets
        if tx_type == "Expense":
            month_str = tx.transaction_date.strftime("%Y-%m")
            await self.check_budget_utilization(user_id, tx.category, amount, month_str)

        return saved_tx

    async def update_transaction(
        self,
        user_id: uuid.UUID,
        tx_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> Transaction:
        tx = await self.transactions.get(tx_id)
        if tx is None or tx.user_id != user_id:
            raise NotFoundError("Transaction not found.")

        values = {k: v for k, v in data.items() if v is not None}
        if "amount" in values:
            amount = Decimal(str(values["amount"]))
            if amount <= 0:
                raise ValidationAppError("Transaction amount must be positive.")

        if values:
            values["updated_by"] = actor_id or user_id
            await self.transactions.update(tx, **values)
            await self.session.refresh(tx)
        return tx

    async def delete_transaction(self, user_id: uuid.UUID, tx_id: uuid.UUID) -> None:
        tx = await self.transactions.get(tx_id)
        if tx is None or tx.user_id != user_id:
            raise NotFoundError("Transaction not found.")
        await self.transactions.soft_delete(tx)

    # --- Budget & Utilization ---
    async def get_or_create_budget(self, user_id: uuid.UUID, month: str) -> Budget:
        budget = await self.budgets.get_by(user_id=user_id, month=month)
        if budget is None:
            budget = Budget(
                user_id=user_id,
                month=month,
                monthly_budget=Decimal("1000.00"),
                category_budgets={},
                budget_utilization={},
                budget_alerts={},
            )
            await self.budgets.add(budget)
            await self.session.refresh(budget)
        return budget

    async def create_budget(
        self,
        user_id: uuid.UUID,
        month: str,
        monthly_budget: Decimal,
        category_budgets: dict[str, float] | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> Budget:
        budget = await self.get_or_create_budget(user_id, month)
        values: dict[str, Any] = {"monthly_budget": monthly_budget}
        if category_budgets is not None:
            values["category_budgets"] = category_budgets
        values["updated_by"] = actor_id or user_id
        await self.budgets.update(budget, **values)
        await self.session.refresh(budget)
        return budget

    async def update_budget(
        self,
        user_id: uuid.UUID,
        budget_id: uuid.UUID,
        data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
    ) -> Budget:
        budget = await self.budgets.get(budget_id)
        if budget is None or budget.user_id != user_id:
            raise NotFoundError("Budget not found.")

        values = {k: v for k, v in data.items() if v is not None}
        if "monthly_budget" in values:
            val = Decimal(str(values["monthly_budget"]))
            if val <= 0:
                raise ValidationAppError("Budget must be positive.")

        if values:
            values["updated_by"] = actor_id or user_id
            await self.budgets.update(budget, **values)
            await self.session.refresh(budget)
        return budget

    async def check_budget_utilization(
        self, user_id: uuid.UUID, category: str, new_expense_amount: Decimal, month_str: str
    ) -> None:
        budget = await self.get_or_create_budget(user_id, month_str)

        from app.core.filtering import FieldFilter, FilterOperator

        user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user_id))]
        all_expenses, _ = await self.expenses.list(
            filters=user_filter, limit=1000, include_deleted=False
        )
        user_expenses = [e for e in all_expenses if e.created_at.strftime("%Y-%m") == month_str]

        util = dict(budget.budget_utilization or {})
        total_util = Decimal("0.00")
        cat_util = Decimal("0.00")

        for e in user_expenses:
            total_util += e.amount
            if e.category == category:
                cat_util += e.amount

        util["total"] = float(total_util)
        util[category] = float(cat_util)

        alerts = dict(budget.budget_alerts or {})
        limit = Decimal(str(budget.monthly_budget))

        if total_util >= limit:
            alerts["total"] = {
                "status": "CRITICAL",
                "message": f"Total monthly budget of {limit} exceeded!",
            }
        elif total_util >= limit * Decimal("0.8"):
            alerts["total"] = {
                "status": "WARNING",
                "message": f"Total monthly budget has reached 80% ({total_util})",
            }

        cat_limit = Decimal(str((budget.category_budgets or {}).get(category, 0)))
        if cat_limit > 0:
            if cat_util >= cat_limit:
                alerts[category] = {
                    "status": "CRITICAL",
                    "message": f"Category '{category}' budget of {cat_limit} exceeded!",
                }
            elif cat_util >= cat_limit * Decimal("0.8"):
                alerts[category] = {
                    "status": "WARNING",
                    "message": f"Category '{category}' budget has reached 80% ({cat_util})",
                }

        await self.budgets.update(budget, budget_utilization=util, budget_alerts=alerts)

    # --- Transaction ledger query (search / filter / sort / paginate) ---
    async def query_transactions(
        self,
        user_id: uuid.UUID,
        *,
        search: str | None = None,
        category: str | None = None,
        tx_type: str | None = None,
        sort_by: str = "transaction_date",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> dict[str, Any]:
        allowed_sorts = {"transaction_date", "amount", "category", "description", "status"}
        if sort_by not in allowed_sorts:
            raise ValidationAppError(f"Cannot sort by '{sort_by}'.")
        if sort_dir not in ("asc", "desc"):
            raise ValidationAppError("Sort direction must be 'asc' or 'desc'.")
        page = max(1, page)
        page_size = min(max(1, page_size), 100)

        filters = self._uf(user_id)
        if category and category.lower() != "all":
            filters.append(
                FieldFilter(field="category", operator=FilterOperator.EQ, value=category)
            )
        if tx_type and tx_type.lower() != "all":
            filters.append(FieldFilter(field="type", operator=FilterOperator.EQ, value=tx_type))
        if search:
            filters.append(
                FieldFilter(field="description", operator=FilterOperator.ILIKE, value=search)
            )

        sort = [SortField(field=sort_by, descending=sort_dir == "desc")]
        items, total = await self.transactions.list(
            filters=filters, sort=sort, limit=page_size, offset=(page - 1) * page_size
        )

        # Every category the user owns, so the filter control lists real options
        # rather than a hardcoded enum. DISTINCT in the database rather than
        # pulling the whole ledger back to deduplicate it here.
        category_rows = await self.session.scalars(
            select(Transaction.category)
            .where(Transaction.user_id == user_id, Transaction.deleted_at.is_(None))
            .distinct()
            .order_by(Transaction.category)
        )
        categories = list(category_rows.all())

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, -(-total // page_size)),
            "categories": categories,
        }

    # --- Shared aggregation helpers ---
    async def _core_figures(self, user_id: uuid.UUID) -> dict[str, Any]:
        """The balance-sheet and cash-flow numbers every read model needs."""
        uf = self._uf(user_id)

        assets, _ = await self.assets.list(filters=uf, limit=1000)
        liabs, _ = await self.liabilities.list(filters=uf, limit=1000)
        loans_all, _ = await self.loans.list(filters=uf, limit=1000)
        incomes, _ = await self.incomes.list(filters=uf, limit=1000)
        expenses, _ = await self.expenses.list(filters=uf, limit=1000)
        investments, _ = await self.investments.list(filters=uf, limit=1000)
        txs, _ = await self.transactions.list(filters=uf, limit=10000)

        loans = [ln for ln in loans_all if ln.status == "ACTIVE"]

        # Investments are held in their own table but are still assets the user
        # owns: leaving them out understates net worth by the whole portfolio.
        investment_value = sum((i.current_value for i in investments), ZERO)
        total_assets = sum((a.current_value for a in assets), ZERO) + investment_value

        total_liabs = sum((liab.outstanding_balance for liab in liabs), ZERO)
        total_loans = sum((ln.outstanding_balance for ln in loans), ZERO)
        total_debt = total_liabs + total_loans

        monthly_income = sum((i.normalized_monthly_amount for i in incomes), ZERO)
        monthly_expense = sum((e.normalized_monthly_amount for e in expenses), ZERO)

        return {
            "assets": assets,
            "liabilities": liabs,
            "loans": loans,
            "incomes": incomes,
            "expenses": expenses,
            "investments": investments,
            "transactions": txs,
            "total_assets": total_assets,
            "total_debt": total_debt,
            "net_worth": total_assets - total_debt,
            "monthly_income": monthly_income,
            "monthly_expense": monthly_expense,
            # Drawable within days — the emergency-fund numerator.
            "liquid_assets": sum(
                (a.current_value for a in assets if a.type in LIQUID_ASSET_TYPES), ZERO
            ),
            # Spendable balance, excluding earmarked savings.
            "current_balance": sum(
                (a.current_value for a in assets if a.type in BALANCE_ASSET_TYPES), ZERO
            ),
            "investment_value": investment_value,
            "total_loan_emi": sum((ln.emi for ln in loans), ZERO),
        }

    @staticmethod
    def _monthly_flows(txs: list[Transaction]) -> dict[str, dict[str, Decimal]]:
        """Net cash flow bucketed by YYYY-MM, oldest key first."""
        flows: dict[str, dict[str, Decimal]] = {}
        for tx in txs:
            key = tx.transaction_date.strftime("%Y-%m")
            bucket = flows.setdefault(key, {"income": ZERO, "expense": ZERO})
            if tx.type in INFLOW_TX_TYPES:
                bucket["income"] += tx.amount
            elif tx.type in OUTFLOW_TX_TYPES:
                bucket["expense"] += tx.amount
        for bucket in flows.values():
            bucket["net"] = bucket["income"] - bucket["expense"]
        return dict(sorted(flows.items()))

    @staticmethod
    def _net_flow_since(txs: list[Transaction], since: Any) -> Decimal:
        total = ZERO
        for tx in txs:
            if tx.transaction_date < since:
                continue
            if tx.type in INFLOW_TX_TYPES:
                total += tx.amount
            elif tx.type in OUTFLOW_TX_TYPES:
                total -= tx.amount
        return total

    @staticmethod
    def _debt_paid_since(txs: list[Transaction], since: Any) -> Decimal:
        return sum(
            (t.amount for t in txs if t.type == "Loan Payment" and t.transaction_date >= since),
            ZERO,
        )

    # --- Dashboard Summary ---
    async def get_dashboard_summary(self, user_id: uuid.UUID) -> dict[str, Any]:
        core = await self._core_figures(user_id)
        txs: list[Transaction] = core["transactions"]

        now = utc_now()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_month = start_of_today.replace(day=1)

        monthly_income = core["monthly_income"]
        monthly_expense = core["monthly_expense"]
        monthly_savings = monthly_income - monthly_expense
        savings_rate = float(monthly_savings / monthly_income) if monthly_income > 0 else 0.0

        # Card movements come from the ledger: what actually moved money today
        # and across the current month.
        today_flow = self._net_flow_since(txs, start_of_today)
        month_flow = self._net_flow_since(txs, start_of_month)
        debt_today = self._debt_paid_since(txs, start_of_today)
        debt_month = self._debt_paid_since(txs, start_of_month)

        net_worth = core["net_worth"]
        net_worth_at_month_start = net_worth - month_flow
        liquid = core["liquid_assets"]
        total_debt = core["total_debt"]

        health = await self.get_health_score(user_id)
        health_today, health_month = await self._health_deltas(user_id, health["score"])

        emergency_months = (
            float(liquid / monthly_expense) if monthly_expense > 0 else (6.0 if liquid > 0 else 0.0)
        )

        recent_tx = sorted(txs, key=lambda t: t.transaction_date, reverse=True)[:5]
        goals, _ = await self.savings_goals.list(filters=self._uf(user_id), limit=100)

        return {
            "net_worth": net_worth,
            "total_assets": core["total_assets"],
            "liquid_assets": liquid,
            "total_liabilities": total_debt,
            "monthly_income": monthly_income,
            "monthly_expense": monthly_expense,
            "monthly_savings_rate": savings_rate,
            "recent_transactions": recent_tx,
            "savings_goals_progress": goals,
            "net_worth_trend": {
                "today": today_flow,
                "month": month_flow,
                "month_pct": _pct_change(net_worth, net_worth_at_month_start),
            },
            "liquid_trend": {
                "today": today_flow,
                "month": month_flow,
                "month_pct": _pct_change(liquid, liquid - month_flow),
            },
            # Debt falls as it is repaid, so a repayment is a negative movement.
            "debt_trend": {
                "today": -debt_today,
                "month": -debt_month,
                "month_pct": _pct_change(total_debt, total_debt + debt_month),
            },
            "health_trend": {
                "today": Decimal(str(round(health_today, 1))),
                "month": Decimal(str(round(health_month, 1))),
                "month_pct": health_month,
            },
            "monthly_overview": {
                "monthly_salary": next(
                    (
                        i.normalized_monthly_amount
                        for i in core["incomes"]
                        if i.source == SALARY_SOURCE
                    ),
                    ZERO,
                ),
                "other_monthly_income": next(
                    (
                        i.normalized_monthly_amount
                        for i in core["incomes"]
                        if i.source == OTHER_INCOME_SOURCE
                    ),
                    ZERO,
                ),
                "total_monthly_income": monthly_income,
                "monthly_expenses": monthly_expense,
                "monthly_savings": monthly_savings,
                "savings_rate": savings_rate * 100,
                "net_monthly_cash_flow": monthly_savings,
            },
            "financial_summary": {
                "current_balance": core["current_balance"],
                "monthly_savings": monthly_savings,
                "monthly_expenses": monthly_expense,
                "investment_value": core["investment_value"],
                "debt": total_debt,
                "emergency_fund_months": round(emergency_months, 1),
                "emergency_fund_status": self._emergency_status(emergency_months, liquid),
                "net_worth_trend": month_flow,
                "net_worth_trend_pct": _pct_change(net_worth, net_worth_at_month_start),
            },
            "has_data": bool(core["incomes"]),
        }

    @staticmethod
    def _emergency_status(months: float, liquid: Decimal) -> str:
        if liquid <= 0:
            return "Not Started"
        if months >= 6:
            return "Fully Funded"
        if months >= 3:
            return "Adequate"
        return "Building"

    async def _health_deltas(self, user_id: uuid.UUID, score: float) -> tuple[float, float]:
        """Score movement measured against previously recorded daily snapshots.

        Read-only by design. Snapshots are appended by ``save_financial_data``;
        writing them from this read path would make every dashboard load mutate
        the profile and take a write lock, which serialises concurrent reads.
        """
        profile = await self.get_profile(user_id)
        history: dict[str, float] = dict(
            (profile.financial_preferences or {}).get("health_history") or {}
        )
        if not history:
            return 0.0, 0.0

        today = utc_now().date().isoformat()
        month_start = utc_now().date().replace(day=1).isoformat()

        prior_days = sorted(d for d in history if d < today)
        month_days = sorted(d for d in history if d <= month_start)

        today_delta = score - history[prior_days[-1]] if prior_days else 0.0
        month_delta = score - history[month_days[-1]] if month_days else 0.0
        return today_delta, month_delta

    async def _record_health_snapshot(self, user_id: uuid.UUID) -> None:
        """Append today's score to the profile's history, one entry per day.

        Called from the write path so the health card can show a real
        day-over-day movement without any read turning into a write.
        """
        health = await self.get_health_score(user_id)
        profile = await self.get_profile(user_id)
        prefs = dict(profile.financial_preferences or {})
        history: dict[str, float] = dict(prefs.get("health_history") or {})

        history[utc_now().date().isoformat()] = round(health["score"], 2)
        # Keep about a quarter's worth: enough for the trend, small enough to store.
        for stale in sorted(history)[:-90]:
            history.pop(stale, None)

        prefs["health_history"] = history
        await self.profiles.update(profile, financial_preferences=prefs)

    # --- Analytics & Cash Flow ---
    async def get_analytics(self, user_id: uuid.UUID) -> dict[str, Any]:
        from app.core.filtering import FieldFilter, FilterOperator

        user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user_id))]
        tx_list, _ = await self.transactions.list(filters=user_filter, limit=10000)
        user_txs = tx_list

        monthly: dict[str, dict[str, Decimal]] = {}
        for tx in user_txs:
            month_str = tx.transaction_date.strftime("%Y-%m")
            if month_str not in monthly:
                monthly[month_str] = {"income": Decimal("0.00"), "expense": Decimal("0.00")}

            if tx.type in ("Income", "Refund"):
                monthly[month_str]["income"] += tx.amount
            elif tx.type in ("Expense", "Investment", "Loan Payment", "Insurance Premium"):
                monthly[month_str]["expense"] += tx.amount

        monthly_res = {}
        quarterly_res: dict[str, dict[str, Decimal]] = {}
        yearly_res: dict[str, dict[str, Decimal]] = {}

        for m, values in sorted(monthly.items()):
            inc, exp = values["income"], values["expense"]
            monthly_res[m] = {
                "income": inc,
                "expense": exp,
                "net_cash_flow": inc - exp,
            }

            year, month = m.split("-")
            quarter = (int(month) - 1) // 3 + 1
            q_key = f"{year}-Q{quarter}"
            if q_key not in quarterly_res:
                quarterly_res[q_key] = {"income": Decimal("0.00"), "expense": Decimal("0.00")}
            quarterly_res[q_key]["income"] += inc
            quarterly_res[q_key]["expense"] += exp

            if year not in yearly_res:
                yearly_res[year] = {"income": Decimal("0.00"), "expense": Decimal("0.00")}
            yearly_res[year]["income"] += inc
            yearly_res[year]["expense"] += exp

        quarterly_flow = {
            q: {
                "income": val["income"],
                "expense": val["expense"],
                "net_cash_flow": val["income"] - val["expense"],
            }
            for q, val in quarterly_res.items()
        }
        yearly_flow = {
            y: {
                "income": val["income"],
                "expense": val["expense"],
                "net_cash_flow": val["income"] - val["expense"],
            }
            for y, val in yearly_res.items()
        }

        from app.core.filtering import FieldFilter, FilterOperator

        user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user_id))]

        assets_list, _ = await self.assets.list(filters=user_filter, limit=1000)
        user_assets = assets_list
        asset_alloc: dict[str, Decimal] = {}
        for a in user_assets:
            asset_alloc[a.type] = asset_alloc.get(a.type, Decimal("0.00")) + a.current_value

        liabs_list, _ = await self.liabilities.list(filters=user_filter, limit=1000)
        user_liabs = liabs_list
        liab_alloc: dict[str, Decimal] = {}
        for liab in user_liabs:
            curr_val = liab_alloc.get(liab.type, Decimal("0.00"))
            liab_alloc[liab.type] = curr_val + liab.outstanding_balance

        loans_list, _ = await self.loans.list(filters=user_filter, limit=1000)
        user_loans = [ln for ln in loans_list if ln.status == "ACTIVE"]
        for ln in user_loans:
            liab_alloc[ln.type] = liab_alloc.get(ln.type, Decimal("0.00")) + ln.outstanding_balance

        return {
            "monthly_cash_flow": monthly_res,
            "quarterly_cash_flow": quarterly_flow,
            "yearly_cash_flow": yearly_flow,
            "asset_allocation": asset_alloc,
            "liability_allocation": liab_alloc,
        }

    # --- Financial Health Score Engine ---
    # Six weighted metrics, every one of them read from stored user data. A
    # metric with no data behind it is reported as unmeasured and its weight is
    # redistributed rather than scored as zero.
    def _score_savings_rate(self, income: Decimal, expense: Decimal) -> dict[str, Any]:
        rate = float((income - expense) / income) if income > 0 else 0.0
        score = _band(rate, [(-0.5, 0.0), (0.0, 30.0), (0.10, 60.0), (0.20, 85.0), (0.30, 100.0)])
        if rate >= 0.30:
            note = "Outstanding — you keep nearly a third of what you earn."
        elif rate >= 0.20:
            note = "Strong savings rate, comfortably above the 20% benchmark."
        elif rate >= 0.10:
            note = "Reasonable, but short of the 20% benchmark."
        elif rate >= 0:
            note = "Thin margin — most of your income is being spent."
        else:
            note = "You are spending more than you earn."
        return {
            "score": score,
            "raw_value": f"{rate * 100:.1f}%",
            "target": ">= 20%",
            "explanation": note,
            "_rate": rate,
        }

    def _score_dti(self, income: Decimal, emi: Decimal, liabilities: Decimal) -> dict[str, Any]:
        # Revolving balances carry no EMI, so charge the conventional 5% minimum.
        monthly_debt = emi + (liabilities * Decimal("0.05"))
        dti = float(monthly_debt / income) if income > 0 else 0.0
        score = _band(-dti, [(-1.0, 0.0), (-0.50, 40.0), (-0.36, 75.0), (-0.20, 100.0)])
        if dti == 0:
            note = "You carry no monthly debt service."
        elif dti <= 0.20:
            note = "Debt service is very comfortable."
        elif dti <= 0.36:
            note = "Debt service is within the 36% guideline."
        elif dti <= 0.50:
            note = "Debt service is above guideline and worth reducing."
        else:
            note = "Debt service is consuming an unsafe share of income."
        return {
            "score": score,
            "raw_value": f"{dti * 100:.1f}%",
            "target": "<= 36%",
            "explanation": note,
            "_dti": dti,
            "_monthly_debt": monthly_debt,
        }

    def _score_emergency_fund(self, liquid: Decimal, expense: Decimal) -> dict[str, Any]:
        if expense <= 0:
            months = 6.0 if liquid > 0 else 0.0
        else:
            months = float(liquid / expense)
        score = _band(months, [(0.0, 0.0), (1.0, 35.0), (3.0, 70.0), (6.0, 100.0)])
        if months >= 6:
            note = "Fully funded — six months or more of expenses covered."
        elif months >= 3:
            note = "Adequate buffer; six months is the goal."
        elif months > 0:
            note = "Buffer is thin for an unexpected loss of income."
        else:
            note = "No emergency reserve set aside."
        return {
            "score": score,
            "raw_value": f"{months:.1f} months",
            "target": ">= 6 months",
            "explanation": note,
            "_months": months,
        }

    def _score_expense_stability(self, flows: dict[str, dict[str, Decimal]]) -> dict[str, Any]:
        unmeasured = {
            "score": 0.0,
            "measurable": False,
            "raw_value": "Not enough history",
            "target": "<= 20% variance",
            "explanation": "Needs at least two months of recorded spending to measure.",
        }
        spends = [float(v["expense"]) for v in flows.values() if v["expense"] > 0]
        if len(spends) < 2:
            return unmeasured
        mean = statistics.fmean(spends)
        if mean == 0:
            return unmeasured
        # Coefficient of variation: spread relative to the size of the spend, so a
        # large steady budget is not penalised against a small erratic one.
        cv = statistics.pstdev(spends) / mean
        score = _band(-cv, [(-0.60, 0.0), (-0.35, 35.0), (-0.20, 70.0), (-0.08, 100.0)])
        if cv <= 0.08:
            note = "Spending is highly predictable month to month."
        elif cv <= 0.20:
            note = "Spending is fairly steady."
        elif cv <= 0.35:
            note = "Spending swings noticeably between months."
        else:
            note = "Spending is volatile, which makes planning difficult."
        return {
            "score": score,
            "raw_value": f"±{cv * 100:.0f}% variance",
            "target": "<= 20% variance",
            "explanation": note,
            "_cv": cv,
        }

    def _score_investment_ratio(self, investments: Decimal, assets: Decimal) -> dict[str, Any]:
        ratio = float(investments / assets) if assets > 0 else 0.0
        score = _band(ratio, [(0.0, 0.0), (0.15, 65.0), (0.30, 100.0)])
        if ratio >= 0.30:
            note = "A healthy share of your assets is invested for growth."
        elif ratio >= 0.15:
            note = "Some growth exposure, but below the recommended level."
        elif investments > 0:
            note = "Most of your assets sit idle in cash rather than growing."
        else:
            note = "No investments recorded — cash alone loses to inflation."
        return {
            "score": score,
            "raw_value": f"{ratio * 100:.1f}% of assets",
            "target": ">= 30% of assets",
            "explanation": note,
            "_ratio": ratio,
        }

    def _score_cash_flow_trend(self, flows: dict[str, dict[str, Decimal]]) -> dict[str, Any]:
        months = list(flows.items())
        if len(months) < 2:
            return {
                "score": 0.0,
                "measurable": False,
                "raw_value": "Not enough history",
                "target": "Positive and rising",
                "explanation": "Needs at least two months of transactions to measure.",
            }
        nets = [float(v["net"]) for _, v in months[-6:]]
        positive_months = sum(1 for n in nets if n >= 0)

        half = max(1, len(nets) // 2)
        recent_avg = statistics.fmean(nets[-half:])
        prior_avg = statistics.fmean(nets[:-half]) if len(nets) > half else nets[0]

        # Consistency of positive months carries most of the weight; direction of
        # travel supplies the rest.
        score = (positive_months / len(nets)) * 70.0
        if recent_avg >= prior_avg:
            score += 30.0
        elif prior_avg != 0:
            decline = (prior_avg - recent_avg) / abs(prior_avg)
            score += max(0.0, 30.0 * (1.0 - decline))
        score = max(0.0, min(100.0, score))

        direction = "Improving" if recent_avg >= prior_avg else "Declining"
        return {
            "score": score,
            "raw_value": direction,
            "target": "Positive and rising",
            "explanation": (
                f"{positive_months} of the last {len(nets)} months ended positive, "
                f"and the trend is {direction.lower()}."
            ),
            "_recent_avg": recent_avg,
            "_prior_avg": prior_avg,
        }

    def _build_insights(
        self,
        core: dict[str, Any],
        metrics: dict[str, dict[str, Any]],
        flows: dict[str, dict[str, Decimal]],
    ) -> list[str]:
        """Observations phrased from the user's own figures. No data, no insight."""
        insights: list[str] = []
        income = core["monthly_income"]
        expense = core["monthly_expense"]

        if income > 0:
            rate = metrics["savings_rate"]["_rate"]
            if rate >= 0:
                insights.append(
                    f"You save {rate * 100:.0f}% of your monthly income "
                    f"({_rupees(income - expense)} of {_rupees(income)})."
                )
            else:
                insights.append(
                    f"You spend {_rupees(expense - income)} more than you earn each month."
                )

        months = list(flows.items())
        if len(months) >= 2:
            prev_exp = float(months[-2][1]["expense"])
            curr_exp = float(months[-1][1]["expense"])
            if prev_exp > 0:
                change = (curr_exp - prev_exp) / prev_exp * 100
                if abs(change) >= 1:
                    verb = "increased" if change > 0 else "decreased"
                    insights.append(
                        f"Your expenses {verb} {abs(change):.0f}% compared to last month."
                    )

        if core["liquid_assets"] > 0 and expense > 0:
            months_covered = metrics["emergency_fund"]["_months"]
            insights.append(f"Emergency fund covers {months_covered:.1f} months of expenses.")
        elif core["liquid_assets"] <= 0:
            insights.append("No liquid savings recorded — an emergency fund is the first priority.")

        if core["total_assets"] > 0:
            inv_ratio = metrics["investment_ratio"]["_ratio"]
            if inv_ratio < 0.30:
                insights.append(
                    f"Investment allocation is {inv_ratio * 100:.0f}% of assets, below the "
                    "recommended 30% level."
                )
            else:
                insights.append(
                    f"Investments make up {inv_ratio * 100:.0f}% of your assets, at or above "
                    "the recommended level."
                )

        # Largest spending category, straight from the ledger.
        spend_by_cat: dict[str, Decimal] = {}
        for tx in core["transactions"]:
            if tx.type == "Expense":
                spend_by_cat[tx.category] = spend_by_cat.get(tx.category, ZERO) + tx.amount
        total_spend = sum(spend_by_cat.values(), ZERO)
        if total_spend > 0:
            top_cat, top_amt = max(spend_by_cat.items(), key=lambda kv: kv[1])
            share = float(top_amt / total_spend) * 100
            insights.append(f"{top_cat} expenses account for {share:.0f}% of total spending.")

        if core["total_debt"] > 0:
            dti = metrics["debt_to_income"]["_dti"]
            insights.append(
                f"Debt service takes {dti * 100:.0f}% of monthly income against "
                f"{_rupees(core['total_debt'])} outstanding."
            )
        elif income > 0:
            insights.append("You carry no outstanding debt.")

        return insights

    def _build_recommendations(
        self, core: dict[str, Any], metrics: dict[str, dict[str, Any]]
    ) -> list[str]:
        """Concrete next actions, each sized in rupees from the user's figures."""
        recs: list[str] = []
        income = core["monthly_income"]
        expense = core["monthly_expense"]

        if metrics["savings_rate"]["_rate"] < 0.20 and income > 0:
            gap = (income * Decimal("0.20")) - (income - expense)
            if gap > 0:
                recs.append(
                    f"Trim {_rupees(gap)} a month from expenses to reach a 20% savings rate."
                )

        if metrics["emergency_fund"]["_months"] < 6 and expense > 0:
            shortfall = (expense * 6) - core["liquid_assets"]
            if shortfall > 0:
                recs.append(
                    f"Build your emergency fund by {_rupees(shortfall)} to cover six months "
                    "of expenses."
                )

        if metrics["debt_to_income"]["_dti"] > 0.36 and income > 0:
            excess = metrics["debt_to_income"]["_monthly_debt"] - (income * Decimal("0.36"))
            recs.append(
                f"Reduce monthly debt payments by about {_rupees(excess)} to bring your "
                "debt-to-income ratio under 36%. Clear the highest-rate balance first."
            )

        if metrics["investment_ratio"]["_ratio"] < 0.30 and core["total_assets"] > 0:
            target = (core["total_assets"] * Decimal("0.30")) - core["investment_value"]
            if target > 0:
                recs.append(
                    f"Move {_rupees(target)} of idle cash into diversified investments to "
                    "reach a 30% growth allocation."
                )

        stability = metrics["expense_stability"]
        if stability.get("measurable", True) and stability["score"] < 60:
            recs.append(
                "Your month-to-month spending swings widely. Set category budgets to make "
                "cash flow predictable."
            )

        trend = metrics["cash_flow_trend"]
        if trend.get("measurable", True) and trend["score"] < 60:
            recs.append(
                "Recent months are trending toward negative cash flow. Review recurring "
                "subscriptions and variable spending before it erodes savings."
            )

        if not recs:
            recs.append(
                "Your fundamentals are sound. Keep contributions automatic and revisit your "
                "allocation each quarter."
            )
        return recs

    async def get_health_score(self, user_id: uuid.UUID) -> dict[str, Any]:
        core = await self._core_figures(user_id)
        flows = self._monthly_flows(core["transactions"])

        income = core["monthly_income"]
        expense = core["monthly_expense"]

        metrics = {
            "savings_rate": self._score_savings_rate(income, expense),
            "debt_to_income": self._score_dti(
                income,
                core["total_loan_emi"],
                sum((liab.outstanding_balance for liab in core["liabilities"]), ZERO),
            ),
            "emergency_fund": self._score_emergency_fund(core["liquid_assets"], expense),
            "expense_stability": self._score_expense_stability(flows),
            "investment_ratio": self._score_investment_ratio(
                core["investment_value"], core["total_assets"]
            ),
            "cash_flow_trend": self._score_cash_flow_trend(flows),
        }

        if not core["incomes"] and not core["assets"]:
            # Nothing entered yet: report that honestly instead of inventing a
            # score from empty inputs.
            return {
                "score": 0.0,
                "grade": "POOR",
                "grade_label": GRADE_LABELS["POOR"],
                "breakdown": {
                    key: {
                        "score": 0.0,
                        "weight": METRIC_WEIGHTS[key],
                        "raw_value": "No data",
                        "target": metric["target"],
                        "explanation": "Upload your financial data to calculate this metric.",
                    }
                    for key, metric in metrics.items()
                },
                "strengths": [],
                "areas_to_improve": [],
                "insights": [],
                "recommendations": [
                    "Upload your financial data to generate your health score and insights."
                ],
                "has_data": False,
            }

        # Renormalise across the metrics we can actually measure.
        measurable = {k: m for k, m in metrics.items() if m.get("measurable", True)}
        total_weight = sum(METRIC_WEIGHTS[k] for k in measurable)
        weighted = (
            sum(measurable[k]["score"] * METRIC_WEIGHTS[k] for k in measurable) / total_weight
            if total_weight
            else 0.0
        )
        score = round(max(0.0, min(100.0, weighted)), 1)

        if score >= 90:
            grade = "EXCELLENT"
        elif score >= 75:
            grade = "VERY_GOOD"
        elif score >= 60:
            grade = "GOOD"
        elif score >= 40:
            grade = "NEEDS_IMPROVEMENT"
        else:
            grade = "POOR"

        strengths = [
            f"{METRIC_LABELS[k]}: {m['raw_value']} — {m['explanation']}"
            for k, m in measurable.items()
            if m["score"] >= 75
        ]
        areas = [
            f"{METRIC_LABELS[k]}: {m['raw_value']} — {m['explanation']}"
            for k, m in measurable.items()
            if m["score"] < 60
        ]

        breakdown = {
            key: {
                "score": round(metric["score"], 1),
                # A metric we cannot measure carries no weight, and says so.
                "weight": METRIC_WEIGHTS[key] if metric.get("measurable", True) else 0.0,
                "raw_value": metric["raw_value"],
                "target": metric["target"],
                "explanation": metric["explanation"],
            }
            for key, metric in metrics.items()
        }

        return {
            "score": score,
            "grade": grade,
            "grade_label": GRADE_LABELS[grade],
            "breakdown": breakdown,
            "strengths": strengths,
            "areas_to_improve": areas,
            "insights": self._build_insights(core, metrics, flows),
            "recommendations": self._build_recommendations(core, metrics),
            "has_data": True,
        }
