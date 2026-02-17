"""Product Preference Tool - Preference collection and storage.

This tool manages product preferences for restaurants, including:
- Brand preferences
- Price thresholds
- Quality requirements
- Specification preferences
- Payment preferences

All preferences track their source for trust and debugging.

During onboarding, preferences are staged in onboarding_staging_preferences.
After onboarding, preferences are stored directly in restaurant_product_preferences.
"""

from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
import logging

from frepi_agent.shared.supabase_client import get_supabase_client, Tables

logger = logging.getLogger(__name__)


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
    restaurant_id: int,
    master_list_id: int,
    preference_type: str,
    preference_value: dict,
    source: str,
    added_by: Optional[int] = None,
) -> dict:
    """
    Save a product preference to the production database.

    Use this for post-onboarding preference updates.

    Args:
        restaurant_id: Restaurant ID
        master_list_id: Product ID from master_list
        preference_type: Type of preference (brand, price, quality, etc.)
        preference_value: The preference data (varies by type)
        source: Where this preference came from
        added_by: Optional person_id who added this preference

    Returns:
        Dict with created/updated preference ID
    """
    try:
        client = get_supabase_client()
        now = datetime.now(timezone.utc).isoformat()

        # Build the update data based on preference type
        update_data = {
            "restaurant_id": restaurant_id,
            "master_list_id": master_list_id,
            "updated_at": now,
        }

        # Map preference type to database columns
        type_column_map = {
            "brand": ("brand_preferences", "brand_preferences_source", "brand_preferences_added_by", "brand_preferences_added_at"),
            "price": ("price_preference", "price_preference_source", "price_preference_added_by", "price_preference_added_at"),
            "quality": ("quality_preference", "quality_preference_source", "quality_preference_added_by", "quality_preference_added_at"),
            "specification": ("specification_preferences", "specification_preferences_source", "specification_preferences_added_by", "specification_preferences_added_at"),
            "payment": ("payment_preference", "payment_preference_source", "payment_preference_added_by", "payment_preference_added_at"),
        }

        if preference_type not in type_column_map:
            return {"status": "error", "message": f"Unknown preference type: {preference_type}"}

        value_col, source_col, by_col, at_col = type_column_map[preference_type]
        update_data[value_col] = preference_value
        update_data[source_col] = source
        if added_by:
            update_data[by_col] = added_by
        update_data[at_col] = now

        # Check if preference record exists
        existing = client.table(Tables.RESTAURANT_PRODUCT_PREFERENCES)\
            .select("id")\
            .eq("restaurant_id", restaurant_id)\
            .eq("master_list_id", master_list_id)\
            .limit(1)\
            .execute()

        if existing.data:
            # Update existing record
            result = client.table(Tables.RESTAURANT_PRODUCT_PREFERENCES)\
                .update(update_data)\
                .eq("id", existing.data[0]["id"])\
                .execute()
            logger.info(f"Updated {preference_type} preference for product {master_list_id}")
        else:
            # Insert new record
            update_data["created_at"] = now
            result = client.table(Tables.RESTAURANT_PRODUCT_PREFERENCES)\
                .insert(update_data)\
                .execute()
            logger.info(f"Created {preference_type} preference for product {master_list_id}")

        if result.data:
            return {
                "status": "success",
                "preference_id": result.data[0]["id"],
                "preference_type": preference_type
            }
        else:
            return {"status": "error", "message": "Failed to save preference"}

    except Exception as e:
        logger.error(f"Error saving preference: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def get_product_preferences(
    restaurant_id: int,
    master_list_id: int,
) -> dict:
    """
    Get all preferences for a specific product at a restaurant.

    Returns:
        Dict with all preference types for this product
    """
    try:
        client = get_supabase_client()

        result = client.table(Tables.RESTAURANT_PRODUCT_PREFERENCES)\
            .select("*")\
            .eq("restaurant_id", restaurant_id)\
            .eq("master_list_id", master_list_id)\
            .limit(1)\
            .execute()

        if not result.data:
            return {
                "status": "success",
                "preferences": {},
                "message": "No preferences found for this product"
            }

        pref = result.data[0]
        preferences = {}

        # Extract each preference type if it exists
        if pref.get("brand_preferences"):
            preferences["brand"] = {
                "value": pref["brand_preferences"],
                "source": pref.get("brand_preferences_source"),
                "added_at": pref.get("brand_preferences_added_at")
            }

        if pref.get("price_preference"):
            preferences["price"] = {
                "value": pref["price_preference"],
                "source": pref.get("price_preference_source"),
                "added_at": pref.get("price_preference_added_at")
            }

        if pref.get("quality_preference"):
            preferences["quality"] = {
                "value": pref["quality_preference"],
                "source": pref.get("quality_preference_source"),
                "added_at": pref.get("quality_preference_added_at")
            }

        if pref.get("specification_preferences"):
            preferences["specification"] = {
                "value": pref["specification_preferences"],
                "source": pref.get("specification_preferences_source"),
                "added_at": pref.get("specification_preferences_added_at")
            }

        if pref.get("payment_preference"):
            preferences["payment"] = {
                "value": pref["payment_preference"],
                "source": pref.get("payment_preference_source"),
                "added_at": pref.get("payment_preference_added_at")
            }

        return {
            "status": "success",
            "preferences": preferences,
            "preference_id": pref["id"]
        }

    except Exception as e:
        logger.error(f"Error getting preferences: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def update_preference_from_correction(
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

    This saves the new preference and logs the correction for learning.

    Args:
        restaurant_id: Restaurant ID
        master_list_id: Product ID
        preference_type: Type being corrected
        old_value: Previous preference value
        new_value: New preference value
        correction_reason: Why the user made this correction
        corrected_by: Person who made the correction

    Returns:
        Dict with updated preference
    """
    try:
        # Save the new preference with 'user_correction' source
        result = await save_product_preference(
            restaurant_id=restaurant_id,
            master_list_id=master_list_id,
            preference_type=preference_type,
            preference_value=new_value,
            source="user_correction",
            added_by=corrected_by
        )

        if result.get("status") == "success":
            logger.info(
                f"Preference corrected: {preference_type} for product {master_list_id}. "
                f"Reason: {correction_reason}"
            )
            # Could add history tracking here if needed
            result["correction_logged"] = True
            result["correction_reason"] = correction_reason

        return result

    except Exception as e:
        logger.error(f"Error updating preference from correction: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def stage_preference_for_onboarding(
    session_id: UUID,
    preference_type: str,
    preference_value: dict,
    staging_product_id: Optional[UUID] = None,
    source: str = "inferred",
    confidence_score: float = 0.8,
    inference_reasoning: Optional[str] = None,
) -> dict:
    """
    Stage a preference during onboarding (before committing to production).

    Args:
        session_id: Onboarding session ID
        preference_type: Type of preference
        preference_value: The preference data
        staging_product_id: Optional product this preference applies to
        source: Source of preference (inferred, user_stated)
        confidence_score: How confident is this inference
        inference_reasoning: Why was this preference inferred

    Returns:
        Dict with staged preference ID
    """
    try:
        client = get_supabase_client()
        now = datetime.now(timezone.utc).isoformat()

        data = {
            "session_id": str(session_id),
            "preference_type": preference_type,
            "preference_value": preference_value,
            "source": source,
            "confidence_score": confidence_score,
            "created_at": now,
            "updated_at": now,
        }

        if staging_product_id:
            data["staging_product_id"] = str(staging_product_id)
        if inference_reasoning:
            data["inference_reasoning"] = inference_reasoning

        result = client.table(Tables.ONBOARDING_STAGING_PREFERENCES)\
            .insert(data)\
            .execute()

        if result.data:
            return {
                "status": "success",
                "staged_preference_id": result.data[0]["id"]
            }
        else:
            return {"status": "error", "message": "Failed to stage preference"}

    except Exception as e:
        logger.error(f"Error staging preference: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def get_staged_preferences(
    session_id: UUID,
    preference_type: Optional[str] = None,
) -> List[dict]:
    """
    Get all staged preferences for an onboarding session.

    Args:
        session_id: Onboarding session ID
        preference_type: Optional filter by type

    Returns:
        List of staged preferences
    """
    try:
        client = get_supabase_client()

        query = client.table(Tables.ONBOARDING_STAGING_PREFERENCES)\
            .select("*")\
            .eq("session_id", str(session_id))

        if preference_type:
            query = query.eq("preference_type", preference_type)

        result = query.order("created_at").execute()

        return result.data or []

    except Exception as e:
        logger.error(f"Error getting staged preferences: {e}", exc_info=True)
        return []
