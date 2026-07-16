"""AI council chat orchestration and loan-document analysis."""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.ai.llm import LLMClient
from app.domain.financial.service import FinancialService
from app.utils.datetime import utc_now

logger = structlog.get_logger(__name__)

PROMPT_INJECTION_RE = re.compile(
    r"(?i)\b(ignore\s+(?:the\s+)?(?:above|previous|system|rule|instruction)|"
    r"you\s+are\s+now\s+(?:a|an)\b|"
    r"system\s+override\b|"
    r"override\s+(?:the\s+)?(?:system|rule|instruction)|"
    r"new\s+instructions\b)"
)

AGENT_PROFILES: dict[str, dict[str, str]] = {
    "advisor": {
        "name": "Chief Financial Advisor",
        "focus": (
            "You coordinate a council of specialist agents. Give balanced, holistic advice "
            "covering budgeting, debt, savings, investments, insurance, and taxes."
        ),
    },
    "budget": {
        "name": "Budget Agent",
        "focus": (
            "You are a budgeting specialist. Focus on envelope allocations, category "
            "overspend, fixed-vs-variable expense structure, and monthly cash-flow discipline."
        ),
    },
    "debt": {
        "name": "Debt Agent",
        "focus": (
            "You are a debt-management specialist. Focus on APRs, avalanche vs snowball "
            "payoff ordering, refinancing options, and debt-to-income ratio."
        ),
    },
    "savings": {
        "name": "Savings Agent",
        "focus": (
            "You are a savings strategist. Focus on emergency-fund months of coverage, "
            "savings rate, goal funding schedules, and high-yield placement of idle cash."
        ),
    },
    "investment": {
        "name": "Investment Agent",
        "focus": (
            "You are an investment guide. Focus on asset allocation, diversification, "
            "risk profile fit, and long-term compounding. Never give specific security picks."
        ),
    },
    "insurance": {
        "name": "Insurance Agent",
        "focus": (
            "You are an insurance advisor. Focus on coverage adequacy versus income, "
            "policy renewals, premium efficiency, and protection gaps."
        ),
    },
    "tax": {
        "name": "Tax Agent",
        "focus": (
            "You are a tax planner. Focus on tax-advantaged accounts, deduction hygiene, "
            "and timing of income and capital events. Note jurisdictions vary."
        ),
    },
    "loan": {
        "name": "Loan Agent",
        "focus": (
            "You are a loan evaluator. Focus on EMIs, effective APR, tenure trade-offs, "
            "prepayment penalties, and predatory clause detection."
        ),
    },
}

BASE_SYSTEM_PROMPT = """You are {name}, one of eight agents in the FIOS (Financial \
Intelligence Operating System) advisory council.

{focus}

Rules:
- Ground every claim in the user's live financial snapshot provided below. Quote actual numbers.
- Be concise: 2-4 short paragraphs or a tight bullet list. Plain markdown.
- You are not a licensed financial advisor; frame guidance as educational analysis.
- If the snapshot lacks the data needed, say exactly what is missing instead of inventing it.

Live financial snapshot (from the FIOS database):
{snapshot}
"""


class ChatService:
    """Per-agent council chat with Redis-backed conversation memory."""

    def __init__(self, db: AsyncSession, redis: Redis, settings: Settings) -> None:
        self.db = db
        self.redis = redis
        self.settings = settings
        self.llm = LLMClient(settings)

    @staticmethod
    def _history_key(user_id: uuid.UUID, agent: str, conversation_id: str) -> str:
        return f"fios:chat:{user_id}:{agent}:{conversation_id}"

    @staticmethod
    def _decisions_key(user_id: uuid.UUID) -> str:
        return f"fios:decisions:{user_id}"

    async def _build_snapshot(self, user_id: uuid.UUID) -> dict[str, Any]:
        financial = FinancialService(self.db)
        summary = await financial.get_dashboard_summary(user_id)
        health = await financial.get_health_score(user_id)
        from app.core.filtering import FieldFilter, FilterOperator

        user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user_id))]
        loans_list, _ = await financial.loans.list(filters=user_filter, limit=100)
        user_loans = loans_list
        liabs_list, _ = await financial.liabilities.list(filters=user_filter, limit=100)
        user_liabs = liabs_list
        return {
            "loans": [
                {
                    "name": ln.name,
                    "type": ln.type,
                    "outstanding_balance": str(ln.outstanding_balance),
                    "apr": str(ln.apr),
                    "emi": str(ln.emi),
                    "status": ln.status,
                }
                for ln in user_loans[:20]
            ],
            "liabilities": [
                {
                    "name": liab.name,
                    "type": liab.type,
                    "outstanding_balance": str(liab.outstanding_balance),
                    "details": liab.details or {},
                }
                for liab in user_liabs[:20]
            ],
            "net_worth": str(summary["net_worth"]),
            "total_assets": str(summary["total_assets"]),
            "total_liabilities": str(summary["total_liabilities"]),
            "monthly_income": str(summary["monthly_income"]),
            "monthly_expense": str(summary["monthly_expense"]),
            "monthly_savings_rate": round(summary["monthly_savings_rate"], 4),
            "health_score": health["score"],
            "health_grade": health["grade"],
            "recent_transactions": [
                {
                    "type": t.type,
                    "category": t.category,
                    "amount": str(t.amount),
                    "date": t.transaction_date.isoformat(),
                }
                for t in summary["recent_transactions"][:10]
            ],
            "savings_goals": [
                {
                    "name": g.name,
                    "target": str(g.target_amount),
                    "progress": str(g.current_progress),
                }
                for g in summary["savings_goals_progress"][:10]
            ],
        }

    async def _load_history(self, key: str) -> list[dict[str, str]]:
        raw = await self.redis.lrange(key, 0, -1)  # type: ignore[misc]
        history: list[dict[str, str]] = []
        for item in raw:
            try:
                entry = json.loads(item)
            except (TypeError, ValueError):
                continue
            if entry.get("role") in ("user", "assistant") and entry.get("content"):
                history.append({"role": entry["role"], "content": entry["content"]})
        return history

    async def _append_history(self, key: str, *entries: dict[str, str]) -> None:
        if entries:
            await self.redis.rpush(key, *[json.dumps(e) for e in entries])  # type: ignore[misc]
            await self.redis.ltrim(key, -self.settings.chat_history_max_messages, -1)  # type: ignore[misc]
            await self.redis.expire(key, self.settings.chat_history_ttl_seconds)

    async def _log_decision(self, user_id: uuid.UUID, entry: dict[str, Any]) -> None:
        key = self._decisions_key(user_id)
        await self.redis.rpush(key, json.dumps(entry))  # type: ignore[misc]
        await self.redis.ltrim(key, -100, -1)  # type: ignore[misc]
        await self.redis.expire(key, self.settings.chat_history_ttl_seconds)

    async def send(
        self,
        user_id: uuid.UUID,
        *,
        agent: str,
        message: str,
        conversation_id: str = "default",
        extra_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if PROMPT_INJECTION_RE.search(message):
            from app.core.errors import BadRequestError

            raise BadRequestError(
                "Suspicious input pattern detected. Your message cannot be processed."
            )

        profile = AGENT_PROFILES.get(agent, AGENT_PROFILES["advisor"])
        started = time.perf_counter()
        reasoning: list[str] = []

        snapshot = await self._build_snapshot(user_id)
        if extra_context:
            snapshot["client_context"] = extra_context
        reasoning.append(
            "Loaded live financial snapshot from database "
            f"(net worth {snapshot['net_worth']}, health score {snapshot['health_score']})."
        )

        history_key = self._history_key(user_id, agent, conversation_id)
        history = await self._load_history(history_key)
        reasoning.append(f"Recalled {len(history)} prior messages from conversation memory.")

        system_prompt = BASE_SYSTEM_PROMPT.format(
            name=profile["name"],
            focus=profile["focus"],
            snapshot=json.dumps(snapshot, indent=2),
        )
        result = await self.llm.complete(
            system_prompt=system_prompt,
            messages=[*history, {"role": "user", "content": message}],
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        reasoning.append(
            f"Generated grounded response with {result.provider}:{result.model} in {latency_ms}ms."
        )

        await self._append_history(
            history_key,
            {"role": "user", "content": message},
            {"role": "assistant", "content": result.text},
        )

        response_id = f"msg-{uuid.uuid4().hex[:12]}"
        await self._log_decision(
            user_id,
            {
                "id": response_id,
                "agent": agent,
                "agent_name": profile["name"],
                "action": "council_reply",
                "question": message[:300],
                "answer_preview": result.text[:300],
                "provider": result.provider,
                "model": result.model,
                "latency_ms": latency_ms,
                "timestamp": utc_now().isoformat(),
            },
        )

        return {
            "id": response_id,
            "agent": agent,
            "conversation_id": conversation_id,
            "text": result.text,
            "reasoning_steps": reasoning,
            "provider": result.provider,
            "model": result.model,
            "latency_ms": latency_ms,
        }

    async def history(
        self, user_id: uuid.UUID, agent: str, conversation_id: str = "default"
    ) -> list[dict[str, str]]:
        return await self._load_history(self._history_key(user_id, agent, conversation_id))

    async def decisions(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        raw = await self.redis.lrange(self._decisions_key(user_id), 0, -1)  # type: ignore[misc]
        entries: list[dict[str, Any]] = []
        for item in raw:
            try:
                entries.append(json.loads(item))
            except (TypeError, ValueError):
                continue
        entries.reverse()  # newest first
        return entries


# --- Loan analysis -----------------------------------------------------------

LOAN_ANALYSIS_PROMPT = """You are a consumer-protection loan analyst. Analyze the loan \
agreement text supplied by the user and respond with ONLY a JSON object of this exact shape:
{
  "apr": <number, best-estimate effective annual percentage rate>,
  "term": "<loan term as a short string, e.g. '1 month' or '36 months'>",
  "cost": "<estimated total payback amount as a short string, e.g. '$1,488'>",
  "flags": [
    {"level": "high"|"medium"|"low", "title": "<short clause title>",
     "desc": "<one-sentence risk explanation quoting the clause>"}
  ],
  "recommendation": "<2-3 sentence plain-language verdict for the borrower>"
}
Flag predatory clauses aggressively: APR above 36%, compounding penalty interest, prepayment
penalties, arbitration/class-action waivers, balloon payments, wage assignments, confession of
judgment. Base every number strictly on the supplied text."""


class LoanAnalyzer:
    """LLM-backed analysis with a deterministic clause-extraction fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = LLMClient(settings)

    async def analyze(self, text: str) -> dict[str, Any]:
        if self.llm.is_configured:
            try:
                result = await self.llm.complete(
                    system_prompt=LOAN_ANALYSIS_PROMPT,
                    messages=[{"role": "user", "content": text[:24000]}],
                    temperature=0.1,
                    max_tokens=1200,
                    json_mode=True,
                )
                parsed = self._parse_llm_json(result.text)
                if parsed is not None:
                    parsed["engine"] = f"{result.provider}:{result.model}"
                    return parsed
                logger.warning("loan_analysis_bad_json", preview=result.text[:200])
            except Exception as exc:
                logger.warning("loan_analysis_llm_failed", error=str(exc))
        return self._heuristic(text)

    @staticmethod
    def _parse_llm_json(raw: str) -> dict[str, Any] | None:
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(cleaned)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        try:
            flags = [
                {
                    "level": str(f.get("level", "medium")).lower(),
                    "title": str(f.get("title", "Clause")),
                    "desc": str(f.get("desc", "")),
                }
                for f in data.get("flags", [])
                if isinstance(f, dict)
            ]
            return {
                "apr": float(data["apr"]),
                "term": str(data.get("term", "Unknown")),
                "cost": str(data.get("cost", "Unknown")),
                "flags": flags,
                "recommendation": str(data.get("recommendation", "")),
            }
        except (KeyError, TypeError, ValueError):
            return None

    def _heuristic(self, text: str) -> dict[str, Any]:
        """Deterministic clause extraction used when no LLM provider is reachable."""
        flags: list[dict[str, str]] = []
        lower = text.lower()

        apr = 0.0
        apr_match = re.search(
            r"(?:apr|annual percentage rate)[^0-9%]{0,40}?(\d+(?:\.\d+)?)\s*%",
            lower,
        ) or re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:apr|annual percentage rate)", lower)
        if apr_match:
            apr = float(apr_match.group(1))
        else:
            rate_match = re.search(r"interest[^0-9%]{0,40}?(\d+(?:\.\d+)?)\s*%", lower)
            if rate_match:
                apr = float(rate_match.group(1))

        term = "Unknown"
        term_match = re.search(r"(\d+)\s*[- ]?(month|week|year|day)s?\s*(?:term)?", lower)
        if term_match:
            term = f"{term_match.group(1)} {term_match.group(2)}(s)"

        cost = "Unknown"
        principal_match = re.search(r"principal[^$]{0,40}\$\s?([\d,]+(?:\.\d{2})?)", lower)
        interest_amt_match = re.search(
            r"(?:interest|finance)\s+charge[^$]{0,40}\$\s?([\d,]+(?:\.\d{2})?)", lower
        )
        if principal_match and interest_amt_match:
            total = float(principal_match.group(1).replace(",", "")) + float(
                interest_amt_match.group(1).replace(",", "")
            )
            cost = f"${total:,.2f}"

        if apr > 36:
            flags.append(
                {
                    "level": "high",
                    "title": "Predatory interest rate",
                    "desc": f"Effective APR of {apr}% far exceeds the 36% consumer guideline.",
                }
            )
        elif apr > 20:
            flags.append(
                {
                    "level": "medium",
                    "title": "Elevated interest rate",
                    "desc": f"APR of {apr}% is above typical secured-loan pricing.",
                }
            )
        if "prepayment" in lower and ("penalt" in lower or "may not" in lower):
            flags.append(
                {
                    "level": "high",
                    "title": "Prepayment restriction",
                    "desc": "The agreement penalizes or blocks early repayment of the balance.",
                }
            )
        if "arbitration" in lower:
            flags.append(
                {
                    "level": "medium",
                    "title": "Binding arbitration clause",
                    "desc": (
                        "Disputes are forced into arbitration, waiving court and "
                        "class-action rights."
                    ),
                }
            )
        if re.search(r"(weekly|daily)\s+(?:compound|interest|accru)", lower):
            flags.append(
                {
                    "level": "high",
                    "title": "High-frequency compounding",
                    "desc": (
                        "Penalty interest compounds weekly or daily, ballooning missed payments."
                    ),
                }
            )
        if "late" in lower and re.search(r"late[^$%]{0,60}(\$\s?[\d,]+|\d+(?:\.\d+)?\s*%)", lower):
            flags.append(
                {
                    "level": "medium",
                    "title": "Late payment penalties",
                    "desc": "Explicit late fees or penalty interest apply to overdue balances.",
                }
            )
        if not flags:
            flags.append(
                {
                    "level": "low",
                    "title": "No predatory clauses detected",
                    "desc": "Rule-based scan found no high-risk clause patterns in the text.",
                }
            )

        if apr > 36:
            recommendation = (
                f"This agreement carries an estimated {apr}% APR with "
                f"{len(flags)} flagged clause(s). It shows predatory-lending markers - "
                "strongly consider declining and exploring credit-union or "
                "personal-loan alternatives."
            )
        elif apr > 0:
            recommendation = (
                f"Estimated APR is {apr}%. Review the flagged clauses and compare at least "
                "two competing offers before signing."
            )
        else:
            recommendation = (
                "No explicit APR was detected in the text. Ask the lender for the effective "
                "APR in writing before signing anything."
            )

        return {
            "apr": apr,
            "term": term,
            "cost": cost,
            "flags": flags,
            "recommendation": recommendation,
            "engine": "heuristic",
        }
