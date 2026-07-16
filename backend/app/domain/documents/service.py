"""File-backed document ingestion for the RAG explorer and loan analyzer.

Files land on local disk under ``settings.upload_dir``; extracted text is
chunked and persisted in the document row's ``metadata_json`` so retrieval
needs no extra vector store. Chunk search scores are cosine similarity over
term-frequency vectors — computed, never fabricated.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import structlog
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import (
    BadRequestError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.domain.financial.service import FinancialService
from app.infra.db.models.financial_document import FinancialDocument

logger = structlog.get_logger(__name__)

TEXT_EXTENSIONS = {".txt", ".csv", ".md", ".json", ".log", ".tsv"}
PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | PDF_EXTENSIONS

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
MAX_STORED_CHUNKS = 200

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def chunk_text(text: str) -> list[str]:
    """Split on paragraph boundaries first, then hard-wrap long runs with overlap."""
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    if not normalized:
        return []

    chunks: list[str] = []
    buffer = ""
    for paragraph in re.split(r"\n{2,}", normalized):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if len(candidate) <= CHUNK_SIZE:
            buffer = candidate
            continue
        if buffer:
            chunks.append(buffer)
        while len(paragraph) > CHUNK_SIZE:
            chunks.append(paragraph[:CHUNK_SIZE])
            paragraph = paragraph[CHUNK_SIZE - CHUNK_OVERLAP :]
        buffer = paragraph
    if buffer:
        chunks.append(buffer)
    return chunks[:MAX_STORED_CHUNKS]


def score_chunks(query: str, chunks: list[str]) -> list[tuple[int, float]]:
    """Cosine similarity between query and chunk term-frequency vectors."""
    query_tf = Counter(_tokenize(query))
    if not query_tf:
        return []
    query_norm = math.sqrt(sum(v * v for v in query_tf.values()))

    scored: list[tuple[int, float]] = []
    for index, chunk in enumerate(chunks):
        chunk_tf = Counter(_tokenize(chunk))
        if not chunk_tf:
            continue
        dot = sum(query_tf[t] * chunk_tf.get(t, 0) for t in query_tf)
        if dot == 0:
            continue
        chunk_norm = math.sqrt(sum(v * v for v in chunk_tf.values()))
        scored.append((index, dot / (query_norm * chunk_norm)))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


class DocumentsService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.financial = FinancialService(db)

    def _user_dir(self, user_id: uuid.UUID) -> Path:
        base = Path(self.settings.upload_dir) / str(user_id)
        base.mkdir(parents=True, exist_ok=True)
        return base

    async def upload(self, user_id: uuid.UUID, file: UploadFile) -> FinancialDocument:
        filename = Path(file.filename or "upload").name
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise UnsupportedMediaTypeError(
                f"Unsupported file type '{extension or 'unknown'}'. "
                f"Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            )

        content = await file.read()
        if len(content) > self.settings.max_upload_bytes:
            limit_mb = self.settings.max_upload_bytes // (1024 * 1024)
            raise PayloadTooLargeError(f"File exceeds the {limit_mb} MB upload limit.")
        if not content:
            raise BadRequestError("Uploaded file is empty.")

        stored_name = f"{uuid.uuid4().hex}{extension}"
        target = self._user_dir(user_id) / stored_name
        target.write_bytes(content)

        text = self._extract_text(target, extension)
        chunks = chunk_text(text)

        document = await self.financial.create_document(
            user_id,
            {
                "name": filename,
                "type": extension.lstrip("."),
                "file_path": str(target),
                "metadata_json": {
                    "size_bytes": len(content),
                    "content_type": file.content_type,
                    "text_length": len(text),
                    "num_chunks": len(chunks),
                    "chunks": [{"index": i, "text": chunk} for i, chunk in enumerate(chunks)],
                },
            },
            actor_id=user_id,
        )
        logger.info(
            "document_ingested",
            document_id=str(document.id),
            size_bytes=len(content),
            chunks=len(chunks),
        )
        return document

    @staticmethod
    def _extract_text(path: Path, extension: str) -> str:
        if extension in TEXT_EXTENSIONS:
            return path.read_bytes().decode("utf-8", errors="ignore")
        if extension in PDF_EXTENSIONS:
            try:
                from pypdf import PdfReader

                reader = PdfReader(str(path))
                return "\n\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as exc:
                logger.warning("pdf_extraction_failed", path=str(path), error=str(exc))
                return ""
        return ""

    async def get_owned(self, user_id: uuid.UUID, doc_id: uuid.UUID) -> FinancialDocument:
        document = await self.financial.documents.get(doc_id)
        if document is None or document.user_id != user_id:
            raise NotFoundError("Financial document not found.")
        return document

    async def search(
        self, user_id: uuid.UUID, doc_id: uuid.UUID, query: str, limit: int = 5
    ) -> dict[str, Any]:
        document = await self.get_owned(user_id, doc_id)
        chunks = [c.get("text", "") for c in (document.metadata_json or {}).get("chunks", [])]
        matches = score_chunks(query, chunks)[:limit]
        return {
            "document_id": str(document.id),
            "document_name": document.name,
            "query": query,
            "results": [
                {"index": index, "text": chunks[index], "score": round(score, 4)}
                for index, score in matches
            ],
        }

    async def delete(self, user_id: uuid.UUID, doc_id: uuid.UUID) -> None:
        document = await self.get_owned(user_id, doc_id)
        file_path = Path(document.file_path)
        await self.financial.delete_document(user_id, doc_id)
        try:
            if file_path.is_file():
                file_path.unlink()
        except OSError as exc:
            logger.warning("document_file_cleanup_failed", path=str(file_path), error=str(exc))
