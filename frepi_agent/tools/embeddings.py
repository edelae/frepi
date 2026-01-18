"""
OpenAI embedding generation for semantic product search.

Uses text-embedding-3-small model with 1536 dimensions.
"""

from typing import Optional

from openai import OpenAI

from frepi_agent.config import get_config


_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Get the OpenAI client instance."""
    global _client
    if _client is None:
        config = get_config()
        _client = OpenAI(api_key=config.openai_api_key)
    return _client


def reset_client():
    """Reset the client (useful for testing)."""
    global _client
    _client = None


async def generate_embedding(text: str) -> list[float]:
    """
    Generate an embedding vector for the given text.

    Args:
        text: Text to embed (product name, description, etc.)

    Returns:
        List of floats representing the embedding vector (1536 dimensions)
    """
    config = get_config()
    client = get_openai_client()

    response = client.embeddings.create(
        model=config.embedding_model,
        input=text,
        dimensions=config.embedding_dimensions,
    )

    return response.data[0].embedding


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embedding vectors for multiple texts.

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    config = get_config()
    client = get_openai_client()

    response = client.embeddings.create(
        model=config.embedding_model,
        input=texts,
        dimensions=config.embedding_dimensions,
    )

    # Sort by index to maintain order
    sorted_data = sorted(response.data, key=lambda x: x.index)
    return [item.embedding for item in sorted_data]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec_a: First vector
        vec_b: Second vector

    Returns:
        Cosine similarity score (0.0 to 1.0)
    """
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def similarity_to_confidence(similarity: float) -> str:
    """
    Convert similarity score to confidence level.

    Args:
        similarity: Cosine similarity score (0.0 to 1.0)

    Returns:
        Confidence level: 'HIGH', 'MEDIUM', or 'LOW'
    """
    config = get_config()

    if similarity >= config.high_confidence_threshold:
        return "HIGH"
    elif similarity >= config.medium_confidence_threshold:
        return "MEDIUM"
    else:
        return "LOW"
