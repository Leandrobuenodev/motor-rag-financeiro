import pytest

from app.domain.document import Document


class TestDocument:
    def test_create_valid_document(self):
        doc = Document(name="relatorio_q4.pdf", content="Balanço patrimonial...")
        assert doc.name == "relatorio_q4.pdf"
        assert doc.content == "Balanço patrimonial..."
        assert doc.id != ""

    def test_document_id_is_unique(self):
        doc1 = Document(name="a.pdf", content="conteudo")
        doc2 = Document(name="b.pdf", content="conteudo")
        assert doc1.id != doc2.id

    def test_rejects_empty_name(self):
        with pytest.raises(ValueError, match="Document name must not be empty"):
            Document(name="", content="conteudo")

    def test_rejects_whitespace_name(self):
        with pytest.raises(ValueError, match="Document name must not be empty"):
            Document(name="   ", content="conteudo")

    def test_rejects_empty_content(self):
        with pytest.raises(ValueError, match="Document content must not be empty"):
            Document(name="teste.pdf", content="")

    def test_rejects_whitespace_content(self):
        with pytest.raises(ValueError, match="Document content must not be empty"):
            Document(name="teste.pdf", content="   ")
