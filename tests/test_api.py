import io

import pytest
from httpx import AsyncClient


def create_minimal_pdf() -> bytes:
    content = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        b"4 0 obj << /Length 61 >> stream\n"
        b"BT /F1 12 Tf 100 700 Td (Receita Liquida R$ 500 milhoes) Tj ET\n"
        b"endstream endobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000271 00000 n \n"
        b"0000000382 00000 n \n"
        b"trailer << /Size 6 /Root 1 0 R >>\n"
        b"startxref\n433\n%%EOF"
    )
    return content


class TestUploadEndpoint:
    @pytest.mark.anyio
    async def test_upload_pdf_returns_document_id_and_chunks(
        self, client: AsyncClient
    ):
        pdf_content = create_minimal_pdf()
        response = await client.post(
            "/upload",
            files={
                "file": (
                    "report.pdf",
                    io.BytesIO(pdf_content),
                    "application/pdf",
                )
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert data["chunk_count"] >= 1

    @pytest.mark.anyio
    async def test_upload_non_pdf_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/upload",
            files={
                "file": (
                    "report.txt",
                    io.BytesIO(b"not a pdf"),
                    "text/plain",
                )
            },
        )
        assert response.status_code == 400

    @pytest.mark.anyio
    async def test_search_returns_results_after_upload(
        self, client: AsyncClient
    ):
        pdf_content = create_minimal_pdf()
        upload_resp = await client.post(
            "/upload",
            files={
                "file": (
                    "report.pdf",
                    io.BytesIO(pdf_content),
                    "application/pdf",
                )
            },
        )
        assert upload_resp.status_code == 200

        search_resp = await client.post(
            "/search",
            json={"query": "Receita liquida", "top_k": 3},
        )
        assert search_resp.status_code == 200
        data = search_resp.json()
        assert "results" in data
        assert data["count"] >= 1

    @pytest.mark.anyio
    async def test_search_empty_query_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/search",
            json={"query": ""},
        )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_search_respects_top_k(self, client: AsyncClient):
        pdf_content = create_minimal_pdf()
        await client.post(
            "/upload",
            files={
                "file": (
                    "report.pdf",
                    io.BytesIO(pdf_content),
                    "application/pdf",
                )
            },
        )

        response = await client.post(
            "/search",
            json={"query": "Receita", "top_k": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] <= 1
