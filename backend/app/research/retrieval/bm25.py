import math
import re
import unicodedata
from collections import Counter
from typing import Any, List, Optional, Sequence, Tuple

# Conservative list of standard English stopwords
STOPWORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "could", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have", "having",
    "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i",
    "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most",
    "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only",
    "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "will", "with", "would", "you",
    "your", "yours", "yourself", "yourselves"
})

# Matches alphanumeric words and technical identifiers (preserving underscores)
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")


def tokenize(text: str, remove_stopwords: bool = True) -> list[str]:
    """
    Standardizes and tokenizes text for lexical search.
    Preserves original source text by working on normalized copies.
    """
    if not text:
        return []
    # Canonical Unicode NFC normalization
    normalized = unicodedata.normalize("NFC", text)
    # Extract lowercased tokens
    tokens = TOKEN_PATTERN.findall(normalized.lower())
    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens


class BM25Okapi:
    """
    Pure-Python implementation of BM25Okapi with Robertson-Zaragoza non-negative IDF.
    Zero external dependencies, deterministic scoring, and robust zero-division guards.
    """

    def __init__(
        self,
        corpus: Sequence[Any],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.corpus_size = len(corpus)

        self.doc_tokens: list[list[str]] = []
        self.doc_len: list[int] = []
        self.doc_freqs: Counter[str] = Counter()
        self.idf: dict[str, float] = {}

        total_tokens = 0
        for doc in corpus:
            # doc can be an object with .text or a raw string
            text = doc.text if hasattr(doc, "text") else str(doc)
            tokens = tokenize(text)
            self.doc_tokens.append(tokens)
            doc_len = len(tokens)
            self.doc_len.append(doc_len)
            total_tokens += doc_len

            # Track unique terms per document for document frequency
            unique_terms = set(tokens)
            for term in unique_terms:
                self.doc_freqs[term] += 1

        self.avgdl = (total_tokens / self.corpus_size) if self.corpus_size > 0 else 0.0

        # Precompute Robertson-Zaragoza / Lucene non-negative IDF:
        # IDF(q) = ln(1 + (N - n(q) + 0.5) / (n(q) + 0.5))
        for term, freq in self.doc_freqs.items():
            self.idf[term] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query: str) -> list[float]:
        """
        Computes BM25 relevance scores for all documents in the corpus for the given query.
        """
        if self.corpus_size == 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return [0.0] * self.corpus_size

        scores = [0.0] * self.corpus_size
        avgdl = self.avgdl if self.avgdl > 0 else 1.0

        for term in query_tokens:
            if term not in self.idf:
                continue
            idf_val = self.idf[term]

            for idx, tokens in enumerate(self.doc_tokens):
                doc_len = self.doc_len[idx]
                if doc_len == 0:
                    continue
                # Count occurrences of term in doc
                tf = tokens.count(term)
                if tf == 0:
                    continue

                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / avgdl))
                if denom > 0:
                    scores[idx] += idf_val * (tf * (self.k1 + 1.0)) / denom

        return scores

    def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> list[tuple[Any, float, int]]:
        """
        Searches the corpus and returns top matching (document, score, index) tuples,
        sorted descending by score with deterministic tie-breaking on document index.
        """
        if self.corpus_size == 0 or not query.strip():
            return []

        scores = self.get_scores(query)
        # Collect candidate indices with score > min_score
        scored_candidates: list[tuple[Any, float, int]] = []
        for idx, score in enumerate(scores):
            if score > min_score:
                scored_candidates.append((self.corpus[idx], score, idx))

        # Sort descending by score; on tie, ascending by doc index
        scored_candidates.sort(key=lambda x: (-x[1], x[2]))
        return scored_candidates[:limit]
