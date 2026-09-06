# Grounded Financial Document QA

A focused proof of concept that ingests text-based financial PDFs, retrieves relevant passages with local multilingual embeddings and pgvector, and generates concise answers backed by trusted source metadata.

## Project status

This repository is a small RAG proof of concept for portfolio demonstration. It implements one explicit path from document ingestion to a grounded answer; it is not a chat product or a production platform.

## What it does

- Accepts text-based PDF uploads through FastAPI.
- Extracts text page by page and creates fixed-size overlapping chunks.
- Generates 384-dimensional multilingual MiniLM embeddings locally through ONNX.
- Stores chunks and vectors in PostgreSQL with pgvector.
- Retrieves the nearest passages using exact L2 distance.
- Sends only the question, retrieved passage text, and temporary source IDs to DeepSeek V4 Pro through OpenCode Go.
- Maps the model's source IDs back to filename, page, and chunk metadata held by the backend.
- Shows the grounded answer, verified sources, and expandable retrieval evidence in a framework-free browser interface.

## What it intentionally does not do

- OCR or extraction from scanned/image-only PDFs.
- Chat history, agents, tools, or autonomous workflows.
- Authentication, authorization, or multi-user isolation.
- Claim-level citation spans or automated grounding evaluation.
- Approximate vector indexes, distributed services, or cloud deployment.
- Financial advice, auditing, or document interpretation beyond the supplied evidence.

## Architecture and flow

```text
POST /upload
  -> validate PDF
  -> extract page text
  -> character chunks with overlap
  -> local multilingual MiniLM passage embeddings
  -> PostgreSQL / pgvector

POST /answer
  -> local multilingual MiniLM query embedding
  -> exact pgvector L2 retrieval
  -> top passages + internal source IDs
  -> DeepSeek V4 Pro through OpenCode Go
  -> validate returned source IDs
  -> resolve trusted filename/page/chunk metadata
  -> grounded answer + sources + retrieved passages
```

The existing `POST /search` endpoint remains available for inspecting retrieval without generation.

The code uses lightweight layers:

- `domain`: document and chunking rules.
- `application`: upload, search, and grounded-answer orchestration.
- `infrastructure`: local embeddings, answer-provider HTTP adapter, SQLAlchemy, and pgvector.
- `api`: FastAPI routes and Pydantic request/response models.
- `static`: the HTML, CSS, and JavaScript interface served by FastAPI.

## Technology choices

- Python 3.12 and FastAPI for the HTTP application.
- SQLAlchemy asyncio and asyncpg for database access.
- PostgreSQL 17 with pgvector for vector persistence and exact search.
- `paraphrase-multilingual-MiniLM-L12-v2` through FastEmbed/ONNX for local Portuguese/English retrieval.
- DeepSeek V4 Pro through the OpenCode Go OpenAI-compatible chat-completions endpoint for generation.
- pypdf for PDFs that already contain a text layer.
- Pydantic Settings for environment configuration.
- Plain HTML, CSS, and JavaScript for a single-service portfolio interface.
- pytest, Ruff, and mypy for automated checks.

The application creates the pgvector extension and its one-table schema during startup. This direct bootstrap is proportional to the current PoC; a migration tool can be introduced if schema evolution justifies it.

## Quick start

Requirements: Docker with Docker Compose and an OpenCode Go API key with access to `deepseek-v4-pro`.

```bash
git clone https://github.com/Leandrobuenodev/motor-rag-financeiro.git
cd motor-rag-financeiro
cp .env.example .env
```

Set `OPENCODE_GO_API_KEY` in the local `.env`, then start the stack:

```bash
docker compose up -d --build --wait
curl http://localhost:8000/health
```

The first image build downloads the local embedding model. Expected health response:

```json
{
  "status": "ok",
  "service": "motor-rag-financeiro",
  "embedding_provider": "local",
  "answer_provider": "opencode-go",
  "answer_model": "deepseek-v4-pro"
}
```

Open:

- Portfolio interface: <http://localhost:8000/>
- Swagger UI: <http://localhost:8000/docs>
- Health endpoint: <http://localhost:8000/health>

Without `OPENCODE_GO_API_KEY`, upload and raw vector search still work, while `POST /answer` returns a clear `503` configuration response.

### Existing development volume

This version changes stored vectors from 1,536 dimensions to 384 dimensions. PostgreSQL cannot mix those schemas. If a volume was created by an earlier version of this PoC, explicitly recreate that local-only data before starting:

```bash
docker compose down -v
docker compose up -d --build --wait
```

This removes previously indexed local chunks. A fresh clone has no migration step.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | Compose-local PostgreSQL URL | Async SQLAlchemy connection string |
| `TEST_DATABASE_URL` | PostgreSQL on `localhost:5432` | Database where tests create isolated temporary schemas |
| `EMBEDDING_PROVIDER` | `local` | Uses `local`; `simulated` is retained for automated tests only |
| `LOCAL_EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Local FastEmbed/ONNX model |
| `ANSWER_PROVIDER` | `opencode-go` | Configured answer-provider adapter |
| `ANSWER_MODEL` | `deepseek-v4-pro` | OpenCode Go model identifier |
| `OPENCODE_GO_API_KEY` | empty | Server-side credential required by `POST /answer` |
| `OPENCODE_GO_ENDPOINT` | OpenCode Go chat-completions URL | Provider endpoint |
| `ANSWER_TIMEOUT_SECONDS` | `60` | Outbound generation request timeout |

### Local embeddings

The default local provider uses `paraphrase-multilingual-MiniLM-L12-v2`, a 384-dimensional model covering roughly 50 languages. FastEmbed exposes distinct query and passage paths, and the adapter normalizes every vector before storage or search. This supports semantic matching between Portuguese document text and Portuguese or English questions without sending document text to an embedding API.

### Simulated embeddings

`EMBEDDING_PROVIDER=simulated` produces deterministic hash-derived vectors so tests can exercise ingestion, persistence, and retrieval without downloading a model. These vectors **do not provide semantic similarity** and are not the portfolio demo mode.

### Answer generation

`ANSWER_PROVIDER=opencode-go` sends a constrained prompt to `deepseek-v4-pro`. The model sees the user's question and the retrieved passage text, labeled only with temporary integer source IDs. It does not receive filenames, page numbers, chunk IDs, the full PDF, or unrelated stored passages.

The provider must return a concise answer, source IDs, and an insufficient-evidence flag. The backend rejects an answer if any cited ID is outside the retrieved set. Only then does it resolve source IDs to database-owned provenance. This boundary prevents model-supplied filenames or page numbers from becoming trusted citations.

## Use the API

Upload a text-based PDF:

```bash
curl -X POST http://localhost:8000/upload \
  -H "accept: application/json" \
  -F "file=@/absolute/path/to/report.pdf;type=application/pdf"
```

Ask a grounded question:

```bash
curl -X POST http://localhost:8000/answer \
  -H "content-type: application/json" \
  -d '{"question":"Qual foi o índice de Basileia no período?","top_k":5}'
```

Representative response:

```json
{
  "answer": "O índice de Basileia foi de 14,2% no período.",
  "insufficient_evidence": false,
  "citations": [
    {
      "source_id": 1,
      "chunk_id": "8bc0f6d8-7b13-4cef-b318-57d3926bdf6a",
      "document_id": "23003d52-a0f4-4115-bd50-d2f89757bfd0",
      "source_filename": "quarterly-report.pdf",
      "page": 2,
      "chunk_index": 1
    }
  ],
  "retrieved_passages": [
    {
      "chunk_id": "8bc0f6d8-7b13-4cef-b318-57d3926bdf6a",
      "document_id": "23003d52-a0f4-4115-bd50-d2f89757bfd0",
      "source_filename": "quarterly-report.pdf",
      "page": 2,
      "chunk_index": 1,
      "text": "O índice de Basileia encerrou o período em 14,2%.",
      "l2_distance": 0.31
    }
  ]
}
```

`l2_distance` is Euclidean distance between normalized stored and query vectors. Lower means closer for this embedding model; it is not a confidence score.

Inspect retrieval without generation:

```bash
curl -X POST http://localhost:8000/search \
  -H "content-type: application/json" \
  -d '{"query":"Basel ratio","top_k":3}'
```

## API endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Browser interface for upload and grounded QA |
| `GET` | `/health` | Process liveness and configured provider names |
| `POST` | `/upload` | Extract, chunk, embed, and persist one PDF |
| `POST` | `/search` | Return nearest chunks, provenance, and L2 distance |
| `POST` | `/answer` | Retrieve evidence and return a grounded answer with trusted sources |

Upload returns `415` for a non-PDF filename, `400` for an empty file, and `422` for an invalid PDF or one without extractable text. Provider configuration failures return `503`; upstream generation failures return `502` without exposing provider details or credentials.

## Tests and static checks

Start PostgreSQL, create a Python 3.12 virtual environment, and install the pinned dependencies:

```bash
docker compose up -d db
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -v
python -m ruff check .
python -m mypy app/ tests/ --ignore-missing-imports
```

Integration tests override the local embedding model with deterministic vectors, mock the answer provider, and create a unique temporary PostgreSQL schema. They do not call OpenCode Go and do not delete data from the application schema.

## Design decisions and trade-offs

- Chunking is character-based (`1,000` characters with `200` overlap) and restarts per page. It is transparent but not language-aware.
- Chunk indexes remain sequential across all extracted pages in an upload; page numbers are 1-based.
- Upload embeds all chunks from one document as a batch. CPU inference runs in a worker thread so it does not block the event loop.
- Search is an exact table scan ordered by L2 distance. This is appropriate for a small PoC dataset and avoids an unjustified ANN index.
- The top retrieved passages are the complete generation context. There is no hidden document-wide context or conversation memory.
- Citations identify supporting chunks, not sentence-level claim spans.
- Files are processed in memory. The original PDF is not stored; extracted text and vectors are persisted.
- The framework-free interface keeps the API and visual demo in one service.

## Known limitations

- pypdf extraction can lose layout, table structure, or reading order.
- Scanned/image-only PDFs are rejected because OCR is outside scope.
- There is no retrieval or answer-quality evaluation set yet.
- There is no reranker, hybrid keyword search, document filter, or deduplication.
- Requests have a timeout but no automatic retry, rate-limit handling, or token-budget estimator.
- The health endpoint reports process liveness and provider names; it does not call the database or external provider.
- Existing vectors must be recreated if the embedding model or dimension changes.

## Security and data handling

- `OPENCODE_GO_API_KEY` is read only by the backend from environment configuration. It is never returned by the API or included in frontend assets.
- `.env` and `.env.*` files are ignored by Git and excluded from the Docker build context.
- The local Compose file publishes API and PostgreSQL ports only on `127.0.0.1`.
- The API has no authentication and must be treated as a local development service.
- Retrieved financial text is sent to OpenCode Go for answer generation. Do not use confidential reports without evaluating the provider's data terms and adding the controls required for your environment.
- Extracted text and embeddings remain in the local PostgreSQL volume until that volume is explicitly removed.

## Small roadmap

1. Add a versioned Portuguese/English retrieval and grounding evaluation set.
2. Measure retrieval recall and citation correctness before tuning chunk size or adding reranking.
3. Add bounded retry/rate-limit behavior if provider failures justify it.
4. Introduce migrations only when further schema evolution makes direct bootstrap insufficient.

## Repository structure

```text
app/
  api/             # FastAPI routes and Pydantic API models
  application/     # Upload, search, and grounded-answer orchestration
  domain/          # Document and chunking rules
  infrastructure/  # Database, embeddings, provider adapter, repository
  static/          # Portfolio interface (HTML, CSS, JavaScript)
  config.py        # Environment settings
  main.py          # Application and resource lifecycle
tests/              # Domain, API, provider, and isolated database tests
Dockerfile
docker-compose.yml
pyproject.toml
requirements.txt
```
