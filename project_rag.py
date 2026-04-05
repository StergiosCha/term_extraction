"""
Per-project vector RAG for the research app.

Embeds corpus chunks via the OpenAI embeddings API (text-embedding-3-small),
then retrieves top-k by cosine similarity using numpy. No local ML models,
no FAISS, no PyTorch — runs on Render's free tier without issues.

Also provides keyword-based retrieval for comparison experiments.
"""

import os
import logging
import numpy as np
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

_EMBED_MODEL = "text-embedding-3-small"
_openai_client = None


def _get_openai_client():
    """Lazy-init OpenAI client."""
    global _openai_client
    if _openai_client is None:
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set — cannot use vector RAG")
        _openai_client = openai.OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized for embeddings.")
    return _openai_client


def _embed_texts(texts: List[str]) -> np.ndarray:
    """
    Embed a list of texts using OpenAI's embedding API.
    Batches automatically (API supports up to 2048 inputs).
    Returns a numpy array of shape (len(texts), embedding_dim).
    """
    client = _get_openai_client()

    # OpenAI API has a limit on input size; batch in groups of 100
    all_embeddings = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embeddings.create(model=_EMBED_MODEL, input=batch)
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    return np.array(all_embeddings, dtype=np.float32)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """
    Split text into overlapping chunks by character count.
    Tries to break at sentence boundaries when possible.
    """
    if not text or not text.strip():
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Try to break at a sentence boundary (., !, ?)
        if end < text_len:
            for i in range(end, max(start + chunk_size // 2, start), -1):
                if text[i] in ".!?\n" and i + 1 < text_len:
                    end = i + 1
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap if end < text_len else text_len

    return chunks


def build_project_index(corpus_texts: List[str], chunk_size: int = 500, overlap: int = 100) -> Tuple[Optional[np.ndarray], List[str]]:
    """
    Build an embedding index from corpus texts using OpenAI API.

    Returns:
        (embeddings_matrix, chunks_list) or (None, []) if empty
    """
    all_chunks = []
    for text in corpus_texts:
        all_chunks.extend(chunk_text(text, chunk_size, overlap))

    if not all_chunks:
        logger.warning("No chunks produced from corpus texts.")
        return None, []

    logger.info(f"Embedding {len(all_chunks)} chunks via OpenAI API...")
    embeddings = _embed_texts(all_chunks)

    # Normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms

    logger.info(f"Embeddings ready: {embeddings.shape[0]} vectors (dim={embeddings.shape[1]}).")
    return embeddings, all_chunks


def retrieve(query: str, embeddings: Optional[np.ndarray], chunks: List[str], top_k: int = 5) -> List[dict]:
    """
    Retrieve the top-k most relevant chunks for a query using cosine similarity.

    Returns:
        list of {"text": str, "score": float, "rank": int}
    """
    if embeddings is None or not chunks:
        return []

    # Embed the query
    query_embedding = _embed_texts([query])
    norm = np.linalg.norm(query_embedding)
    if norm > 0:
        query_embedding = query_embedding / norm

    # Cosine similarity = dot product on normalized vectors
    similarities = np.dot(embeddings, query_embedding.T).flatten()

    # Get top-k indices
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for rank, idx in enumerate(top_indices):
        results.append({
            "text": chunks[idx],
            "score": float(similarities[idx]),
            "rank": rank + 1,
        })

    return results


def keyword_retrieve(query: str, corpus_texts: List[str], top_k: int = 5) -> List[dict]:
    """
    Simple keyword-based retrieval.
    Finds lines containing the query term.

    Returns:
        list of {"text": str, "score": float, "rank": int}
    """
    query_lower = query.lower()
    all_lines = []
    for text in corpus_texts:
        for line in text.split("\n"):
            line = line.strip()
            if line and query_lower in line.lower():
                all_lines.append(line)

    # Deduplicate and take top_k
    seen = set()
    unique_lines = []
    for line in all_lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)

    results = []
    for rank, line in enumerate(unique_lines[:top_k]):
        results.append({
            "text": line,
            "score": 1.0,  # keyword match = binary
            "rank": rank + 1,
        })

    return results
