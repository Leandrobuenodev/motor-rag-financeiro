# Roadmap

This roadmap keeps the project focused on a small grounded-QA workflow over financial documents.

## Implemented

- FastAPI endpoints for health, PDF upload, vector search, and grounded answers.
- Text extraction from PDFs with page-level provenance.
- Fixed-size character chunking with overlap and sequential chunk indexes.
- Local multilingual MiniLM embeddings, with deterministic simulated vectors limited to tests.
- PostgreSQL persistence with pgvector and exact L2 retrieval.
- Source filename, page number, and chunk index in search results.
- Automatic pgvector extension and table bootstrap for a clean Compose start.
- Explicit 4xx responses for unsupported, empty, invalid, and textless PDFs.
- Isolated integration-test schemas plus pytest, Ruff, and mypy validation.
- Local Docker configuration that excludes secrets from the image context.
- Lightweight browser interface for PDF ingestion and provenance-aware retrieval.
- Grounded answer generation with DeepSeek V4 Pro through OpenCode Go.
- Backend-validated source IDs mapped to trusted filename, page, and chunk metadata.
- Explicit insufficient-evidence behavior for missing or invalid supporting sources.

## Near-term retrieval improvements

- Build a small, versioned evaluation set for financial retrieval queries.
- Measure Portuguese and cross-language retrieval quality with the local embedding model.
- Evaluate citation correctness and insufficient-evidence behavior.
- Evaluate alternative chunk sizes and retrieval strategies using evidence from the evaluation set.
- Add bounded retry and rate-limit behavior if provider failures justify it.
- Introduce schema migrations only when further schema evolution justifies them.

## Intentionally outside the current scope

- OCR for scanned or image-only PDFs.
- Chat, conversation memory, or agents.
- Authentication and multi-user tenancy.
- Cloud deployment and infrastructure as code.
- Distributed services, messaging, or approximate vector indexes.
