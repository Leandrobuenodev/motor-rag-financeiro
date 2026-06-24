# Motor RAG Financeiro

Motor de busca vetorial local para relatórios financeiros (PoC).

## Requisitos

- Docker e Docker Compose
- Python 3.12+

## Execução

```bash
cp .env.example .env
docker compose up -d --build
```

Acesse o Swagger UI em http://localhost:8000/docs

## Endpoints

| Método | Rota      | Descrição                                  |
|--------|-----------|--------------------------------------------|
| GET    | /health   | Health check                               |
| POST   | /upload   | Upload de PDF para indexação vetorial      |
| POST   | /search   | Busca semântica por similaridade vetorial  |

## Estrutura

```
app/
  domain/         # Entidades e regras de negócio
  application/    # Casos de uso
  infrastructure/ # Banco, embeddings, repositórios
  api/            # Rotas REST
  main.py         # Aplicação FastAPI
  config.py       # Configurações
tests/            # Testes unitários e de integração
```

## Testes

```bash
pip install -r requirements.txt
docker compose up -d db
python -m pytest tests/ -v
python -m ruff check .
python -m mypy app/ tests/ --ignore-missing-imports
```
