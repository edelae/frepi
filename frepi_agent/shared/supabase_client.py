"""
Supabase client for database operations.

Provides connection management and base operations for Frepi tables.
"""

from typing import Any, Optional

from supabase import create_client, Client

from frepi_agent.config import get_config


_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Get the Supabase client instance."""
    global _client
    if _client is None:
        config = get_config()
        _client = create_client(config.supabase_url, config.supabase_key)
    return _client


def reset_client():
    """Reset the client (useful for testing)."""
    global _client
    _client = None


# Table names as constants
class Tables:
    # Production tables
    MASTER_LIST = "master_list"
    SUPPLIER_MAPPED_PRODUCTS = "supplier_mapped_products"
    PRICING_HISTORY = "pricing_history"
    SUPPLIERS = "suppliers"
    RESTAURANTS = "restaurants"
    RESTAURANT_PEOPLE = "restaurant_people"
    RESTAURANT_PRODUCT_PREFERENCES = "restaurant_product_preferences"
    PURCHASE_ORDERS = "purchase_orders"
    LINE_SESSIONS = "line_sessions"
    USER_PREFERENCES = "user_preferences"

    # Onboarding staging tables
    ONBOARDING_SESSIONS = "onboarding_sessions"
    ONBOARDING_STAGING_SUPPLIERS = "onboarding_staging_suppliers"
    ONBOARDING_STAGING_PRODUCTS = "onboarding_staging_products"
    ONBOARDING_STAGING_PRICES = "onboarding_staging_prices"
    ONBOARDING_STAGING_PREFERENCES = "onboarding_staging_preferences"
    ONBOARDING_INVOICE_PHOTOS = "onboarding_invoice_photos"
    ONBOARDING_ANALYSIS_INSIGHTS = "onboarding_analysis_insights"

    # Preference & engagement tables (shared across agents)
    PREFERENCE_COLLECTION_QUEUE = "preference_collection_queue"
    ENGAGEMENT_PROFILE = "engagement_profile"
    PREFERENCE_CORRECTIONS = "preference_corrections"


async def fetch_one(table: str, filters: dict[str, Any]) -> Optional[dict]:
    """
    Fetch a single record from a table.

    Args:
        table: Table name
        filters: Dictionary of column=value filters

    Returns:
        Single record dict or None if not found
    """
    client = get_supabase_client()
    query = client.table(table).select("*")

    for column, value in filters.items():
        query = query.eq(column, value)

    result = query.limit(1).execute()

    if result.data:
        return result.data[0]
    return None


async def fetch_many(
    table: str,
    filters: Optional[dict[str, Any]] = None,
    order_by: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Fetch multiple records from a table.

    Args:
        table: Table name
        filters: Optional dictionary of column=value filters
        order_by: Optional column name to order by (prefix with '-' for descending)
        limit: Optional limit on number of records

    Returns:
        List of record dicts
    """
    client = get_supabase_client()
    query = client.table(table).select("*")

    if filters:
        for column, value in filters.items():
            if isinstance(value, list):
                query = query.in_(column, value)
            else:
                query = query.eq(column, value)

    if order_by:
        if order_by.startswith("-"):
            query = query.order(order_by[1:], desc=True)
        else:
            query = query.order(order_by)

    if limit:
        query = query.limit(limit)

    result = query.execute()
    return result.data or []


async def insert_one(table: str, data: dict[str, Any]) -> dict:
    """
    Insert a single record into a table.

    Args:
        table: Table name
        data: Record data to insert

    Returns:
        Inserted record dict
    """
    client = get_supabase_client()
    result = client.table(table).insert(data).execute()

    if result.data:
        return result.data[0]
    raise Exception(f"Insert failed: {result}")


async def update_one(
    table: str, filters: dict[str, Any], data: dict[str, Any]
) -> Optional[dict]:
    """
    Update a single record in a table.

    Args:
        table: Table name
        filters: Dictionary of column=value filters to identify the record
        data: Data to update

    Returns:
        Updated record dict or None if not found
    """
    client = get_supabase_client()
    query = client.table(table).update(data)

    for column, value in filters.items():
        query = query.eq(column, value)

    result = query.execute()

    if result.data:
        return result.data[0]
    return None


async def execute_rpc(function_name: str, params: dict[str, Any]) -> Any:
    """
    Execute a Supabase RPC function.

    Args:
        function_name: Name of the database function
        params: Parameters to pass to the function

    Returns:
        Function result
    """
    client = get_supabase_client()
    result = client.rpc(function_name, params).execute()
    return result.data


async def test_connection() -> bool:
    """
    Test the database connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        client = get_supabase_client()
        # Try to fetch from master_list to verify connection
        result = client.table(Tables.MASTER_LIST).select("id").limit(1).execute()
        return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False
