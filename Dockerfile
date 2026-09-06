FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG LOCAL_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ENV FASTEMBED_CACHE_PATH=/opt/fastembed_cache \
    LOCAL_EMBEDDING_MODEL=${LOCAL_EMBEDDING_MODEL}
RUN python -c "from fastembed import TextEmbedding; list(TextEmbedding(model_name='${LOCAL_EMBEDDING_MODEL}').embed(['model warmup']))"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
