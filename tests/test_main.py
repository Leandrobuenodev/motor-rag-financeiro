import pytest

from app.config import settings


@pytest.mark.anyio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "motor-rag-financeiro"
    assert data["embedding_provider"] == settings.embedding_provider
    assert data["answer_provider"] == "opencode-go"
    assert data["answer_model"] == "deepseek-v4-pro"


@pytest.mark.anyio
async def test_portfolio_ui_is_served_at_root(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "FINANCIAL" in response.text
    assert "GROUNDED QA" in response.text
    assert "UPLOAD A REPORT" in response.text
    assert "ASK ABOUT THE REPORT" in response.text
    assert "GROUNDED RESPONSE" in response.text
    assert "LOCAL EMBEDDINGS + DEEPSEEK V4 PRO · OPENCODE GO" in response.text
    assert "/static/styles.css" in response.text
    assert "/static/app.js" in response.text


@pytest.mark.anyio
async def test_portfolio_ui_static_assets_are_served(client):
    css_response = await client.get("/static/styles.css")
    javascript_response = await client.get("/static/app.js")

    assert css_response.status_code == 200
    assert css_response.headers["content-type"].startswith("text/css")
    assert javascript_response.status_code == 200
    assert javascript_response.headers["content-type"].startswith("text/javascript")
