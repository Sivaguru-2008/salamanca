"""Financial-domain gate applied to uploads before chunking or embedding.

Hybrid two-stage design. Stage A is a keyword detector over a bounded
preview of the document: cheap, deterministic, and enough to clear the
obvious financial cases without an API call. Stage B asks Groq only when
Stage A is undecided, which keeps the common path free.

Stage B is pinned to Groq rather than taking ``LLMClient``'s default
Gemini-then-Groq chain: classification wants one cheap fast model with a
stable verdict, not the best available answer.

Stage B is best-effort by design: when Groq is unconfigured or the call
fails, the Stage A verdict stands rather than failing the upload.
Ingestion already runs without any LLM key (see ``DocumentsService``),
and a classifier outage must not be the thing that takes it down.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import structlog

from app.core.config import Settings
from app.domain.ai.llm import LLMClient

logger = structlog.get_logger(__name__)

DOMAIN_FINANCE = "finance"
CATEGORY_UNSUPPORTED = "Unsupported"
CATEGORY_FALLBACK = "Other Financial"

# Stage B runs on Groq specifically, not on whichever provider ranks
# first in LLMClient's fallback chain.
CLASSIFIER_PROVIDER = "groq"

SUPPORTED_CATEGORIES: tuple[str, ...] = (
    "Loan Agreement",
    "Bank Statement",
    "Credit Report",
    "Salary Slip",
    "Income Proof",
    "Tax Document",
    "Insurance Policy",
    "Property Valuation",
    "Mortgage Document",
    "KYC",
    CATEGORY_FALLBACK,
)

UNSUPPORTED_MESSAGE = "Unsupported document. This RAG currently accepts only financial documents."

# Bounds what Stage A scans and what Stage B is billed for. Roughly the
# first 2-3 pages; extracted text carries no recoverable page breaks, so
# the cap is by word count rather than page count.
MAX_PREVIEW_WORDS = 2500

FINANCIAL_KEYWORDS: tuple[str, ...] = (
    "loan",
    "borrower",
    "lender",
    "bank",
    "interest",
    "emi",
    "mortgage",
    "credit",
    "debit",
    "balance",
    "statement",
    "transaction",
    "salary",
    "income",
    "tax",
    "insurance",
    "account number",
    "ifsc",
    "upi",
    "rtgs",
    "neft",
    "swift",
    "collateral",
)

# Distinct keywords (not total hits) needed to clear Stage A outright. A
# single "bank" or "swift" is noise in ordinary prose; three different
# terms co-occurring is a document about money.
STRONG_MATCH_THRESHOLD = 3

# Keyword profiles for naming a category without an LLM. Each entry lists
# terms that are distinctive of that category rather than merely present
# in it, so "Other Financial" stays the honest answer when nothing fits.
CATEGORY_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Loan Agreement", ("loan agreement", "borrower", "lender", "principal", "collateral")),
    ("Bank Statement", ("account statement", "bank statement", "closing balance", "debit")),
    ("Credit Report", ("credit report", "credit score", "cibil", "creditworthiness")),
    ("Salary Slip", ("salary slip", "payslip", "pay slip", "net pay", "gross salary")),
    ("Income Proof", ("income proof", "proof of income", "annual income")),
    ("Tax Document", ("tax return", "form 16", "income tax", "assessment year", "tds")),
    (
        "Insurance Policy",
        ("insurance policy", "policy number", "premium", "insured", "sum assured"),
    ),
    ("Property Valuation", ("valuation report", "market value", "property valuation", "appraisal")),
    ("Mortgage Document", ("mortgage", "deed of trust", "hypothecation")),
    ("KYC", ("know your customer", "kyc", "aadhaar", "pan card", "passport number")),
)

_SYSTEM_PROMPT = (
    "You classify uploaded documents for a finance-only retrieval system. "
    "Decide whether the excerpt is a financial document, and if so which category. "
    f"Valid categories: {', '.join(SUPPORTED_CATEGORIES)}. "
    "A document is financial only if its subject matter is money, accounts, credit, "
    "tax, insurance, income, or property value. A passing mention of a price or a "
    "bank name does not make a document financial. "
    'Reply with JSON only: {"supported": bool, "domain": "finance" or null, '
    '"category": string, "confidence": float between 0 and 1}. '
    f'When it is not a financial document, use {{"supported": false, "domain": null, '
    f'"category": "{CATEGORY_UNSUPPORTED}", "confidence": <your confidence>}}.'
)


@dataclass(frozen=True)
class Classification:
    """Verdict for one document. ``domain`` is None when unsupported."""

    supported: bool
    category: str
    confidence: float
    domain: str | None = None
    stage: str = "keyword"

    def to_dict(self) -> dict[str, Any]:
        """The wire/JSON shape: unsupported carries no domain or confidence."""
        if not self.supported:
            return {"supported": False, "category": CATEGORY_UNSUPPORTED}
        return {
            "supported": True,
            "domain": self.domain,
            "category": self.category,
            "confidence": self.confidence,
        }

    def to_metadata(self, filename: str) -> dict[str, Any]:
        """Extra keys merged into the document's stored metadata."""
        return {
            "domain": self.domain,
            "category": self.category,
            "confidence": self.confidence,
            "filename": filename,
        }


def build_preview(text: str, max_words: int = MAX_PREVIEW_WORDS) -> str:
    """First ``max_words`` words of ``text``, whitespace-normalized."""
    words = text.split()
    return " ".join(words[:max_words])


def matched_keywords(text: str) -> list[str]:
    """Distinct financial keywords present in ``text``, in declaration order.

    Matching is word-bounded so "credit" does not fire on "accreditation";
    multi-word keywords tolerate arbitrary whitespace between their parts.
    """
    lowered = text.lower()
    hits: list[str] = []
    for keyword in FINANCIAL_KEYWORDS:
        pattern = r"\b" + r"\s+".join(re.escape(part) for part in keyword.split()) + r"\b"
        if re.search(pattern, lowered):
            hits.append(keyword)
    return hits


def infer_category(text: str) -> tuple[str, float]:
    """Best-matching category for ``text`` and a confidence in [0, 1].

    Confidence scales with how many distinctive terms of the winning
    category appear, capped below the LLM's ceiling: a keyword profile is
    weaker evidence than a read of the document.
    """
    lowered = text.lower()
    best_category = CATEGORY_FALLBACK
    best_hits = 0
    for category, signals in CATEGORY_SIGNALS:
        hits = sum(1 for signal in signals if signal in lowered)
        if hits > best_hits:
            best_category, best_hits = category, hits
    if best_hits == 0:
        return CATEGORY_FALLBACK, 0.5
    return best_category, min(0.6 + 0.1 * best_hits, 0.9)


def classify_by_keywords(text: str) -> Classification:
    """Stage A verdict. Undecided cases surface as low-confidence support."""
    hits = matched_keywords(text)
    if len(hits) >= STRONG_MATCH_THRESHOLD:
        category, confidence = infer_category(text)
        return Classification(
            supported=True,
            category=category,
            confidence=confidence,
            domain=DOMAIN_FINANCE,
            stage="keyword",
        )
    if hits:
        return Classification(
            supported=True,
            category=CATEGORY_FALLBACK,
            confidence=0.4,
            domain=DOMAIN_FINANCE,
            stage="keyword",
        )
    return Classification(
        supported=False,
        category=CATEGORY_UNSUPPORTED,
        confidence=0.6,
        domain=None,
        stage="keyword",
    )


def _parse_llm_json(raw: str) -> dict[str, Any]:
    """Parse an LLM JSON reply, tolerating markdown fences around it."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected a JSON object, got {type(parsed).__name__}.")
    return parsed


def _classification_from_llm(payload: dict[str, Any]) -> Classification:
    """Coerce an LLM payload into a Classification, rejecting unknown categories."""
    supported = bool(payload.get("supported"))
    try:
        confidence = float(payload.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = min(max(confidence, 0.0), 1.0)

    if not supported:
        return Classification(
            supported=False,
            category=CATEGORY_UNSUPPORTED,
            confidence=confidence,
            domain=None,
            stage="llm",
        )

    category = str(payload.get("category") or "").strip()
    if category not in SUPPORTED_CATEGORIES:
        # Supported but off-list: keep the document, drop the invented label.
        logger.warning("classifier_llm_unknown_category", category=category)
        category = CATEGORY_FALLBACK
    return Classification(
        supported=True,
        category=category,
        confidence=confidence,
        domain=DOMAIN_FINANCE,
        stage="llm",
    )


class DocumentClassifier:
    """Two-stage financial-document gate."""

    def __init__(self, settings: Settings, llm_client: LLMClient | None = None) -> None:
        self.settings = settings
        self.llm = llm_client or LLMClient(settings)

    async def classify(self, text: str) -> Classification:
        """Classify a document from its leading text.

        Stage A alone decides when it finds strong keyword evidence. Every
        other case defers to Stage B when Groq is configured, and falls
        back to Stage A when it is not or when the call fails.
        """
        preview = build_preview(text)
        if not preview.strip():
            return Classification(
                supported=False,
                category=CATEGORY_UNSUPPORTED,
                confidence=1.0,
                domain=None,
                stage="empty",
            )

        keyword_result = classify_by_keywords(preview)
        if keyword_result.supported and keyword_result.confidence >= 0.5:
            return keyword_result

        if not self.llm.supports(CLASSIFIER_PROVIDER):
            logger.info("classifier_llm_unavailable_using_keywords")
            return keyword_result

        try:
            return await self._classify_with_llm(preview)
        except Exception as exc:
            logger.warning("classifier_llm_failed_using_keywords", error=str(exc))
            return keyword_result

    async def _classify_with_llm(self, preview: str) -> Classification:
        result = await self.llm.complete(
            system_prompt=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Document excerpt:\n\n{preview}"}],
            temperature=0.0,
            max_tokens=200,
            json_mode=True,
            provider=CLASSIFIER_PROVIDER,
        )
        classification = _classification_from_llm(_parse_llm_json(result.text))
        logger.info(
            "classifier_llm_verdict",
            provider=result.provider,
            supported=classification.supported,
            category=classification.category,
        )
        return classification
