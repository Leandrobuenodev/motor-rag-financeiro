# Financial Document Vector Retrieval

A local proof of concept for ingesting text-based financial PDFs and retrieving their chunks with PostgreSQL and pgvector.

## Problem

Financial reports are long, page-oriented documents whose relevant passages are difficult to locate with exact keyword matching alone. This project isolates the retrieval problem: it turns PDF text into traceable vector chunks that can be searched before any optional answer-generation layer is introduced.

## Project status

This repository is a PoC and the retrieval foundation of a possible future RAG system. It demonstrates a complete ingestion and vector-retrieval path, but it does not generate answers.

## What it does

- Accepts text-based PDF uploads through a FastAPI endpoint.
- Extracts text while preserving the source filename and page number.
- Splits each page into fixed-size overlapping chunks.
- Generates either deterministic simulated vectors or Azure OpenAI embeddings.
- Stores the chunks and vectors in PostgreSQL with pgvector.
- Retrieves the nearest chunks using exact L2 distance.
- Provides a focused browser interface for upload, search, and provenance inspection.

## What it intentionally does not do

- Generate answers with an LLM or provide chat.
- Produce citations for generated answers.
- Run OCR on scanned or image-only PDFs.
- Provide authentication, cloud deployment, or distributed infrastructure.
- Use an approximate nearest-neighbor index; exact search is sufficient for this PoC's intended data volume.

## Architecture and flow

```text
POST /upload
  -> validate and extract PDF pages
  -> fixed-size chunking with overlap
  -> configured embedding provider
  -> PostgreSQL / pgvector

POST /search
  -> embed the query
  -> exact nearest-neighbor search by L2 distance
  -> return chunks with source metadata and distance
```

The code is split into lightweight layers:

- `domain`: document and chunking rules.
- `application`: upload and search use cases.
- `infrastructure`: settings, embedding adapters, SQLAlchemy, and pgvector.
- `api`: FastAPI routes and request/response models.

## Technology choices

- Python 3.12 and FastAPI for the HTTP API.
- SQLAlchemy asyncio and asyncpg for non-blocking database access.
- PostgreSQL 17 with pgvector for vector persistence and exact L2 search.
- pypdf for text extraction from PDFs that already contain a text layer.
- Pydantic Settings for environment-based configuration.
- pytest, Ruff, and mypy for validation.

The application creates the pgvector extension and its small schema during startup. This direct bootstrap is deliberately proportional to the current one-table PoC; migrations can be introduced if the schema starts evolving beyond this scope.

## Quick start

Requirements: Docker with Docker Compose.

```bash
git clone https://github.com/Leandrobuenodev/motor-rag-financeiro.git
cd motor-rag-financeiro
cp .env.example .env
docker compose up -d --build --wait
curl http://localhost:8000/health
```

Expected health response:

```json
{"status":"ok","service":"motor-rag-financeiro"}
```

Open the portfolio interface at <http://localhost:8000/>. Swagger UI remains
available at <http://localhost:8000/docs>.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | Compose-local PostgreSQL URL | Async SQLAlchemy connection string |
| `TEST_DATABASE_URL` | PostgreSQL on `localhost:5432` | Database where tests create an isolated temporary schema |
| `EMBEDDING_PROVIDER` | `simulated` | Selects `simulated` or `azure` |
| `AZURE_OPENAI_ENDPOINT` | empty | Required when the Azure provider is selected |
| `AZURE_OPENAI_API_KEY` | empty | Required when the Azure provider is selected |
| `AZURE_OPENAI_API_VERSION` | `2024-02-01` | Azure OpenAI API version |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `text-embedding-3-small` | Existing Azure embedding deployment name |

### Simulated embeddings

`EMBEDDING_PROVIDER=simulated` is the default so the complete storage and retrieval pipeline can run without external credentials. Its vectors are deterministic: the same text produces the same vector.

These vectors are generated from hashes and **do not provide real semantic similarity**. Results in this mode validate the pipeline mechanics, not retrieval quality.

### Azure OpenAI embeddings

`EMBEDDING_PROVIDER=azure` enables semantic retrieval through the existing Azure OpenAI embedding adapter. Supply a valid endpoint, API key, API version, and embedding deployment in `.env`; the project does not create Azure resources or credentials.

If Azure is selected with required settings missing, application startup fails with a message listing the missing variables. Startup only constructs the client; remote calls occur when upload or search requests require embeddings.

## Use the API

The browser interface at <http://localhost:8000/> supports the same upload and
search flow without adding a separate frontend service. The examples below show
the underlying API directly.

Upload a text-based PDF:

```bash
curl -X POST http://localhost:8000/upload \
  -H "accept: application/json" \
  -F "file=@/absolute/path/to/report.pdf;type=application/pdf"
```

Search the stored chunks:

```bash
curl -X POST http://localhost:8000/search \
  -H "content-type: application/json" \
  -d '{"query":"quarterly revenue","top_k":3}'
```

Representative search response:

```json
{
  "results": [
    {
      "chunk_id": "8bc0f6d8-7b13-4cef-b318-57d3926bdf6a",
      "document_id": "23003d52-a0f4-4115-bd50-d2f89757bfd0",
      "source_filename": "report.pdf",
      "page": 1,
      "chunk_index": 0,
      "text": "Quarterly revenue increased...",
      "l2_distance": 0.42
    }
  ],
  "count": 1
}
```

`l2_distance` is the Euclidean distance between stored and query vectors. Lower values mean closer vectors for the selected provider; it is not a confidence score.

## API endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Lightweight portfolio interface for ingestion and retrieval |
| `GET` | `/health` | Process liveness check |
| `POST` | `/upload` | Extract, chunk, embed, and store a PDF |
| `POST` | `/search` | Return the nearest stored chunks and provenance |

The upload endpoint returns `415` for a non-PDF filename, `400` for an empty upload, and `422` for an invalid PDF or a PDF without extractable text.

## Tests and static checks

Start only PostgreSQL, create a virtual environment, and install the pinned dependencies:

```bash
docker compose up -d db
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -v
python -m ruff check .
python -m mypy app/ tests/ --ignore-missing-imports
```

Integration tests create a unique temporary PostgreSQL schema and remove that schema after each test. They do not delete application data from the default `public` schema.

## Design decisions and trade-offs

- Chunking is character-based (`1,000` characters with `200` characters of overlap) and restarts at each page. It is transparent and easy to test, but not language-aware.
- Chunk indexes are sequential across all extracted pages in one upload. Page numbers are 1-based.
- Vector dimensionality is fixed at 1,536. Azure deployments must return 1,536-dimensional embeddings.
- Search performs an exact table scan ordered by L2 distance. This keeps the implementation small and is appropriate only for the PoC's expected volume.
- Files are processed in memory and only extracted chunks are persisted; the original PDF is not stored.
- The interface uses framework-free HTML, CSS, and JavaScript served by FastAPI to keep the PoC as one deployable unit.

## Known limitations

- Scanned and image-only PDFs require OCR and are rejected because OCR is outside the project scope.
- PDF layout, tables, and reading order are limited by pypdf text extraction.
- Simulated mode does not demonstrate semantic relevance.
- Uploads are not deduplicated, and there are no endpoints to list or delete documents.
- The health endpoint reports process liveness and does not perform a database readiness query.
- Azure embedding calls do not yet implement batching, retries, or retrieval evaluation.

## Security and data handling

- `.env` is ignored by Git and Docker; local credentials are not copied into the image.
- The API and PostgreSQL are published only on the host loopback interface by the local Compose file.
- The API has no authentication and should be treated as a local development service.
- Uploaded PDF bytes are not retained, but extracted text and vectors remain in the PostgreSQL volume.
- Do not use confidential reports with this demonstration setup.

## Small roadmap

1. Add a small retrieval evaluation set for a real embedding provider.
2. Add batching and explicit timeout/retry behavior for Azure embeddings.
3. Introduce schema migrations only when schema evolution justifies them.
4. Consider grounded answer generation with source citations as a separate future cycle.

## Repository structure

```text
app/
  api/             # HTTP routes and Pydantic API models
  application/     # Upload and search orchestration
  domain/          # Document and chunking rules
  infrastructure/  # Database, embeddings, and repository
  config.py        # Environment settings
  main.py          # FastAPI app and lifecycle
  static/           # Browser interface (HTML, CSS, and JavaScript)
tests/              # Domain, API, provider, and database tests
Dockerfile
docker-compose.yml
pyproject.toml
requirements.txt
```
