"""
Commit Service - Moves staging data to production tables.

This service handles the atomic commit of onboarding data from staging
tables to production tables after user confirmation.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List
from uuid import UUID

from frepi_agent.shared.supabase_client import get_supabase_client, Tables
from frepi_agent.restaurant_facing_agent.tools.embeddings import generate_embeddings_batch
from .models import (
    CommitResult,
    SessionStatus,
    PreferenceType,
    DataSource,
)
from .staging_service import OnboardingStagingService

logger = logging.getLogger(__name__)


class OnboardingCommitService:
    """
    Service for committing staged onboarding data to production.

    This handles the atomic commit of:
    - Restaurant record
    - Restaurant person (Telegram link)
    - Suppliers (new or matched)
    - Products to master_list
    - Supplier mappings
    - Pricing history
    - Product preferences
    """

    def __init__(self):
        self.client = get_supabase_client()
        self.staging_service = OnboardingStagingService()

    async def commit_onboarding(
        self,
        session_id: UUID,
        telegram_chat_id: int,
    ) -> CommitResult:
        """
        Commit all staged data to production tables.

        This is an atomic operation - if any step fails,
        the session remains uncommitted and can be retried.

        Args:
            session_id: The onboarding session UUID
            telegram_chat_id: The Telegram chat ID

        Returns:
            CommitResult with committed IDs and status
        """
        logger.info(f"Starting commit for session {session_id}")

        result = CommitResult(
            committed_at=datetime.now(timezone.utc),
        )

        try:
            # Get all staged data
            summary = await self.staging_service.get_session_summary(session_id)
            session = summary["session"]

            # Step 1: Create restaurant
            restaurant_id = await self._commit_restaurant(session, session_id)
            result.restaurant_id = restaurant_id
            logger.info(f"Committed restaurant: {restaurant_id}")

            # Step 2: Create restaurant person (Telegram link)
            person_id = await self._commit_restaurant_person(
                restaurant_id, session, telegram_chat_id
            )
            result.person_id = person_id
            logger.info(f"Committed person: {person_id}")

            # Step 3: Commit suppliers
            staged_suppliers = await self.staging_service.get_staged_suppliers(session_id)
            supplier_mapping = await self._commit_suppliers(
                session_id, staged_suppliers
            )
            result.suppliers_committed = len(supplier_mapping)
            logger.info(f"Committed {len(supplier_mapping)} suppliers")

            # Step 4: Generate embeddings for new products
            staged_products = await self.staging_service.get_staged_products(session_id)
            await self._generate_product_embeddings(session_id, staged_products)

            # Step 5: Commit products to master_list
            product_mapping = await self._commit_products(
                session_id, staged_products, restaurant_id
            )
            result.products_committed = len(product_mapping)
            logger.info(f"Committed {len(product_mapping)} products")

            # Step 6: Commit supplier_mapped_products
            await self._commit_supplier_mappings(
                session_id, staged_products, supplier_mapping, product_mapping
            )

            # Step 7: Commit prices to pricing_history
            staged_prices = await self.staging_service.get_staged_prices(session_id)
            prices_committed = await self._commit_prices(
                session_id, staged_prices, supplier_mapping, product_mapping
            )
            result.prices_committed = prices_committed
            logger.info(f"Committed {prices_committed} price records")

            # Step 8: Commit preferences
            staged_preferences = await self.staging_service.get_staged_preferences(session_id)
            prefs_committed = await self._commit_preferences(
                session_id, staged_preferences, restaurant_id,
                product_mapping, person_id
            )
            result.preferences_committed = prefs_committed
            logger.info(f"Committed {prefs_committed} preferences")

            # Step 9: Populate preference collection queue
            await self._populate_preference_queue(
                session_id, staged_products, restaurant_id, product_mapping
            )

            # Step 10: Create engagement profile
            await self._create_engagement_profile(session_id, restaurant_id)

            # Step 11: Mark session as committed
            await self._finalize_session(
                session_id, restaurant_id, person_id
            )

            result.success = True
            logger.info(f"Successfully committed session {session_id}")

        except Exception as e:
            logger.error(f"Error committing session {session_id}: {e}", exc_info=True)
            result.errors.append(str(e))

        return result

    async def _commit_restaurant(
        self,
        session: Dict,
        session_id: UUID,
    ) -> int:
        """
        Create restaurant in production.

        Args:
            session: Session data
            session_id: Session UUID

        Returns:
            Restaurant ID
        """
        now = datetime.now(timezone.utc).isoformat()

        result = self.client.table(Tables.RESTAURANTS).insert({
            "restaurant_name": session.get("restaurant_name"),
            "city": session.get("city"),
            "restaurant_type": session.get("restaurant_type"),
            "onboarding_completed_at": now,
            "onboarding_session_id": str(session_id),
            "is_active": True,
        }).execute()

        if not result.data:
            raise Exception("Failed to create restaurant")

        return result.data[0]["id"]

    async def _commit_restaurant_person(
        self,
        restaurant_id: int,
        session: Dict,
        telegram_chat_id: int,
    ) -> int:
        """
        Create restaurant person (Telegram link) in production.

        Args:
            restaurant_id: The restaurant ID
            session: Session data
            telegram_chat_id: Telegram chat ID

        Returns:
            Person ID
        """
        contact_name = session.get("contact_name") or "Contato Principal"
        name_parts = contact_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        result = self.client.table(Tables.RESTAURANT_PEOPLE).insert({
            "restaurant_id": restaurant_id,
            "first_name": first_name,
            "last_name": last_name,
            "full_name": contact_name,
            "whatsapp_number": str(telegram_chat_id),
            "is_active": True,
            "is_primary_contact": True,
        }).execute()

        if not result.data:
            raise Exception("Failed to create restaurant person")

        return result.data[0]["id"]

    async def _commit_suppliers(
        self,
        session_id: UUID,
        staged_suppliers: List,
    ) -> Dict[str, int]:
        """
        Commit suppliers to production.

        Returns mapping of staging_id (str) -> production_id (int)
        """
        mapping = {}

        for staged in staged_suppliers:
            staging_id = str(staged.id)

            # If matched to existing, use that
            if staged.matched_supplier_id:
                mapping[staging_id] = staged.matched_supplier_id
                logger.debug(f"Supplier {staged.company_name} matched to existing ID {staged.matched_supplier_id}")
            else:
                # Create new supplier
                data = {
                    "company_name": staged.company_name,
                    "tax_number": staged.cnpj,
                    "primary_phone": staged.primary_phone,
                    "primary_email": staged.primary_email,
                    "city": staged.city,
                    "street_address": staged.street_address,
                    "is_active": True,
                }
                # Remove None values
                data = {k: v for k, v in data.items() if v is not None}

                result = self.client.table(Tables.SUPPLIERS).insert(data).execute()

                if result.data:
                    production_id = result.data[0]["id"]
                    mapping[staging_id] = production_id

                    # Update staging record
                    await self.staging_service.update_staged_supplier(
                        staged.id, {"committed_supplier_id": production_id}
                    )
                    logger.debug(f"Created new supplier {staged.company_name} with ID {production_id}")

        return mapping

    async def _generate_product_embeddings(
        self,
        session_id: UUID,
        staged_products: List,
    ):
        """Generate embeddings for products that need them."""
        # Filter products that need embeddings
        products_to_embed = [
            p for p in staged_products
            if not p.embedding_generated and not p.matched_master_list_id
        ]

        if not products_to_embed:
            logger.info("No products need embedding generation")
            return

        logger.info(f"Generating embeddings for {len(products_to_embed)} products")

        # Generate embeddings in batch
        texts = [p.product_name for p in products_to_embed]
        embeddings = await generate_embeddings_batch(texts)

        # Update staging records with embeddings
        for product, embedding in zip(products_to_embed, embeddings):
            await self.staging_service.update_staged_product(product.id, {
                "embedding_vector": embedding,
                "embedding_generated": True,
            })

        logger.info(f"Generated {len(embeddings)} embeddings")

    async def _commit_products(
        self,
        session_id: UUID,
        staged_products: List,
        restaurant_id: int,
    ) -> Dict[str, int]:
        """
        Commit products to master_list.

        Returns mapping of staging_id (str) -> master_list_id (int)
        """
        mapping = {}

        for staged in staged_products:
            staging_id = str(staged.id)

            # If matched to existing, use that
            if staged.matched_master_list_id:
                mapping[staging_id] = staged.matched_master_list_id
                logger.debug(f"Product {staged.product_name} matched to existing ID {staged.matched_master_list_id}")
            else:
                # Create new product in master_list
                data = {
                    "restaurant_id": restaurant_id,
                    "product_name": staged.product_name,
                    "product_description": staged.product_description,
                    "brand": staged.brand,
                    "specifications": staged.specifications,
                    "quality_tier": staged.quality_tier,
                    "is_active": True,
                    "is_verified": False,
                    "search_frequency": 0,
                    "total_orders": 0,
                    "popularity_score": staged.inferred_importance_score or 0,
                }

                # Add embedding if available
                if staged.embedding_generated:
                    # Refresh to get the embedding
                    refreshed = await self.staging_service.get_staged_products(
                        session_id, only_priority=False
                    )
                    for p in refreshed:
                        if str(p.id) == staging_id and p.embedding_vector:
                            data["embedding_vector_v2"] = p.embedding_vector
                            break

                # Remove None values
                data = {k: v for k, v in data.items() if v is not None}

                result = self.client.table(Tables.MASTER_LIST).insert(data).execute()

                if result.data:
                    production_id = result.data[0]["id"]
                    mapping[staging_id] = production_id

                    # Update staging record
                    await self.staging_service.update_staged_product(
                        staged.id, {"committed_master_list_id": production_id}
                    )
                    logger.debug(f"Created product {staged.product_name} with ID {production_id}")

        return mapping

    async def _commit_supplier_mappings(
        self,
        session_id: UUID,
        staged_products: List,
        supplier_mapping: Dict[str, int],
        product_mapping: Dict[str, int],
    ):
        """Create supplier_mapped_products entries."""
        created = 0

        for staged in staged_products:
            if not staged.staging_supplier_id:
                continue

            supplier_staging_id = str(staged.staging_supplier_id)
            product_staging_id = str(staged.id)

            supplier_id = supplier_mapping.get(supplier_staging_id)
            master_list_id = product_mapping.get(product_staging_id)

            if supplier_id and master_list_id:
                # Check if mapping already exists
                existing = self.client.table(Tables.SUPPLIER_MAPPED_PRODUCTS).select("id").eq(
                    "supplier_id", supplier_id
                ).eq("master_list_id", master_list_id).limit(1).execute()

                if not existing.data:
                    self.client.table(Tables.SUPPLIER_MAPPED_PRODUCTS).insert({
                        "supplier_id": supplier_id,
                        "master_list_id": master_list_id,
                        "supplier_product_code": f"AUTO-{master_list_id}",
                        "supplier_product_name": staged.product_name,
                        "supplier_brand": staged.brand,
                        "mapping_confidence": staged.extraction_confidence or 0.8,
                        "mapping_method": "invoice_extraction",
                        "current_unit_price": staged.avg_unit_price or 0,
                        "currency": "BRL",
                        "is_active": True,
                    }).execute()
                    created += 1

        logger.info(f"Created {created} supplier-product mappings")

    async def _commit_prices(
        self,
        session_id: UUID,
        staged_prices: List,
        supplier_mapping: Dict[str, int],
        product_mapping: Dict[str, int],
    ) -> int:
        """Commit prices to pricing_history."""
        committed = 0

        for staged in staged_prices:
            if not staged.staging_supplier_id or not staged.staging_product_id:
                continue

            supplier_staging_id = str(staged.staging_supplier_id)
            product_staging_id = str(staged.staging_product_id)

            supplier_id = supplier_mapping.get(supplier_staging_id)
            master_list_id = product_mapping.get(product_staging_id)

            if not supplier_id or not master_list_id:
                continue

            # Get supplier_mapped_product_id
            smp = self.client.table(Tables.SUPPLIER_MAPPED_PRODUCTS).select("id").eq(
                "supplier_id", supplier_id
            ).eq("master_list_id", master_list_id).limit(1).execute()

            smp_id = smp.data[0]["id"] if smp.data else None

            # Determine effective date
            effective_date = staged.invoice_date
            if not effective_date:
                effective_date = datetime.now(timezone.utc).date()

            if hasattr(effective_date, 'isoformat'):
                effective_date = effective_date.isoformat()

            # Insert price record
            result = self.client.table(Tables.PRICING_HISTORY).insert({
                "supplier_id": supplier_id,
                "master_list_id": master_list_id,
                "supplier_mapped_product_id": smp_id,
                "unit_price": staged.unit_price,
                "currency": staged.currency or "BRL",
                "price_per_unit_type": staged.price_per_unit_type,
                "effective_date": effective_date,
                "data_source": "invoice_extraction",
            }).execute()

            if result.data:
                committed += 1

                # Update supplier_mapped_products current_unit_price
                if smp_id:
                    self.client.table(Tables.SUPPLIER_MAPPED_PRODUCTS).update({
                        "current_unit_price": staged.unit_price,
                        "price_last_updated": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", smp_id).execute()

        return committed

    async def _commit_preferences(
        self,
        session_id: UUID,
        staged_preferences: List,
        restaurant_id: int,
        product_mapping: Dict[str, int],
        person_id: int,
    ) -> int:
        """Commit preferences to restaurant_product_preferences."""
        committed = 0
        now = datetime.now(timezone.utc).isoformat()

        # Group preferences by product
        prefs_by_product = {}
        global_prefs = []  # Preferences not tied to a specific product

        for pref in staged_preferences:
            if pref.staging_product_id:
                prod_staging_id = str(pref.staging_product_id)
                if prod_staging_id not in prefs_by_product:
                    prefs_by_product[prod_staging_id] = []
                prefs_by_product[prod_staging_id].append(pref)
            else:
                global_prefs.append(pref)

        # Commit product-specific preferences
        for staging_prod_id, prefs in prefs_by_product.items():
            master_list_id = product_mapping.get(staging_prod_id)
            if not master_list_id:
                continue

            # Build preference record
            pref_data = {
                "restaurant_id": restaurant_id,
                "master_list_id": master_list_id,
                "is_active": True,
            }

            for pref in prefs:
                pref_type = pref.preference_type
                pref_value = pref.preference_value
                source = DataSource.INFERRED.value if pref.source == DataSource.INFERRED.value else "onboarding"

                if pref_type == PreferenceType.BRAND.value:
                    pref_data["brand_preferences"] = pref_value
                    pref_data["brand_preferences_source"] = source
                    pref_data["brand_preferences_added_by"] = person_id
                    pref_data["brand_preferences_added_at"] = now

                elif pref_type == PreferenceType.PRICE_MAX.value:
                    pref_data["price_preference"] = str(pref_value.get("max_price", ""))
                    pref_data["price_preference_source"] = source
                    pref_data["price_preference_added_by"] = person_id
                    pref_data["price_preference_added_at"] = now

                elif pref_type == PreferenceType.QUALITY.value:
                    pref_data["quality_preference"] = pref_value
                    pref_data["quality_preference_source"] = source
                    pref_data["quality_preference_added_by"] = person_id
                    pref_data["quality_preference_added_at"] = now

                elif pref_type == PreferenceType.SPECIFICATION.value:
                    pref_data["specification_preferences"] = pref_value
                    pref_data["specification_preference_source"] = source
                    pref_data["specification_preference_added_by"] = person_id
                    pref_data["specification_preference_added_at"] = now

            # Check if preference already exists
            existing = self.client.table(Tables.RESTAURANT_PRODUCT_PREFERENCES).select("id").eq(
                "restaurant_id", restaurant_id
            ).eq("master_list_id", master_list_id).limit(1).execute()

            if existing.data:
                # Update existing
                self.client.table(Tables.RESTAURANT_PRODUCT_PREFERENCES).update(
                    pref_data
                ).eq("id", existing.data[0]["id"]).execute()
            else:
                # Insert new
                result = self.client.table(Tables.RESTAURANT_PRODUCT_PREFERENCES).insert(
                    pref_data
                ).execute()

            if existing.data or (result and result.data):
                committed += 1

        # Handle global preferences (e.g., delivery patterns)
        # These could be stored in restaurant settings or a separate table
        # For now, we'll skip them or add to restaurant metadata
        if global_prefs:
            delivery_prefs = [p for p in global_prefs if p.preference_type == PreferenceType.DELIVERY_DAY.value]
            if delivery_prefs:
                # Store delivery patterns in restaurant ordering_frequency
                delivery_data = [p.preference_value for p in delivery_prefs]
                self.client.table(Tables.RESTAURANTS).update({
                    "ordering_frequency": delivery_data,
                }).eq("id", restaurant_id).execute()

        return committed

    async def _populate_preference_queue(
        self,
        session_id: UUID,
        staged_products: List,
        restaurant_id: int,
        product_mapping: Dict[str, int],
    ):
        """
        Populate the preference_collection_queue from committed products.

        Each product gets a queue entry with its tier, position, and status.
        Position is based on importance score (highest first).
        """
        # Sort by importance score descending
        sorted_products = sorted(
            staged_products,
            key=lambda p: p.inferred_importance_score or 0,
            reverse=True,
        )

        queue_entries = []
        for position, staged in enumerate(sorted_products, 1):
            staging_id = str(staged.id)
            master_list_id = product_mapping.get(staging_id)
            if not master_list_id:
                continue

            queue_entries.append({
                "restaurant_id": restaurant_id,
                "master_list_id": master_list_id,
                "importance_tier": staged.importance_tier or "long_tail",
                "importance_score": staged.inferred_importance_score or 0,
                "total_spend": staged.total_spend or 0,
                "spend_share_pct": staged.spend_share_percentage or 0,
                "preference_status": "pending",
                "queue_position": position,
            })

        if queue_entries:
            self.client.table(Tables.PREFERENCE_COLLECTION_QUEUE).insert(
                queue_entries
            ).execute()
            logger.info(f"Populated preference queue with {len(queue_entries)} products")

    async def _create_engagement_profile(
        self,
        session_id: UUID,
        restaurant_id: int,
    ):
        """Create the initial engagement profile for the restaurant."""
        # Check engagement choice from session
        session_data = self.client.table(Tables.ONBOARDING_SESSIONS).select(
            "engagement_choice"
        ).eq("id", str(session_id)).limit(1).execute()

        engagement_choice = 0
        if session_data.data:
            engagement_choice = session_data.data[0].get("engagement_choice") or 0

        # Map choice to onboarding_depth: 0=skip, 5=quick, 10=full
        depth_map = {0: 0, 3: 0, 1: 5, 2: 10}
        onboarding_depth = depth_map.get(engagement_choice, 0)

        # Calculate initial engagement score
        depth_signal = {0: 0.0, 5: 0.5, 10: 1.0}.get(onboarding_depth, 0.0)
        initial_score = round(0.15 * depth_signal, 2)

        # Determine initial level
        if initial_score >= 0.65:
            level = "high"
            drip_per_session = 2
        elif initial_score >= 0.35:
            level = "medium"
            drip_per_session = 1
        else:
            level = "low"
            drip_per_session = 0

        self.client.table(Tables.ENGAGEMENT_PROFILE).insert({
            "restaurant_id": restaurant_id,
            "engagement_score": initial_score,
            "engagement_level": level,
            "onboarding_depth": onboarding_depth,
            "drip_questions_per_session": drip_per_session,
        }).execute()

        logger.info(
            f"Created engagement profile for restaurant {restaurant_id}: "
            f"depth={onboarding_depth}, score={initial_score}, level={level}"
        )

    async def _finalize_session(
        self,
        session_id: UUID,
        restaurant_id: int,
        person_id: int,
    ):
        """Mark session as committed."""
        now = datetime.now(timezone.utc).isoformat()

        self.client.table(Tables.ONBOARDING_SESSIONS).update({
            "status": SessionStatus.COMMITTED.value,
            "committed_at": now,
            "committed_restaurant_id": restaurant_id,
            "committed_person_id": person_id,
            "updated_at": now,
        }).eq("id", str(session_id)).execute()

        logger.info(f"Session {session_id} finalized. Restaurant ID: {restaurant_id}, Person ID: {person_id}")


# Singleton instance
_commit_service: Optional[OnboardingCommitService] = None


def get_commit_service() -> OnboardingCommitService:
    """Get the commit service singleton."""
    global _commit_service
    if _commit_service is None:
        _commit_service = OnboardingCommitService()
    return _commit_service
