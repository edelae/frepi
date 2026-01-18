"""Product Preference Tool - Preference collection and storage.

This tool manages product preferences for restaurants, including:
- Brand preferences
- Price thresholds
- Quality requirements
- Specification preferences
- Payment preferences

All preferences track their source for trust and debugging.
"""

from typing import Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ProductPreference:
    """A product preference with source tracking."""

    restaurant_id: int
    master_list_id: int
    preference_type: str  # 'brand', 'price', 'quality', 'specification', 'payment'
    preference_value: dict
    source: str  # 'onboarding', 'user_correction', 'invoice_extraction', 'learned'
    added_by: Optional[int] = None  # restaurant_people.id
    added_at: Optional[datetime] = None


async def save_product_preference(
    supabase_client,
    restaurant_id: int,
    master_list_id: int,
    preference_type: str,
    preference_value: dict,
    source: str,
    added_by: Optional[int] = None,
) -> dict:
    """
    Save a product preference to the database.

    Args:
        supabase_client: Supabase client instance
        restaurant_id: Restaurant ID
        master_list_id: Product ID from master_list
        preference_type: Type of preference (brand, price, quality, etc.)
        preference_value: The preference data (varies by type)
        source: Where this preference came from
        added_by: Optional person_id who added this preference

    Returns:
        Dict with created/updated preference ID

    Database interactions:
        - UPSERT into restaurant_product_preferences
        - INSERT into restaurant_product_preferences_history
    """
    # TODO: Implement preference saving
    pass


async def get_product_preferences(
    supabase_client,
    restaurant_id: int,
    master_list_id: int,
) -> dict:
    """
    Get all preferences for a specific product at a restaurant.

    Returns:
        Dict with all preference types for this product
    """
    # TODO: Implement preference retrieval
    pass


async def update_preference_from_correction(
    supabase_client,
    restaurant_id: int,
    master_list_id: int,
    preference_type: str,
    old_value: dict,
    new_value: dict,
    correction_reason: str,
    corrected_by: Optional[int] = None,
) -> dict:
    """
    Update a preference based on user correction (learning).

    This creates a history record to track preference evolution.

    Args:
        supabase_client: Supabase client
        restaurant_id: Restaurant ID
        master_list_id: Product ID
        preference_type: Type being corrected
        old_value: Previous preference value
        new_value: New preference value
        correction_reason: Why the user made this correction
        corrected_by: Person who made the correction

    Returns:
        Dict with updated preference and history record
    """
    # TODO: Implement preference update with history
    pass
