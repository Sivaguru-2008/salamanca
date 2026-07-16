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
    ConflictError,
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


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2, strict=True))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


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

        # Signature/MIME Validation
        if extension in PDF_EXTENSIONS and not content.startswith(b"%PDF"):
            raise BadRequestError("Invalid PDF signature or structure.")
        elif extension in TEXT_EXTENSIONS and b"\x00" in content:
            raise BadRequestError("Binary content is not supported for text formats.")

        # Duplicate Detection using SHA-256
        import hashlib

        file_hash = hashlib.sha256(content).hexdigest()
        from app.core.filtering import FieldFilter, FilterOperator

        user_filter = [FieldFilter(field="user_id", operator=FilterOperator.EQ, value=str(user_id))]
        existing_docs, _ = await self.financial.documents.list(filters=user_filter, limit=1000)
        for doc in existing_docs:
            if doc.metadata_json and doc.metadata_json.get("file_hash") == file_hash:
                raise ConflictError("A document with identical content has already been uploaded.")

        stored_name = f"{uuid.uuid4().hex}{extension}"
        target = self._user_dir(user_id) / stored_name
        target.write_bytes(content)

        text = self._extract_text(target, extension)
        chunks = chunk_text(text)

        # Generate semantic embeddings for each chunk if Gemini is configured
        from app.domain.ai.llm import LLMClient

        llm_client = LLMClient(self.settings)
        chunks_data = []
        if llm_client.settings.gemini_api_key:

            async def _embed_chunk(i: int, chunk: str) -> dict[str, Any]:
                try:
                    emb = await llm_client.embed_text(chunk)
                    return {"index": i, "text": chunk, "embedding": emb}
                except Exception as exc:
                    logger.warning("chunk_embedding_failed", index=i, error=str(exc))
                    return {"index": i, "text": chunk}

            import asyncio

            chunks_data = await asyncio.gather(
                *[_embed_chunk(i, chunk) for i, chunk in enumerate(chunks)]
            )
        else:
            chunks_data = [{"index": i, "text": chunk} for i, chunk in enumerate(chunks)]

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
                    "file_hash": file_hash,
                    "chunks": chunks_data,
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
        chunks_meta = (document.metadata_json or {}).get("chunks", [])

        # Check if chunks have semantic embeddings
        has_embeddings = all("embedding" in c for c in chunks_meta) if chunks_meta else False
        from app.domain.ai.llm import LLMClient

        llm_client = LLMClient(self.settings)

        scored: list[tuple[int, float]] = []
        if has_embeddings and llm_client.settings.gemini_api_key:
            try:
                query_emb = await llm_client.embed_text(query)
                for c in chunks_meta:
                    similarity = cosine_similarity(query_emb, c["embedding"])
                    if similarity > 0:
                        scored.append((c["index"], similarity))
                scored.sort(key=lambda item: item[1], reverse=True)
            except Exception as exc:
                logger.warning("semantic_search_failed_falling_back", error=str(exc))
                scored = []

        if not scored:
            # Fallback to lexical term-frequency search
            chunks = [c.get("text", "") for c in chunks_meta]
            scored = score_chunks(query, chunks)

        matches = scored[:limit]
        return {
            "document_id": str(document.id),
            "document_name": document.name,
            "query": query,
            "results": [
                {
                    "index": index,
                    "text": chunks_meta[index].get("text", ""),
                    "score": round(score, 4),
                }
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
