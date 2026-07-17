from __future__ import annotations

from typing import Any

import pytest
from app.domain.ai.llm import LLMResult
from app.domain.documents.classifier import (
    CATEGORY_FALLBACK,
    CATEGORY_UNSUPPORTED,
    DOMAIN_FINANCE,
    MAX_PREVIEW_WORDS,
    Classification,
    DocumentClassifier,
    build_preview,
    classify_by_keywords,
    infer_category,
    matched_keywords,
)

from tests.conftest import make_test_settings

BANK_STATEMENT = (
    "ACCOUNT STATEMENT\n\n"
    "Bank of India — account number 0012345678, IFSC INDB0000123.\n\n"
    "Transaction history: UPI transfer received, NEFT debit, salary credit.\n\n"
    "Closing balance as of 31 March: 45,200.00"
)

RECIPE = (
    "CLASSIC TOMATO SOUP\n\n"
    "Roast six tomatoes with olive oil until the skins blister.\n\n"
    "Blend with basil and cream, then simmer for twenty minutes.\n\n"
    "Season to taste and serve with toasted sourdough."
)


class _StubLLM:
    """Stands in for LLMClient: records calls, replays a scripted reply."""

    def __init__(self, *, text: str = "", configured: bool = True, error: Exception | None = None):
        self.text = text
        self.is_configured = configured
        self.error = error
        self.calls: list[dict[str, Any]] = []
        self.supports_queries: list[str | None] = []

    def supports(self, provider: str | None = None) -> bool:
        self.supports_queries.append(provider)
        return self.is_configured

    async def complete(self, **kwargs: Any) -> LLMResult:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return LLMResult(text=self.text, provider="groq", model="llama-3.3-70b-versatile")


def _classifier(llm: _StubLLM) -> DocumentClassifier:
    return DocumentClassifier(make_test_settings(), llm_client=llm)  # type: ignore[arg-type]


class TestPreview:
    def test_caps_at_word_budget(self) -> None:
        preview = build_preview("word " * (MAX_PREVIEW_WORDS + 500))
        assert len(preview.split()) == MAX_PREVIEW_WORDS

    def test_short_text_survives_intact(self) -> None:
        assert build_preview("loan agreement terms") == "loan agreement terms"

    def test_normalizes_whitespace(self) -> None:
        assert build_preview("loan\n\n  agreement\ttext") == "loan agreement text"


class TestKeywordDetector:
    def test_finds_distinct_keywords(self) -> None:
        hits = matched_keywords(BANK_STATEMENT)
        assert {"bank", "account number", "ifsc", "upi", "neft", "balance"} <= set(hits)

    def test_deduplicates_repeats(self) -> None:
        assert matched_keywords("loan loan loan") == ["loan"]

    def test_respects_word_boundaries(self) -> None:
        # "accreditation" contains "credit"; "swiftly" contains "swift".
        assert matched_keywords("accreditation handled swiftly") == []

    def test_matches_multiword_keyword_across_whitespace(self) -> None:
        assert "account number" in matched_keywords("the account\n  number is 55")

    def test_is_case_insensitive(self) -> None:
        assert "emi" in matched_keywords("Your EMI is due")

    def test_no_hits_on_unrelated_prose(self) -> None:
        assert matched_keywords(RECIPE) == []


class TestCategoryInference:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("This loan agreement binds the borrower and lender.", "Loan Agreement"),
            ("Bank statement showing closing balance and debit entries.", "Bank Statement"),
            ("Your credit report lists a CIBIL credit score.", "Credit Report"),
            ("Payslip: gross salary and net pay for March.", "Salary Slip"),
            ("Income tax return for assessment year 2024, form 16.", "Tax Document"),
            ("Insurance policy number 22 with premium and sum assured.", "Insurance Policy"),
            ("Property valuation report stating market value.", "Property Valuation"),
            ("Mortgage secured by a deed of trust.", "Mortgage Document"),
            ("KYC: aadhaar and pan card collected.", "KYC"),
        ],
    )
    def test_names_the_category(self, text: str, expected: str) -> None:
        category, confidence = infer_category(text)
        assert category == expected
        assert 0 < confidence <= 0.9

    def test_falls_back_when_no_profile_matches(self) -> None:
        category, confidence = infer_category("Generic notes about money and a bank.")
        assert category == CATEGORY_FALLBACK
        assert confidence == 0.5

    def test_confidence_never_reaches_llm_ceiling(self) -> None:
        _, confidence = infer_category(
            "loan agreement borrower lender principal collateral in one document"
        )
        assert confidence <= 0.9


class TestStageAVerdict:
    def test_strong_match_is_supported(self) -> None:
        result = classify_by_keywords(BANK_STATEMENT)
        assert result.supported
        assert result.domain == DOMAIN_FINANCE
        assert result.category == "Bank Statement"
        assert result.stage == "keyword"

    def test_single_hit_is_low_confidence(self) -> None:
        result = classify_by_keywords("The bank was closed that afternoon.")
        assert result.confidence < 0.5

    def test_no_hits_is_unsupported(self) -> None:
        result = classify_by_keywords(RECIPE)
        assert not result.supported
        assert result.category == CATEGORY_UNSUPPORTED
        assert result.domain is None


class TestClassificationShape:
    def test_supported_dict_matches_contract(self) -> None:
        result = Classification(
            supported=True, category="Bank Statement", confidence=0.97, domain=DOMAIN_FINANCE
        )
        assert result.to_dict() == {
            "supported": True,
            "domain": "finance",
            "category": "Bank Statement",
            "confidence": 0.97,
        }

    def test_unsupported_dict_matches_contract(self) -> None:
        result = Classification(supported=False, category=CATEGORY_UNSUPPORTED, confidence=0.8)
        assert result.to_dict() == {"supported": False, "category": "Unsupported"}

    def test_metadata_carries_the_four_extra_keys(self) -> None:
        result = Classification(
            supported=True, category="KYC", confidence=0.9, domain=DOMAIN_FINANCE
        )
        assert result.to_metadata("id.pdf") == {
            "domain": "finance",
            "category": "KYC",
            "confidence": 0.9,
            "filename": "id.pdf",
        }


class TestHybridFlow:
    async def test_strong_keywords_skip_the_llm(self) -> None:
        llm = _StubLLM(text="{}")
        result = await _classifier(llm).classify(BANK_STATEMENT)
        assert result.supported
        assert result.stage == "keyword"
        assert llm.calls == [], "Stage B ran despite a decisive Stage A"

    async def test_ambiguous_text_escalates_to_the_llm(self) -> None:
        llm = _StubLLM(
            text='{"supported": true, "domain": "finance", '
            '"category": "Income Proof", "confidence": 0.88}'
        )
        result = await _classifier(llm).classify("The bank was closed that afternoon.")
        assert len(llm.calls) == 1
        assert result.stage == "llm"
        assert result.category == "Income Proof"
        assert result.confidence == 0.88

    async def test_llm_can_reject_a_keyword_false_positive(self) -> None:
        llm = _StubLLM(text='{"supported": false, "category": "Unsupported", "confidence": 0.95}')
        result = await _classifier(llm).classify("The bank of the river was muddy.")
        assert not result.supported
        assert result.domain is None

    async def test_llm_sees_only_the_preview(self) -> None:
        llm = _StubLLM(text='{"supported": false, "category": "Unsupported"}')
        await _classifier(llm).classify("bank " + "filler " * (MAX_PREVIEW_WORDS + 400))
        sent = llm.calls[0]["messages"][0]["content"]
        assert len(sent.split()) <= MAX_PREVIEW_WORDS + 5  # + the prompt's own preamble words

    async def test_llm_is_asked_for_json(self) -> None:
        llm = _StubLLM(text='{"supported": false, "category": "Unsupported"}')
        await _classifier(llm).classify("The bank was closed.")
        assert llm.calls[0]["json_mode"] is True

    async def test_stage_b_is_pinned_to_groq(self) -> None:
        llm = _StubLLM(text='{"supported": false, "category": "Unsupported"}')
        await _classifier(llm).classify("The bank was closed that afternoon.")
        assert llm.calls[0]["provider"] == "groq", "Stage B must not fall through to Gemini"
        assert llm.supports_queries == ["groq"]

    async def test_availability_is_checked_against_groq_not_any_provider(self) -> None:
        # A Gemini-only deployment has no Groq key, so Stage B must sit out.
        llm = _StubLLM(configured=False)
        result = await _classifier(llm).classify("The bank was closed that afternoon.")
        assert llm.supports_queries == ["groq"]
        assert llm.calls == []
        assert result.stage == "keyword"


class TestStageBResilience:
    async def test_unconfigured_llm_falls_back_to_keywords(self) -> None:
        llm = _StubLLM(configured=False)
        result = await _classifier(llm).classify(RECIPE)
        assert llm.calls == []
        assert not result.supported
        assert result.stage == "keyword"

    async def test_llm_outage_falls_back_to_keywords(self) -> None:
        llm = _StubLLM(error=RuntimeError("groq is down"))
        result = await _classifier(llm).classify("The bank was closed that afternoon.")
        assert result.supported, "an LLM outage must not reject a plausible document"
        assert result.stage == "keyword"

    async def test_malformed_json_falls_back_to_keywords(self) -> None:
        llm = _StubLLM(text="I think this is a bank statement!")
        result = await _classifier(llm).classify("The bank was closed that afternoon.")
        assert result.stage == "keyword"

    async def test_fenced_json_is_parsed(self) -> None:
        llm = _StubLLM(
            text='```json\n{"supported": true, "domain": "finance", '
            '"category": "Tax Document", "confidence": 0.7}\n```'
        )
        result = await _classifier(llm).classify("The bank was closed that afternoon.")
        assert result.stage == "llm"
        assert result.category == "Tax Document"

    async def test_unknown_category_degrades_to_other_financial(self) -> None:
        llm = _StubLLM(
            text='{"supported": true, "domain": "finance", '
            '"category": "Crypto Whitepaper", "confidence": 0.7}'
        )
        result = await _classifier(llm).classify("The bank was closed that afternoon.")
        assert result.supported
        assert result.category == CATEGORY_FALLBACK

    async def test_out_of_range_confidence_is_clamped(self) -> None:
        llm = _StubLLM(
            text='{"supported": true, "domain": "finance", ' '"category": "KYC", "confidence": 4.2}'
        )
        result = await _classifier(llm).classify("The bank was closed that afternoon.")
        assert result.confidence == 1.0

    async def test_non_numeric_confidence_is_defaulted(self) -> None:
        llm = _StubLLM(
            text='{"supported": true, "domain": "finance", '
            '"category": "KYC", "confidence": "very sure"}'
        )
        result = await _classifier(llm).classify("The bank was closed that afternoon.")
        assert result.confidence == 0.5

    async def test_empty_document_is_unsupported_without_an_llm_call(self) -> None:
        llm = _StubLLM(text="{}")
        result = await _classifier(llm).classify("   \n\n  ")
        assert not result.supported
        assert result.stage == "empty"
        assert llm.calls == []
