"""Financial Data Upload, weighted health score, and the ledger query."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from tests.helpers import auth_headers, login_user, register_user

VALID_PAYLOAD = {
    "monthly_salary": "75000",
    "other_monthly_income": "5000",
    "monthly_expenses": "38500",
    "current_savings": "200000",
    "existing_investments": "150000",
    "current_bank_balance": "60000",
}


async def _headers(client: AsyncClient, email: str) -> dict[str, str]:
    await register_user(client, email=email)
    tokens = await login_user(client, email=email)
    return auth_headers(tokens)


class TestFinancialDataUpload:
    async def test_defaults_to_empty_before_upload(self, client: AsyncClient) -> None:
        headers = await _headers(client, "fd_empty@example.com")

        response = await client.get("/api/v1/financial/financial-data", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["has_data"] is False
        assert float(body["monthly_salary"]) == 0

    async def test_upload_then_read_back_persists(self, client: AsyncClient) -> None:
        headers = await _headers(client, "fd_save@example.com")

        saved = await client.put(
            "/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers
        )
        assert saved.status_code == 200
        assert saved.json()["has_data"] is True

        # A fresh read is what the page does on reload.
        reread = await client.get("/api/v1/financial/financial-data", headers=headers)
        body = reread.json()
        assert float(body["monthly_salary"]) == 75000
        assert float(body["other_monthly_income"]) == 5000
        assert float(body["monthly_expenses"]) == 38500
        assert float(body["current_savings"]) == 200000
        assert float(body["existing_investments"]) == 150000
        assert float(body["current_bank_balance"]) == 60000

    async def test_update_overwrites_rather_than_duplicating(self, client: AsyncClient) -> None:
        headers = await _headers(client, "fd_update@example.com")
        await client.put("/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers)

        await client.put(
            "/api/v1/financial/financial-data",
            json={**VALID_PAYLOAD, "monthly_salary": "90000"},
            headers=headers,
        )

        body = (await client.get("/api/v1/financial/financial-data", headers=headers)).json()
        assert float(body["monthly_salary"]) == 90000

        # The upload writes real domain rows; updating must not create a second one.
        incomes = (await client.get("/api/v1/financial/incomes", headers=headers)).json()
        salary_rows = [i for i in incomes if i["source"] == "Monthly Salary"]
        assert len(salary_rows) == 1
        assert float(salary_rows[0]["normalized_monthly_amount"]) == 90000

    async def test_upload_feeds_the_dashboard_summary(self, client: AsyncClient) -> None:
        headers = await _headers(client, "fd_summary@example.com")
        await client.put("/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers)

        body = (await client.get("/api/v1/financial/summary", headers=headers)).json()
        assert float(body["monthly_income"]) == 80000  # salary + other income
        assert float(body["monthly_expense"]) == 38500

        overview = body["monthly_overview"]
        assert float(overview["monthly_salary"]) == 75000
        assert float(overview["monthly_savings"]) == 41500
        assert round(overview["savings_rate"], 1) == 51.9
        assert float(overview["net_monthly_cash_flow"]) == 41500

        summary = body["financial_summary"]
        # Current balance is the spendable bank money, not earmarked savings.
        assert float(summary["current_balance"]) == 60000
        assert float(summary["investment_value"]) == 150000
        assert summary["emergency_fund_status"] in {"Building", "Adequate", "Fully Funded"}

    async def test_net_worth_includes_investments(self, client: AsyncClient) -> None:
        """Investments live in their own table but are still assets the user owns."""
        headers = await _headers(client, "fd_networth@example.com")
        await client.put("/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers)

        body = (await client.get("/api/v1/financial/summary", headers=headers)).json()
        # savings 200,000 + bank 60,000 + investments 150,000
        assert float(body["total_assets"]) == 410000
        # Liquid excludes the portfolio: savings 200,000 + bank 60,000.
        assert float(body["liquid_assets"]) == 260000
        assert float(body["total_liabilities"]) == 0
        assert float(body["net_worth"]) == 410000

    async def test_zero_optional_field_is_accepted(self, client: AsyncClient) -> None:
        headers = await _headers(client, "fd_zero@example.com")

        response = await client.put(
            "/api/v1/financial/financial-data",
            json={**VALID_PAYLOAD, "other_monthly_income": "0"},
            headers=headers,
        )
        assert response.status_code == 200
        assert float(response.json()["other_monthly_income"]) == 0

    async def test_clearing_a_field_retires_the_row(self, client: AsyncClient) -> None:
        headers = await _headers(client, "fd_clear@example.com")
        await client.put("/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers)

        await client.put(
            "/api/v1/financial/financial-data",
            json={**VALID_PAYLOAD, "other_monthly_income": "0"},
            headers=headers,
        )

        body = (await client.get("/api/v1/financial/summary", headers=headers)).json()
        assert float(body["monthly_income"]) == 75000


class TestFinancialDataValidation:
    async def test_negative_salary_rejected(self, client: AsyncClient) -> None:
        headers = await _headers(client, "fd_neg@example.com")
        response = await client.put(
            "/api/v1/financial/financial-data",
            json={**VALID_PAYLOAD, "monthly_salary": "-1"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_zero_salary_rejected(self, client: AsyncClient) -> None:
        headers = await _headers(client, "fd_zerosal@example.com")
        response = await client.put(
            "/api/v1/financial/financial-data",
            json={**VALID_PAYLOAD, "monthly_salary": "0"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_negative_expenses_rejected(self, client: AsyncClient) -> None:
        headers = await _headers(client, "fd_negexp@example.com")
        response = await client.put(
            "/api/v1/financial/financial-data",
            json={**VALID_PAYLOAD, "monthly_expenses": "-500"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_non_numeric_rejected(self, client: AsyncClient) -> None:
        headers = await _headers(client, "fd_text@example.com")
        response = await client.put(
            "/api/v1/financial/financial-data",
            json={**VALID_PAYLOAD, "current_savings": "not a number"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_missing_field_rejected(self, client: AsyncClient) -> None:
        headers = await _headers(client, "fd_missing@example.com")
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "current_bank_balance"}
        response = await client.put(
            "/api/v1/financial/financial-data", json=payload, headers=headers
        )
        assert response.status_code == 422


class TestHealthScore:
    async def test_no_data_scores_zero_without_inventing_numbers(self, client: AsyncClient) -> None:
        headers = await _headers(client, "hs_empty@example.com")

        body = (await client.get("/api/v1/financial/health-score", headers=headers)).json()
        assert body["has_data"] is False
        assert body["score"] == 0.0
        assert body["insights"] == []
        assert body["strengths"] == []

    async def test_score_is_derived_from_uploaded_data(self, client: AsyncClient) -> None:
        headers = await _headers(client, "hs_data@example.com")
        await client.put("/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers)

        body = (await client.get("/api/v1/financial/health-score", headers=headers)).json()
        assert body["has_data"] is True
        assert 0 <= body["score"] <= 100
        assert body["grade"] in {
            "EXCELLENT",
            "VERY_GOOD",
            "GOOD",
            "NEEDS_IMPROVEMENT",
            "POOR",
        }
        assert body["grade_label"]

        breakdown = body["breakdown"]
        assert set(breakdown) == {
            "savings_rate",
            "debt_to_income",
            "emergency_fund",
            "expense_stability",
            "investment_ratio",
            "cash_flow_trend",
        }
        # 51.9% of income saved, and no debt at all.
        assert breakdown["savings_rate"]["raw_value"] == "51.9%"
        assert breakdown["savings_rate"]["score"] == 100.0
        assert breakdown["debt_to_income"]["raw_value"] == "0.0%"
        assert breakdown["debt_to_income"]["score"] == 100.0

    async def test_metrics_without_history_carry_no_weight(self, client: AsyncClient) -> None:
        headers = await _headers(client, "hs_weights@example.com")
        await client.put("/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers)

        body = (await client.get("/api/v1/financial/health-score", headers=headers)).json()
        breakdown = body["breakdown"]
        # A brand-new account has no transaction history, so these two cannot be
        # measured and must not drag the score down.
        assert breakdown["expense_stability"]["weight"] == 0.0
        assert breakdown["cash_flow_trend"]["weight"] == 0.0
        assert breakdown["savings_rate"]["weight"] == 30.0
        assert breakdown["debt_to_income"]["weight"] == 25.0
        assert breakdown["emergency_fund"]["weight"] == 15.0
        assert breakdown["investment_ratio"]["weight"] == 10.0

    async def test_score_is_stable_across_calls(self, client: AsyncClient) -> None:
        """Nothing in the engine may be random."""
        headers = await _headers(client, "hs_stable@example.com")
        await client.put("/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers)

        first = (await client.get("/api/v1/financial/health-score", headers=headers)).json()
        second = (await client.get("/api/v1/financial/health-score", headers=headers)).json()
        assert first == second

    async def test_reads_do_not_mutate_the_profile(self, client: AsyncClient) -> None:
        """Reads must stay reads.

        The health history is written by the upload endpoint. If a GET wrote to
        it, every dashboard load would take a write lock and concurrent reads
        would serialise behind it.
        """
        headers = await _headers(client, "hs_readonly@example.com")
        await client.put("/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers)

        before = (await client.get("/api/v1/financial/profile", headers=headers)).json()
        await client.get("/api/v1/financial/health-score", headers=headers)
        await client.get("/api/v1/financial/summary", headers=headers)
        after = (await client.get("/api/v1/financial/profile", headers=headers)).json()

        assert before["updated_at"] == after["updated_at"]
        assert before["financial_preferences"] == after["financial_preferences"]

    async def test_upload_records_a_health_snapshot(self, client: AsyncClient) -> None:
        headers = await _headers(client, "hs_snapshot@example.com")
        await client.put("/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers)

        profile = (await client.get("/api/v1/financial/profile", headers=headers)).json()
        history = profile["financial_preferences"]["health_history"]
        assert len(history) == 1
        health = (await client.get("/api/v1/financial/health-score", headers=headers)).json()
        assert next(iter(history.values())) == health["score"]

    async def test_concurrent_dashboard_reads_all_complete(self, client: AsyncClient) -> None:
        """Two dashboard loads at once must not block each other."""
        headers = await _headers(client, "hs_concurrent@example.com")
        await client.put("/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers)

        responses = await asyncio.gather(
            client.get("/api/v1/financial/summary", headers=headers),
            client.get("/api/v1/financial/summary", headers=headers),
            client.get("/api/v1/financial/health-score", headers=headers),
            client.get("/api/v1/financial/transactions/query", headers=headers),
        )
        assert [r.status_code for r in responses] == [200, 200, 200, 200]

    async def test_overspending_is_reported_honestly(self, client: AsyncClient) -> None:
        headers = await _headers(client, "hs_overspend@example.com")
        await client.put(
            "/api/v1/financial/financial-data",
            json={**VALID_PAYLOAD, "monthly_salary": "30000", "monthly_expenses": "45000"},
            headers=headers,
        )

        body = (await client.get("/api/v1/financial/health-score", headers=headers)).json()
        # Income 35,000 against 45,000 of expenses: a negative rate scores below
        # the break-even anchor of 30 and is called out as an area to improve.
        # The overall grade stays respectable because this profile still carries
        # no debt and holds several months of reserves — the weights say so.
        assert body["breakdown"]["savings_rate"]["raw_value"] == "-28.6%"
        assert body["breakdown"]["savings_rate"]["score"] < 30.0
        assert any("Savings rate" in a for a in body["areas_to_improve"])
        assert any("more than you earn" in i for i in body["insights"])
        assert any("Trim ₹" in r for r in body["recommendations"])

    async def test_insights_quote_the_users_own_figures(self, client: AsyncClient) -> None:
        headers = await _headers(client, "hs_insights@example.com")
        await client.put("/api/v1/financial/financial-data", json=VALID_PAYLOAD, headers=headers)

        body = (await client.get("/api/v1/financial/health-score", headers=headers)).json()
        insights = body["insights"]
        assert any("You save 52% of your monthly income" in i for i in insights)
        assert any("Emergency fund covers" in i for i in insights)
        assert any("₹" in i for i in insights)


class TestTransactionQuery:
    async def _seed(self, client: AsyncClient, headers: dict[str, str]) -> None:
        # Cash to spend from, so Expense rows are not rejected for insufficient funds.
        await client.post(
            "/api/v1/financial/assets",
            json={"name": "Wallet", "type": "Cash", "current_value": "500000"},
            headers=headers,
        )
        now = datetime.now(UTC)
        rows = [
            ("Income", "Salary", "75000", "Bank Transfer", "Completed", 0),
            ("Expense", "Food", "4500", "UPI", "Completed", 1),
            ("Expense", "Rent", "22000", "Auto Debit", "Completed", 2),
            ("Expense", "Food", "1200", "Credit Card", "Pending", 3),
        ]
        for tx_type, category, amount, method, status, days in rows:
            response = await client.post(
                "/api/v1/financial/transactions",
                json={
                    "type": tx_type,
                    "category": category,
                    "amount": amount,
                    "description": f"{category} entry",
                    "payment_method": method,
                    "status": status,
                    "transaction_date": (now - timedelta(days=days)).isoformat(),
                },
                headers=headers,
            )
            assert response.status_code == 201

    async def test_returns_newest_first_with_payment_fields(self, client: AsyncClient) -> None:
        headers = await _headers(client, "tq_list@example.com")
        await self._seed(client, headers)

        body = (await client.get("/api/v1/financial/transactions/query", headers=headers)).json()
        assert body["total"] == 4
        assert body["items"][0]["category"] == "Salary"  # most recent
        assert body["items"][0]["payment_method"] == "Bank Transfer"
        assert body["items"][0]["status"] == "Completed"
        assert body["categories"] == ["Food", "Rent", "Salary"]

    async def test_category_filter(self, client: AsyncClient) -> None:
        headers = await _headers(client, "tq_cat@example.com")
        await self._seed(client, headers)

        body = (
            await client.get(
                "/api/v1/financial/transactions/query", params={"category": "Food"}, headers=headers
            )
        ).json()
        assert body["total"] == 2
        assert {i["category"] for i in body["items"]} == {"Food"}

    async def test_search_matches_description(self, client: AsyncClient) -> None:
        headers = await _headers(client, "tq_search@example.com")
        await self._seed(client, headers)

        body = (
            await client.get(
                "/api/v1/financial/transactions/query", params={"search": "rent"}, headers=headers
            )
        ).json()
        assert body["total"] == 1
        assert body["items"][0]["category"] == "Rent"

    async def test_amount_sorting(self, client: AsyncClient) -> None:
        headers = await _headers(client, "tq_sort@example.com")
        await self._seed(client, headers)

        body = (
            await client.get(
                "/api/v1/financial/transactions/query",
                params={"sort_by": "amount", "sort_dir": "asc"},
                headers=headers,
            )
        ).json()
        amounts = [float(i["amount"]) for i in body["items"]]
        assert amounts == sorted(amounts)

    async def test_pagination(self, client: AsyncClient) -> None:
        headers = await _headers(client, "tq_page@example.com")
        await self._seed(client, headers)

        page1 = (
            await client.get(
                "/api/v1/financial/transactions/query",
                params={"page": 1, "page_size": 3},
                headers=headers,
            )
        ).json()
        assert len(page1["items"]) == 3
        assert page1["total_pages"] == 2

        page2 = (
            await client.get(
                "/api/v1/financial/transactions/query",
                params={"page": 2, "page_size": 3},
                headers=headers,
            )
        ).json()
        assert len(page2["items"]) == 1
        ids = {i["id"] for i in page1["items"]} | {i["id"] for i in page2["items"]}
        assert len(ids) == 4

    async def test_unknown_sort_field_rejected(self, client: AsyncClient) -> None:
        headers = await _headers(client, "tq_badsort@example.com")
        response = await client.get(
            "/api/v1/financial/transactions/query",
            params={"sort_by": "user_id"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_transactions_default_to_inr(self, client: AsyncClient) -> None:
        headers = await _headers(client, "tq_inr@example.com")
        await self._seed(client, headers)

        body = (await client.get("/api/v1/financial/transactions/query", headers=headers)).json()
        assert {i["currency"] for i in body["items"]} == {"INR"}
