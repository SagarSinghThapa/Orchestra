from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.research.chunking.base import DocumentChunk
from app.research.chunking.normalizer import TextNormalizer
from app.research.chunking.recursive import RecursiveTokenChunker
from app.research.embeddings.base import EmbeddingProvider
from app.research.embeddings.provider import get_embedding_provider
from app.research.exceptions import ParserError, VectorStoreError
from app.research.parsers.registry import ParserRegistry
from app.research.storage.base import StorageBackend
from app.research.storage.local import LocalStorageBackend
from app.research.vectorstore.qdrant import QdrantVectorStore


class IngestionService:
    """
    Coordinates bounded synchronous ingestion across document storage, format parsing,
    NFC normalization, page-bounded chunking, embedding generation, and Qdrant vector storage.
    
    Guarantees:
    - Status State Machine: uploaded -> processing -> indexed (or failed with sanitized message).
    - Failure compensation: cleans up partial vectors on failure and records failed state.
    - Source preservation: original file on disk is retained on failure to permit retry/re-indexing.
    - Idempotent deletion: deletes Qdrant vectors, storage file, and DB record cleanly.
    - Purge-first re-index: purges stale vectors before regenerating new ones.
    """

    def __init__(
        self,
        db: Session,
        storage: Optional[StorageBackend] = None,
        parser_registry: Optional[ParserRegistry] = None,
        normalizer: Optional[TextNormalizer] = None,
        chunker: Optional[RecursiveTokenChunker] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_store: Optional[QdrantVectorStore] = None,
    ) -> None:
        self.db = db
        self.storage = storage or LocalStorageBackend()
        self.parser_registry = parser_registry or ParserRegistry()
        self.normalizer = normalizer or TextNormalizer()
        self.chunker = chunker or RecursiveTokenChunker()
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.vector_store = vector_store or QdrantVectorStore()

    async def process_document(self, document_id: int) -> Document:
        """
        Executes synchronous document ingestion lifecycle.
        Transitions status from uploaded/failed -> processing -> indexed or failed.
        """
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise KeyError(f"Document with ID {document_id} not found")

        # Status transition to processing
        document.status = DocumentStatus.PROCESSING.value
        document.error_message = None
        self.db.commit()
        self.db.refresh(document)

        try:
            # 1. Ensure Qdrant collection is ready with correct dimensions
            await self.vector_store.ensure_collection(
                dimension=self.embedding_provider.dimension
            )

            # 2. Read raw content from storage backend
            content = self.storage.read(document.storage_key)

            # 3. Parse content into page units
            parser = self.parser_registry.get_parser_for_filename(document.original_filename)
            extracted_doc = parser.parse(content, document.original_filename)

            # 4. Chunk document page-by-page (chunks never cross page boundaries)
            chunks: list[DocumentChunk] = self.chunker.chunk_document(
                extracted_doc,
                document_id=document.id,
                project_id=document.project_id,
            )

            if not chunks:
                raise ParserError("Document contains no extractable text; OCR is not supported.")

            # 5. Generate embeddings for chunk texts
            chunk_texts = [c.text for c in chunks]
            vectors = await self.embedding_provider.embed_documents(chunk_texts)

            # 6. Upsert points into Qdrant collection
            await self.vector_store.upsert_chunks(chunks, vectors)

            # 7. Finalize status to INDEXED
            now = datetime.utcnow()
            if document.updated_at and now <= document.updated_at:
                now = document.updated_at + timedelta(milliseconds=50)
            document.updated_at = now
            document.status = DocumentStatus.INDEXED.value
            document.chunk_count = len(chunks)
            document.error_message = None
            self.db.commit()
            self.db.refresh(document)
            return document

        except Exception as exc:
            # Failure compensation: clean up any partially upserted vectors
            try:
                await self.vector_store.delete_document_vectors(
                    project_id=document.project_id,
                    document_id=document.id,
                )
            except Exception:
                pass  # Do not mask original exception

            # Record failed status
            document.status = DocumentStatus.FAILED.value
            document.chunk_count = 0
            document.error_message = str(exc)[:1000]
            self.db.commit()
            self.db.refresh(document)
            return document

    async def delete_document(self, project_id: int, document_id: int) -> None:
        """
        Deletes a document: purges Qdrant vectors, deletes disk file idempotently, and deletes DB row.
        """
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.project_id == project_id)
            .first()
        )
        if not document:
            raise KeyError(f"Document with ID {document_id} under project {project_id} not found")

        # 1. Purge Qdrant vectors
        await self.vector_store.delete_document_vectors(
            project_id=project_id,
            document_id=document_id,
        )

        # 2. Delete storage file idempotently
        self.storage.delete(document.storage_key)

        # 3. Delete database record
        self.db.delete(document)
        self.db.commit()

    async def reindex_document(self, project_id: int, document_id: int) -> Document:
        """
        Re-indexes an existing document: purges old vectors first, then re-runs process_document.
        """
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.project_id == project_id)
            .first()
        )
        if not document:
            raise KeyError(f"Document with ID {document_id} under project {project_id} not found")

        # 1. Purge existing vectors first
        await self.vector_store.delete_document_vectors(
            project_id=project_id,
            document_id=document_id,
        )

        # 2. Reset status to processing
        document.status = DocumentStatus.PROCESSING.value
        document.error_message = None
        self.db.commit()
        self.db.refresh(document)

        # 3. Re-process document
        return await self.process_document(document.id)
