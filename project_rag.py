"""
Per-project vector RAG for the research app.

Builds a lightweight FAISS index from a project's corpus files,
embeds queries with SentenceTransformer, and returns the top-k
most relevant passages. Lazy-loads the model on first use.

Designed to be self-contained — no dependency on main.py's RAG system.
"""

import logging
import numpy as np
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

# Lazy-loaded globals
_embedding_model = None
_MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model():
    """Lazy-load the SentenceTransformer model on first use."""
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading SentenceTransformer model '{_MODEL_NAME}'...")
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(_MODEL_NAME)
        logger.info("SentenceTransformer model loaded.")
    return _embedding_model


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
            # Look backward from end for a sentence boundary
            for i in range(end, max(start + chunk_size // 2, start), -1):
                if text[i] in ".!?\n" and i + 1 < text_len:
                    end = i + 1
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap if end < text_len else text_len

    return chunks


def build_project_index(corpus_texts: List[str], chunk_size: int = 500, overlap: int = 100) -> Tuple[Optional[object], List[str]]:
    """
    Build a FAISS index from a list of corpus texts.

    Args:
        corpus_texts: list of full text content from corpus files
        chunk_size: characters per chunk
        overlap: overlap between chunks

    Returns:
        (faiss_index, chunks_list) or (None, []) if empty
    """
    import faiss

    # Chunk all texts
    all_chunks = []
    for text in corpus_texts:
        all_chunks.extend(chunk_text(text, chunk_size, overlap))

    if not all_chunks:
        logger.warning("No chunks produced from corpus texts.")
        return None, []

    logger.info(f"Embedding {len(all_chunks)} chunks for project index...")
    model = _get_model()
    embeddings = model.encode(all_chunks, show_progress_bar=False, convert_to_numpy=True)

    # Normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms

    # Build FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # Inner product on normalized = cosine sim
    index.add(embeddings.astype(np.float32))

    logger.info(f"FAISS index built with {index.ntotal} vectors (dim={dim}).")
    return index, all_chunks


def retrieve(query: str, faiss_index, chunks: List[str], top_k: int = 5) -> List[dict]:
    """
    Retrieve the top-k most relevant chunks for a query.

    Returns:
        list of {"text": str, "score": float, "rank": int}
    """
    if faiss_index is None or not chunks:
        return []

    model = _get_model()
    query_embedding = model.encode([query], convert_to_numpy=True)

    # Normalize
    norm = np.linalg.norm(query_embedding)
    if norm > 0:
        query_embedding = query_embedding / norm

    distances, indices = faiss_index.search(query_embedding.astype(np.float32), min(top_k, len(chunks)))

    results = []
    for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        if idx < 0:
            continue
        results.append({
            "text": chunks[idx],
            "score": float(dist),
            "rank": rank + 1,
        })

    return results


def keyword_retrieve(query: str, corpus_texts: List[str], top_k: int = 5) -> List[dict]:
    """
    Simple keyword-based retrieval (the existing approach).
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
