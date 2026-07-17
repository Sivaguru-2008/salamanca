from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.api.v1.schemas.common import PROBLEM_RESPONSES
from app.api.v1.schemas.financial import (
    AnalyticsRead,
    AssetCreate,
    AssetRead,
    AssetUpdate,
    BudgetCreate,
    BudgetRead,
    BudgetUpdate,
    DashboardSummaryRead,
    ExpenseCreate,
    ExpenseRead,
    ExpenseUpdate,
    FinancialDataRead,
    FinancialDataWrite,
    FinancialDocumentCreate,
    FinancialDocumentRead,
    FinancialDocumentUpdate,
    FinancialProfileRead,
    FinancialProfileUpdate,
    HealthScoreRead,
    IncomeCreate,
    IncomeRead,
    IncomeUpdate,
    InsuranceCreate,
    InsuranceRead,
    InsuranceUpdate,
    InvestmentCreate,
    InvestmentRead,
    InvestmentUpdate,
    LiabilityCreate,
    LiabilityRead,
    LiabilityUpdate,
    LoanCreate,
    LoanRead,
    LoanUpdate,
    SavingsGoalCreate,
    SavingsGoalRead,
    SavingsGoalUpdate,
    TransactionCreate,
    TransactionPage,
    TransactionRead,
    TransactionUpdate,
)
from app.core.errors import NotFoundError
from app.domain.financial.service import FinancialService
from app.utils.datetime import utc_now

router = APIRouter(prefix="/financial", tags=["financial"], responses=PROBLEM_RESPONSES)


# --- Financial Profile ---
@router.get("/profile", response_model=FinancialProfileRead, summary="Get user financial profile")
async def get_profile(user: CurrentUser, db: DbSession) -> FinancialProfileRead:
    profile = await FinancialService(db).get_profile(user.id)
    return FinancialProfileRead.model_validate(profile)


@router.put(
    "/profile", response_model=FinancialProfileRead, summary="Update user financial profile"
)
async def update_profile(
    payload: FinancialProfileUpdate, user: CurrentUser, db: DbSession
) -> FinancialProfileRead:
    profile = await FinancialService(db).update_profile(
        user.id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return FinancialProfileRead.model_validate(profile)


# --- Financial Data Upload ---
@router.get(
    "/financial-data",
    response_model=FinancialDataRead,
    summary="Get the user's stored monthly financial figures",
)
async def get_financial_data(user: CurrentUser, db: DbSession) -> FinancialDataRead:
    data = await FinancialService(db).get_financial_data(user.id)
    return FinancialDataRead.model_validate(data)


@router.put(
    "/financial-data",
    response_model=FinancialDataRead,
    summary="Upload or update the user's monthly financial figures",
)
async def save_financial_data(
    payload: FinancialDataWrite, user: CurrentUser, db: DbSession
) -> FinancialDataRead:
    data = await FinancialService(db).save_financial_data(
        user.id, payload.model_dump(), actor_id=user.id
    )
    return FinancialDataRead.model_validate(data)


# --- Incomes ---
@router.get("/incomes", response_model=list[IncomeRead], summary="List user incomes")
async def list_incomes(user: CurrentUser, db: DbSession) -> list[IncomeRead]:
    from app.core.filtering import FieldFilter, FilterOperator

    user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user.id))]
    incomes, _ = await FinancialService(db).incomes.list(filters=user_filter, limit=1000)
    return [IncomeRead.model_validate(i) for i in incomes]


@router.post(
    "/incomes",
    response_model=IncomeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create income",
)
async def create_income(payload: IncomeCreate, user: CurrentUser, db: DbSession) -> IncomeRead:
    income = await FinancialService(db).create_income(
        user.id, payload.model_dump(), actor_id=user.id
    )
    return IncomeRead.model_validate(income)


@router.get("/incomes/{income_id}", response_model=IncomeRead, summary="Get income detail")
async def get_income(income_id: uuid.UUID, user: CurrentUser, db: DbSession) -> IncomeRead:
    income = await FinancialService(db).incomes.get(income_id)
    if income is None or income.user_id != user.id:
        raise NotFoundError("Income not found.")
    return IncomeRead.model_validate(income)


@router.put("/incomes/{income_id}", response_model=IncomeRead, summary="Update income")
async def update_income(
    income_id: uuid.UUID, payload: IncomeUpdate, user: CurrentUser, db: DbSession
) -> IncomeRead:
    income = await FinancialService(db).update_income(
        user.id, income_id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return IncomeRead.model_validate(income)


@router.delete(
    "/incomes/{income_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete income"
)
async def delete_income(income_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await FinancialService(db).delete_income(user.id, income_id)


# --- Expenses ---
@router.get("/expenses", response_model=list[ExpenseRead], summary="List user expenses")
async def list_expenses(user: CurrentUser, db: DbSession) -> list[ExpenseRead]:
    from app.core.filtering import FieldFilter, FilterOperator

    user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user.id))]
    expenses, _ = await FinancialService(db).expenses.list(filters=user_filter, limit=1000)
    return [ExpenseRead.model_validate(e) for e in expenses]


@router.post(
    "/expenses",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create expense",
)
async def create_expense(payload: ExpenseCreate, user: CurrentUser, db: DbSession) -> ExpenseRead:
    expense = await FinancialService(db).create_expense(
        user.id, payload.model_dump(), actor_id=user.id
    )
    return ExpenseRead.model_validate(expense)


@router.get("/expenses/{expense_id}", response_model=ExpenseRead, summary="Get expense detail")
async def get_expense(expense_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ExpenseRead:
    expense = await FinancialService(db).expenses.get(expense_id)
    if expense is None or expense.user_id != user.id:
        raise NotFoundError("Expense not found.")
    return ExpenseRead.model_validate(expense)


@router.put("/expenses/{expense_id}", response_model=ExpenseRead, summary="Update expense")
async def update_expense(
    expense_id: uuid.UUID, payload: ExpenseUpdate, user: CurrentUser, db: DbSession
) -> ExpenseRead:
    expense = await FinancialService(db).update_expense(
        user.id, expense_id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return ExpenseRead.model_validate(expense)


@router.delete(
    "/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete expense"
)
async def delete_expense(expense_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await FinancialService(db).delete_expense(user.id, expense_id)


# --- Assets ---
@router.get("/assets", response_model=list[AssetRead], summary="List user assets")
async def list_assets(user: CurrentUser, db: DbSession) -> list[AssetRead]:
    from app.core.filtering import FieldFilter, FilterOperator

    user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user.id))]
    assets, _ = await FinancialService(db).assets.list(filters=user_filter, limit=1000)
    return [AssetRead.model_validate(a) for a in assets]


@router.post(
    "/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED, summary="Create asset"
)
async def create_asset(payload: AssetCreate, user: CurrentUser, db: DbSession) -> AssetRead:
    asset = await FinancialService(db).create_asset(user.id, payload.model_dump(), actor_id=user.id)
    return AssetRead.model_validate(asset)


@router.get("/assets/{asset_id}", response_model=AssetRead, summary="Get asset detail")
async def get_asset(asset_id: uuid.UUID, user: CurrentUser, db: DbSession) -> AssetRead:
    asset = await FinancialService(db).assets.get(asset_id)
    if asset is None or asset.user_id != user.id:
        raise NotFoundError("Asset not found.")
    return AssetRead.model_validate(asset)


@router.put("/assets/{asset_id}", response_model=AssetRead, summary="Update asset")
async def update_asset(
    asset_id: uuid.UUID, payload: AssetUpdate, user: CurrentUser, db: DbSession
) -> AssetRead:
    asset = await FinancialService(db).update_asset(
        user.id, asset_id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return AssetRead.model_validate(asset)


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete asset")
async def delete_asset(asset_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await FinancialService(db).delete_asset(user.id, asset_id)


# --- Liabilities ---
@router.get("/liabilities", response_model=list[LiabilityRead], summary="List user liabilities")
async def list_liabilities(user: CurrentUser, db: DbSession) -> list[LiabilityRead]:
    from app.core.filtering import FieldFilter, FilterOperator

    user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user.id))]
    liabs, _ = await FinancialService(db).liabilities.list(filters=user_filter, limit=1000)
    return [LiabilityRead.model_validate(liab) for liab in liabs]


@router.post(
    "/liabilities",
    response_model=LiabilityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create liability",
)
async def create_liability(
    payload: LiabilityCreate, user: CurrentUser, db: DbSession
) -> LiabilityRead:
    liability = await FinancialService(db).create_liability(
        user.id, payload.model_dump(), actor_id=user.id
    )
    return LiabilityRead.model_validate(liability)


@router.get(
    "/liabilities/{liability_id}", response_model=LiabilityRead, summary="Get liability detail"
)
async def get_liability(liability_id: uuid.UUID, user: CurrentUser, db: DbSession) -> LiabilityRead:
    liability = await FinancialService(db).liabilities.get(liability_id)
    if liability is None or liability.user_id != user.id:
        raise NotFoundError("Liability not found.")
    return LiabilityRead.model_validate(liability)


@router.put("/liabilities/{liability_id}", response_model=LiabilityRead, summary="Update liability")
async def update_liability(
    liability_id: uuid.UUID, payload: LiabilityUpdate, user: CurrentUser, db: DbSession
) -> LiabilityRead:
    liability = await FinancialService(db).update_liability(
        user.id, liability_id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return LiabilityRead.model_validate(liability)


@router.delete(
    "/liabilities/{liability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete liability",
)
async def delete_liability(liability_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await FinancialService(db).delete_liability(user.id, liability_id)


# --- Loans ---
@router.get("/loans", response_model=list[LoanRead], summary="List user loans")
async def list_loans(user: CurrentUser, db: DbSession) -> list[LoanRead]:
    from app.core.filtering import FieldFilter, FilterOperator

    user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user.id))]
    loans, _ = await FinancialService(db).loans.list(filters=user_filter, limit=1000)
    return [LoanRead.model_validate(ln) for ln in loans]


@router.post(
    "/loans", response_model=LoanRead, status_code=status.HTTP_201_CREATED, summary="Create loan"
)
async def create_loan(payload: LoanCreate, user: CurrentUser, db: DbSession) -> LoanRead:
    loan = await FinancialService(db).create_loan(user.id, payload.model_dump(), actor_id=user.id)
    return LoanRead.model_validate(loan)


@router.get("/loans/{loan_id}", response_model=LoanRead, summary="Get loan detail")
async def get_loan(loan_id: uuid.UUID, user: CurrentUser, db: DbSession) -> LoanRead:
    loan = await FinancialService(db).loans.get(loan_id)
    if loan is None or loan.user_id != user.id:
        raise NotFoundError("Loan not found.")
    return LoanRead.model_validate(loan)


@router.put("/loans/{loan_id}", response_model=LoanRead, summary="Update loan")
async def update_loan(
    loan_id: uuid.UUID, payload: LoanUpdate, user: CurrentUser, db: DbSession
) -> LoanRead:
    loan = await FinancialService(db).update_loan(
        user.id, loan_id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return LoanRead.model_validate(loan)


@router.delete("/loans/{loan_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete loan")
async def delete_loan(loan_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await FinancialService(db).delete_loan(user.id, loan_id)


# --- Insurances ---
@router.get("/insurances", response_model=list[InsuranceRead], summary="List user insurances")
async def list_insurances(user: CurrentUser, db: DbSession) -> list[InsuranceRead]:
    from app.core.filtering import FieldFilter, FilterOperator

    user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user.id))]
    ins, _ = await FinancialService(db).insurances.list(filters=user_filter, limit=1000)
    return [InsuranceRead.model_validate(i) for i in ins]


@router.post(
    "/insurances",
    response_model=InsuranceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create insurance",
)
async def create_insurance(
    payload: InsuranceCreate, user: CurrentUser, db: DbSession
) -> InsuranceRead:
    insurance = await FinancialService(db).create_insurance(
        user.id, payload.model_dump(), actor_id=user.id
    )
    return InsuranceRead.model_validate(insurance)


@router.get(
    "/insurances/{insurance_id}", response_model=InsuranceRead, summary="Get insurance detail"
)
async def get_insurance(insurance_id: uuid.UUID, user: CurrentUser, db: DbSession) -> InsuranceRead:
    insurance = await FinancialService(db).insurances.get(insurance_id)
    if insurance is None or insurance.user_id != user.id:
        raise NotFoundError("Insurance not found.")
    return InsuranceRead.model_validate(insurance)


@router.put("/insurances/{insurance_id}", response_model=InsuranceRead, summary="Update insurance")
async def update_insurance(
    insurance_id: uuid.UUID, payload: InsuranceUpdate, user: CurrentUser, db: DbSession
) -> InsuranceRead:
    insurance = await FinancialService(db).update_insurance(
        user.id, insurance_id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return InsuranceRead.model_validate(insurance)


@router.delete(
    "/insurances/{insurance_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete insurance"
)
async def delete_insurance(insurance_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await FinancialService(db).delete_insurance(user.id, insurance_id)


# --- Investments ---
@router.get("/investments", response_model=list[InvestmentRead], summary="List user investments")
async def list_investments(user: CurrentUser, db: DbSession) -> list[InvestmentRead]:
    from app.core.filtering import FieldFilter, FilterOperator

    user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user.id))]
    invs, _ = await FinancialService(db).investments.list(filters=user_filter, limit=1000)
    return [InvestmentRead.model_validate(i) for i in invs]


@router.post(
    "/investments",
    response_model=InvestmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create investment",
)
async def create_investment(
    payload: InvestmentCreate, user: CurrentUser, db: DbSession
) -> InvestmentRead:
    investment = await FinancialService(db).create_investment(
        user.id, payload.model_dump(), actor_id=user.id
    )
    return InvestmentRead.model_validate(investment)


@router.get(
    "/investments/{investment_id}", response_model=InvestmentRead, summary="Get investment detail"
)
async def get_investment(
    investment_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> InvestmentRead:
    investment = await FinancialService(db).investments.get(investment_id)
    if investment is None or investment.user_id != user.id:
        raise NotFoundError("Investment not found.")
    return InvestmentRead.model_validate(investment)


@router.put(
    "/investments/{investment_id}", response_model=InvestmentRead, summary="Update investment"
)
async def update_investment(
    investment_id: uuid.UUID, payload: InvestmentUpdate, user: CurrentUser, db: DbSession
) -> InvestmentRead:
    investment = await FinancialService(db).update_investment(
        user.id, investment_id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return InvestmentRead.model_validate(investment)


@router.delete(
    "/investments/{investment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete investment",
)
async def delete_investment(investment_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await FinancialService(db).delete_investment(user.id, investment_id)


# --- Savings Goals ---
@router.get(
    "/savings-goals", response_model=list[SavingsGoalRead], summary="List user savings goals"
)
async def list_savings_goals(user: CurrentUser, db: DbSession) -> list[SavingsGoalRead]:
    from app.core.filtering import FieldFilter, FilterOperator

    user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user.id))]
    goals, _ = await FinancialService(db).savings_goals.list(filters=user_filter, limit=1000)
    return [SavingsGoalRead.model_validate(g) for g in goals]


@router.post(
    "/savings-goals",
    response_model=SavingsGoalRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create savings goal",
)
async def create_savings_goal(
    payload: SavingsGoalCreate, user: CurrentUser, db: DbSession
) -> SavingsGoalRead:
    goal = await FinancialService(db).create_savings_goal(
        user.id, payload.model_dump(), actor_id=user.id
    )
    return SavingsGoalRead.model_validate(goal)


@router.get(
    "/savings-goals/{goal_id}", response_model=SavingsGoalRead, summary="Get savings goal detail"
)
async def get_savings_goal(goal_id: uuid.UUID, user: CurrentUser, db: DbSession) -> SavingsGoalRead:
    goal = await FinancialService(db).savings_goals.get(goal_id)
    if goal is None or goal.user_id != user.id:
        raise NotFoundError("Savings goal not found.")
    return SavingsGoalRead.model_validate(goal)


@router.put(
    "/savings-goals/{goal_id}", response_model=SavingsGoalRead, summary="Update savings goal"
)
async def update_savings_goal(
    goal_id: uuid.UUID, payload: SavingsGoalUpdate, user: CurrentUser, db: DbSession
) -> SavingsGoalRead:
    goal = await FinancialService(db).update_savings_goal(
        user.id, goal_id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return SavingsGoalRead.model_validate(goal)


@router.delete(
    "/savings-goals/{goal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete savings goal",
)
async def delete_savings_goal(goal_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await FinancialService(db).delete_savings_goal(user.id, goal_id)


# --- Financial Documents ---
@router.get(
    "/documents",
    response_model=list[FinancialDocumentRead],
    summary="List user financial documents",
)
async def list_documents(user: CurrentUser, db: DbSession) -> list[FinancialDocumentRead]:
    from app.core.filtering import FieldFilter, FilterOperator

    user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user.id))]
    docs, _ = await FinancialService(db).documents.list(filters=user_filter, limit=1000)
    return [FinancialDocumentRead.model_validate(d) for d in docs]


@router.post(
    "/documents",
    response_model=FinancialDocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create document metadata",
)
async def create_document(
    payload: FinancialDocumentCreate, user: CurrentUser, db: DbSession
) -> FinancialDocumentRead:
    doc = await FinancialService(db).create_document(
        user.id, payload.model_dump(), actor_id=user.id
    )
    return FinancialDocumentRead.model_validate(doc)


@router.get(
    "/documents/{doc_id}",
    response_model=FinancialDocumentRead,
    summary="Get document metadata detail",
)
async def get_document(
    doc_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> FinancialDocumentRead:
    doc = await FinancialService(db).documents.get(doc_id)
    if doc is None or doc.user_id != user.id:
        raise NotFoundError("Financial document not found.")
    return FinancialDocumentRead.model_validate(doc)


@router.put(
    "/documents/{doc_id}", response_model=FinancialDocumentRead, summary="Update document metadata"
)
async def update_document(
    doc_id: uuid.UUID, payload: FinancialDocumentUpdate, user: CurrentUser, db: DbSession
) -> FinancialDocumentRead:
    doc = await FinancialService(db).update_document(
        user.id, doc_id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return FinancialDocumentRead.model_validate(doc)


@router.delete(
    "/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document metadata",
)
async def delete_document(doc_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await FinancialService(db).delete_document(user.id, doc_id)


# --- Transactions ---
@router.get("/transactions", response_model=list[TransactionRead], summary="List user transactions")
async def list_transactions(user: CurrentUser, db: DbSession) -> list[TransactionRead]:
    from app.core.filtering import FieldFilter, FilterOperator

    user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user.id))]
    txs, _ = await FinancialService(db).transactions.list(filters=user_filter, limit=1000)
    return [TransactionRead.model_validate(t) for t in txs]


@router.post(
    "/transactions",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create transaction",
)
async def create_transaction(
    payload: TransactionCreate, user: CurrentUser, db: DbSession
) -> TransactionRead:
    tx = await FinancialService(db).create_transaction(
        user.id, payload.model_dump(), actor_id=user.id
    )
    return TransactionRead.model_validate(tx)


@router.get(
    "/transactions/query",
    response_model=TransactionPage,
    summary="Search, filter, sort and paginate the transaction ledger",
)
async def query_transactions(
    user: CurrentUser,
    db: DbSession,
    search: str | None = Query(default=None, max_length=100, description="Matches description"),
    category: str | None = Query(default=None, max_length=100),
    type: str | None = Query(default=None, max_length=50, description="Income, Expense, ..."),
    sort_by: str = Query(default="transaction_date"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> TransactionPage:
    result = await FinancialService(db).query_transactions(
        user.id,
        search=search,
        category=category,
        tx_type=type,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    return TransactionPage.model_validate(result)


@router.get(
    "/transactions/{tx_id}", response_model=TransactionRead, summary="Get transaction detail"
)
async def get_transaction(tx_id: uuid.UUID, user: CurrentUser, db: DbSession) -> TransactionRead:
    tx = await FinancialService(db).transactions.get(tx_id)
    if tx is None or tx.user_id != user.id:
        raise NotFoundError("Transaction not found.")
    return TransactionRead.model_validate(tx)


@router.put("/transactions/{tx_id}", response_model=TransactionRead, summary="Update transaction")
async def update_transaction(
    tx_id: uuid.UUID, payload: TransactionUpdate, user: CurrentUser, db: DbSession
) -> TransactionRead:
    tx = await FinancialService(db).update_transaction(
        user.id, tx_id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return TransactionRead.model_validate(tx)


@router.delete(
    "/transactions/{tx_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete transaction"
)
async def delete_transaction(tx_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await FinancialService(db).delete_transaction(user.id, tx_id)


# --- Budgets ---
@router.get("/budgets/current", response_model=BudgetRead, summary="Get current month budget")
async def get_current_budget(user: CurrentUser, db: DbSession) -> BudgetRead:
    month_str = utc_now().strftime("%Y-%m")
    budget = await FinancialService(db).get_or_create_budget(user.id, month_str)
    return BudgetRead.model_validate(budget)


@router.post(
    "/budgets",
    response_model=BudgetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create/Get budget for month",
)
async def create_budget(payload: BudgetCreate, user: CurrentUser, db: DbSession) -> BudgetRead:
    budget = await FinancialService(db).create_budget(
        user.id, payload.month, payload.monthly_budget, payload.category_budgets, actor_id=user.id
    )
    return BudgetRead.model_validate(budget)


@router.put("/budgets/{budget_id}", response_model=BudgetRead, summary="Update budget")
async def update_budget(
    budget_id: uuid.UUID, payload: BudgetUpdate, user: CurrentUser, db: DbSession
) -> BudgetRead:
    budget = await FinancialService(db).update_budget(
        user.id, budget_id, payload.model_dump(exclude_unset=True), actor_id=user.id
    )
    return BudgetRead.model_validate(budget)


@router.get(
    "/budgets/current/utilization",
    response_model=BudgetRead,
    summary="Get current budget utilization details",
)
async def get_current_utilization(user: CurrentUser, db: DbSession) -> BudgetRead:
    month_str = utc_now().strftime("%Y-%m")
    budget = await FinancialService(db).get_or_create_budget(user.id, month_str)
    return BudgetRead.model_validate(budget)


# --- Health Score ---
@router.get(
    "/health-score", response_model=HealthScoreRead, summary="Get user financial health score"
)
async def get_health_score(user: CurrentUser, db: DbSession) -> HealthScoreRead:
    score_data = await FinancialService(db).get_health_score(user.id)
    return HealthScoreRead.model_validate(score_data)


# --- Dashboard Summary ---
@router.get(
    "/summary", response_model=DashboardSummaryRead, summary="Get user dashboard financial summary"
)
async def get_summary(user: CurrentUser, db: DbSession) -> DashboardSummaryRead:
    summary_data = await FinancialService(db).get_dashboard_summary(user.id)
    return DashboardSummaryRead.model_validate(summary_data)


# --- Analytics ---
@router.get("/analytics", response_model=AnalyticsRead, summary="Get user financial analytics")
async def get_analytics(user: CurrentUser, db: DbSession) -> AnalyticsRead:
    analytics_data = await FinancialService(db).get_analytics(user.id)
    return AnalyticsRead.model_validate(analytics_data)
