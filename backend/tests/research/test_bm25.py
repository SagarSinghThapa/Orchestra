import pytest

from app.research.retrieval.bm25 import BM25Okapi, tokenize


class DummyChunk:
    def __init__(self, text: str, chunk_id: str = "chunk-1"):
        self.text = text
        self.chunk_id = chunk_id


class TestBM25Okapi:
    def test_bm25_empty_corpus(self):
        bm25 = BM25Okapi(corpus=[])
        assert bm25.corpus_size == 0
        assert bm25.avgdl == 0.0
        assert bm25.get_scores("query") == []
        assert bm25.search("query") == []

    def test_bm25_empty_query_or_whitespace(self):
        docs = [DummyChunk("PostgreSQL database connection pooling"), DummyChunk("Redis caching layer")]
        bm25 = BM25Okapi(docs)
        assert bm25.search("") == []
        assert bm25.search("   ") == []
        assert bm25.search("\n\t") == []

    def test_bm25_exact_keyword_ranking(self):
        docs = [
            DummyChunk("General system architecture and design principles", chunk_id="c1"),
            DummyChunk("Optimized PostgreSQL relational database with connection pooling", chunk_id="c2"),
            DummyChunk("Redis in-memory caching and session key expiration", chunk_id="c3"),
        ]
        bm25 = BM25Okapi(docs)
        results = bm25.search("PostgreSQL pooling", limit=3)
        assert len(results) > 0
        top_doc, top_score, top_idx = results[0]
        assert top_doc.chunk_id == "c2"
        assert top_idx == 1
        assert top_score > 0.0

    def test_bm25_term_frequency_saturation(self):
        docs = [
            DummyChunk("caching caching caching caching caching with redis", chunk_id="high_tf"),
            DummyChunk("caching with redis", chunk_id="low_tf"),
            DummyChunk("completely unrelated database text", chunk_id="none"),
        ]
        bm25 = BM25Okapi(docs)
        scores = bm25.get_scores("caching")
        # High TF document scores higher than low TF document
        assert scores[0] > scores[1]
        assert scores[2] == 0.0

        # Verify saturation: 5x occurrences does NOT give 5x score due to k1 saturation
        ratio = scores[0] / scores[1]
        assert ratio < 5.0

    def test_bm25_length_normalization(self):
        # Shorter document with target keyword scores higher than long document with same single mention
        docs = [
            DummyChunk("distributed vector database Qdrant", chunk_id="short"),
            DummyChunk("this is a very long and detailed explanation of various systems including Qdrant and many other tools and libraries", chunk_id="long"),
        ]
        bm25 = BM25Okapi(docs)
        scores = bm25.get_scores("Qdrant")
        assert scores[0] > scores[1]

    def test_bm25_tokenization_and_stopwords(self):
        tokens = tokenize("The quick brown fox jumps over the lazy dog.")
        assert "the" not in tokens
        assert "over" not in tokens
        assert "quick" in tokens
        assert "fox" in tokens

        # Underscores and technical identifiers preserved
        tech_tokens = tokenize("uq_project_document_checksum SHA256_HASH")
        assert "uq_project_document_checksum" in tech_tokens
        assert "sha256_hash" in tech_tokens

    def test_bm25_non_negative_idf(self):
        # Term appearing in every document must maintain non-negative (strictly positive) IDF
        docs = [
            DummyChunk("system architecture overview"),
            DummyChunk("system database layer"),
            DummyChunk("system caching layer"),
        ]
        bm25 = BM25Okapi(docs)
        assert "system" in bm25.idf
        assert bm25.idf["system"] > 0.0

    def test_bm25_single_document_corpus(self):
        docs = [DummyChunk("Orchestra multi-agent platform")]
        bm25 = BM25Okapi(docs)
        results = bm25.search("Orchestra")
        assert len(results) == 1
        assert results[0][1] > 0.0

    def test_bm25_deterministic_ties(self):
        # Two identical documents for a query should tie-break deterministically by document index
        docs = [
            DummyChunk("identical target content", chunk_id="d0"),
            DummyChunk("identical target content", chunk_id="d1"),
        ]
        bm25 = BM25Okapi(docs)
        results = bm25.search("target", limit=2)
        assert len(results) == 2
        assert results[0][2] == 0
        assert results[1][2] == 1
        assert results[0][0].chunk_id == "d0"
        assert results[1][0].chunk_id == "d1"

    def test_bm25_unicode_accented_latin_tokenization_and_search(self):
        """Optional fix: Accented Latin terms tokenize cleanly and match sparse retrieval."""
        tokens = tokenize("Le café est un lieu idéal pour réviser un résumé naïve.")
        assert "café" in tokens
        assert "résumé" in tokens
        assert "naïve" in tokens

        docs = [
            DummyChunk("Discussion sur les algorithmes dans un café parisien", chunk_id="doc_cafe"),
            DummyChunk("Rapport technique sur les bases de données SQL", chunk_id="doc_sql"),
        ]
        bm25 = BM25Okapi(docs)
        results = bm25.search("café", limit=1)
        assert len(results) == 1
        assert results[0][0].chunk_id == "doc_cafe"
        assert results[0][1] > 0.0

    def test_bm25_unicode_devanagari_tokenization_and_search(self):
        """Optional fix: Non-Latin script (Devanagari) terms tokenize cleanly and match."""
        tokens = tokenize("आर्टिफिशियल इंटेलिजेंस और बहु-एजेंट अनुसंधान प्रणाली")
        assert "अनुसंधान" in tokens
        assert "प्रणाली" in tokens

        docs = [
            DummyChunk("बहु-एजेंट अनुसंधान प्रणाली का अवलोकन", chunk_id="doc_hindi"),
            DummyChunk("PostgreSQL database transaction management", chunk_id="doc_en"),
        ]
        bm25 = BM25Okapi(docs)
        results = bm25.search("अनुसंधान", limit=1)
        assert len(results) == 1
        assert results[0][0].chunk_id == "doc_hindi"
        assert results[0][1] > 0.0

    def test_bm25_technical_identifiers_preserved_and_source_unchanged(self):
        """Optional fix: Technical identifiers with underscores are preserved and source text is not mutated."""
        source = "API_KEY_SECRET_V1 and model_checkpoint_999."
        tokens = tokenize(source)
        assert "api_key_secret_v1" in tokens
        assert "model_checkpoint_999" in tokens

        doc = DummyChunk(source, chunk_id="doc_tech")
        bm25 = BM25Okapi([doc])
        results = bm25.search("model_checkpoint_999")
        assert len(results) == 1
        assert results[0][0].chunk_id == "doc_tech"
        # Source text must be completely unchanged
        assert doc.text == "API_KEY_SECRET_V1 and model_checkpoint_999."

