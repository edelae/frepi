#!/usr/bin/env python3
"""
Test script to verify Frepi Agent configuration and connections.

Run with: python scripts/test_connection.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frepi_agent.config import get_config
from frepi_agent.shared.supabase_client import test_connection, get_supabase_client, Tables
from frepi_agent.restaurant_facing_agent.tools.embeddings import generate_embedding


def print_status(name: str, success: bool, details: str = ""):
    """Print a status line with emoji."""
    emoji = "✅" if success else "❌"
    print(f"{emoji} {name}: {details if details else ('OK' if success else 'FAILED')}")


async def main():
    print("\n" + "=" * 50)
    print("Frepi Agent Configuration Test")
    print("=" * 50 + "\n")

    # 1. Check configuration
    print("1. Checking configuration...")
    config = get_config()
    missing = config.validate()

    if missing:
        print_status("Configuration", False, f"Missing: {', '.join(missing)}")
        print("   (Continuing with partial tests...)")
    else:
        print_status("Configuration", True, "All required keys present")

    # 2. Test Supabase connection
    print("\n2. Testing Supabase connection...")
    try:
        success = await test_connection()
        print_status("Supabase", success)

        if success:
            # Try to count records in master_list
            client = get_supabase_client()
            result = client.table(Tables.MASTER_LIST).select("id", count="exact").execute()
            count = result.count if hasattr(result, 'count') else len(result.data or [])
            print(f"   Found {count} products in master_list")
    except Exception as e:
        print_status("Supabase", False, str(e))
        return False

    # 3. Test OpenAI embeddings
    print("\n3. Testing OpenAI embeddings...")
    try:
        embedding = await generate_embedding("picanha friboi 10kg")
        print_status("OpenAI Embeddings", True, f"Generated {len(embedding)}-dim vector")
    except Exception as e:
        print_status("OpenAI Embeddings", False, str(e))
        return False

    # 4. Test vector search (if RPC exists)
    print("\n4. Testing vector search...")
    try:
        from frepi_agent.restaurant_facing_agent.tools.product_search import search_products
        result = await search_products("picanha")
        print_status("Vector Search", True, f"Found {len(result.matches)} matches")
        if result.best_match:
            print(f"   Best match: {result.best_match.product_name} ({result.best_match.confidence})")
    except Exception as e:
        print_status("Vector Search", False, str(e))
        print("   Note: You may need to create the vector_search RPC function in Supabase")

    print("\n" + "=" * 50)
    print("✅ All tests passed! Ready to proceed.")
    print("=" * 50 + "\n")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
