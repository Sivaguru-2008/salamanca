from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- Financial Profile ---
class FinancialProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    currency: str
    country: str
    risk_profile: str
    financial_literacy_level: str
    personal_info: dict[str, Any] | None = None
    financial_preferences: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class FinancialProfileCreate(BaseModel):
    currency: str = Field(default="USD", max_length=3)
    country: str = Field(default="", max_length=100)
    risk_profile: str = Field(default="MEDIUM", max_length=50)
    financial_literacy_level: str = Field(default="BEGINNER", max_length=50)
    personal_info: dict[str, Any] | None = None
    financial_preferences: dict[str, Any] | None = None


class FinancialProfileUpdate(BaseModel):
    currency: str | None = Field(default=None, max_length=3)
    country: str | None = Field(default=None, max_length=100)
    risk_profile: str | None = Field(default=None, max_length=50)
    financial_literacy_level: str | None = Field(default=None, max_length=50)
    personal_info: dict[str, Any] | None = None
    financial_preferences: dict[str, Any] | None = None


# --- Income ---
class IncomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    source: str
    amount: Decimal
    currency: str
    frequency: str
    is_recurring: bool
    start_date: date
    end_date: date | None = None
    normalized_monthly_amount: Decimal
    created_at: datetime
    updated_at: datetime


class IncomeCreate(BaseModel):
    source: str = Field(..., max_length=100)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    frequency: str = Field(..., max_length=50)  # ONE_TIME, WEEKLY, BI_WEEKLY, MONTHLY, YEARLY
    is_recurring: bool = Field(default=True)
    start_date: date
    end_date: date | None = None


class IncomeUpdate(BaseModel):
    source: str | None = Field(default=None, max_length=100)
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, max_length=3)
    frequency: str | None = Field(default=None, max_length=50)
    is_recurring: bool | None = None
    start_date: date | None = None
    end_date: date | None = None


# --- Expense ---
class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    category: str
    expense_type: str
    amount: Decimal
    currency: str
    is_recurring: bool
    due_date: date | None = None
    normalized_monthly_amount: Decimal
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class ExpenseCreate(BaseModel):
    category: str = Field(..., max_length=100)  # Housing, Food, etc.
    expense_type: str = Field(..., max_length=50)  # FIXED, VARIABLE, RECURRING
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    is_recurring: bool = Field(default=False)
    due_date: date | None = None
    description: str | None = Field(default=None, max_length=255)


class ExpenseUpdate(BaseModel):
    category: str | None = Field(default=None, max_length=100)
    expense_type: str | None = Field(default=None, max_length=50)
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, max_length=3)
    is_recurring: bool | None = None
    due_date: date | None = None
    description: str | None = Field(default=None, max_length=255)


# --- Asset ---
class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: str
    current_value: Decimal
    currency: str
    details: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class AssetCreate(BaseModel):
    name: str = Field(..., max_length=255)
    type: str = Field(..., max_length=100)  # Cash, Bank accounts, FD, Gold, etc.
    current_value: Decimal = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=3)
    details: dict[str, Any] | None = None


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    type: str | None = Field(default=None, max_length=100)
    current_value: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    details: dict[str, Any] | None = None


# --- Liability ---
class LiabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: str
    outstanding_balance: Decimal
    currency: str
    details: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class LiabilityCreate(BaseModel):
    name: str = Field(..., max_length=255)
    type: str = Field(..., max_length=100)  # Credit Cards, Personal Loans, etc.
    outstanding_balance: Decimal = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=3)
    details: dict[str, Any] | None = None


class LiabilityUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    type: str | None = Field(default=None, max_length=100)
    outstanding_balance: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    details: dict[str, Any] | None = None


# --- Loan ---
class LoanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: str
    interest_rate: Decimal
    apr: Decimal
    processing_fees: Decimal
    emi: Decimal
    remaining_tenure: int
    outstanding_balance: Decimal
    collateral: str | None = None
    status: str
    payment_history: list[dict[str, Any]] | None = None
    created_at: datetime
    updated_at: datetime


class LoanCreate(BaseModel):
    name: str = Field(..., max_length=255)
    type: str = Field(..., max_length=100)
    interest_rate: Decimal = Field(..., ge=0)
    apr: Decimal = Field(..., ge=0)
    processing_fees: Decimal = Field(default=Decimal("0.00"), ge=0)
    emi: Decimal = Field(..., gt=0)
    remaining_tenure: int = Field(..., ge=0)
    outstanding_balance: Decimal = Field(..., ge=0)
    collateral: str | None = Field(default=None, max_length=255)
    status: str = Field(default="ACTIVE", max_length=50)
    payment_history: list[dict[str, Any]] | None = None


class LoanUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    type: str | None = Field(default=None, max_length=100)
    interest_rate: Decimal | None = Field(default=None, ge=0)
    apr: Decimal | None = Field(default=None, ge=0)
    processing_fees: Decimal | None = Field(default=None, ge=0)
    emi: Decimal | None = Field(default=None, gt=0)
    remaining_tenure: int | None = Field(default=None, ge=0)
    outstanding_balance: Decimal | None = Field(default=None, ge=0)
    collateral: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=50)
    payment_history: list[dict[str, Any]] | None = None


# --- Insurance ---
class InsuranceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    policy_number: str
    provider: str
    type: str
    coverage_amount: Decimal
    premium_amount: Decimal
    premium_frequency: str
    renewal_date: date
    beneficiaries: list[str] | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class InsuranceCreate(BaseModel):
    policy_number: str = Field(..., max_length=100)
    provider: str = Field(..., max_length=255)
    type: str = Field(..., max_length=100)
    coverage_amount: Decimal = Field(..., gt=0)
    premium_amount: Decimal = Field(..., gt=0)
    premium_frequency: str = Field(..., max_length=50)  # MONTHLY, QUARTERLY, HALF_YEARLY, YEARLY
    renewal_date: date
    beneficiaries: list[str] | None = None
    status: str = Field(default="ACTIVE", max_length=50)


class InsuranceUpdate(BaseModel):
    policy_number: str | None = Field(default=None, max_length=100)
    provider: str | None = Field(default=None, max_length=255)
    type: str | None = Field(default=None, max_length=100)
    coverage_amount: Decimal | None = Field(default=None, gt=0)
    premium_amount: Decimal | None = Field(default=None, gt=0)
    premium_frequency: str | None = Field(default=None, max_length=50)
    renewal_date: date | None = None
    beneficiaries: list[str] | None = None
    status: str | None = Field(default=None, max_length=50)


# --- Investment ---
class InvestmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: str
    amount_invested: Decimal
    current_value: Decimal
    quantity: Decimal | None = None
    purchase_price: Decimal | None = None
    ticker: str | None = None
    currency: str
    last_updated_at: datetime
    created_at: datetime
    updated_at: datetime


class InvestmentCreate(BaseModel):
    name: str = Field(..., max_length=255)
    type: str = Field(..., max_length=100)
    amount_invested: Decimal = Field(..., ge=0)
    current_value: Decimal = Field(..., ge=0)
    quantity: Decimal | None = Field(default=None, ge=0)
    purchase_price: Decimal | None = Field(default=None, ge=0)
    ticker: str | None = Field(default=None, max_length=50)
    currency: str = Field(default="USD", max_length=3)
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)


class InvestmentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    type: str | None = Field(default=None, max_length=100)
    amount_invested: Decimal | None = Field(default=None, ge=0)
    current_value: Decimal | None = Field(default=None, ge=0)
    quantity: Decimal | None = Field(default=None, ge=0)
    purchase_price: Decimal | None = Field(default=None, ge=0)
    ticker: str | None = Field(default=None, max_length=50)
    currency: str | None = Field(default=None, max_length=3)
    last_updated_at: datetime | None = None


# --- Savings Goal ---
class SavingsGoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    category: str
    target_amount: Decimal
    target_date: date
    current_progress: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime


class SavingsGoalCreate(BaseModel):
    name: str = Field(..., max_length=255)
    category: str = Field(..., max_length=100)
    target_amount: Decimal = Field(..., gt=0)
    target_date: date
    current_progress: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = Field(default="USD", max_length=3)


class SavingsGoalUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    target_amount: Decimal | None = Field(default=None, gt=0)
    target_date: date | None = None
    current_progress: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)


# --- Financial Document ---
class FinancialDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: str
    file_path: str
    uploaded_at: datetime
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class FinancialDocumentCreate(BaseModel):
    name: str = Field(..., max_length=255)
    type: str = Field(..., max_length=100)
    file_path: str = Field(..., max_length=512)
    metadata_json: dict[str, Any] | None = None


class FinancialDocumentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    type: str | None = Field(default=None, max_length=100)
    file_path: str | None = Field(default=None, max_length=512)
    metadata_json: dict[str, Any] | None = None


# --- Transaction ---
class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    category: str
    amount: Decimal
    currency: str
    transaction_date: datetime
    description: str | None = None
    reference_id: str | None = None
    created_at: datetime
    updated_at: datetime


class TransactionCreate(BaseModel):
    type: str = Field(..., max_length=50)  # Income, Expense, Transfer, etc.
    category: str = Field(..., max_length=100)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    transaction_date: datetime = Field(default_factory=datetime.utcnow)
    description: str | None = Field(default=None, max_length=255)
    reference_id: str | None = Field(default=None, max_length=100)


class TransactionUpdate(BaseModel):
    type: str | None = Field(default=None, max_length=50)
    category: str | None = Field(default=None, max_length=100)
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, max_length=3)
    transaction_date: datetime | None = None
    description: str | None = Field(default=None, max_length=255)
    reference_id: str | None = Field(default=None, max_length=100)


# --- Budget ---
class BudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    month: str
    monthly_budget: Decimal
    category_budgets: dict[str, float] | None = None
    budget_utilization: dict[str, float] | None = None
    budget_alerts: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class BudgetCreate(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")  # YYYY-MM
    monthly_budget: Decimal = Field(..., gt=0)
    category_budgets: dict[str, float] | None = None
    budget_alerts: dict[str, Any] | None = None


class BudgetUpdate(BaseModel):
    monthly_budget: Decimal | None = Field(default=None, gt=0)
    category_budgets: dict[str, float] | None = None
    budget_alerts: dict[str, Any] | None = None


# --- Financial Health Score ---
class HealthScoreMetricBreakdown(BaseModel):
    score: float
    raw_value: str
    target: str
    explanation: str


class HealthScoreRead(BaseModel):
    score: float
    grade: str
    breakdown: dict[str, HealthScoreMetricBreakdown]
    recommendations: list[str]


# --- Dashboard Summary ---
class DashboardSummaryRead(BaseModel):
    net_worth: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    monthly_income: Decimal
    monthly_expense: Decimal
    monthly_savings_rate: float
    recent_transactions: list[TransactionRead]
    savings_goals_progress: list[SavingsGoalRead]


# --- Analytics Summary ---
class CashFlowReport(BaseModel):
    income: Decimal
    expense: Decimal
    net_cash_flow: Decimal


class AnalyticsRead(BaseModel):
    monthly_cash_flow: dict[str, CashFlowReport]  # Key: "YYYY-MM"
    quarterly_cash_flow: dict[str, CashFlowReport]  # Key: "YYYY-Q1", etc.
    yearly_cash_flow: dict[str, CashFlowReport]  # Key: "YYYY"
    asset_allocation: dict[str, Decimal]
    liability_allocation: dict[str, Decimal]
