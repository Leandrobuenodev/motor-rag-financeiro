import io

import pytest
from httpx import AsyncClient
from pypdf import PdfWriter

from app.infrastructure.answers import (
    AnswerService,
    GeneratedAnswer,
    GroundingPassage,
    OpenCodeGoAnswerService,
)


class FakeAnswerService(AnswerService):
    def __init__(
        self,
        source_ids: list[int],
        answer: str = "O índice de Basileia foi 14,2%.",
        insufficient_evidence: bool = False,
    ) -> None:
        self.source_ids = source_ids
        self.answer = answer
        self.insufficient_evidence = insufficient_evidence
        self.passages: list[GroundingPassage] = []

    async def generate(
        self, question: str, passages: list[GroundingPassage]
    ) -> GeneratedAnswer:
        self.passages = passages
        return GeneratedAnswer(
            answer=self.answer,
            source_ids=self.source_ids,
            insufficient_evidence=self.insufficient_evidence,
        )


def create_pdf_with_pages(page_texts: list[str]) -> bytes:
    font_id = 3 + (2 * len(page_texts))
    page_ids = [3 + (2 * index) for index in range(len(page_texts))]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode(),
    ]

    for index, page_text in enumerate(page_texts):
        content_id = page_ids[index] + 1
        stream = (
            f"BT /F1 12 Tf 100 700 Td ({page_text}) Tj ET\n".encode("latin-1")
        )
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Contents {content_id} 0 R /Resources << /Font << "
                    f"/F1 {font_id} 0 R >> >> >>"
                ).encode(),
                (
                    f"<< /Length {len(stream)} >> stream\n".encode()
                    + stream
                    + b"endstream"
                ),
            ]
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    parts = [b"%PDF-1.4\n"]
    offsets = [0]
    for object_id, body in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in parts))
        parts.append(
            f"{object_id} 0 obj\n".encode() + body + b"\nendobj\n"
        )

    xref_offset = sum(len(part) for part in parts)
    xref_entries = b"".join(
        f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]
    )
    parts.append(
        f"xref\n0 {len(objects) + 1}\n".encode()
        + b"0000000000 65535 f \n"
        + xref_entries
        + (
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode()
    )
    return b"".join(parts)


def create_minimal_pdf() -> bytes:
    return create_pdf_with_pages(["Net revenue was 500 million"])


def create_blank_pdf() -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


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
        assert data["source_filename"] == "report.pdf"
        assert data["chunks"][0]["page"] == 1
        assert data["chunks"][0]["source_filename"] == "report.pdf"

    @pytest.mark.anyio
    async def test_upload_preserves_page_and_global_chunk_index(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/upload",
            files={
                "file": (
                    "two-pages.pdf",
                    io.BytesIO(create_pdf_with_pages(["Page one", "Page two"])),
                    "application/pdf",
                )
            },
        )
        assert response.status_code == 200
        chunks = response.json()["chunks"]
        assert [chunk["page"] for chunk in chunks] == [1, 2]
        assert [chunk["chunk_index"] for chunk in chunks] == [0, 1]

    @pytest.mark.anyio
    async def test_upload_non_pdf_returns_415(self, client: AsyncClient):
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
        assert response.status_code == 415

    @pytest.mark.anyio
    async def test_upload_empty_pdf_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/upload",
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "The uploaded file is empty"

    @pytest.mark.anyio
    async def test_upload_corrupt_pdf_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/upload",
            files={
                "file": (
                    "corrupt.pdf",
                    io.BytesIO(b"%PDF-1.4\nnot a valid PDF"),
                    "application/pdf",
                )
            },
        )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_upload_pdf_without_text_returns_422(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/upload",
            files={
                "file": (
                    "scanned.pdf",
                    io.BytesIO(create_blank_pdf()),
                    "application/pdf",
                )
            },
        )
        assert response.status_code == 422
        assert "OCR is not supported" in response.json()["detail"]

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
            json={"query": "Net revenue was 500 million", "top_k": 3},
        )
        assert search_resp.status_code == 200
        data = search_resp.json()
        assert "results" in data
        assert data["count"] >= 1
        result = data["results"][0]
        assert result["source_filename"] == "report.pdf"
        assert result["page"] == 1
        assert result["l2_distance"] == pytest.approx(0.0, abs=1e-6)

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


class TestAnswerEndpoint:
    @pytest.mark.anyio
    async def test_answer_maps_internal_source_id_to_trusted_provenance(
        self, client: AsyncClient
    ) -> None:
        from app.api.routers import get_answer_service
        from app.main import app

        upload = await client.post(
            "/upload",
            files={
                "file": (
                    "quarterly-report.pdf",
                    io.BytesIO(
                        create_pdf_with_pages(
                            [
                                "A receita líquida foi de R$ 500 milhões.",
                                "O índice de Basileia foi 14,2% em março de 2026.",
                            ]
                        )
                    ),
                    "application/pdf",
                )
            },
        )
        assert upload.status_code == 200

        answer_service = FakeAnswerService(source_ids=[1])
        app.dependency_overrides[get_answer_service] = lambda: answer_service
        response = await client.post(
            "/answer",
            json={
                "question": "O índice de Basileia foi 14,2% em março de 2026.",
                "top_k": 2,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "O índice de Basileia foi 14,2%."
        assert data["insufficient_evidence"] is False
        assert len(data["citations"]) == 1
        citation = data["citations"][0]
        assert citation["source_id"] == 1
        assert citation["source_filename"] == "quarterly-report.pdf"
        assert citation["page"] == 2
        assert citation["chunk_index"] == 1
        assert citation["chunk_id"] == data["retrieved_passages"][0]["chunk_id"]
        assert answer_service.passages[0].text == data["retrieved_passages"][0]["text"]

    @pytest.mark.anyio
    async def test_answer_rejects_any_source_id_not_in_retrieval_set(
        self, client: AsyncClient
    ) -> None:
        from app.api.routers import get_answer_service
        from app.main import app

        await client.post(
            "/upload",
            files={
                "file": (
                    "report.pdf",
                    io.BytesIO(create_minimal_pdf()),
                    "application/pdf",
                )
            },
        )
        app.dependency_overrides[get_answer_service] = lambda: FakeAnswerService(
            source_ids=[1, 99]
        )

        response = await client.post(
            "/answer",
            json={"question": "Net revenue was 500 million", "top_k": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["insufficient_evidence"] is True
        assert data["citations"] == []
        assert "not contain enough evidence" in data["answer"]

    @pytest.mark.anyio
    async def test_answer_returns_503_when_provider_key_is_missing(
        self, client: AsyncClient
    ) -> None:
        from app.api.routers import get_answer_service
        from app.main import app

        await client.post(
            "/upload",
            files={
                "file": (
                    "report.pdf",
                    io.BytesIO(create_minimal_pdf()),
                    "application/pdf",
                )
            },
        )
        missing_key_service = OpenCodeGoAnswerService(api_key="")
        app.dependency_overrides[get_answer_service] = lambda: missing_key_service

        response = await client.post(
            "/answer",
            json={"question": "Net revenue was 500 million", "top_k": 1},
        )

        assert response.status_code == 503
        assert "OPENCODE_GO_API_KEY" in response.json()["detail"]
        await missing_key_service.close()

    @pytest.mark.anyio
    async def test_answer_rejects_blank_question(self, client: AsyncClient) -> None:
        response = await client.post(
            "/answer", json={"question": "   ", "top_k": 3}
        )

        assert response.status_code == 422
