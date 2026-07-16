from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationAppError
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
                currency="USD",
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
            currency=data.get("currency", "USD"),
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
            currency=data.get("currency", "USD"),
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
            currency=data.get("currency", "USD"),
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
            currency=data.get("currency", "USD"),
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
            currency=data.get("currency", "USD"),
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
            currency=data.get("currency", "USD"),
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
            currency=data.get("currency", "USD"),
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
                currency=data.get("currency", "USD"),
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
        all_expenses, _ = await self.expenses.list(filters=user_filter, limit=1000, include_deleted=False)
        user_expenses = [
            e
            for e in all_expenses
            if e.created_at.strftime("%Y-%m") == month_str
        ]

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

    # --- Dashboard Summary ---
    async def get_dashboard_summary(self, user_id: uuid.UUID) -> dict[str, Any]:
        from app.core.filtering import FieldFilter, FilterOperator
        user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user_id))]

        assets_list, _ = await self.assets.list(filters=user_filter, limit=1000)
        user_assets = assets_list
        total_assets = sum((a.current_value for a in user_assets), Decimal("0.00"))

        liabs_list, _ = await self.liabilities.list(filters=user_filter, limit=1000)
        user_liabs = liabs_list
        total_liabs = sum((liab.outstanding_balance for liab in user_liabs), Decimal("0.00"))

        loans_list, _ = await self.loans.list(filters=user_filter, limit=1000)
        user_loans = [ln for ln in loans_list if ln.status == "ACTIVE"]
        total_loans = sum((ln.outstanding_balance for ln in user_loans), Decimal("0.00"))

        net_worth = total_assets - (total_liabs + total_loans)

        incomes_list, _ = await self.incomes.list(filters=user_filter, limit=1000)
        user_incomes = incomes_list
        monthly_income = sum((i.normalized_monthly_amount for i in user_incomes), Decimal("0.00"))

        expenses_list, _ = await self.expenses.list(filters=user_filter, limit=1000)
        user_expenses = expenses_list
        monthly_expense = sum((e.normalized_monthly_amount for e in user_expenses), Decimal("0.00"))

        savings_rate = 0.0
        if monthly_income > 0:
            savings_rate = float((monthly_income - monthly_expense) / monthly_income)

        tx_list, _ = await self.transactions.list(filters=user_filter, limit=5, sort=[])
        user_tx = tx_list

        sg_list, _ = await self.savings_goals.list(filters=user_filter, limit=100)
        user_sg = sg_list

        return {
            "net_worth": net_worth,
            "total_assets": total_assets,
            "total_liabilities": total_liabs + total_loans,
            "monthly_income": monthly_income,
            "monthly_expense": monthly_expense,
            "monthly_savings_rate": savings_rate,
            "recent_transactions": user_tx,
            "savings_goals_progress": user_sg,
        }

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
    async def get_health_score(self, user_id: uuid.UUID) -> dict[str, Any]:
        from app.core.filtering import FieldFilter, FilterOperator
        user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user_id))]

        incomes_list, _ = await self.incomes.list(filters=user_filter, limit=1000)
        user_incomes = incomes_list
        monthly_income = sum((i.normalized_monthly_amount for i in user_incomes), Decimal("0.00"))
        if monthly_income == 0:
            monthly_income = Decimal("1.00")

        expenses_list, _ = await self.expenses.list(filters=user_filter, limit=1000)
        user_expenses = expenses_list
        monthly_expense = sum((e.normalized_monthly_amount for e in user_expenses), Decimal("0.00"))

        loans_list, _ = await self.loans.list(filters=user_filter, limit=1000)
        user_loans = [ln for ln in loans_list if ln.status == "ACTIVE"]
        total_loan_emi = sum((ln.emi for ln in user_loans), Decimal("0.00"))

        liabs_list, _ = await self.liabilities.list(filters=user_filter, limit=1000)
        user_liabs = liabs_list
        total_liab_bal = sum((liab.outstanding_balance for liab in user_liabs), Decimal("0.00"))

        assets_list, _ = await self.assets.list(filters=user_filter, limit=1000)
        user_assets = assets_list
        liquid_assets = sum(
            (a.current_value for a in user_assets if a.type in ("Cash", "Bank accounts")),
            Decimal("0.00"),
        )

        insurances_list, _ = await self.insurances.list(filters=user_filter, limit=1000)
        user_ins = [
            ins for ins in insurances_list if ins.status == "ACTIVE"
        ]

        tx_list, _ = await self.transactions.list(filters=user_filter, limit=1000)
        thirty_days_ago = utc_now() - timedelta(days=30)
        recent_investments = sum(
            (
                t.amount
                for t in tx_list
                if t.type == "Investment"
                and t.transaction_date >= thirty_days_ago
            ),
            Decimal("0.00"),
        )

        breakdown = {}
        recommendations = []

        # Metric A: Savings Rate (Weight: 25%)
        savings_rate = (monthly_income - monthly_expense) / monthly_income
        if savings_rate >= Decimal("0.20"):
            rate_score = 100
        elif savings_rate >= Decimal("0.10"):
            rate_score = 70
        elif savings_rate >= Decimal("0.00"):
            rate_score = 40
        else:
            rate_score = 0

        breakdown["savings_rate"] = {
            "score": float(rate_score),
            "raw_value": f"{float(savings_rate) * 100:.1f}%",
            "target": ">= 20.0%",
            "explanation": (
                "Excellent savings rate."
                if rate_score == 100
                else (
                    "Healthy savings rate."
                    if rate_score == 70
                    else (
                        "Low savings rate, try to reduce variable expenses."
                        if rate_score == 40
                        else "Negative savings rate! You are spending more than you earn."
                    )
                )
            ),
        }
        if rate_score < 70:
            recommendations.append(
                "Your savings rate is below the recommended 10-20% threshold. "
                "Try to analyze and cut down on variable expenses."
            )

        # Metric B: Debt-to-Income (DTI) Ratio (Weight: 25%)
        monthly_debt_pay = total_loan_emi + (total_liab_bal * Decimal("0.05"))
        dti = monthly_debt_pay / monthly_income
        if dti == 0 or dti <= Decimal("0.36"):
            dti_score = 100
        elif dti <= Decimal("0.50"):
            dti_score = 60
        else:
            dti_score = 20

        breakdown["debt_to_income"] = {
            "score": float(dti_score),
            "raw_value": f"{float(dti) * 100:.1f}%",
            "target": "<= 36.0%",
            "explanation": (
                "Excellent! Very low or no monthly debt service."
                if dti_score == 100
                else (
                    "Moderate debt levels, manage outstanding balances carefully."
                    if dti_score == 60
                    else "High debt service ratio! Focus on paydown strategies."
                )
            ),
        }
        if dti_score < 100:
            recommendations.append(
                "Your debt-to-income ratio is high. "
                "Focus on paying down high-interest liabilities first (e.g. Credit Cards, BNPL)."
            )

        # Metric C: Emergency Fund Coverage (Weight: 20%)
        month_exp_divisor = monthly_expense if monthly_expense > 0 else Decimal("1000.00")
        emergency_months = liquid_assets / month_exp_divisor
        if emergency_months >= 6:
            em_score = 100
        elif emergency_months >= 3:
            em_score = 85
        elif emergency_months >= 1:
            em_score = 50
        else:
            em_score = 10

        breakdown["emergency_fund"] = {
            "score": float(em_score),
            "raw_value": f"{float(emergency_months):.1f} months",
            "target": ">= 6.0 months",
            "explanation": (
                "Excellent emergency fund reserves."
                if em_score == 100
                else (
                    "Good coverage of essential expenses."
                    if em_score == 85
                    else (
                        "Low emergency buffer. Recommended is 3-6 months."
                        if em_score == 50
                        else "Dangerously low emergency reserves!"
                    )
                )
            ),
        }
        if em_score < 85:
            recommendations.append(
                "Your emergency fund covers less than 3 months of expenses. "
                "Set aside a portion of your income into high-yield bank accounts."
            )

        # Metric D: Investment Ratio (Weight: 15%)
        inv_ratio = recent_investments / monthly_income
        if inv_ratio >= Decimal("0.15"):
            inv_score = 100
        elif inv_ratio >= Decimal("0.05"):
            inv_score = 60
        else:
            inv_score = 20

        breakdown["investment_ratio"] = {
            "score": float(inv_score),
            "raw_value": f"{float(inv_ratio) * 100:.1f}%",
            "target": ">= 15.0%",
            "explanation": (
                "Excellent rate of investment."
                if inv_score == 100
                else (
                    "Moderate investing rate."
                    if inv_score == 60
                    else "Very low investment rate, consider automated investing plans."
                )
            ),
        }
        if inv_score < 60:
            recommendations.append(
                "You are investing less than 15% of your income. "
                "Consider setting up automatic monthly contributions to mutual funds or ETFs."
            )

        # Metric E: Insurance Coverage (Weight: 15%)
        has_health = any(ins.type.upper() == "HEALTH" for ins in user_ins)
        has_life = any(ins.type.upper() == "LIFE" for ins in user_ins)

        if has_health and has_life:
            ins_score = 100
        elif has_health or has_life:
            ins_score = 50
        else:
            ins_score = 0

        breakdown["insurance_coverage"] = {
            "score": float(ins_score),
            "raw_value": (
                "Health & Life"
                if (has_health and has_life)
                else "Health Only" if has_health else "Life Only" if has_life else "None"
            ),
            "target": "Health & Life Active",
            "explanation": (
                "Well covered."
                if ins_score == 100
                else (
                    "Partial insurance coverage, missing life or health policies."
                    if ins_score == 50
                    else "No active insurance policies detected!"
                )
            ),
        }
        if ins_score < 100:
            recommendations.append(
                "Ensure you have active Health and Life insurance policies to protect "
                "yourself and your dependents from unexpected events."
            )

        weighted_score = (
            (rate_score * 0.25)
            + (dti_score * 0.25)
            + (em_score * 0.20)
            + (inv_score * 0.15)
            + (ins_score * 0.15)
        )

        grade = "POOR"
        if weighted_score >= 85:
            grade = "EXCELLENT"
        elif weighted_score >= 70:
            grade = "GOOD"
        elif weighted_score >= 50:
            grade = "FAIR"

        if weighted_score >= 85:
            recommendations.append(
                "Keep up the excellent work! Continue optimizing your portfolio "
                "and monitoring your expenses."
            )

        return {
            "score": float(weighted_score),
            "grade": grade,
            "breakdown": breakdown,
            "recommendations": recommendations,
        }
