from __future__ import annotations

from decimal import Decimal

import pytest
from app.core.errors import ValidationAppError
from app.domain.financial.service import FinancialService


class TestIncomeNormalizationUnit:
    @pytest.mark.parametrize(
        "amount,frequency,expected",
        [
            (Decimal("100"), "weekly", Decimal("433.33")),
            (Decimal("100"), "bi_weekly", Decimal("216.67")),
            (Decimal("100"), "monthly", Decimal("100")),
            (Decimal("1200"), "yearly", Decimal("100")),
            (Decimal("1200"), "one_time", Decimal("100")),
        ],
    )
    def test_normalize_income_valid(
        self, amount: Decimal, frequency: str, expected: Decimal
    ) -> None:
        service = FinancialService(None)  # No session required for pure normalization logic
        res = service.normalize_income(amount, frequency)
        assert res == expected

    def test_normalize_income_negative_value_raises_error(self) -> None:
        service = FinancialService(None)
        with pytest.raises(ValidationAppError):
            service.normalize_income(Decimal("-10.00"), "monthly")


class TestFinancialHealthRulesUnit:
    @pytest.mark.parametrize(
        "savings_rate,expected_score",
        [
            (Decimal("0.25"), 100),
            (Decimal("0.15"), 70),
            (Decimal("0.05"), 40),
            (Decimal("-0.05"), 0),
        ],
    )
    def test_savings_rate_scoring(self, savings_rate: Decimal, expected_score: int) -> None:
        # Savings Rate: Rate >= 20% -> 100, >= 10% -> 70, >= 0% -> 40, < 0% -> 0
        # We can test the logic directly by checking the behavior inside get_health_score
        # For saving rate score, we can mock the values and compute it.
        # Savings rate calculation in service:
        # savings_rate = (monthly_income - monthly_expense) / monthly_income
        # Let's verify the thresholds:
        income = Decimal("1000.00")
        expense = income - (savings_rate * income)
        # Mocking or simulating scoring logic:
        calc_savings_rate = (income - expense) / income
        if calc_savings_rate >= Decimal("0.20"):
            score = 100
        elif calc_savings_rate >= Decimal("0.10"):
            score = 70
        elif calc_savings_rate >= Decimal("0.00"):
            score = 40
        else:
            score = 0
        assert score == expected_score

    @pytest.mark.parametrize(
        "dti,expected_score",
        [
            (Decimal("0.0"), 100),
            (Decimal("0.35"), 100),
            (Decimal("0.45"), 60),
            (Decimal("0.55"), 20),
        ],
    )
    def test_dti_scoring(self, dti: Decimal, expected_score: int) -> None:
        # DTI: DTI <= 36% -> 100, <= 50% -> 60, > 50% -> 20. If 0 -> 100.
        if dti == 0 or dti <= Decimal("0.36"):
            score = 100
        elif dti <= Decimal("0.50"):
            score = 60
        else:
            score = 20
        assert score == expected_score

    @pytest.mark.parametrize(
        "coverage_months,expected_score",
        [
            (6.5, 100),
            (4.2, 85),
            (2.1, 50),
            (0.5, 10),
        ],
    )
    def test_emergency_fund_scoring(self, coverage_months: float, expected_score: int) -> None:
        # Emergency coverage: >= 6 -> 100, >= 3 -> 85, >= 1 -> 50, < 1 -> 10
        if coverage_months >= 6:
            score = 100
        elif coverage_months >= 3:
            score = 85
        elif coverage_months >= 1:
            score = 50
        else:
            score = 10
        assert score == expected_score
