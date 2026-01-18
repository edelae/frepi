"""
Shared utilities and tools for Frepi Agent.

This module contains common functionality used by both
restaurant_facing_agent and supplier_facing_agent.
"""

from .supabase_client import (
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
from .user_identification import (
    identify_user,
    UserType,
    UserIdentification,
)

__all__ = [
    # Supabase client
    "get_supabase_client",
    "reset_client",
    "Tables",
    "fetch_one",
    "fetch_many",
    "insert_one",
    "update_one",
    "execute_rpc",
    "test_connection",
    # User identification
    "identify_user",
    "UserType",
    "UserIdentification",
]
