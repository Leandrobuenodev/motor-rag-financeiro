# Roadmap

This roadmap keeps the project focused on financial document ingestion and vector retrieval. Answer generation is a separate possible iteration, not part of the current system.

## Implemented

- FastAPI endpoints for health, PDF upload, and vector search.
- Text extraction from PDFs with page-level provenance.
- Fixed-size character chunking with overlap and sequential chunk indexes.
- Explicit simulated and Azure OpenAI embedding providers.
- PostgreSQL persistence with pgvector and exact L2 retrieval.
- Source filename, page number, and chunk index in search results.
- Automatic pgvector extension and table bootstrap for a clean Compose start.
- Explicit 4xx responses for unsupported, empty, invalid, and textless PDFs.
- Isolated integration-test schemas plus pytest, Ruff, and mypy validation.
- Local Docker configuration that excludes secrets from the image context.
- Lightweight browser interface for PDF ingestion and provenance-aware retrieval.

## Near-term retrieval improvements

- Build a small, versioned evaluation set for financial retrieval queries.
- Measure retrieval quality with a real embedding provider.
- Add batching, timeout, and bounded retry behavior to Azure embedding calls.
- Evaluate alternative chunk sizes and retrieval strategies using evidence from the evaluation set.
- Introduce schema migrations only when further schema evolution justifies them.

## Possible later cycle

- Generate grounded answers from retrieved chunks.
- Return citations that map generated claims to source filename and page.
- Add explicit insufficient-evidence behavior and evaluate answer grounding.

These capabilities would extend the retrieval foundation into a RAG workflow. They are not implemented today.

## Intentionally outside the current scope

- OCR for scanned or image-only PDFs.
- Chat or agents.
- Authentication and multi-user tenancy.
- Cloud deployment and infrastructure as code.
- Distributed services, messaging, or approximate vector indexes.
