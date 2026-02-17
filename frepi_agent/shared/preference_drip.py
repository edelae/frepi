"""
Preference Drip Service - Progressive preference collection after onboarding.

Sneaks 1-2 preference questions into normal sessions based on engagement level.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from frepi_agent.shared.supabase_client import get_supabase_client, Tables
from frepi_agent.shared.engagement_scoring import recalculate_engagement

logger = logging.getLogger(__name__)


@dataclass
class DripQuestion:
    """A single drip question to ask the user."""
    product_name: str
    master_list_id: int
    preference_type: str
    queue_position: int
    importance_tier: str
    known_info: dict  # What we already know about this product


class PreferenceDripService:
    """
    Service for progressive preference collection via drip questions.

    Determines how many questions to ask per session based on engagement,
    then picks the highest-priority pending products from the queue.
    """

    def __init__(self):
        self.client = get_supabase_client()

    async def get_drip_questions(self, restaurant_id: int) -> List[DripQuestion]:
        """
        Get drip questions for this session.

        Returns:
            List of DripQuestion objects (0-2 depending on engagement)
        """
        # Load engagement profile
        profile_result = self.client.table(Tables.ENGAGEMENT_PROFILE).select(
            "*"
        ).eq("restaurant_id", restaurant_id).limit(1).execute()

        if not profile_result.data:
            return []

        profile = profile_result.data[0]
        level = profile.get("engagement_level", "low")
        drip_per_session = profile.get("drip_questions_per_session", 0)

        if drip_per_session == 0 or level in ("low", "dormant"):
            return []

        # Get pending items from the queue, ordered by position
        # For high engagement, include mid_tail products too
        tier_filter = ["head"]
        if level == "high":
            tier_filter.append("mid_tail")

        queue_result = self.client.table(
            Tables.PREFERENCE_COLLECTION_QUEUE
        ).select("*").eq(
            "restaurant_id", restaurant_id
        ).in_(
            "preference_status", ["pending", "asked_drip"]
        ).in_(
            "importance_tier", tier_filter
        ).order(
            "queue_position"
        ).limit(drip_per_session).execute()

        if not queue_result.data:
            return []

        questions = []
        for item in queue_result.data:
            # Get product name from master_list
            product_result = self.client.table(Tables.MASTER_LIST).select(
                "id, product_name, brand"
            ).eq("id", item["master_list_id"]).limit(1).execute()

            if not product_result.data:
                continue

            product = product_result.data[0]

            # Get existing preferences to know what we already have
            prefs_result = self.client.table(
                Tables.RESTAURANT_PRODUCT_PREFERENCES
            ).select("*").eq(
                "restaurant_id", restaurant_id
            ).eq("master_list_id", item["master_list_id"]).limit(1).execute()

            known_info = {}
            if prefs_result.data:
                pref = prefs_result.data[0]
                if pref.get("brand_preferences"):
                    known_info["brand"] = pref["brand_preferences"]
                if pref.get("price_preference"):
                    known_info["price_max"] = pref["price_preference"]
                if pref.get("quality_preference"):
                    known_info["quality"] = pref["quality_preference"]

            # Determine what to ask about
            pending = item.get("preferences_pending", [])
            if not pending:
                pending = ["brand", "price_max", "quality", "supplier"]

            # Pick first pending preference type
            pref_type = pending[0] if pending else "brand"

            questions.append(DripQuestion(
                product_name=product["product_name"],
                master_list_id=item["master_list_id"],
                preference_type=pref_type,
                queue_position=item["queue_position"],
                importance_tier=item["importance_tier"],
                known_info=known_info,
            ))

            # Mark as asked
            now = datetime.now(timezone.utc).isoformat()
            self.client.table(Tables.PREFERENCE_COLLECTION_QUEUE).update({
                "preference_status": "asked_drip",
                "asked_count": item.get("asked_count", 0) + 1,
                "last_asked_at": now,
            }).eq("id", item["id"]).execute()

        return questions

    async def record_drip_response(
        self,
        restaurant_id: int,
        master_list_id: int,
        preference_type: str,
        value: Optional[str] = None,
        skipped: bool = False,
    ):
        """
        Record a user's response to a drip question.

        Args:
            restaurant_id: Restaurant ID
            master_list_id: Product ID
            preference_type: Type of preference asked
            value: The user's answer (None if skipped)
            skipped: Whether the user skipped
        """
        now = datetime.now(timezone.utc).isoformat()

        if not skipped and value:
            # Save the preference to restaurant_product_preferences
            pref_data = {}
            source = "drip"

            if preference_type == "brand":
                pref_data["brand_preferences"] = {"brand": value}
                pref_data["brand_preferences_source"] = source
                pref_data["brand_preferences_added_at"] = now
            elif preference_type == "price_max":
                pref_data["price_preference"] = value
                pref_data["price_preference_source"] = source
                pref_data["price_preference_added_at"] = now
            elif preference_type == "quality":
                pref_data["quality_preference"] = {"quality": value}
                pref_data["quality_preference_source"] = source
                pref_data["quality_preference_added_at"] = now

            if pref_data:
                existing = self.client.table(
                    Tables.RESTAURANT_PRODUCT_PREFERENCES
                ).select("id").eq(
                    "restaurant_id", restaurant_id
                ).eq("master_list_id", master_list_id).limit(1).execute()

                if existing.data:
                    self.client.table(
                        Tables.RESTAURANT_PRODUCT_PREFERENCES
                    ).update(pref_data).eq("id", existing.data[0]["id"]).execute()
                else:
                    pref_data["restaurant_id"] = restaurant_id
                    pref_data["master_list_id"] = master_list_id
                    pref_data["is_active"] = True
                    self.client.table(
                        Tables.RESTAURANT_PRODUCT_PREFERENCES
                    ).insert(pref_data).execute()

        # Update queue status
        new_status = "collected" if not skipped else "skipped"
        queue_update = {"preference_status": new_status}

        if not skipped:
            # Move preference from pending to collected
            queue_item = self.client.table(
                Tables.PREFERENCE_COLLECTION_QUEUE
            ).select("preferences_collected, preferences_pending").eq(
                "restaurant_id", restaurant_id
            ).eq("master_list_id", master_list_id).limit(1).execute()

            if queue_item.data:
                collected = queue_item.data[0].get("preferences_collected", [])
                pending = queue_item.data[0].get("preferences_pending", [])
                if preference_type not in collected:
                    collected.append(preference_type)
                if preference_type in pending:
                    pending.remove(preference_type)
                queue_update["preferences_collected"] = collected
                queue_update["preferences_pending"] = pending

                # Only mark as "collected" if all pending are done
                if pending:
                    queue_update["preference_status"] = "asked_drip"

        self.client.table(Tables.PREFERENCE_COLLECTION_QUEUE).update(
            queue_update
        ).eq(
            "restaurant_id", restaurant_id
        ).eq("master_list_id", master_list_id).execute()

        # Update engagement profile counters
        profile = self.client.table(Tables.ENGAGEMENT_PROFILE).select(
            "drip_questions_answered, drip_questions_skipped"
        ).eq("restaurant_id", restaurant_id).limit(1).execute()

        if profile.data:
            p = profile.data[0]
            if skipped:
                self.client.table(Tables.ENGAGEMENT_PROFILE).update({
                    "drip_questions_skipped": p["drip_questions_skipped"] + 1,
                }).eq("restaurant_id", restaurant_id).execute()
            else:
                self.client.table(Tables.ENGAGEMENT_PROFILE).update({
                    "drip_questions_answered": p["drip_questions_answered"] + 1,
                }).eq("restaurant_id", restaurant_id).execute()

        # Recalculate engagement score after drip response
        try:
            recalculate_engagement(restaurant_id)
        except Exception as e:
            logger.warning(f"Failed to recalculate engagement: {e}")

    def format_drip_questions(self, questions: List[DripQuestion]) -> str:
        """
        Format drip questions as a natural Portuguese message to append to responses.

        Returns:
            Formatted string, or empty string if no questions
        """
        if not questions:
            return ""

        lines = ["\n\n---\n💡 **Aproveitando, uma perguntinha rápida:**\n"]

        for q in questions:
            if q.preference_type == "brand":
                lines.append(
                    f"Sobre **{q.product_name}**: tem marca preferida? "
                    f"(ex: pode ser qualquer marca ou prefere uma específica?)"
                )
            elif q.preference_type == "price_max":
                known_price = q.known_info.get("price_max")
                if known_price:
                    lines.append(
                        f"Sobre **{q.product_name}**: o preço médio que vi foi R$ {known_price}. "
                        f"Qual seria o máximo aceitável?"
                    )
                else:
                    lines.append(
                        f"Sobre **{q.product_name}**: qual o preço máximo aceitável?"
                    )
            elif q.preference_type == "quality":
                lines.append(
                    f"Sobre **{q.product_name}**: prefere premium, padrão ou econômico?"
                )
            elif q.preference_type == "supplier":
                lines.append(
                    f"Sobre **{q.product_name}**: tem fornecedor preferido?"
                )

        lines.append("\n_(Pode responder ou ignorar, sem problema!)_")
        return "\n".join(lines)


# Singleton
_drip_service: Optional[PreferenceDripService] = None


def get_drip_service() -> PreferenceDripService:
    """Get the drip service singleton."""
    global _drip_service
    if _drip_service is None:
        _drip_service = PreferenceDripService()
    return _drip_service
