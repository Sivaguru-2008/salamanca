from __future__ import annotations

import pytest
from app.domain.ai import service as ai_service
from app.domain.ai.llm import LLMClient, LLMResult
from httpx import AsyncClient

from tests.helpers import auth_headers, login_user, register_user

SAMPLE_LOAN_TEXT = """LOAN AGREEMENT AND TERM SHEET
Lender: QuickCapital Payday Services
Principal Loan Amount: $1,200.00
Maturity Date: 1 month term
Interest Details: Flat interest charge of $288.00 due at maturity.
Equivalent annual percentage rate (APR): 240.0%
Late Payment Terms: A penalty fee of $50.00 plus an additional 15% interest accrues weekly.
Prepayment Penalty: Borrower may NOT pay back early unless full interest is satisfied.
Arbitration: Borrower agrees to settle any dispute via binding arbitration."""


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await register_user(client, email=email)
    tokens = await login_user(client, email=email)
    return auth_headers(tokens)


class TestChat:
    async def test_chat_unconfigured_falls_back_to_offline_reply(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth(client, "chat503@example.com")
        response = await client.post(
            "/api/v1/chat",
            json={"agent": "budget", "message": "How is my budget?"},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "offline"
        assert body["model"] == "rule-based"
        assert "offline mode" in body["text"]

    async def test_chat_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/chat", json={"message": "hi"})
        assert response.status_code == 401

    async def test_chat_happy_path_with_mocked_llm(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        async def fake_complete(self: LLMClient, **kwargs: object) -> LLMResult:
            captured.update(kwargs)
            return LLMResult(text="Cut lifestyle spend by 10%.", provider="gemini", model="test")

        monkeypatch.setattr(LLMClient, "complete", fake_complete)
        monkeypatch.setattr(LLMClient, "is_configured", property(lambda self: True))

        headers = await _auth(client, "chatok@example.com")
        response = await client.post(
            "/api/v1/chat",
            json={
                "agent": "budget",
                "message": "Where should I cut spending?",
                "conversation_id": "conv-1",
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["text"] == "Cut lifestyle spend by 10%."
        assert body["agent"] == "budget"
        assert body["provider"] == "gemini"
        assert len(body["reasoning_steps"]) == 3
        # The system prompt must carry the live snapshot, not canned data.
        assert "net_worth" in str(captured["system_prompt"])

        # Conversation memory: history now holds both turns.
        history = await client.get(
            "/api/v1/chat/budget/history",
            params={"conversation_id": "conv-1"},
            headers=headers,
        )
        assert history.status_code == 200
        messages = history.json()["messages"]
        assert [m["role"] for m in messages] == ["user", "assistant"]

        # Decision log records the exchange.
        decisions = await client.get("/api/v1/chat/decisions", headers=headers)
        assert decisions.status_code == 200
        entries = decisions.json()
        assert len(entries) == 1
        assert entries[0]["agent"] == "budget"
        assert entries[0]["action"] == "council_reply"

    async def test_chat_memory_passed_to_llm(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[dict[str, str]]] = []

        async def fake_complete(self: LLMClient, **kwargs: object) -> LLMResult:
            calls.append(list(kwargs["messages"]))  # type: ignore[arg-type]
            return LLMResult(text=f"reply-{len(calls)}", provider="groq", model="test")

        monkeypatch.setattr(LLMClient, "complete", fake_complete)
        monkeypatch.setattr(LLMClient, "is_configured", property(lambda self: True))

        headers = await _auth(client, "chatmem@example.com")
        for question in ("first question", "second question"):
            response = await client.post(
                "/api/v1/chat",
                json={"agent": "advisor", "message": question},
                headers=headers,
            )
            assert response.status_code == 200

        # Second call must include the first exchange as memory.
        assert len(calls[1]) == 3
        assert calls[1][0]["content"] == "first question"
        assert calls[1][1]["content"] == "reply-1"
        assert calls[1][2]["content"] == "second question"


class TestLoanAnalysis:
    async def test_heuristic_analysis_without_llm(self, client: AsyncClient) -> None:
        headers = await _auth(client, "loanh@example.com")
        response = await client.post(
            "/api/v1/loan-analysis/analyze",
            json={"text": SAMPLE_LOAN_TEXT},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["engine"] == "heuristic"
        assert body["apr"] == 240.0
        assert body["cost"] == "$1,488.00"
        titles = [f["title"] for f in body["flags"]]
        assert "Predatory interest rate" in titles
        assert "Prepayment restriction" in titles
        assert "Binding arbitration clause" in titles

    async def test_llm_analysis_parsed(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llm_json = (
            '{"apr": 240.0, "term": "1 month", "cost": "$1,488",'
            ' "flags": [{"level": "high", "title": "Payday APR", "desc": "240% APR."}],'
            ' "recommendation": "Decline this offer."}'
        )

        async def fake_complete(self: LLMClient, **kwargs: object) -> LLMResult:
            return LLMResult(text=llm_json, provider="gemini", model="test-model")

        monkeypatch.setattr(LLMClient, "complete", fake_complete)
        monkeypatch.setattr(LLMClient, "is_configured", property(lambda self: True))

        headers = await _auth(client, "loanllm@example.com")
        response = await client.post(
            "/api/v1/loan-analysis/analyze",
            json={"text": SAMPLE_LOAN_TEXT},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["engine"] == "gemini:test-model"
        assert body["recommendation"] == "Decline this offer."
        assert body["flags"][0]["title"] == "Payday APR"


class TestHeuristicUnit:
    def test_parse_llm_json_with_code_fence(self) -> None:
        raw = (
            '```json\n{"apr": 12.5, "term": "36 months", "cost": "$12,000",'
            ' "flags": [], "recommendation": "ok"}\n```'
        )
        parsed = ai_service.LoanAnalyzer._parse_llm_json(raw)
        assert parsed is not None
        assert parsed["apr"] == 12.5

    def test_parse_llm_json_rejects_garbage(self) -> None:
        assert ai_service.LoanAnalyzer._parse_llm_json("not json at all") is None
