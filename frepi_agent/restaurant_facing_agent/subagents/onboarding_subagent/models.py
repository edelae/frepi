"""Data models for onboarding staging and analysis."""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from uuid import UUID
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class SessionStatus(str, Enum):
    """Onboarding session status."""
    IN_PROGRESS = "in_progress"
    PENDING_CONFIRMATION = "pending_confirmation"
    COMMITTED = "committed"
    ABANDONED = "abandoned"
    EXPIRED = "expired"


class SessionPhase(str, Enum):
    """Current phase of onboarding."""
    BASIC_INFO = "basic_info"
    INVOICES_UPLOAD = "invoices_upload"
    INVOICES_PROCESSING = "invoices_processing"
    PRODUCTS_COLLECTED = "products_collected"
    CONFIRM_PRODUCTS = "confirm_products"
    PREFERENCES = "preferences"
    ANALYSIS = "analysis"
    ANALYSIS_COMPLETE = "analysis_complete"
    ENGAGEMENT_GAUGE = "engagement_gauge"
    TARGETED_PREFERENCES = "targeted_preferences"
    SUMMARY = "summary"
    COMPLETED = "completed"


class DataSource(str, Enum):
    """Source of extracted/staged data."""
    INVOICE_EXTRACTION = "invoice_extraction"
    MANUAL_ENTRY = "manual_entry"
    INFERRED = "inferred"
    USER_STATED = "user_stated"
    USER_CONFIRMED = "user_confirmed"
    USER_REJECTED = "user_rejected"


class PreferenceType(str, Enum):
    """Types of product preferences."""
    BRAND = "brand"
    PRICE_MAX = "price_max"
    PRICE_TYPICAL = "price_typical"
    QUALITY = "quality"
    SUPPLIER = "supplier"
    DELIVERY_DAY = "delivery_day"
    PURCHASE_FREQUENCY = "purchase_frequency"
    SPECIFICATION = "specification"


class InsightType(str, Enum):
    """Types of analysis insights."""
    BRAND_PREFERENCE = "brand_preference"
    PRICE_THRESHOLD = "price_threshold"
    DELIVERY_PATTERN = "delivery_pattern"
    SUPPLIER_RANKING = "supplier_ranking"
    PRODUCT_IMPORTANCE = "product_importance"
    SPEND_DISTRIBUTION = "spend_distribution"
    CATEGORY_BREAKDOWN = "category_breakdown"
    PURCHASING_FREQUENCY = "purchasing_frequency"
    PARETO_ANALYSIS = "pareto_analysis"
    DIVERSIFICATION_SUGGESTION = "diversification_suggestion"
    PRICE_OPPORTUNITY = "price_opportunity"


class ProductCategory(str, Enum):
    """Product categories for analysis."""
    PROTEINAS = "proteinas"
    HORTIFRUTI = "hortifruti"
    MERCEARIA = "mercearia"
    LATICINIOS = "laticinios"
    BEBIDAS = "bebidas"
    PADARIA = "padaria"
    CONGELADOS = "congelados"
    LIMPEZA = "limpeza"
    DESCARTAVEIS = "descartaveis"
    OUTROS = "outros"


# ============================================================================
# STAGED DATA MODELS
# ============================================================================

@dataclass
class StagedSupplier:
    """A supplier staged during onboarding."""
    id: Optional[UUID] = None
    session_id: Optional[UUID] = None

    # Supplier data
    company_name: str = ""
    cnpj: Optional[str] = None
    primary_phone: Optional[str] = None
    primary_email: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None

    # Extraction metadata
    source: str = DataSource.INVOICE_EXTRACTION.value
    source_invoice_index: Optional[int] = None
    extraction_confidence: float = 0.8

    # User confirmation
    user_confirmed: bool = False
    user_modified: bool = False
    original_data: Optional[Dict] = None

    # Match to existing
    matched_supplier_id: Optional[int] = None
    match_confidence: Optional[float] = None

    # Analysis fields
    invoice_count: int = 0
    total_spend: float = 0.0
    product_categories: Optional[List[str]] = None
    avg_delivery_days: Optional[List[str]] = None
    price_competitiveness_score: Optional[float] = None

    # Commit result
    committed_supplier_id: Optional[int] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        data = {
            "company_name": self.company_name,
            "cnpj": self.cnpj,
            "primary_phone": self.primary_phone,
            "primary_email": self.primary_email,
            "street_address": self.street_address,
            "city": self.city,
            "source": self.source,
            "source_invoice_index": self.source_invoice_index,
            "extraction_confidence": self.extraction_confidence,
            "user_confirmed": self.user_confirmed,
            "user_modified": self.user_modified,
            "original_data": self.original_data,
            "matched_supplier_id": self.matched_supplier_id,
            "match_confidence": self.match_confidence,
            "invoice_count": self.invoice_count,
            "total_spend": self.total_spend,
            "product_categories": self.product_categories,
            "avg_delivery_days": self.avg_delivery_days,
            "price_competitiveness_score": self.price_competitiveness_score,
        }
        if self.id:
            data["id"] = str(self.id)
        if self.session_id:
            data["session_id"] = str(self.session_id)
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class StagedProduct:
    """A product staged during onboarding."""
    id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    staging_supplier_id: Optional[UUID] = None

    # Product data
    product_name: str = ""
    product_description: Optional[str] = None
    brand: Optional[str] = None
    specifications: Optional[Dict] = None
    quality_tier: Optional[str] = None

    # Embedding
    embedding_vector: Optional[List[float]] = None
    embedding_generated: bool = False

    # Extraction metadata
    source: str = DataSource.INVOICE_EXTRACTION.value
    source_invoice_index: Optional[int] = None
    extraction_confidence: float = 0.8

    # User confirmation
    user_confirmed: bool = False
    user_modified: bool = False
    original_data: Optional[Dict] = None

    # Match to existing
    matched_master_list_id: Optional[int] = None
    match_confidence: Optional[float] = None
    is_new_product: bool = True

    # Priority
    is_priority: bool = False
    priority_rank: Optional[int] = None

    # Analysis fields
    purchase_frequency: int = 0
    total_quantity_purchased: Optional[float] = None
    total_spend: float = 0.0
    avg_unit_price: Optional[float] = None
    price_range_min: Optional[float] = None
    price_range_max: Optional[float] = None
    spend_share_percentage: Optional[float] = None
    inferred_importance_score: Optional[float] = None
    inferred_category: Optional[str] = None
    importance_tier: Optional[str] = None  # 'head', 'mid_tail', 'long_tail'

    # Commit result
    committed_master_list_id: Optional[int] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        data = {
            "product_name": self.product_name,
            "product_description": self.product_description,
            "brand": self.brand,
            "specifications": self.specifications,
            "quality_tier": self.quality_tier,
            "embedding_generated": self.embedding_generated,
            "source": self.source,
            "source_invoice_index": self.source_invoice_index,
            "extraction_confidence": self.extraction_confidence,
            "user_confirmed": self.user_confirmed,
            "user_modified": self.user_modified,
            "original_data": self.original_data,
            "matched_master_list_id": self.matched_master_list_id,
            "match_confidence": self.match_confidence,
            "is_new_product": self.is_new_product,
            "is_priority": self.is_priority,
            "priority_rank": self.priority_rank,
            "purchase_frequency": self.purchase_frequency,
            "total_quantity_purchased": self.total_quantity_purchased,
            "total_spend": self.total_spend,
            "avg_unit_price": self.avg_unit_price,
            "price_range_min": self.price_range_min,
            "price_range_max": self.price_range_max,
            "spend_share_percentage": self.spend_share_percentage,
            "inferred_importance_score": self.inferred_importance_score,
            "inferred_category": self.inferred_category,
            "importance_tier": self.importance_tier,
        }
        if self.id:
            data["id"] = str(self.id)
        if self.session_id:
            data["session_id"] = str(self.session_id)
        if self.staging_supplier_id:
            data["staging_supplier_id"] = str(self.staging_supplier_id)
        if self.embedding_vector:
            data["embedding_vector"] = self.embedding_vector
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class StagedPrice:
    """A price record staged during onboarding."""
    id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    staging_product_id: Optional[UUID] = None
    staging_supplier_id: Optional[UUID] = None

    # Price data
    unit_price: float = 0.0
    currency: str = "BRL"
    price_per_unit_type: Optional[str] = None  # 'kg', 'un', 'cx', etc.

    # Invoice data
    invoice_date: Optional[date] = None
    invoice_number: Optional[str] = None
    quantity_purchased: Optional[float] = None
    total_line_amount: Optional[float] = None

    # Extraction metadata
    source: str = DataSource.INVOICE_EXTRACTION.value
    source_invoice_index: Optional[int] = None
    extraction_confidence: float = 0.8

    # Commit result
    committed_pricing_id: Optional[int] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        data = {
            "unit_price": self.unit_price,
            "currency": self.currency,
            "price_per_unit_type": self.price_per_unit_type,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "invoice_number": self.invoice_number,
            "quantity_purchased": self.quantity_purchased,
            "total_line_amount": self.total_line_amount,
            "source": self.source,
            "source_invoice_index": self.source_invoice_index,
            "extraction_confidence": self.extraction_confidence,
        }
        if self.id:
            data["id"] = str(self.id)
        if self.session_id:
            data["session_id"] = str(self.session_id)
        if self.staging_product_id:
            data["staging_product_id"] = str(self.staging_product_id)
        if self.staging_supplier_id:
            data["staging_supplier_id"] = str(self.staging_supplier_id)
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class StagedPreference:
    """A product preference staged during onboarding."""
    id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    staging_product_id: Optional[UUID] = None

    # Preference data
    preference_type: str = ""  # PreferenceType value
    preference_value: Dict = field(default_factory=dict)

    # Inference metadata
    confidence_score: Optional[float] = None
    source: str = DataSource.INFERRED.value
    inference_reasoning: Optional[str] = None

    # User feedback
    user_feedback: Optional[str] = None  # 'confirmed', 'rejected', 'modified'

    # Commit result
    committed_preference_id: Optional[int] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        data = {
            "preference_type": self.preference_type,
            "preference_value": self.preference_value,
            "confidence_score": self.confidence_score,
            "source": self.source,
            "inference_reasoning": self.inference_reasoning,
            "user_feedback": self.user_feedback,
        }
        if self.id:
            data["id"] = str(self.id)
        if self.session_id:
            data["session_id"] = str(self.session_id)
        if self.staging_product_id:
            data["staging_product_id"] = str(self.staging_product_id)
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class InvoicePhoto:
    """Metadata for an uploaded invoice photo."""
    id: Optional[UUID] = None
    session_id: Optional[UUID] = None

    # Photo storage
    telegram_file_id: str = ""
    telegram_file_url: str = ""
    storage_path: Optional[str] = None

    # Parsing results
    parsed_at: Optional[datetime] = None
    parsing_success: Optional[bool] = None
    parsing_error: Optional[str] = None
    raw_extraction_result: Optional[Dict] = None

    # Extraction summary
    supplier_name_extracted: Optional[str] = None
    supplier_cnpj_extracted: Optional[str] = None
    invoice_date_extracted: Optional[date] = None
    invoice_number_extracted: Optional[str] = None
    products_count: int = 0
    total_amount_extracted: Optional[float] = None

    photo_index: int = 0
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        data = {
            "telegram_file_id": self.telegram_file_id,
            "telegram_file_url": self.telegram_file_url,
            "storage_path": self.storage_path,
            "photo_index": self.photo_index,
        }
        if self.id:
            data["id"] = str(self.id)
        if self.session_id:
            data["session_id"] = str(self.session_id)
        return {k: v for k, v in data.items() if v is not None}


# ============================================================================
# ANALYSIS MODELS
# ============================================================================

@dataclass
class AnalysisInsight:
    """A single insight generated by the analysis engine."""
    id: Optional[UUID] = None
    session_id: Optional[UUID] = None

    insight_type: str = ""  # InsightType value
    insight_category: Optional[str] = None  # e.g., "carnes", "hortifruti"
    insight_title: str = ""
    insight_description: str = ""
    insight_data: Dict = field(default_factory=dict)

    confidence_score: Optional[float] = None
    display_priority: int = 0  # Lower = higher priority

    user_feedback: Optional[str] = None

    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        data = {
            "insight_type": self.insight_type,
            "insight_category": self.insight_category,
            "insight_title": self.insight_title,
            "insight_description": self.insight_description,
            "insight_data": self.insight_data,
            "confidence_score": self.confidence_score,
            "display_priority": self.display_priority,
            "user_feedback": self.user_feedback,
        }
        if self.id:
            data["id"] = str(self.id)
        if self.session_id:
            data["session_id"] = str(self.session_id)
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class CategorySpend:
    """Spend breakdown for a product category."""
    category: str
    total_spend: float
    percentage: float
    product_count: int
    top_products: List[str] = field(default_factory=list)


@dataclass
class SupplierRanking:
    """Supplier ranking within a category."""
    supplier_id: UUID
    supplier_name: str
    category: str
    total_spend: float
    product_count: int
    rank: int
    price_competitiveness: Optional[float] = None


@dataclass
class BrandPreference:
    """Detected brand preference for a product."""
    product_name: str
    brand_name: str
    purchase_percentage: float
    purchase_count: int
    confidence: float  # 'strong' if >80%, 'moderate' if 50-80%

    @property
    def strength(self) -> str:
        if self.purchase_percentage >= 0.9:
            return "forte"
        elif self.purchase_percentage >= 0.7:
            return "moderada"
        else:
            return "fraca"


@dataclass
class PriceRange:
    """Price range analysis for a product."""
    product_name: str
    product_id: UUID
    min_price: float
    max_price: float
    avg_price: float
    suggested_max: float  # Inferred maximum acceptable price
    unit: str
    variance_percentage: float


@dataclass
class DeliveryPattern:
    """Detected delivery pattern for a category."""
    category: str
    supplier_name: Optional[str]
    delivery_days: List[str]  # ["segunda", "quarta", "sexta"]
    frequency_description: str  # "3x por semana"
    confidence: float


# ============================================================================
# SESSION & RESULT MODELS
# ============================================================================

@dataclass
class OnboardingSession:
    """Complete onboarding session data."""
    id: Optional[UUID] = None
    telegram_chat_id: int = 0

    # Session state
    status: str = SessionStatus.IN_PROGRESS.value
    current_phase: str = SessionPhase.BASIC_INFO.value

    # Restaurant basic info
    restaurant_name: Optional[str] = None
    city: Optional[str] = None
    restaurant_type: Optional[str] = None
    contact_name: Optional[str] = None

    # Timestamps
    started_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    committed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Commit results
    committed_restaurant_id: Optional[int] = None
    committed_person_id: Optional[int] = None

    # Counters
    photos_uploaded: int = 0
    products_extracted: int = 0
    suppliers_extracted: int = 0
    preferences_configured: int = 0

    # Analysis
    analysis_completed_at: Optional[datetime] = None
    analysis_result: Optional[Dict] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        data = {
            "telegram_chat_id": self.telegram_chat_id,
            "status": self.status,
            "current_phase": self.current_phase,
            "restaurant_name": self.restaurant_name,
            "city": self.city,
            "restaurant_type": self.restaurant_type,
            "contact_name": self.contact_name,
            "photos_uploaded": self.photos_uploaded,
            "products_extracted": self.products_extracted,
            "suppliers_extracted": self.suppliers_extracted,
            "preferences_configured": self.preferences_configured,
        }
        if self.id:
            data["id"] = str(self.id)
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class OnboardingAnalysisResult:
    """Complete analysis result for an onboarding session."""
    session_id: UUID

    # Summary statistics
    total_spend: float = 0.0
    invoice_count: int = 0
    supplier_count: int = 0
    product_count: int = 0

    # Category breakdown
    category_spend: List[CategorySpend] = field(default_factory=list)

    # Top products
    top_products: List[StagedProduct] = field(default_factory=list)
    priority_products: List[StagedProduct] = field(default_factory=list)

    # Supplier rankings
    supplier_rankings: List[SupplierRanking] = field(default_factory=list)

    # Detected preferences
    brand_preferences: List[BrandPreference] = field(default_factory=list)
    price_ranges: List[PriceRange] = field(default_factory=list)
    delivery_patterns: List[DeliveryPattern] = field(default_factory=list)

    # Insights
    insights: List[AnalysisInsight] = field(default_factory=list)

    # Pareto analysis
    pareto_percentage: float = 0.0  # % of spend from top 20% products
    pareto_product_count: int = 0

    # Analysis metadata
    analysis_timestamp: Optional[datetime] = None
    confidence_score: float = 0.0


@dataclass
class CommitResult:
    """Result of committing onboarding data to production."""
    success: bool = False

    restaurant_id: Optional[int] = None
    person_id: Optional[int] = None

    suppliers_committed: int = 0
    products_committed: int = 0
    prices_committed: int = 0
    preferences_committed: int = 0

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    committed_at: Optional[datetime] = None
