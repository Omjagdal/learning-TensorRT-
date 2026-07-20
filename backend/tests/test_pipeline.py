"""
tests/test_pipeline.py — Functional and unit tests for the RAG pipeline.
Run with: pytest tests/ -v
"""

import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_TEXT = """
SAFETY PRECAUTIONS
Before operating the machine, read this manual completely.
Always disconnect power before performing maintenance.
Wear appropriate personal protective equipment (PPE).

MACHINE SPECIFICATIONS
Model: XR-5000
Operating Voltage: 380V / 3-phase
Maximum RPM: 3500
Motor Power: 15 kW
Weight: 450 kg

STARTUP PROCEDURE
1. Inspect all safety guards are in place.
2. Check lubrication levels on all bearings.
3. Verify emergency stop is functional.
4. Turn key switch to ON position.
5. Press GREEN START button.

TROUBLESHOOTING
Problem: Machine does not start
Cause 1: Emergency stop activated — Reset E-stop
Cause 2: Low oil pressure — Check oil level and refill
Cause 3: Overload relay tripped — Reset relay and reduce load
"""


@pytest.fixture
def temp_dir(tmp_path):
    yield tmp_path


@pytest.fixture
def sample_chunks():
    return [
        {
            "chunk_id": "test001_0",
            "manual_id": "test001",
            "filename": "xr5000_manual.pdf",
            "page": 1,
            "chunk_index": 0,
            "text": "SAFETY PRECAUTIONS: Always disconnect power before performing maintenance. Wear appropriate personal protective equipment (PPE).",
        },
        {
            "chunk_id": "test001_1",
            "manual_id": "test001",
            "filename": "xr5000_manual.pdf",
            "page": 2,
            "chunk_index": 1,
            "text": "MACHINE SPECIFICATIONS: Model XR-5000. Operating Voltage: 380V / 3-phase. Maximum RPM: 3500. Motor Power: 15 kW.",
        },
        {
            "chunk_id": "test001_2",
            "manual_id": "test001",
            "filename": "xr5000_manual.pdf",
            "page": 3,
            "chunk_index": 2,
            "text": "TROUBLESHOOTING: Machine does not start. Cause: Emergency stop activated — Reset E-stop. Low oil pressure — Check oil level.",
        },
    ]


# ── Unit tests: chunking ───────────────────────────────────────────────────────

class TestChunking:
    def test_chunk_generation(self):
        from app.services.pdf_service import chunk_pages

        pages = [{"page": 1, "text": SAMPLE_TEXT}]
        chunks = chunk_pages(pages, "t001", "test.pdf", chunk_size=200, chunk_overlap=30)

        assert len(chunks) > 0, "Should produce at least one chunk"
        assert all("text" in c for c in chunks), "All chunks must have text"
        assert all("page" in c for c in chunks), "All chunks must have page"
        assert all("manual_id" in c for c in chunks), "All chunks must have manual_id"
        for c in chunks:
            assert len(c["text"]) <= 300, "Chunks should be roughly bounded"

    def test_chunk_ids_are_unique(self):
        from app.services.pdf_service import chunk_pages

        pages = [{"page": i, "text": SAMPLE_TEXT} for i in range(1, 4)]
        chunks = chunk_pages(pages, "t002", "test.pdf")
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs must be unique"

    def test_empty_pages_filtered(self):
        from app.services.pdf_service import chunk_pages

        pages = [{"page": 1, "text": ""}, {"page": 2, "text": "Real content here."}]
        chunks = chunk_pages(pages, "t003", "test.pdf")
        assert all(c["text"].strip() for c in chunks), "Empty chunks should be filtered"


# ── Unit tests: vector store ──────────────────────────────────────────────────

class TestVectorStore:
    def test_build_and_search(self, sample_chunks, tmp_path, monkeypatch):
        from app.rag import vector_store as vs_module

        # Patch storage paths to temp dir
        monkeypatch.setattr(vs_module, "INDEX_FILE", tmp_path / "index.faiss")
        monkeypatch.setattr(vs_module, "CHUNKS_MAP_FILE", tmp_path / "chunks.pkl")

        store = vs_module.VectorStore()
        store.build_index(sample_chunks)

        assert store.total_chunks == len(sample_chunks)

        results = store.search("how to start the machine", top_k=2)
        assert len(results) >= 1
        assert all("relevance_score" in r for r in results)

    def test_search_returns_relevant_chunk(self, sample_chunks, tmp_path, monkeypatch):
        from app.rag import vector_store as vs_module

        monkeypatch.setattr(vs_module, "INDEX_FILE", tmp_path / "index.faiss")
        monkeypatch.setattr(vs_module, "CHUNKS_MAP_FILE", tmp_path / "chunks.pkl")

        store = vs_module.VectorStore()
        store.build_index(sample_chunks)

        results = store.search("machine voltage specifications", top_k=1)
        assert len(results) == 1
        assert "380V" in results[0]["text"] or "SPECIFICATIONS" in results[0]["text"]

    def test_filter_by_manual_id(self, tmp_path, monkeypatch):
        from app.rag import vector_store as vs_module

        monkeypatch.setattr(vs_module, "INDEX_FILE", tmp_path / "index.faiss")
        monkeypatch.setattr(vs_module, "CHUNKS_MAP_FILE", tmp_path / "chunks.pkl")

        chunks_a = [{"chunk_id": "a_0", "manual_id": "aaa", "filename": "a.pdf",
                     "page": 1, "chunk_index": 0, "text": "Motor safety procedures for type A machine"}]
        chunks_b = [{"chunk_id": "b_0", "manual_id": "bbb", "filename": "b.pdf",
                     "page": 1, "chunk_index": 0, "text": "Hydraulic system pressure specifications"}]

        store = vs_module.VectorStore()
        store.build_index(chunks_a + chunks_b)

        results = store.search("motor", top_k=5, manual_ids=["aaa"])
        assert all(r["manual_id"] == "aaa" for r in results)


# ── Integration test: RAG pipeline ───────────────────────────────────────────

class TestRAGPipeline:
    def test_pipeline_returns_response(self, sample_chunks, tmp_path, monkeypatch):
        from app.rag import vector_store as vs_module
        from app.rag import pipeline as p_module

        monkeypatch.setattr(vs_module, "INDEX_FILE", tmp_path / "index.faiss")
        monkeypatch.setattr(vs_module, "CHUNKS_MAP_FILE", tmp_path / "chunks.pkl")

        store = vs_module.VectorStore()
        store.build_index(sample_chunks)

        # Monkeypatch the global store
        monkeypatch.setattr(vs_module, "_store", store)

        with patch("app.rag.pipeline.generate_answer", return_value="The machine requires 380V."):
            response = p_module.run_rag_pipeline("What is the operating voltage?")

        assert response.answer == "The machine requires 380V."
        assert len(response.sources) > 0
        assert response.processing_time_ms > 0


# ── Performance test ──────────────────────────────────────────────────────────

class TestPerformance:
    def test_search_speed(self, tmp_path, monkeypatch):
        import time
        from app.rag import vector_store as vs_module

        monkeypatch.setattr(vs_module, "INDEX_FILE", tmp_path / "index.faiss")
        monkeypatch.setattr(vs_module, "CHUNKS_MAP_FILE", tmp_path / "chunks.pkl")

        # Build a larger index
        chunks = [
            {
                "chunk_id": f"perf_{i}",
                "manual_id": "perf",
                "filename": "large_manual.pdf",
                "page": i + 1,
                "chunk_index": i,
                "text": f"Section {i}: {SAMPLE_TEXT[i % len(SAMPLE_TEXT):i % len(SAMPLE_TEXT) + 200]}",
            }
            for i in range(500)
        ]

        store = vs_module.VectorStore()
        store.build_index(chunks)

        start = time.perf_counter()
        results = store.search("emergency stop procedure", top_k=5)
        elapsed = (time.perf_counter() - start) * 1000

        assert elapsed < 2000, f"Search took {elapsed:.1f}ms — should be under 2s"
        print(f"\nSearch time for 500-chunk index: {elapsed:.1f}ms")
