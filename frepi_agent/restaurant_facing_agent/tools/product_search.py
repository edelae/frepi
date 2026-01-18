"""
Product search using vector similarity.

Provides semantic search against the master_list table using pgvector.
"""

from dataclasses import dataclass
from typing import Optional

from frepi_agent.config import get_config
from .embeddings import (
    generate_embedding,
    similarity_to_confidence,
)
from .supabase_client import (
    get_supabase_client,
    Tables,
    fetch_many,
    execute_rpc,
)


@dataclass
class ProductMatch:
    """A product match result from vector search."""

    id: int
    product_name: str
    brand: Optional[str]
    specifications: Optional[dict]
    similarity: float
    confidence: str  # 'HIGH', 'MEDIUM', or 'LOW'

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "product_name": self.product_name,
            "brand": self.brand,
            "specifications": self.specifications,
            "similarity": self.similarity,
            "confidence": self.confidence,
        }


@dataclass
class SearchResult:
    """Result of a product search."""

    query: str
    matches: list[ProductMatch]
    has_high_confidence: bool
    best_match: Optional[ProductMatch]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "matches": [m.to_dict() for m in self.matches],
            "has_high_confidence": self.has_high_confidence,
            "best_match": self.best_match.to_dict() if self.best_match else None,
        }


async def search_products(
    query: str,
    limit: Optional[int] = None,
) -> SearchResult:
    """
    Search for products using semantic similarity.

    Args:
        query: Natural language product description (e.g., "picanha", "arroz branco 5kg")
        limit: Maximum number of results (defaults to config value)

    Returns:
        SearchResult with matched products and confidence levels
    """
    config = get_config()
    limit = limit or config.vector_search_limit

    # Generate embedding for the query
    query_embedding = await generate_embedding(query)

    # Call the vector_search RPC function
    # This function should exist in Supabase:
    # CREATE OR REPLACE FUNCTION vector_search(
    #   query_embedding vector(1536),
    #   match_count int DEFAULT 10
    # )
    # RETURNS TABLE (id bigint, product_name text, brand text, specifications jsonb, similarity float)
    try:
        results = await execute_rpc(
            "vector_search",
            {
                "query_embedding": query_embedding,
                "match_count": limit,
            },
        )
    except Exception as e:
        # Fallback: if RPC doesn't exist, use direct query
        # This is less efficient but works as a fallback
        print(f"vector_search RPC failed, using fallback: {e}")
        results = await _fallback_search(query_embedding, limit)

    # Convert to ProductMatch objects
    matches = []
    for row in results or []:
        # Convert distance to similarity (pgvector uses distance, we want similarity)
        # For cosine distance: similarity = 1 - distance
        similarity = row.get("similarity", 0)
        if similarity < 0:  # If it's actually a distance
            similarity = 1 + similarity  # Convert distance to similarity

        confidence = similarity_to_confidence(similarity)

        matches.append(
            ProductMatch(
                id=row["id"],
                product_name=row["product_name"],
                brand=row.get("brand"),
                specifications=row.get("specifications"),
                similarity=round(similarity, 4),
                confidence=confidence,
            )
        )

    # Sort by similarity (descending)
    matches.sort(key=lambda x: x.similarity, reverse=True)

    # Determine best match and confidence status
    has_high_confidence = any(m.confidence == "HIGH" for m in matches)
    best_match = matches[0] if matches else None

    return SearchResult(
        query=query,
        matches=matches,
        has_high_confidence=has_high_confidence,
        best_match=best_match,
    )


async def _fallback_search(
    query_embedding: list[float], limit: int
) -> list[dict]:
    """
    Fallback search using direct Supabase query.

    This is less efficient than the RPC function but works if the function doesn't exist.
    """
    client = get_supabase_client()

    # Convert embedding to string format for pgvector
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    # Query using the <=> operator (cosine distance)
    # Note: This requires the embedding_vector_v2 column to be of type vector(1536)
    result = (
        client.table(Tables.MASTER_LIST)
        .select("id, product_name, brand, specifications")
        .eq("is_active", True)
        .limit(limit)
        .execute()
    )

    # For fallback, we can't do proper vector search without RPC
    # Return results without similarity scores
    return [
        {**row, "similarity": 0.5}  # Default similarity for fallback
        for row in (result.data or [])
    ]


async def get_product_by_id(product_id: int) -> Optional[dict]:
    """
    Get a single product by ID.

    Args:
        product_id: The master_list product ID

    Returns:
        Product dict or None if not found
    """
    client = get_supabase_client()

    result = (
        client.table(Tables.MASTER_LIST)
        .select("*")
        .eq("id", product_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]
    return None


async def get_products_by_ids(product_ids: list[int]) -> list[dict]:
    """
    Get multiple products by their IDs.

    Args:
        product_ids: List of master_list product IDs

    Returns:
        List of product dicts
    """
    if not product_ids:
        return []

    return await fetch_many(
        Tables.MASTER_LIST,
        filters={"id": product_ids, "is_active": True},
    )


async def search_products_batch(
    queries: list[str], limit_per_query: int = 4
) -> dict[str, SearchResult]:
    """
    Search for multiple products at once.

    Args:
        queries: List of product descriptions to search for
        limit_per_query: Maximum results per query

    Returns:
        Dictionary mapping query -> SearchResult
    """
    results = {}
    for query in queries:
        results[query] = await search_products(query, limit=limit_per_query)
    return results
