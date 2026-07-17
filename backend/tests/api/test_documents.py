from __future__ import annotations

from pathlib import Path

import pytest
from app.domain.documents.service import chunk_text, score_chunks
from httpx import AsyncClient

from tests.helpers import auth_headers, login_user, register_user

LOAN_DOC = (
    "LOAN AGREEMENT\n\n"
    "The borrower agrees to repay the principal of $5,000 over 24 months.\n\n"
    "Interest accrues at an annual percentage rate of 18.5% compounded monthly.\n\n"
    "A late payment fee of $35 applies to any installment more than 5 days overdue.\n\n"
    "Prepayment is permitted without penalty after the sixth installment."
)

RECIPE_DOC = (
    "CLASSIC TOMATO SOUP\n\n"
    "Roast six tomatoes with olive oil until the skins blister.\n\n"
    "Blend with basil and cream, then simmer for twenty minutes.\n\n"
    "Season to taste and serve with toasted sourdough."
)


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await register_user(client, email=email)
    tokens = await login_user(client, email=email)
    return auth_headers(tokens)


@pytest.fixture(autouse=True)
def _tmp_upload_dir(tmp_path: Path, settings) -> None:  # type: ignore[no-untyped-def]
    settings.upload_dir = str(tmp_path / "uploads")


class TestDocumentUpload:
    async def test_upload_txt_extracts_and_chunks(self, client: AsyncClient) -> None:
        headers = await _auth(client, "docs@example.com")
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("loan.txt", LOAN_DOC.encode(), "text/plain")},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "loan.txt"
        assert body["type"] == "txt"
        meta = body["metadata_json"]
        assert meta["size_bytes"] == len(LOAN_DOC.encode())
        assert meta["num_chunks"] >= 1
        assert "LOAN AGREEMENT" in meta["chunks"][0]["text"]

        # The document also appears in the financial documents listing.
        listing = await client.get("/api/v1/financial/documents", headers=headers)
        assert listing.status_code == 200
        assert any(d["id"] == body["id"] for d in listing.json())

    async def test_upload_rejects_unsupported_type(self, client: AsyncClient) -> None:
        headers = await _auth(client, "docsbad@example.com")
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("virus.exe", b"MZ....", "application/octet-stream")},
            headers=headers,
        )
        assert response.status_code == 415

    async def test_upload_rejects_empty_file(self, client: AsyncClient) -> None:
        headers = await _auth(client, "docsempty@example.com")
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
            headers=headers,
        )
        assert response.status_code == 400

    async def test_upload_stores_classification_metadata(self, client: AsyncClient) -> None:
        headers = await _auth(client, "docsclass@example.com")
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("loan.txt", LOAN_DOC.encode(), "text/plain")},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        meta = response.json()["metadata_json"]
        assert meta["domain"] == "finance"
        assert meta["category"] == "Loan Agreement"
        assert 0 < meta["confidence"] <= 1
        assert meta["filename"] == "loan.txt"
        # Pre-existing metadata survives alongside the new keys.
        assert meta["file_hash"] and meta["num_chunks"] >= 1

    async def test_upload_rejects_non_financial_document(
        self, client: AsyncClient, tmp_path: Path
    ) -> None:
        headers = await _auth(client, "docsrecipe@example.com")
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("soup.txt", RECIPE_DOC.encode(), "text/plain")},
            headers=headers,
        )
        assert response.status_code == 400
        assert "only financial documents" in response.json()["detail"]

        # Nothing was persisted: no row, and no orphaned file on disk.
        listing = await client.get("/api/v1/financial/documents", headers=headers)
        assert listing.json() == []
        uploads = tmp_path / "uploads"
        stored = list(uploads.rglob("*")) if uploads.exists() else []
        assert [p for p in stored if p.is_file()] == []

    async def test_search_returns_real_scores(self, client: AsyncClient) -> None:
        headers = await _auth(client, "docsearch@example.com")
        upload = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("loan.txt", LOAN_DOC.encode(), "text/plain")},
            headers=headers,
        )
        doc_id = upload.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/search",
            params={"query": "late payment fee overdue"},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["results"], "expected at least one matching chunk"
        top = body["results"][0]
        assert "late payment fee" in top["text"].lower()
        assert 0 < top["score"] <= 1

    async def test_download_and_delete(self, client: AsyncClient) -> None:
        headers = await _auth(client, "docdel@example.com")
        upload = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("loan.txt", LOAN_DOC.encode(), "text/plain")},
            headers=headers,
        )
        doc_id = upload.json()["id"]
        stored_path = Path(upload.json()["file_path"])
        assert stored_path.is_file()

        download = await client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
        assert download.status_code == 200
        assert download.content == LOAN_DOC.encode()

        delete = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
        assert delete.status_code == 204
        assert not stored_path.exists()

        missing = await client.get(f"/api/v1/documents/{doc_id}/search?query=fee", headers=headers)
        assert missing.status_code == 404

    async def test_cannot_touch_other_users_document(self, client: AsyncClient) -> None:
        headers_a = await _auth(client, "owner-a@example.com")
        upload = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("loan.txt", LOAN_DOC.encode(), "text/plain")},
            headers=headers_a,
        )
        doc_id = upload.json()["id"]

        headers_b = await _auth(client, "owner-b@example.com")
        for method, url in (
            ("GET", f"/api/v1/documents/{doc_id}/search?query=fee"),
            ("GET", f"/api/v1/documents/{doc_id}/download"),
            ("DELETE", f"/api/v1/documents/{doc_id}"),
        ):
            response = await client.request(method, url, headers=headers_b)
            assert response.status_code == 404, f"{method} {url} leaked across users"


class TestChunkingUnit:
    def test_chunk_text_splits_and_overlaps(self) -> None:
        long_paragraph = "word " * 500  # ~2500 chars, forces hard wrapping
        chunks = chunk_text(long_paragraph)
        assert len(chunks) > 1
        assert all(len(c) <= 900 for c in chunks)

    def test_chunk_text_empty(self) -> None:
        assert chunk_text("   \n\n  ") == []

    def test_score_chunks_ranks_relevant_first(self) -> None:
        chunks = [
            "interest accrues at an annual percentage rate",
            "the borrower shall provide proof of insurance",
            "late payment fee applies to overdue installments",
        ]
        ranked = score_chunks("late fee overdue payment", chunks)
        assert ranked[0][0] == 2
        assert ranked[0][1] > 0
