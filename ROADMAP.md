# ROADMAP.md — Ciclo 1: Motor RAG Financeiro Local

## 1. Cycle metadata

- Project: Motor RAG Financeiro (PoC)
- Cycle: Ciclo 1 - Ingestão e Busca Local
- Type: greenfield
- Roadmap version: 1.0
- Date: 2026-06-24
- Target branch: main
- Current baseline: N/A (Project Start)
- Expected final state: Motor de busca vetorial local operacional via API REST
- Expected version: 0.1.0
- Expected tags: v0.1.0

## 2. Objective

Construir a base limpa e testável de um sistema RAG (Retrieval-Augmented Generation) focado em relatórios financeiros, isolando as regras de domínio e operando 100% via containers locais (FastAPI + PostgreSQL com pgvector) para garantir custo zero de infraestrutura na fase de testes.

## 3. Context

- Problema que resolve: LLMs alucinam ou não possuem contexto atualizado de balanços financeiros de empresas. A PoC resolve isso vetorizando PDFs financeiros e fornecendo o contexto exato antes de o LLM responder.
- Público-alvo: Portfólio técnico e validação de estudos para a certificação AI-200.
- Restrições iniciais: Tudo deve rodar localmente via `docker-compose`. Cloud deployments (Azure) estão fora deste ciclo.

## 4. Scope

### In scope

- Configuração do ambiente Docker local (FastAPI + pgvector).
- Estrutura de pastas separando Domain, Application e Infrastructure.
- `Infrastructure`: Endpoint REST para upload de PDF e conversão em texto.
- `Domain`: Regra de validação de arquivo e estratégia de chunking (divisão de texto).
- `Infrastructure`: Integração simulada ou real com Azure OpenAI para gerar embeddings.
- `Infrastructure`: Repositório de persistência e busca por similaridade usando `pgvector`.
- Documentação básica de execução (README.md).

### Out of scope

- Deploy na Azure (Container Apps, ACR).
- Interface de usuário (React, Vue).
- Autenticação de usuários (JWT, Entra ID).
- Mensageria assíncrona (Service Bus).

### Deferred

- Fase 2: Scripts de automação de infraestrutura (Azure CLI) para subida na nuvem.
- Integração completa com o agente LLM para a resposta final (Foco agora é a busca vetorial).

## 5. Assumptions

- O modelo de embedding a ser utilizado será baseado na API da Azure OpenAI (ou fallback local).
- Os documentos enviados serão PDFs legíveis (texto, não apenas imagens escaneadas sem OCR prévio).

## 6. Architecture / implementation direction

- Direção arquitetural: Arquitetura em camadas (Sem Cerimônia), focando em isolamento de dependências.
- Módulos esperados: `domain` (regras e tipos), `application` (casos de uso), `infrastructure` (rotas, db, adaptadores).
- Padrões a preservar: Injeção de dependência simples para permitir mock do banco e da API nos testes.
- Decisões técnicas principais: FastAPI (Framework web), asyncpg / SQLAlchemy (Banco de dados), pytest (Validação).

## 7. Compatibility policy

- APIs ou contratos iniciais esperados: Rotas RESTful limpas documentadas automaticamente pelo OpenAPI (Swagger) gerado pelo FastAPI.

## 8. Security and privacy policy

- limits de rede: N/A (ambiente local).
- secrets: Chaves de API não devem ser comitadas (uso rigoroso de `.env`).
- dados do usuário: Não haverá persistência de dados sensíveis além dos PDFs públicos de exemplo.

## 9. Phases

### Phase 1 — Setup Base e Infraestrutura Docker

- Goal: Subir o esqueleto do projeto e os containers.
- Scope: Criar `docker-compose.yml`, `requirements.txt`/`pyproject.toml`, e um "Hello World" estruturado no FastAPI.
- Likely files: `docker-compose.yml`, `app/main.py`, `Dockerfile`.
- Acceptance criteria: Executar `docker-compose up` deve disponibilizar o Swagger UI na porta 8000 e conectar ao Postgres na 5432.
- Required tests: Configuração do pytest rodando no CI/ambiente local.

### Phase 2 — Domínio de Ingestão e Chunking

- Goal: Isolar a regra matemática/texto de preparação de dados.
- Scope: Criar as entidades e lógicas de quebra do documento.
- Likely files: `app/domain/document.py`, `app/domain/chunker.py`.
- Acceptance criteria: Receber um texto longo e retornar uma lista de fragmentos válidos segundo a regra estabelecida.
- Required tests: Testes unitários puros verificando o tamanho dos chunks.

### Phase 3 — Persistência Vetorial (pgvector)

- Goal: Salvar e buscar dados vetorizados.
- Scope: Configurar extensão pgvector, criar a tabela de chunks, e implementar as queries de `INSERT` e busca por similaridade (L2 ou Cosine).
- Likely files: `app/infrastructure/db.py`, `app/infrastructure/repositories.py`.
- Acceptance criteria: Conseguir inserir um vetor e recuperá-lo como o mais próximo de uma query de teste.
- Required tests: Teste de integração rápido contra o banco local.

### Phase 4 — Casos de Uso e Endpoints

- Goal: Conectar o Domínio e a Infraestrutura.
- Scope: Criar as rotas de `POST /upload` e `POST /search` que orquestram o fluxo completo.
- Likely files: `app/api/routers.py`, `app/application/use_cases.py`.
- Acceptance criteria: Endpoint de busca recebe uma string e retorna os chunks de texto mais relevantes.
- Commit expected: Sim
- Tag expected: Sim (v0.1.0)
- Stop conditions: Rotas respondendo HTTP 200 com os dados corretos no Swagger.

## 10. Required validation

- testes unitários nas regras de negócio (domínio);
- lint (flake8 / ruff);
- typecheck (mypy);
- validação manual pelo Swagger (Smoke test local).

## 11. Commit policy

- commit por fase validada;
- não commitar fase parcial;
- mensagem esperada por fase: "[Phase X] Resumo claro do que foi feito".

## 12. Tag policy

- criar tag somente se este roadmap exigir;
- tags devem ser locais e anotadas (ex: `git tag -a v0.1.0 -m "Release PoC RAG"`).
- não fazer push.

## 13. Failure policy

- Parar execução caso algum container não suba ou falhe na conexão de rede.
- Recomendar correção pontual se for problema de importação/tipagem.
- Recomendar rollback e novo planejamento se houver bloqueio arquitetural (ex: versão do pgvector incompatível).

## 14. Final report format

(Seguir padrão obrigatório definido na diretriz do repositório)
