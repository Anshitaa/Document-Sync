"""
RAG (Retrieval-Augmented Generation) pipeline for Docu-Sync.

Instead of blindly taking the first N characters of a README, this module:
  1. Chunks the README into meaningful sections (by markdown headers / paragraphs)
  2. Embeds each chunk using Gemini text-embedding-004
  3. Embeds the change summary (the query)
  4. Retrieves the top-k most semantically relevant chunks via cosine similarity
  5. Returns those chunks as focused context for the documentation generator

Design decision: semantic retrieval over truncation
---------------------------------------------------
Naive truncation (readme[:500]) always feeds the same boilerplate intro text
regardless of what actually changed.  A RAG approach retrieves the section
that is *most relevant to the detected change* — e.g. if a navigation bar
changed, it retrieves the UI/Navigation section of the README rather than
the project description at the top.  This produces significantly more
accurate and context-aware documentation updates.
"""

import re
import logging
import numpy as np
import google.generativeai as genai

logger = logging.getLogger("docu-sync.rag")

# Gemini's best embedding model (free tier, 768-dim)
EMBEDDING_MODEL = "models/text-embedding-004"

# ── Chunking ───────────────────────────────────────────────────────────────────


def chunk_markdown(text: str, max_chunk_chars: int = 500) -> list[dict]:
    """
    Split a markdown document into semantically meaningful chunks.

    Strategy:
    - Primary split: on ## / ### headers (each section becomes a chunk)
    - Secondary split: if a section exceeds max_chunk_chars, split further
      by double newlines (paragraph boundaries)

    Args:
        text: full markdown content
        max_chunk_chars: max character length for a single chunk

    Returns:
        list of dicts: [{"text": str, "heading": str}, ...]
    """
    if not text or not text.strip():
        return []

    # Split on markdown headers (##, ###, ####)
    sections = re.split(r'\n(?=#{1,4}\s)', text.strip())
    chunks = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Extract heading for metadata
        first_line = section.splitlines()[0]
        heading = first_line.lstrip('#').strip() if first_line.startswith('#') else "Introduction"

        if len(section) <= max_chunk_chars:
            chunks.append({"text": section, "heading": heading})
        else:
            # Split long sections by paragraph
            paragraphs = [p.strip() for p in section.split('\n\n') if p.strip()]
            for para in paragraphs:
                if len(para) > max_chunk_chars:
                    # Hard split as last resort
                    for i in range(0, len(para), max_chunk_chars):
                        chunks.append({"text": para[i:i + max_chunk_chars], "heading": heading})
                else:
                    chunks.append({"text": para, "heading": heading})

    logger.debug("Chunked README into %d sections", len(chunks))
    return chunks


# ── Embedding ──────────────────────────────────────────────────────────────────


def _embed_batch(texts: list[str], task_type: str) -> np.ndarray:
    """
    Embed a list of texts using Gemini text-embedding-004.

    Args:
        texts: list of strings to embed
        task_type: "retrieval_document" for corpus, "retrieval_query" for queries

    Returns:
        numpy array of shape (len(texts), 768)
    """
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=texts,
        task_type=task_type,
    )
    # result['embedding'] is a list of lists when content is a list
    embeddings = result.get('embedding', [])
    if embeddings and not isinstance(embeddings[0], list):
        # Single embedding returned — wrap it
        embeddings = [embeddings]
    return np.array(embeddings, dtype=np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors."""
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 1e-9 else 0.0


# ── Retrieval ──────────────────────────────────────────────────────────────────


def retrieve_relevant_chunks(
    query: str,
    chunks: list[dict],
    top_k: int = 3,
) -> list[dict]:
    """
    Retrieve the top-k most relevant chunks for a given query.

    Args:
        query: the change summary / search query
        chunks: list of chunk dicts (from chunk_markdown)
        top_k: number of chunks to return

    Returns:
        list of top-k chunk dicts, sorted by relevance (most relevant first)
    """
    if not chunks:
        return []

    top_k = min(top_k, len(chunks))

    # Embed query
    query_emb = _embed_batch([query], task_type="retrieval_query")[0]

    # Embed all document chunks
    chunk_texts = [c["text"] for c in chunks]
    chunk_embs = _embed_batch(chunk_texts, task_type="retrieval_document")

    # Score and rank
    scored = [
        (_cosine_similarity(query_emb, chunk_embs[i]), chunks[i])
        for i in range(len(chunks))
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    top = scored[:top_k]
    logger.info(
        "RAG retrieval: top-%d scores = %s",
        top_k,
        [f"{s:.3f}" for s, _ in top],
    )
    return [chunk for _, chunk in top]


# ── Public API ─────────────────────────────────────────────────────────────────


def build_rag_context(
    change_summary: str,
    readme_content: str,
    top_k: int = 3,
) -> dict:
    """
    Build a RAG context block from a README and a change summary.

    This is the main entry point called by llm_client.generate_documentation().

    Args:
        change_summary: description of the detected UI changes (used as query)
        readme_content: full README / documentation text to search
        top_k: number of relevant chunks to retrieve

    Returns:
        dict with:
            "context":          str  — concatenated retrieved sections
            "chunks_retrieved": int  — how many chunks were retrieved
            "total_chunks":     int  — total chunks in the document
            "headings":         list[str] — headings of retrieved sections
    """
    if not readme_content or not readme_content.strip():
        logger.info("RAG: no README content provided, skipping retrieval")
        return {"context": "", "chunks_retrieved": 0, "total_chunks": 0, "headings": []}

    try:
        chunks = chunk_markdown(readme_content)
        if not chunks:
            return {"context": readme_content[:500], "chunks_retrieved": 1, "total_chunks": 1, "headings": []}

        logger.info("RAG: %d chunks indexed, retrieving top-%d for query", len(chunks), top_k)
        relevant = retrieve_relevant_chunks(change_summary, chunks, top_k=top_k)

        context = "\n\n---\n\n".join(c["text"] for c in relevant)
        headings = [c["heading"] for c in relevant]

        logger.info(
            "RAG: retrieved sections: %s (%d chars of context)",
            headings,
            len(context),
        )
        return {
            "context": context,
            "chunks_retrieved": len(relevant),
            "total_chunks": len(chunks),
            "headings": headings,
        }

    except Exception as e:
        # RAG failing should never crash the main pipeline — degrade gracefully
        logger.warning("RAG retrieval failed, falling back to truncation: %s", e)
        return {
            "context": readme_content[:500],
            "chunks_retrieved": 1,
            "total_chunks": 1,
            "headings": [],
        }
