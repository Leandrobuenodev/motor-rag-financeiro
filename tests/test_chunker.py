import pytest

from app.domain.chunker import Chunker


class TestChunker:
    def test_splits_text_into_chunks_of_expected_size(self):
        chunker = Chunker(chunk_size=10, chunk_overlap=0)
        text = "A" * 25
        chunks = chunker.split(text, document_id="doc-1")
        assert len(chunks) == 3
        assert len(chunks[0].text) == 10
        assert len(chunks[1].text) == 10
        assert len(chunks[2].text) == 5

    def test_all_chunks_have_correct_document_id(self):
        chunker = Chunker(chunk_size=10, chunk_overlap=0)
        chunks = chunker.split("A" * 20, document_id="doc-x")
        assert all(c.document_id == "doc-x" for c in chunks)

    def test_chunk_indices_are_sequential(self):
        chunker = Chunker(chunk_size=10, chunk_overlap=0)
        chunks = chunker.split("A" * 20, document_id="doc-1")
        assert [c.index for c in chunks] == [0, 1]

    def test_overlap_reduces_total_chunks_and_repeats_content(self):
        chunker = Chunker(chunk_size=10, chunk_overlap=2)
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        chunks = chunker.split(text, document_id="doc-1")
        assert len(chunks) >= 1
        if len(chunks) > 1:
            assert chunks[0].text[-2:] == chunks[1].text[:2]

    def test_empty_text_returns_no_chunks(self):
        chunker = Chunker(chunk_size=10, chunk_overlap=0)
        chunks = chunker.split("", document_id="doc-1")
        assert chunks == []

    def test_whitespace_only_text_returns_no_chunks(self):
        chunker = Chunker(chunk_size=10, chunk_overlap=0)
        chunks = chunker.split("   ", document_id="doc-1")
        assert chunks == []

    def test_text_smaller_than_chunk_size_returns_single_chunk(self):
        chunker = Chunker(chunk_size=100, chunk_overlap=0)
        chunks = chunker.split("Hello", document_id="doc-1")
        assert len(chunks) == 1
        assert chunks[0].text == "Hello"

    def test_rejects_invalid_chunk_size(self):
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            Chunker(chunk_size=0, chunk_overlap=0)

        with pytest.raises(ValueError, match="chunk_size must be positive"):
            Chunker(chunk_size=-5, chunk_overlap=0)

    def test_rejects_invalid_chunk_overlap(self):
        with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
            Chunker(chunk_size=10, chunk_overlap=-1)

    def test_rejects_overlap_gte_chunk_size(self):
        with pytest.raises(
            ValueError,
            match="chunk_overlap must be less than chunk_size",
        ):
            Chunker(chunk_size=10, chunk_overlap=10)

    def test_chunk_ids_are_unique(self):
        chunker = Chunker(chunk_size=10, chunk_overlap=0)
        chunks = chunker.split("A" * 30, document_id="doc-1")
        ids = {c.id for c in chunks}
        assert len(ids) == len(chunks)
