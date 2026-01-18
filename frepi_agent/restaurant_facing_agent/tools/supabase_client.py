"""
Supabase client for database operations.

Re-exports from the shared module for backwards compatibility.
"""

# Re-export everything from shared module
from frepi_agent.shared.supabase_client import (
    get_supabase_client,
    reset_client,
    Tables,
    fetch_one,
    fetch_many,
    insert_one,
    update_one,
    execute_rpc,
    test_connection,
)

__all__ = [
    "get_supabase_client",
    "reset_client",
    "Tables",
    "fetch_one",
    "fetch_many",
    "insert_one",
    "update_one",
    "execute_rpc",
    "test_connection",
]
