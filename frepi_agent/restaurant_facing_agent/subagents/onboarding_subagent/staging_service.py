"""
Onboarding Staging Service - Manages staging data during onboarding.

This service handles all CRUD operations for the staging tables, allowing
data to be collected incrementally during onboarding before being committed
to production tables.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID, uuid4

from frepi_agent.shared.supabase_client import get_supabase_client, Tables
from .models import (
    OnboardingSession,
    StagedSupplier,
    StagedProduct,
    StagedPrice,
    StagedPreference,
    InvoicePhoto,
    SessionStatus,
    SessionPhase,
    DataSource,
)

logger = logging.getLogger(__name__)


class OnboardingStagingService:
    """Service for managing onboarding staging data."""

    def __init__(self):
        self.client = get_supabase_client()

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    async def create_session(self, telegram_chat_id: int) -> UUID:
        """
        Create a new onboarding session.

        Args:
            telegram_chat_id: The Telegram chat ID for the user

        Returns:
            UUID of the created session
        """
        session_id = uuid4()

        self.client.table(Tables.ONBOARDING_SESSIONS).insert({
            "id": str(session_id),
            "telegram_chat_id": telegram_chat_id,
            "status": SessionStatus.IN_PROGRESS.value,
            "current_phase": SessionPhase.BASIC_INFO.value,
        }).execute()

        logger.info(f"Created onboarding session {session_id} for chat {telegram_chat_id}")
        return session_id

    async def get_session(self, session_id: UUID) -> Optional[OnboardingSession]:
        """Get a session by ID."""
        result = self.client.table(Tables.ONBOARDING_SESSIONS).select("*").eq(
            "id", str(session_id)
        ).limit(1).execute()

        if result.data:
            return self._row_to_session(result.data[0])
        return None

    async def get_active_session(self, telegram_chat_id: int) -> Optional[UUID]:
        """
        Get active (in_progress) session for a telegram chat.

        Args:
            telegram_chat_id: The Telegram chat ID

        Returns:
            UUID of active session or None if not found
        """
        result = self.client.table(Tables.ONBOARDING_SESSIONS).select("id").eq(
            "telegram_chat_id", telegram_chat_id
        ).eq("status", SessionStatus.IN_PROGRESS.value).limit(1).execute()

        if result.data:
            return UUID(result.data[0]["id"])
        return None

    async def get_or_create_session(self, telegram_chat_id: int) -> UUID:
        """
        Get existing active session or create new one.

        Args:
            telegram_chat_id: The Telegram chat ID

        Returns:
            UUID of the session (existing or new)
        """
        session_id = await self.get_active_session(telegram_chat_id)
        if session_id:
            await self.update_session_activity(session_id)
            return session_id
        return await self.create_session(telegram_chat_id)

    async def update_session_activity(self, session_id: UUID):
        """Update last activity timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        self.client.table(Tables.ONBOARDING_SESSIONS).update({
            "last_activity_at": now,
            "updated_at": now,
        }).eq("id", str(session_id)).execute()

    async def update_session_phase(self, session_id: UUID, phase: SessionPhase):
        """
        Update the current phase of onboarding.

        Args:
            session_id: The session UUID
            phase: The new phase
        """
        now = datetime.now(timezone.utc).isoformat()
        self.client.table(Tables.ONBOARDING_SESSIONS).update({
            "current_phase": phase.value,
            "last_activity_at": now,
            "updated_at": now,
        }).eq("id", str(session_id)).execute()
        logger.info(f"Session {session_id} phase updated to {phase.value}")

    async def update_session_status(self, session_id: UUID, status: SessionStatus):
        """Update session status."""
        now = datetime.now(timezone.utc).isoformat()
        self.client.table(Tables.ONBOARDING_SESSIONS).update({
            "status": status.value,
            "updated_at": now,
        }).eq("id", str(session_id)).execute()
        logger.info(f"Session {session_id} status updated to {status.value}")

    async def save_restaurant_basic_info(
        self,
        session_id: UUID,
        restaurant_name: str,
        city: str,
        contact_name: Optional[str] = None,
        restaurant_type: Optional[str] = None,
    ):
        """
        Save restaurant basic info to staging.

        Args:
            session_id: The session UUID
            restaurant_name: Name of the restaurant
            city: City location
            contact_name: Optional contact person name
            restaurant_type: Optional type of restaurant
        """
        now = datetime.now(timezone.utc).isoformat()
        self.client.table(Tables.ONBOARDING_SESSIONS).update({
            "restaurant_name": restaurant_name,
            "city": city,
            "contact_name": contact_name,
            "restaurant_type": restaurant_type,
            "current_phase": SessionPhase.INVOICES_UPLOAD.value,
            "updated_at": now,
        }).eq("id", str(session_id)).execute()
        logger.info(f"Saved basic info for session {session_id}: {restaurant_name}, {city}")

    # =========================================================================
    # SUPPLIER STAGING
    # =========================================================================

    async def stage_supplier(
        self,
        session_id: UUID,
        supplier: StagedSupplier,
    ) -> UUID:
        """
        Stage a supplier from invoice extraction.

        Args:
            session_id: The session UUID
            supplier: The supplier data to stage

        Returns:
            UUID of the staged supplier
        """
        supplier_id = uuid4()

        # Check for existing supplier match by CNPJ or name
        matched_id, match_confidence = await self._find_existing_supplier(
            supplier.company_name, supplier.cnpj
        )

        data = supplier.to_dict()
        data["id"] = str(supplier_id)
        data["session_id"] = str(session_id)
        data["matched_supplier_id"] = matched_id
        data["match_confidence"] = match_confidence

        self.client.table(Tables.ONBOARDING_STAGING_SUPPLIERS).insert(data).execute()

        # Update session counter
        await self._increment_counter(session_id, "suppliers_extracted")

        logger.info(f"Staged supplier {supplier.company_name} with ID {supplier_id}")
        return supplier_id

    async def get_staged_suppliers(self, session_id: UUID) -> List[StagedSupplier]:
        """Get all staged suppliers for a session."""
        result = self.client.table(Tables.ONBOARDING_STAGING_SUPPLIERS).select("*").eq(
            "session_id", str(session_id)
        ).order("created_at").execute()

        return [self._row_to_staged_supplier(row) for row in (result.data or [])]

    async def update_staged_supplier(
        self,
        supplier_id: UUID,
        updates: Dict[str, Any],
    ):
        """Update a staged supplier."""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.client.table(Tables.ONBOARDING_STAGING_SUPPLIERS).update(updates).eq(
            "id", str(supplier_id)
        ).execute()

    async def _find_existing_supplier(
        self,
        company_name: str,
        cnpj: Optional[str],
    ) -> Tuple[Optional[int], Optional[float]]:
        """
        Find matching existing supplier in production.

        Args:
            company_name: Supplier name
            cnpj: Optional CNPJ

        Returns:
            Tuple of (supplier_id, confidence) or (None, None)
        """
        # Try CNPJ first (exact match)
        if cnpj:
            result = self.client.table(Tables.SUPPLIERS).select("id").eq(
                "tax_number", cnpj
            ).limit(1).execute()
            if result.data:
                return result.data[0]["id"], 1.0

        # Try name similarity (case-insensitive)
        result = self.client.table(Tables.SUPPLIERS).select("id, company_name").ilike(
            "company_name", f"%{company_name}%"
        ).limit(1).execute()
        if result.data:
            return result.data[0]["id"], 0.85

        return None, None

    # =========================================================================
    # PRODUCT STAGING
    # =========================================================================

    async def stage_product(
        self,
        session_id: UUID,
        product: StagedProduct,
    ) -> UUID:
        """
        Stage a product from invoice extraction.

        Args:
            session_id: The session UUID
            product: The product data to stage

        Returns:
            UUID of the staged product
        """
        product_id = uuid4()

        data = product.to_dict()
        data["id"] = str(product_id)
        data["session_id"] = str(session_id)

        self.client.table(Tables.ONBOARDING_STAGING_PRODUCTS).insert(data).execute()

        # Update session counter
        await self._increment_counter(session_id, "products_extracted")

        logger.info(f"Staged product {product.product_name} with ID {product_id}")
        return product_id

    async def get_staged_products(
        self,
        session_id: UUID,
        only_priority: bool = False,
    ) -> List[StagedProduct]:
        """
        Get staged products for a session.

        Args:
            session_id: The session UUID
            only_priority: If True, only return priority products

        Returns:
            List of staged products
        """
        query = self.client.table(Tables.ONBOARDING_STAGING_PRODUCTS).select("*").eq(
            "session_id", str(session_id)
        )

        if only_priority:
            query = query.eq("is_priority", True).order("priority_rank")
        else:
            query = query.order("inferred_importance_score", desc=True)

        result = query.execute()
        return [self._row_to_staged_product(row) for row in (result.data or [])]

    async def update_staged_product(
        self,
        product_id: UUID,
        updates: Dict[str, Any],
    ):
        """Update a staged product."""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.client.table(Tables.ONBOARDING_STAGING_PRODUCTS).update(updates).eq(
            "id", str(product_id)
        ).execute()

    async def set_priority_products(
        self,
        session_id: UUID,
        product_ids: List[UUID],
    ):
        """
        Mark products as priority (top 10).

        Args:
            session_id: The session UUID
            product_ids: List of product UUIDs in priority order
        """
        # First, clear existing priority flags for this session
        self.client.table(Tables.ONBOARDING_STAGING_PRODUCTS).update({
            "is_priority": False,
            "priority_rank": None,
        }).eq("session_id", str(session_id)).execute()

        # Set new priority products
        for rank, product_id in enumerate(product_ids[:10], 1):
            self.client.table(Tables.ONBOARDING_STAGING_PRODUCTS).update({
                "is_priority": True,
                "priority_rank": rank,
            }).eq("id", str(product_id)).execute()

        logger.info(f"Set {len(product_ids[:10])} priority products for session {session_id}")

    async def find_or_create_staged_product(
        self,
        session_id: UUID,
        product_name: str,
        staging_supplier_id: Optional[UUID] = None,
        source: str = DataSource.INVOICE_EXTRACTION.value,
        source_invoice_index: Optional[int] = None,
    ) -> UUID:
        """
        Find existing staged product by name or create new one.

        This helps consolidate products from multiple invoices.

        Args:
            session_id: The session UUID
            product_name: Product name to search for
            staging_supplier_id: Optional supplier ID
            source: Data source
            source_invoice_index: Invoice index

        Returns:
            UUID of existing or new product
        """
        # Search for existing product with similar name
        result = self.client.table(Tables.ONBOARDING_STAGING_PRODUCTS).select("id").eq(
            "session_id", str(session_id)
        ).ilike("product_name", product_name).limit(1).execute()

        if result.data:
            return UUID(result.data[0]["id"])

        # Create new product
        product = StagedProduct(
            product_name=product_name,
            staging_supplier_id=staging_supplier_id,
            source=source,
            source_invoice_index=source_invoice_index,
        )
        return await self.stage_product(session_id, product)

    # =========================================================================
    # PRICE STAGING
    # =========================================================================

    async def stage_price(
        self,
        session_id: UUID,
        price: StagedPrice,
    ) -> UUID:
        """
        Stage a price record from invoice extraction.

        Args:
            session_id: The session UUID
            price: The price data to stage

        Returns:
            UUID of the staged price
        """
        price_id = uuid4()

        data = price.to_dict()
        data["id"] = str(price_id)
        data["session_id"] = str(session_id)

        self.client.table(Tables.ONBOARDING_STAGING_PRICES).insert(data).execute()

        logger.debug(f"Staged price {price.unit_price} for product {price.staging_product_id}")
        return price_id

    async def get_staged_prices(
        self,
        session_id: UUID,
        product_id: Optional[UUID] = None,
    ) -> List[StagedPrice]:
        """
        Get staged prices for a session.

        Args:
            session_id: The session UUID
            product_id: Optional filter by product

        Returns:
            List of staged prices
        """
        query = self.client.table(Tables.ONBOARDING_STAGING_PRICES).select("*").eq(
            "session_id", str(session_id)
        )

        if product_id:
            query = query.eq("staging_product_id", str(product_id))

        result = query.order("invoice_date", desc=True).execute()
        return [self._row_to_staged_price(row) for row in (result.data or [])]

    # =========================================================================
    # PREFERENCE STAGING
    # =========================================================================

    async def stage_preference(
        self,
        session_id: UUID,
        preference: StagedPreference,
    ) -> UUID:
        """
        Stage a product preference.

        Args:
            session_id: The session UUID
            preference: The preference data to stage

        Returns:
            UUID of the staged preference
        """
        pref_id = uuid4()

        data = preference.to_dict()
        data["id"] = str(pref_id)
        data["session_id"] = str(session_id)

        self.client.table(Tables.ONBOARDING_STAGING_PREFERENCES).insert(data).execute()

        # Update session counter
        await self._increment_counter(session_id, "preferences_configured")

        logger.info(f"Staged {preference.preference_type} preference with ID {pref_id}")
        return pref_id

    async def get_staged_preferences(
        self,
        session_id: UUID,
        preference_type: Optional[str] = None,
    ) -> List[StagedPreference]:
        """
        Get staged preferences for a session.

        Args:
            session_id: The session UUID
            preference_type: Optional filter by type

        Returns:
            List of staged preferences
        """
        query = self.client.table(Tables.ONBOARDING_STAGING_PREFERENCES).select("*").eq(
            "session_id", str(session_id)
        )

        if preference_type:
            query = query.eq("preference_type", preference_type)

        result = query.execute()
        return [self._row_to_staged_preference(row) for row in (result.data or [])]

    async def update_preference_feedback(
        self,
        preference_id: UUID,
        feedback: str,
    ):
        """
        Update user feedback on a preference.

        Args:
            preference_id: The preference UUID
            feedback: 'confirmed', 'rejected', or 'modified'
        """
        self.client.table(Tables.ONBOARDING_STAGING_PREFERENCES).update({
            "user_feedback": feedback,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", str(preference_id)).execute()

    # =========================================================================
    # PHOTO TRACKING
    # =========================================================================

    async def save_photo_metadata(
        self,
        session_id: UUID,
        telegram_file_id: str,
        telegram_file_url: str,
        photo_index: int,
    ) -> UUID:
        """
        Save metadata for an uploaded invoice photo.

        Args:
            session_id: The session UUID
            telegram_file_id: Telegram's file ID
            telegram_file_url: URL to download the file
            photo_index: Index/order of the photo

        Returns:
            UUID of the photo record
        """
        photo_id = uuid4()

        self.client.table(Tables.ONBOARDING_INVOICE_PHOTOS).insert({
            "id": str(photo_id),
            "session_id": str(session_id),
            "telegram_file_id": telegram_file_id,
            "telegram_file_url": telegram_file_url,
            "photo_index": photo_index,
        }).execute()

        # Update session photo count
        self.client.table(Tables.ONBOARDING_SESSIONS).update({
            "photos_uploaded": photo_index + 1,
        }).eq("id", str(session_id)).execute()

        logger.info(f"Saved photo {photo_index + 1} metadata for session {session_id}")
        return photo_id

    async def update_photo_parsing_result(
        self,
        photo_id: UUID,
        success: bool,
        raw_result: Dict,
        supplier_name: Optional[str] = None,
        supplier_cnpj: Optional[str] = None,
        invoice_date: Optional[str] = None,
        invoice_number: Optional[str] = None,
        products_count: int = 0,
        total_amount: Optional[float] = None,
        error: Optional[str] = None,
    ):
        """
        Update photo with parsing results.

        Args:
            photo_id: The photo UUID
            success: Whether parsing succeeded
            raw_result: Raw extraction result from GPT-4 Vision
            supplier_name: Extracted supplier name
            supplier_cnpj: Extracted CNPJ
            invoice_date: Extracted date
            invoice_number: Extracted invoice number
            products_count: Number of products extracted
            total_amount: Total invoice amount
            error: Error message if parsing failed
        """
        self.client.table(Tables.ONBOARDING_INVOICE_PHOTOS).update({
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "parsing_success": success,
            "parsing_error": error,
            "raw_extraction_result": raw_result,
            "supplier_name_extracted": supplier_name,
            "supplier_cnpj_extracted": supplier_cnpj,
            "invoice_date_extracted": invoice_date,
            "invoice_number_extracted": invoice_number,
            "products_count": products_count,
            "total_amount_extracted": total_amount,
        }).eq("id", str(photo_id)).execute()

    async def get_invoice_photos(self, session_id: UUID) -> List[InvoicePhoto]:
        """Get all invoice photos for a session."""
        result = self.client.table(Tables.ONBOARDING_INVOICE_PHOTOS).select("*").eq(
            "session_id", str(session_id)
        ).order("photo_index").execute()

        return [self._row_to_invoice_photo(row) for row in (result.data or [])]

    # =========================================================================
    # SUMMARY & RETRIEVAL
    # =========================================================================

    async def get_session_summary(self, session_id: UUID) -> Dict[str, Any]:
        """
        Get complete summary of staged data for confirmation.

        Args:
            session_id: The session UUID

        Returns:
            Dictionary with all staged data and summary statistics
        """
        # Get session info
        session_result = self.client.table(Tables.ONBOARDING_SESSIONS).select("*").eq(
            "id", str(session_id)
        ).single().execute()

        # Get staged data
        suppliers = await self.get_staged_suppliers(session_id)
        products = await self.get_staged_products(session_id)
        prices = await self.get_staged_prices(session_id)
        preferences = await self.get_staged_preferences(session_id)
        photos = await self.get_invoice_photos(session_id)

        # Calculate statistics
        total_spend = sum(p.total_spend for p in products)
        priority_products = [p for p in products if p.is_priority]
        new_suppliers = [s for s in suppliers if not s.matched_supplier_id]
        existing_suppliers = [s for s in suppliers if s.matched_supplier_id]

        return {
            "session": session_result.data,
            "suppliers": [s.__dict__ for s in suppliers],
            "products": [p.__dict__ for p in products],
            "prices": [pr.__dict__ for pr in prices],
            "preferences": [pref.__dict__ for pref in preferences],
            "photos": [ph.__dict__ for ph in photos],
            "summary": {
                "restaurant_name": session_result.data.get("restaurant_name"),
                "city": session_result.data.get("city"),
                "invoice_count": len(photos),
                "supplier_count": len(suppliers),
                "new_supplier_count": len(new_suppliers),
                "existing_supplier_count": len(existing_suppliers),
                "product_count": len(products),
                "priority_product_count": len(priority_products),
                "price_record_count": len(prices),
                "preference_count": len(preferences),
                "total_spend": total_spend,
            }
        }

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    async def _increment_counter(self, session_id: UUID, field: str):
        """Increment a counter field in the session."""
        try:
            self.client.rpc("increment_staging_count", {
                "p_session_id": str(session_id),
                "p_field": field,
            }).execute()
        except Exception as e:
            # Fallback if RPC doesn't exist
            logger.warning(f"RPC increment failed, using fallback: {e}")
            session = await self.get_session(session_id)
            if session:
                current = getattr(session, field, 0) or 0
                self.client.table(Tables.ONBOARDING_SESSIONS).update({
                    field: current + 1,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", str(session_id)).execute()

    def _row_to_session(self, row: Dict) -> OnboardingSession:
        """Convert database row to OnboardingSession."""
        return OnboardingSession(
            id=UUID(row["id"]) if row.get("id") else None,
            telegram_chat_id=row.get("telegram_chat_id", 0),
            status=row.get("status", SessionStatus.IN_PROGRESS.value),
            current_phase=row.get("current_phase", SessionPhase.BASIC_INFO.value),
            restaurant_name=row.get("restaurant_name"),
            city=row.get("city"),
            restaurant_type=row.get("restaurant_type"),
            contact_name=row.get("contact_name"),
            photos_uploaded=row.get("photos_uploaded", 0),
            products_extracted=row.get("products_extracted", 0),
            suppliers_extracted=row.get("suppliers_extracted", 0),
            preferences_configured=row.get("preferences_configured", 0),
            committed_restaurant_id=row.get("committed_restaurant_id"),
            committed_person_id=row.get("committed_person_id"),
        )

    def _row_to_staged_supplier(self, row: Dict) -> StagedSupplier:
        """Convert database row to StagedSupplier."""
        return StagedSupplier(
            id=UUID(row["id"]) if row.get("id") else None,
            session_id=UUID(row["session_id"]) if row.get("session_id") else None,
            company_name=row.get("company_name", ""),
            cnpj=row.get("cnpj"),
            primary_phone=row.get("primary_phone"),
            primary_email=row.get("primary_email"),
            street_address=row.get("street_address"),
            city=row.get("city"),
            source=row.get("source", DataSource.INVOICE_EXTRACTION.value),
            source_invoice_index=row.get("source_invoice_index"),
            extraction_confidence=row.get("extraction_confidence", 0.8),
            user_confirmed=row.get("user_confirmed", False),
            user_modified=row.get("user_modified", False),
            matched_supplier_id=row.get("matched_supplier_id"),
            match_confidence=row.get("match_confidence"),
            invoice_count=row.get("invoice_count", 0),
            total_spend=row.get("total_spend", 0.0),
            product_categories=row.get("product_categories"),
            avg_delivery_days=row.get("avg_delivery_days"),
            price_competitiveness_score=row.get("price_competitiveness_score"),
            committed_supplier_id=row.get("committed_supplier_id"),
        )

    def _row_to_staged_product(self, row: Dict) -> StagedProduct:
        """Convert database row to StagedProduct."""
        return StagedProduct(
            id=UUID(row["id"]) if row.get("id") else None,
            session_id=UUID(row["session_id"]) if row.get("session_id") else None,
            staging_supplier_id=UUID(row["staging_supplier_id"]) if row.get("staging_supplier_id") else None,
            product_name=row.get("product_name", ""),
            product_description=row.get("product_description"),
            brand=row.get("brand"),
            specifications=row.get("specifications"),
            quality_tier=row.get("quality_tier"),
            embedding_generated=row.get("embedding_generated", False),
            source=row.get("source", DataSource.INVOICE_EXTRACTION.value),
            source_invoice_index=row.get("source_invoice_index"),
            extraction_confidence=row.get("extraction_confidence", 0.8),
            user_confirmed=row.get("user_confirmed", False),
            user_modified=row.get("user_modified", False),
            matched_master_list_id=row.get("matched_master_list_id"),
            match_confidence=row.get("match_confidence"),
            is_new_product=row.get("is_new_product", True),
            is_priority=row.get("is_priority", False),
            priority_rank=row.get("priority_rank"),
            purchase_frequency=row.get("purchase_frequency", 0),
            total_quantity_purchased=row.get("total_quantity_purchased"),
            total_spend=row.get("total_spend", 0.0),
            avg_unit_price=row.get("avg_unit_price"),
            price_range_min=row.get("price_range_min"),
            price_range_max=row.get("price_range_max"),
            spend_share_percentage=row.get("spend_share_percentage"),
            inferred_importance_score=row.get("inferred_importance_score"),
            inferred_category=row.get("inferred_category"),
            committed_master_list_id=row.get("committed_master_list_id"),
        )

    def _row_to_staged_price(self, row: Dict) -> StagedPrice:
        """Convert database row to StagedPrice."""
        return StagedPrice(
            id=UUID(row["id"]) if row.get("id") else None,
            session_id=UUID(row["session_id"]) if row.get("session_id") else None,
            staging_product_id=UUID(row["staging_product_id"]) if row.get("staging_product_id") else None,
            staging_supplier_id=UUID(row["staging_supplier_id"]) if row.get("staging_supplier_id") else None,
            unit_price=row.get("unit_price", 0.0),
            currency=row.get("currency", "BRL"),
            price_per_unit_type=row.get("price_per_unit_type"),
            invoice_number=row.get("invoice_number"),
            quantity_purchased=row.get("quantity_purchased"),
            total_line_amount=row.get("total_line_amount"),
            source=row.get("source", DataSource.INVOICE_EXTRACTION.value),
            source_invoice_index=row.get("source_invoice_index"),
            extraction_confidence=row.get("extraction_confidence", 0.8),
            committed_pricing_id=row.get("committed_pricing_id"),
        )

    def _row_to_staged_preference(self, row: Dict) -> StagedPreference:
        """Convert database row to StagedPreference."""
        return StagedPreference(
            id=UUID(row["id"]) if row.get("id") else None,
            session_id=UUID(row["session_id"]) if row.get("session_id") else None,
            staging_product_id=UUID(row["staging_product_id"]) if row.get("staging_product_id") else None,
            preference_type=row.get("preference_type", ""),
            preference_value=row.get("preference_value", {}),
            confidence_score=row.get("confidence_score"),
            source=row.get("source", DataSource.INFERRED.value),
            inference_reasoning=row.get("inference_reasoning"),
            user_feedback=row.get("user_feedback"),
            committed_preference_id=row.get("committed_preference_id"),
        )

    def _row_to_invoice_photo(self, row: Dict) -> InvoicePhoto:
        """Convert database row to InvoicePhoto."""
        return InvoicePhoto(
            id=UUID(row["id"]) if row.get("id") else None,
            session_id=UUID(row["session_id"]) if row.get("session_id") else None,
            telegram_file_id=row.get("telegram_file_id", ""),
            telegram_file_url=row.get("telegram_file_url", ""),
            storage_path=row.get("storage_path"),
            parsing_success=row.get("parsing_success"),
            parsing_error=row.get("parsing_error"),
            raw_extraction_result=row.get("raw_extraction_result"),
            supplier_name_extracted=row.get("supplier_name_extracted"),
            supplier_cnpj_extracted=row.get("supplier_cnpj_extracted"),
            products_count=row.get("products_count", 0),
            total_amount_extracted=row.get("total_amount_extracted"),
            photo_index=row.get("photo_index", 0),
        )
