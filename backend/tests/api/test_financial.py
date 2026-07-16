from __future__ import annotations

from datetime import UTC, date, datetime

from httpx import AsyncClient

from tests.helpers import auth_headers, login_user, register_user


class TestFinancialProfile:
    async def test_get_profile_defaults(self, client: AsyncClient) -> None:
        await register_user(client, email="profile@example.com")
        tokens = await login_user(client, email="profile@example.com")
        headers = auth_headers(tokens)

        response = await client.get("/api/v1/financial/profile", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["currency"] == "USD"
        assert body["risk_profile"] == "MEDIUM"
        assert body["financial_literacy_level"] == "BEGINNER"

    async def test_update_profile(self, client: AsyncClient) -> None:
        await register_user(client, email="profile_up@example.com")
        tokens = await login_user(client, email="profile_up@example.com")
        headers = auth_headers(tokens)

        response = await client.put(
            "/api/v1/financial/profile",
            json={
                "currency": "EUR",
                "risk_profile": "HIGH",
                "financial_literacy_level": "ADVANCED",
            },
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["currency"] == "EUR"
        assert body["risk_profile"] == "HIGH"
        assert body["financial_literacy_level"] == "ADVANCED"


class TestIncomes:
    async def test_crud_income_and_normalization(self, client: AsyncClient) -> None:
        await register_user(client, email="income@example.com")
        tokens = await login_user(client, email="income@example.com")
        headers = auth_headers(tokens)

        # 1. Create weekly income
        response = await client.post(
            "/api/v1/financial/incomes",
            json={
                "source": "Freelance Work",
                "amount": "1000.00",
                "currency": "USD",
                "frequency": "WEEKLY",
                "is_recurring": True,
                "start_date": str(date.today()),
            },
            headers=headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["source"] == "Freelance Work"
        assert float(body["normalized_monthly_amount"]) == 4333.3  # 1000 * 4.3333
        income_id = body["id"]

        # 2. Get income detail
        response = await client.get(f"/api/v1/financial/incomes/{income_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["source"] == "Freelance Work"

        # 3. Update income to yearly
        response = await client.put(
            f"/api/v1/financial/incomes/{income_id}",
            json={"amount": "12000.00", "frequency": "YEARLY"},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert float(body["normalized_monthly_amount"]) == 1000.0  # 12000 / 12

        # 4. List incomes
        response = await client.get("/api/v1/financial/incomes", headers=headers)
        assert response.status_code == 200
        assert len(response.json()) == 1

        # 5. Delete income
        response = await client.delete(f"/api/v1/financial/incomes/{income_id}", headers=headers)
        assert response.status_code == 204

        # 6. Detail of deleted
        response = await client.get(f"/api/v1/financial/incomes/{income_id}", headers=headers)
        assert response.status_code == 404

    async def test_negative_income_rejected(self, client: AsyncClient) -> None:
        await register_user(client, email="income_neg@example.com")
        tokens = await login_user(client, email="income_neg@example.com")
        headers = auth_headers(tokens)

        response = await client.post(
            "/api/v1/financial/incomes",
            json={
                "source": "Freelance Work",
                "amount": "-500.00",
                "currency": "USD",
                "frequency": "WEEKLY",
                "is_recurring": True,
                "start_date": str(date.today()),
            },
            headers=headers,
        )
        assert response.status_code == 422


class TestExpensesAndBudgets:
    async def test_expense_crud_and_budget_alert(self, client: AsyncClient) -> None:
        await register_user(client, email="expense@example.com")
        tokens = await login_user(client, email="expense@example.com")
        headers = auth_headers(tokens)

        # 1. Create a budget for Food category
        response = await client.post(
            "/api/v1/financial/budgets",
            json={
                "month": datetime.now(UTC).strftime("%Y-%m"),
                "monthly_budget": "500.00",
                "category_budgets": {"Food": "100.00"},
            },
            headers=headers,
        )
        assert response.status_code == 201

        # 2. Add an expense of $50 (within limit)
        response = await client.post(
            "/api/v1/financial/expenses",
            json={
                "category": "Food",
                "expense_type": "VARIABLE",
                "amount": "50.00",
                "currency": "USD",
                "is_recurring": False,
            },
            headers=headers,
        )
        assert response.status_code == 201
        exp_id = response.json()["id"]

        # 3. Check budget utilization (should be 50% warning)
        response = await client.get(
            "/api/v1/financial/budgets/current/utilization", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert float(body["budget_utilization"]["Food"]) == 50.0

        # 4. Add another expense of $60 (total $110, exceeds Food budget limit of $100)
        response = await client.post(
            "/api/v1/financial/expenses",
            json={
                "category": "Food",
                "expense_type": "VARIABLE",
                "amount": "60.00",
                "currency": "USD",
                "is_recurring": False,
            },
            headers=headers,
        )
        assert response.status_code == 201

        # 5. Check budget alerts (Food should have alert warning/critical)
        response = await client.get(
            "/api/v1/financial/budgets/current/utilization", headers=headers
        )
        body = response.json()
        assert float(body["budget_utilization"]["Food"]) == 110.0
        assert body["budget_alerts"]["Food"]["status"] == "CRITICAL"

        # Cleanup
        await client.delete(f"/api/v1/financial/expenses/{exp_id}", headers=headers)


class TestAssetsAndLiabilities:
    async def test_asset_crud_and_validations(self, client: AsyncClient) -> None:
        await register_user(client, email="asset@example.com")
        tokens = await login_user(client, email="asset@example.com")
        headers = auth_headers(tokens)

        # 1. Create a bank asset
        response = await client.post(
            "/api/v1/financial/assets",
            json={
                "name": "Checking Account",
                "type": "Bank accounts",
                "current_value": "5000.00",
                "currency": "USD",
            },
            headers=headers,
        )
        assert response.status_code == 201
        asset_id = response.json()["id"]

        # 2. Prevent negative current_value
        response = await client.put(
            f"/api/v1/financial/assets/{asset_id}",
            json={"current_value": "-10.00"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_liability_crud_and_validations(self, client: AsyncClient) -> None:
        await register_user(client, email="liability@example.com")
        tokens = await login_user(client, email="liability@example.com")
        headers = auth_headers(tokens)

        # 1. Create a credit card liability
        response = await client.post(
            "/api/v1/financial/liabilities",
            json={
                "name": "Visa CC",
                "type": "Credit Cards",
                "outstanding_balance": "1200.00",
                "currency": "USD",
            },
            headers=headers,
        )
        assert response.status_code == 201
        liab_id = response.json()["id"]

        # 2. Prevent negative outstanding balance
        response = await client.put(
            f"/api/v1/financial/liabilities/{liab_id}",
            json={"outstanding_balance": "-500.00"},
            headers=headers,
        )
        assert response.status_code == 422


class TestLoansAndInsurances:
    async def test_loan_crud_and_validations(self, client: AsyncClient) -> None:
        await register_user(client, email="loans@example.com")
        tokens = await login_user(client, email="loans@example.com")
        headers = auth_headers(tokens)

        # 1. Create Loan
        response = await client.post(
            "/api/v1/financial/loans",
            json={
                "name": "Auto Loan",
                "type": "Vehicle Loans",
                "interest_rate": "4.5",
                "apr": "4.9",
                "processing_fees": "150.00",
                "emi": "350.00",
                "remaining_tenure": 36,
                "outstanding_balance": "12600.00",
            },
            headers=headers,
        )
        assert response.status_code == 201

        # 2. Negative validations
        response = await client.post(
            "/api/v1/financial/loans",
            json={
                "name": "Auto Loan",
                "type": "Vehicle Loans",
                "interest_rate": "4.5",
                "apr": "4.9",
                "processing_fees": "150.00",
                "emi": "-10.00",  # Negative EMI rejected
                "remaining_tenure": 36,
                "outstanding_balance": "12600.00",
            },
            headers=headers,
        )
        assert response.status_code == 422

    async def test_insurance_crud_and_validations(self, client: AsyncClient) -> None:
        await register_user(client, email="insurance@example.com")
        tokens = await login_user(client, email="insurance@example.com")
        headers = auth_headers(tokens)

        # 1. Create Insurance
        response = await client.post(
            "/api/v1/financial/insurances",
            json={
                "policy_number": "POL-9992",
                "provider": "State Farm",
                "type": "Health",
                "coverage_amount": "50000.00",
                "premium_amount": "120.00",
                "premium_frequency": "MONTHLY",
                "renewal_date": str(date.today()),
            },
            headers=headers,
        )
        assert response.status_code == 201


class TestInvestmentsAndGoals:
    async def test_investment_crud(self, client: AsyncClient) -> None:
        await register_user(client, email="investment@example.com")
        tokens = await login_user(client, email="investment@example.com")
        headers = auth_headers(tokens)

        response = await client.post(
            "/api/v1/financial/investments",
            json={
                "name": "S&P 500 Index Fund",
                "type": "Mutual Funds",
                "amount_invested": "1000.00",
                "current_value": "1150.00",
                "currency": "USD",
            },
            headers=headers,
        )
        assert response.status_code == 201

    async def test_savings_goals_crud(self, client: AsyncClient) -> None:
        await register_user(client, email="goals@example.com")
        tokens = await login_user(client, email="goals@example.com")
        headers = auth_headers(tokens)

        response = await client.post(
            "/api/v1/financial/savings-goals",
            json={
                "name": "Emergency Fund",
                "category": "Emergency Fund",
                "target_amount": "10000.00",
                "target_date": str(date.today()),
                "current_progress": "1200.00",
            },
            headers=headers,
        )
        assert response.status_code == 201


class TestTransactionsAndSideEffects:
    async def test_transaction_updates_linked_models(self, client: AsyncClient) -> None:
        await register_user(client, email="transactions@example.com")
        tokens = await login_user(client, email="transactions@example.com")
        headers = auth_headers(tokens)

        # 1. Create a loan
        response = await client.post(
            "/api/v1/financial/loans",
            json={
                "name": "School Loan",
                "type": "Education Loans",
                "interest_rate": "5.0",
                "apr": "5.2",
                "emi": "200.00",
                "remaining_tenure": 12,
                "outstanding_balance": "2400.00",
            },
            headers=headers,
        )
        loan_id = response.json()["id"]

        # 2. Create a Loan Payment transaction of $200 pointing to the Loan ID
        response = await client.post(
            "/api/v1/financial/transactions",
            json={
                "type": "Loan Payment",
                "category": "Debt Payment",
                "amount": "200.00",
                "currency": "USD",
                "reference_id": loan_id,
            },
            headers=headers,
        )
        assert response.status_code == 201

        # 3. Verify loan outstanding balance was decreased to $2200 and payment logged in history
        response = await client.get(f"/api/v1/financial/loans/{loan_id}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert float(body["outstanding_balance"]) == 2200.0
        assert len(body["payment_history"]) == 1


class TestFinancialIntelligenceDashboards:
    async def test_dashboard_aggregates_net_worth_and_health_score(
        self, client: AsyncClient
    ) -> None:
        await register_user(client, email="summary@example.com")
        tokens = await login_user(client, email="summary@example.com")
        headers = auth_headers(tokens)

        # 1. Create Assets ($12000 total)
        await client.post(
            "/api/v1/financial/assets",
            json={
                "name": "Savings",
                "type": "Bank accounts",
                "current_value": "10000.00",
                "currency": "USD",
            },
            headers=headers,
        )
        await client.post(
            "/api/v1/financial/assets",
            json={"name": "Cash", "type": "Cash", "current_value": "2000.00", "currency": "USD"},
            headers=headers,
        )

        # 2. Create Liability ($2000 total)
        await client.post(
            "/api/v1/financial/liabilities",
            json={
                "name": "Credit Card",
                "type": "Credit Cards",
                "outstanding_balance": "2000.00",
                "currency": "USD",
            },
            headers=headers,
        )

        # 3. Create Loan ($4000 outstanding)
        await client.post(
            "/api/v1/financial/loans",
            json={
                "name": "Auto Loan",
                "type": "Vehicle Loans",
                "interest_rate": "4.0",
                "apr": "4.2",
                "emi": "250.00",
                "remaining_tenure": 20,
                "outstanding_balance": "4000.00",
            },
            headers=headers,
        )

        # 4. Check summary: net worth should be 12000 - 2000 - 4000 = 6000
        response = await client.get("/api/v1/financial/summary", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert float(body["net_worth"]) == 6000.0
        assert float(body["total_assets"]) == 12000.0
        assert float(body["total_liabilities"]) == 6000.0

        # 5. Check health score calculation
        response = await client.get("/api/v1/financial/health-score", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert "score" in body
        assert "grade" in body
        assert "breakdown" in body
        assert "recommendations" in body

        # 6. Check analytics cash flows
        response = await client.get("/api/v1/financial/analytics", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert "monthly_cash_flow" in body
        assert "asset_allocation" in body
