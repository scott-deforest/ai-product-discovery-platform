"""Split extracted documents into overlapping, traceable chunks."""

import re


DEFAULT_CHUNK_SIZE = 180
DEFAULT_CHUNK_OVERLAP = 30


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text by word count while preserving original whitespace."""
    if chunk_size <= 0:
        raise ValueError("Chunk size must be greater than zero.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("Overlap must be at least zero and smaller than chunk size.")

    words = list(re.finditer(r"\S+", text))
    if not words:
        return []

    chunks = []
    step = chunk_size - overlap

    for start_index in range(0, len(words), step):
        end_index = min(start_index + chunk_size, len(words))
        start_character = words[start_index].start()
        end_character = words[end_index - 1].end()
        chunks.append(text[start_character:end_character].strip())

        if end_index == len(words):
            break

    return chunks
