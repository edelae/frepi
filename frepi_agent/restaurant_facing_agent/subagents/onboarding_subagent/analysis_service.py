"""
Onboarding Analysis Service - The Intelligence Layer.

This service analyzes staged onboarding data to extract insights and infer
preferences about buying patterns, brand tendencies, price thresholds,
delivery patterns, and product importance.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID, uuid4
import statistics

from frepi_agent.shared.supabase_client import get_supabase_client, Tables
from .models import (
    StagedSupplier,
    StagedProduct,
    StagedPrice,
    StagedPreference,
    AnalysisInsight,
    OnboardingAnalysisResult,
    CategorySpend,
    SupplierRanking,
    BrandPreference,
    PriceRange,
    DeliveryPattern,
    InsightType,
    PreferenceType,
    ProductCategory,
    DataSource,
    SessionPhase,
)
from .staging_service import OnboardingStagingService

logger = logging.getLogger(__name__)


# Product category keywords for classification
CATEGORY_KEYWORDS = {
    ProductCategory.PROTEINAS.value: [
        "picanha", "carne", "bife", "alcatra", "costela", "frango", "peito",
        "coxa", "asa", "linguiça", "salsicha", "bacon", "presunto", "mortadela",
        "peixe", "tilápia", "salmão", "camarão", "atum", "sardinha", "bacalhau",
        "carne seca", "charque", "cupim", "maminha", "contra filé", "filé mignon",
        "acém", "patinho", "músculo", "pernil", "lombo", "bisteca", "coxinha",
        "sobrecoxa", "fígado", "moela", "coração", "porco", "suíno",
    ],
    ProductCategory.HORTIFRUTI.value: [
        "tomate", "cebola", "alho", "batata", "cenoura", "beterraba", "mandioca",
        "abobrinha", "berinjela", "pimentão", "pepino", "alface", "rúcula",
        "agrião", "espinafre", "couve", "repolho", "brócolis", "couve-flor",
        "vagem", "ervilha", "milho", "laranja", "limão", "maçã", "banana",
        "mamão", "melancia", "melão", "abacaxi", "uva", "morango", "manga",
        "goiaba", "maracujá", "abacate", "coco", "kiwi", "pera", "pêssego",
        "cheiro verde", "salsa", "cebolinha", "coentro", "hortelã", "manjericão",
        "jiló", "quiabo", "chuchu", "aipim", "inhame", "gengibre",
    ],
    ProductCategory.MERCEARIA.value: [
        "arroz", "feijão", "macarrão", "farinha", "açúcar", "sal", "óleo",
        "azeite", "vinagre", "molho", "extrato", "massa", "tempero", "pimenta",
        "orégano", "colorau", "cominho", "curry", "mostarda", "ketchup",
        "maionese", "catchup", "sardinha lata", "atum lata", "milho lata",
        "ervilha lata", "leite condensado", "creme de leite", "café", "chá",
        "achocolatado", "biscoito", "bolacha", "pão", "torrada", "cereais",
        "aveia", "granola", "soja", "lentilha", "grão de bico",
    ],
    ProductCategory.LATICINIOS.value: [
        "leite", "queijo", "mussarela", "parmesão", "provolone", "gorgonzola",
        "requeijão", "cream cheese", "manteiga", "margarina", "iogurte",
        "creme de leite", "leite condensado", "nata", "ricota", "cottage",
        "coalho", "minas", "prato",
    ],
    ProductCategory.BEBIDAS.value: [
        "água", "refrigerante", "suco", "cerveja", "vinho", "cachaça", "vodka",
        "whisky", "rum", "gin", "tequila", "energético", "isotônico", "chá gelado",
        "guaraná", "coca", "pepsi", "fanta", "sprite", "h2oh", "mate",
    ],
    ProductCategory.PADARIA.value: [
        "pão", "bolo", "torta", "salgado", "croissant", "sonho", "rosquinha",
        "brioche", "ciabatta", "baguete", "pão de queijo", "fermento",
    ],
    ProductCategory.CONGELADOS.value: [
        "congelado", "sorvete", "picolé", "hambúrguer", "nuggets", "empanado",
        "lasanha", "pizza congelada", "batata frita", "polpa",
    ],
    ProductCategory.LIMPEZA.value: [
        "detergente", "desinfetante", "água sanitária", "sabão", "esponja",
        "pano", "luva", "saco de lixo", "papel toalha", "guardanapo",
        "álcool", "multiuso", "limpa vidro", "removedor",
    ],
    ProductCategory.DESCARTAVEIS.value: [
        "copo descartável", "prato descartável", "talher descartável",
        "embalagem", "marmitex", "quentinha", "sacola", "canudo", "tampa",
        "papel alumínio", "filme plástico", "papel manteiga",
    ],
}

# Days of week in Portuguese
DIAS_SEMANA = {
    0: "segunda",
    1: "terça",
    2: "quarta",
    3: "quinta",
    4: "sexta",
    5: "sábado",
    6: "domingo",
}


class OnboardingAnalysisService:
    """
    Analyzes staged onboarding data to extract insights and preferences.

    This is the intelligence layer that:
    - Calculates product importance scores
    - Categorizes products automatically
    - Analyzes spend distribution
    - Detects brand preferences
    - Infers price thresholds
    - Identifies delivery patterns
    - Generates actionable insights
    """

    def __init__(self):
        self.client = get_supabase_client()
        self.staging_service = OnboardingStagingService()

    async def run_full_analysis(self, session_id: UUID) -> OnboardingAnalysisResult:
        """
        Run complete analysis on staged data.

        This is the main entry point that orchestrates all analysis steps.

        Args:
            session_id: The onboarding session UUID

        Returns:
            OnboardingAnalysisResult with all analysis data
        """
        logger.info(f"Starting full analysis for session {session_id}")

        # Update phase
        await self.staging_service.update_session_phase(
            session_id, SessionPhase.ANALYSIS
        )

        # Get all staged data
        suppliers = await self.staging_service.get_staged_suppliers(session_id)
        products = await self.staging_service.get_staged_products(session_id)
        prices = await self.staging_service.get_staged_prices(session_id)
        photos = await self.staging_service.get_invoice_photos(session_id)

        # Initialize result
        result = OnboardingAnalysisResult(
            session_id=session_id,
            invoice_count=len(photos),
            supplier_count=len(suppliers),
            product_count=len(products),
            analysis_timestamp=datetime.now(timezone.utc),
        )

        # Step 1: Analyze products (importance, categories, spend)
        await self._analyze_products(session_id, products, prices, result)

        # Step 2: Analyze suppliers
        await self._analyze_suppliers(session_id, suppliers, products, prices, result)

        # Step 3: Analyze prices
        await self._analyze_prices(session_id, products, prices, result)

        # Step 4: Analyze patterns
        await self._analyze_patterns(session_id, products, prices, photos, result)

        # Step 5: Detect brand preferences
        await self._analyze_brand_preferences(session_id, products, prices, result)

        # Step 6: Generate and save insights
        await self._generate_insights(session_id, result)

        # Update session with analysis completion
        now = datetime.now(timezone.utc).isoformat()
        self.client.table(Tables.ONBOARDING_SESSIONS).update({
            "analysis_completed_at": now,
            "analysis_result": {
                "total_spend": result.total_spend,
                "supplier_count": result.supplier_count,
                "product_count": result.product_count,
                "pareto_percentage": result.pareto_percentage,
            },
            "current_phase": SessionPhase.SUMMARY.value,
            "updated_at": now,
        }).eq("id", str(session_id)).execute()

        logger.info(f"Analysis complete for session {session_id}")
        return result

    # =========================================================================
    # PRODUCT ANALYSIS
    # =========================================================================

    async def _analyze_products(
        self,
        session_id: UUID,
        products: List[StagedProduct],
        prices: List[StagedPrice],
        result: OnboardingAnalysisResult,
    ):
        """Analyze products: importance, categories, spend distribution."""
        logger.info(f"Analyzing {len(products)} products")

        # Build price lookup
        price_by_product = defaultdict(list)
        for price in prices:
            if price.staging_product_id:
                price_by_product[price.staging_product_id].append(price)

        total_spend = 0.0
        product_updates = []

        for product in products:
            product_prices = price_by_product.get(product.id, [])

            # Calculate spend for this product
            product_spend = 0.0
            quantities = []
            unit_prices = []

            for p in product_prices:
                if p.total_line_amount:
                    product_spend += p.total_line_amount
                elif p.unit_price and p.quantity_purchased:
                    product_spend += p.unit_price * p.quantity_purchased
                if p.quantity_purchased:
                    quantities.append(p.quantity_purchased)
                if p.unit_price:
                    unit_prices.append(p.unit_price)

            total_spend += product_spend

            # Calculate statistics
            avg_price = statistics.mean(unit_prices) if unit_prices else 0
            min_price = min(unit_prices) if unit_prices else 0
            max_price = max(unit_prices) if unit_prices else 0
            total_qty = sum(quantities) if quantities else 0

            # Categorize product
            category = self._categorize_product(product.product_name)

            # Store updates
            product_updates.append({
                "product_id": product.id,
                "total_spend": product_spend,
                "purchase_frequency": len(product_prices),
                "total_quantity_purchased": total_qty,
                "avg_unit_price": avg_price,
                "price_range_min": min_price,
                "price_range_max": max_price,
                "inferred_category": category,
            })

        result.total_spend = total_spend

        # Calculate importance scores and spend share
        for update in product_updates:
            if total_spend > 0:
                update["spend_share_percentage"] = (
                    update["total_spend"] / total_spend * 100
                )

            # Importance score: weighted average of frequency, spend, and share
            freq_score = min(update["purchase_frequency"] / 10, 1.0)  # Cap at 10 purchases
            spend_score = min(update["total_spend"] / (total_spend * 0.2), 1.0) if total_spend > 0 else 0
            share_score = min(update["spend_share_percentage"] / 10, 1.0) if update.get("spend_share_percentage") else 0

            importance = (freq_score * 0.3 + spend_score * 0.4 + share_score * 0.3)
            update["inferred_importance_score"] = round(importance, 2)

        # Update products in database
        for update in product_updates:
            product_id = update.pop("product_id")
            await self.staging_service.update_staged_product(product_id, update)

        # Refresh products and build result lists
        products = await self.staging_service.get_staged_products(session_id)

        # Sort by importance and set top 10 as priority
        sorted_products = sorted(
            products,
            key=lambda p: p.inferred_importance_score or 0,
            reverse=True
        )

        top_10_ids = [p.id for p in sorted_products[:10]]
        await self.staging_service.set_priority_products(session_id, top_10_ids)

        # Store in result
        result.top_products = sorted_products[:10]
        result.priority_products = sorted_products[:10]

        # Calculate category breakdown
        category_spend = defaultdict(lambda: {"spend": 0, "count": 0, "products": []})
        for product in products:
            cat = product.inferred_category or ProductCategory.OUTROS.value
            category_spend[cat]["spend"] += product.total_spend or 0
            category_spend[cat]["count"] += 1
            category_spend[cat]["products"].append(product.product_name)

        result.category_spend = [
            CategorySpend(
                category=cat,
                total_spend=data["spend"],
                percentage=(data["spend"] / total_spend * 100) if total_spend > 0 else 0,
                product_count=data["count"],
                top_products=data["products"][:5],
            )
            for cat, data in sorted(
                category_spend.items(),
                key=lambda x: x[1]["spend"],
                reverse=True
            )
        ]

        # Assign importance tiers based on cumulative spend
        await self._assign_tiers(session_id, sorted_products, total_spend)

        # Pareto analysis (80/20 rule)
        cumulative = 0
        pareto_count = 0
        for product in sorted_products:
            cumulative += product.total_spend or 0
            pareto_count += 1
            if cumulative >= total_spend * 0.8:
                break

        result.pareto_percentage = (pareto_count / len(products) * 100) if products else 0
        result.pareto_product_count = pareto_count

        logger.info(f"Product analysis complete. Total spend: R${total_spend:.2f}")

    async def _assign_tiers(
        self,
        session_id: UUID,
        sorted_products: List[StagedProduct],
        total_spend: float,
    ):
        """
        Assign importance tiers based on cumulative spend distribution.

        - head: top products whose cumulative spend reaches 60% of total
        - mid_tail: next products up to 90% cumulative
        - long_tail: everything else
        """
        if not sorted_products or total_spend <= 0:
            return

        cumulative = 0.0
        for product in sorted_products:
            cumulative += product.total_spend or 0
            pct = cumulative / total_spend

            if pct <= 0.60:
                tier = "head"
            elif pct <= 0.90:
                tier = "mid_tail"
            else:
                tier = "long_tail"

            product.importance_tier = tier
            await self.staging_service.update_staged_product(product.id, {
                "importance_tier": tier,
            })

        tier_counts = {"head": 0, "mid_tail": 0, "long_tail": 0}
        for p in sorted_products:
            tier_counts[p.importance_tier or "long_tail"] += 1

        logger.info(
            f"Tier assignment: head={tier_counts['head']}, "
            f"mid_tail={tier_counts['mid_tail']}, long_tail={tier_counts['long_tail']}"
        )

    def _categorize_product(self, product_name: str) -> str:
        """
        Categorize a product based on keywords.

        Args:
            product_name: The product name

        Returns:
            Category string
        """
        name_lower = product_name.lower()

        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return category

        return ProductCategory.OUTROS.value

    # =========================================================================
    # SUPPLIER ANALYSIS
    # =========================================================================

    async def _analyze_suppliers(
        self,
        session_id: UUID,
        suppliers: List[StagedSupplier],
        products: List[StagedProduct],
        prices: List[StagedPrice],
        result: OnboardingAnalysisResult,
    ):
        """Analyze suppliers: spend, categories, rankings."""
        logger.info(f"Analyzing {len(suppliers)} suppliers")

        # Build supplier lookup
        supplier_by_id = {s.id: s for s in suppliers}

        # Calculate supplier metrics
        supplier_metrics = defaultdict(lambda: {
            "spend": 0,
            "product_count": 0,
            "categories": set(),
            "invoice_count": 0,
        })

        for product in products:
            if product.staging_supplier_id:
                metrics = supplier_metrics[product.staging_supplier_id]
                metrics["spend"] += product.total_spend or 0
                metrics["product_count"] += 1
                if product.inferred_category:
                    metrics["categories"].add(product.inferred_category)

        # Count invoices per supplier
        for price in prices:
            if price.staging_supplier_id:
                supplier_metrics[price.staging_supplier_id]["invoice_count"] += 1

        # Update suppliers in database
        for supplier_id, metrics in supplier_metrics.items():
            supplier = supplier_by_id.get(supplier_id)
            if supplier:
                await self.staging_service.update_staged_supplier(supplier_id, {
                    "total_spend": metrics["spend"],
                    "invoice_count": len(set([p.invoice_number for p in prices
                                              if p.staging_supplier_id == supplier_id])),
                    "product_categories": list(metrics["categories"]),
                })

        # Build supplier rankings per category
        rankings = []
        category_suppliers = defaultdict(list)

        for supplier_id, metrics in supplier_metrics.items():
            supplier = supplier_by_id.get(supplier_id)
            if supplier:
                for category in metrics["categories"]:
                    category_suppliers[category].append({
                        "supplier_id": supplier_id,
                        "supplier_name": supplier.company_name,
                        "category": category,
                        "spend": metrics["spend"],
                        "product_count": metrics["product_count"],
                    })

        # Rank within each category
        for category, suppliers_in_cat in category_suppliers.items():
            sorted_suppliers = sorted(
                suppliers_in_cat,
                key=lambda x: x["spend"],
                reverse=True
            )
            for rank, s in enumerate(sorted_suppliers, 1):
                rankings.append(SupplierRanking(
                    supplier_id=s["supplier_id"],
                    supplier_name=s["supplier_name"],
                    category=category,
                    total_spend=s["spend"],
                    product_count=s["product_count"],
                    rank=rank,
                ))

        result.supplier_rankings = rankings
        logger.info(f"Supplier analysis complete. {len(rankings)} rankings created")

    # =========================================================================
    # PRICE ANALYSIS
    # =========================================================================

    async def _analyze_prices(
        self,
        session_id: UUID,
        products: List[StagedProduct],
        prices: List[StagedPrice],
        result: OnboardingAnalysisResult,
    ):
        """Analyze prices: ranges, thresholds, opportunities."""
        logger.info(f"Analyzing {len(prices)} price records")

        product_by_id = {p.id: p for p in products}
        price_ranges = []

        # Group prices by product
        prices_by_product = defaultdict(list)
        for price in prices:
            if price.staging_product_id:
                prices_by_product[price.staging_product_id].append(price)

        # Calculate price ranges for each product
        for product_id, product_prices in prices_by_product.items():
            product = product_by_id.get(product_id)
            if not product:
                continue

            unit_prices = [p.unit_price for p in product_prices if p.unit_price]
            if not unit_prices:
                continue

            min_price = min(unit_prices)
            max_price = max(unit_prices)
            avg_price = statistics.mean(unit_prices)

            # Calculate variance
            variance_pct = ((max_price - min_price) / avg_price * 100) if avg_price > 0 else 0

            # Suggest max price: 10% above max observed, or 20% above avg if high variance
            if variance_pct > 20:
                suggested_max = avg_price * 1.2
            else:
                suggested_max = max_price * 1.1

            # Get unit from first price
            unit = product_prices[0].price_per_unit_type or "un"

            price_ranges.append(PriceRange(
                product_name=product.product_name,
                product_id=product_id,
                min_price=round(min_price, 2),
                max_price=round(max_price, 2),
                avg_price=round(avg_price, 2),
                suggested_max=round(suggested_max, 2),
                unit=unit,
                variance_percentage=round(variance_pct, 1),
            ))

            # Create price preference
            preference = StagedPreference(
                staging_product_id=product_id,
                preference_type=PreferenceType.PRICE_MAX.value,
                preference_value={
                    "max_price": round(suggested_max, 2),
                    "unit": unit,
                    "based_on_avg": round(avg_price, 2),
                    "based_on_max": round(max_price, 2),
                },
                confidence_score=0.8 if variance_pct < 20 else 0.6,
                source=DataSource.INFERRED.value,
                inference_reasoning=f"Baseado em {len(unit_prices)} registros de preço. "
                                   f"Variação: {variance_pct:.1f}%",
            )
            await self.staging_service.stage_preference(session_id, preference)

        result.price_ranges = sorted(price_ranges, key=lambda x: x.avg_price, reverse=True)[:10]
        logger.info(f"Price analysis complete. {len(price_ranges)} ranges calculated")

    # =========================================================================
    # PATTERN ANALYSIS
    # =========================================================================

    async def _analyze_patterns(
        self,
        session_id: UUID,
        products: List[StagedProduct],
        prices: List[StagedPrice],
        photos: List,
        result: OnboardingAnalysisResult,
    ):
        """Analyze delivery patterns and purchase frequency."""
        logger.info("Analyzing delivery patterns")

        # Group by category and supplier
        category_days = defaultdict(lambda: defaultdict(int))
        supplier_days = defaultdict(lambda: defaultdict(int))

        # Get supplier lookup
        suppliers = await self.staging_service.get_staged_suppliers(session_id)
        supplier_by_id = {s.id: s for s in suppliers}

        product_by_id = {p.id: p for p in products}

        for price in prices:
            if not price.invoice_date:
                continue

            # Get day of week
            try:
                if isinstance(price.invoice_date, str):
                    date_obj = datetime.fromisoformat(price.invoice_date)
                else:
                    date_obj = datetime.combine(price.invoice_date, datetime.min.time())
                day = DIAS_SEMANA[date_obj.weekday()]
            except Exception:
                continue

            # Get product category
            product = product_by_id.get(price.staging_product_id)
            if product and product.inferred_category:
                category_days[product.inferred_category][day] += 1

            # Track by supplier
            if price.staging_supplier_id:
                supplier = supplier_by_id.get(price.staging_supplier_id)
                if supplier:
                    supplier_days[supplier.company_name][day] += 1

        # Determine most common delivery days per category
        delivery_patterns = []
        for category, days in category_days.items():
            if not days:
                continue

            # Sort by frequency and take top days
            sorted_days = sorted(days.items(), key=lambda x: x[1], reverse=True)
            common_days = [d[0] for d in sorted_days if d[1] > 1][:3]

            if common_days:
                freq_description = self._describe_frequency(len(common_days))
                delivery_patterns.append(DeliveryPattern(
                    category=category,
                    supplier_name=None,
                    delivery_days=common_days,
                    frequency_description=freq_description,
                    confidence=min(sum(days.values()) / 10, 0.9),
                ))

                # Create delivery preference
                preference = StagedPreference(
                    preference_type=PreferenceType.DELIVERY_DAY.value,
                    preference_value={
                        "category": category,
                        "days": common_days,
                        "frequency": freq_description,
                    },
                    confidence_score=0.7,
                    source=DataSource.INFERRED.value,
                    inference_reasoning=f"Baseado em {sum(days.values())} entregas registradas",
                )
                await self.staging_service.stage_preference(session_id, preference)

        result.delivery_patterns = delivery_patterns
        logger.info(f"Pattern analysis complete. {len(delivery_patterns)} patterns found")

    def _describe_frequency(self, days_per_week: int) -> str:
        """Describe delivery frequency in Portuguese."""
        if days_per_week >= 5:
            return "diariamente"
        elif days_per_week >= 3:
            return f"{days_per_week}x por semana"
        elif days_per_week >= 2:
            return "2x por semana"
        elif days_per_week == 1:
            return "semanalmente"
        else:
            return "esporadicamente"

    # =========================================================================
    # BRAND PREFERENCE ANALYSIS
    # =========================================================================

    async def _analyze_brand_preferences(
        self,
        session_id: UUID,
        products: List[StagedProduct],
        prices: List[StagedPrice],
        result: OnboardingAnalysisResult,
    ):
        """Detect brand preferences from purchase patterns."""
        logger.info("Analyzing brand preferences")

        # Group products by base name (without brand)
        product_groups = defaultdict(list)
        for product in products:
            if product.brand:
                base_name = self._get_base_product_name(product.product_name)
                product_groups[base_name].append(product)

        brand_preferences = []

        for base_name, group in product_groups.items():
            if len(group) < 2:
                continue

            # Count purchases per brand
            brand_counts = defaultdict(lambda: {"count": 0, "spend": 0})
            total_count = 0

            for product in group:
                brand_counts[product.brand]["count"] += product.purchase_frequency or 1
                brand_counts[product.brand]["spend"] += product.total_spend or 0
                total_count += product.purchase_frequency or 1

            if total_count == 0:
                continue

            # Find dominant brand
            sorted_brands = sorted(
                brand_counts.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )

            top_brand, top_data = sorted_brands[0]
            percentage = top_data["count"] / total_count

            if percentage >= 0.5:  # At least 50% of purchases
                brand_pref = BrandPreference(
                    product_name=base_name,
                    brand_name=top_brand,
                    purchase_percentage=percentage,
                    purchase_count=top_data["count"],
                    confidence=min(percentage + 0.1, 0.95),
                )
                brand_preferences.append(brand_pref)

                # Find the main product for this brand
                main_product = next(
                    (p for p in group if p.brand == top_brand),
                    group[0]
                )

                # Create preference
                preference = StagedPreference(
                    staging_product_id=main_product.id,
                    preference_type=PreferenceType.BRAND.value,
                    preference_value={
                        "brand": top_brand,
                        "percentage": round(percentage * 100, 1),
                        "alternatives": [b for b, _ in sorted_brands[1:3]],
                    },
                    confidence_score=brand_pref.confidence,
                    source=DataSource.INFERRED.value,
                    inference_reasoning=f"{top_brand} representa {percentage*100:.0f}% das compras de {base_name}",
                )
                await self.staging_service.stage_preference(session_id, preference)

        result.brand_preferences = sorted(
            brand_preferences,
            key=lambda x: x.purchase_percentage,
            reverse=True
        )
        logger.info(f"Brand analysis complete. {len(brand_preferences)} preferences found")

    def _get_base_product_name(self, product_name: str) -> str:
        """Extract base product name without brand/size details."""
        # Simple approach: take first 2-3 words
        words = product_name.lower().split()
        return " ".join(words[:min(2, len(words))])

    # =========================================================================
    # INSIGHT GENERATION
    # =========================================================================

    async def _generate_insights(
        self,
        session_id: UUID,
        result: OnboardingAnalysisResult,
    ):
        """Generate and save actionable insights."""
        logger.info("Generating insights")

        insights = []

        # Insight 1: Spend distribution
        if result.category_spend:
            top_category = result.category_spend[0]
            insights.append(AnalysisInsight(
                insight_type=InsightType.SPEND_DISTRIBUTION.value,
                insight_category=top_category.category,
                insight_title="Distribuição de Gastos",
                insight_description=f"A categoria '{top_category.category}' representa "
                                   f"{top_category.percentage:.0f}% do gasto total (R${top_category.total_spend:,.2f})",
                insight_data={
                    "categories": [
                        {
                            "name": c.category,
                            "spend": c.total_spend,
                            "percentage": c.percentage,
                        }
                        for c in result.category_spend
                    ]
                },
                confidence_score=0.95,
                display_priority=1,
            ))

        # Insight 2: Pareto analysis
        if result.pareto_percentage > 0:
            insights.append(AnalysisInsight(
                insight_type=InsightType.PARETO_ANALYSIS.value,
                insight_title="Concentração de Gastos (80/20)",
                insight_description=f"80% do seu gasto vem de apenas {result.pareto_product_count} produtos "
                                   f"({result.pareto_percentage:.0f}% do total)",
                insight_data={
                    "products_for_80_percent": result.pareto_product_count,
                    "percentage_of_products": result.pareto_percentage,
                },
                confidence_score=0.95,
                display_priority=2,
            ))

        # Insight 3: Supplier concentration
        if result.supplier_rankings:
            top_suppliers = [r for r in result.supplier_rankings if r.rank == 1]
            if top_suppliers:
                top = top_suppliers[0]
                supplier_share = (top.total_spend / result.total_spend * 100) if result.total_spend > 0 else 0
                if supplier_share > 40:
                    insights.append(AnalysisInsight(
                        insight_type=InsightType.DIVERSIFICATION_SUGGESTION.value,
                        insight_title="Concentração em Fornecedor",
                        insight_description=f"'{top.supplier_name}' representa {supplier_share:.0f}% do gasto total. "
                                           "Considere diversificar fornecedores.",
                        insight_data={
                            "supplier": top.supplier_name,
                            "share_percentage": supplier_share,
                            "spend": top.total_spend,
                        },
                        confidence_score=0.85,
                        display_priority=3,
                    ))

        # Insight 4: Price opportunities
        high_variance_products = [
            p for p in result.price_ranges
            if p.variance_percentage > 15
        ]
        if high_variance_products:
            top_opportunity = high_variance_products[0]
            insights.append(AnalysisInsight(
                insight_type=InsightType.PRICE_OPPORTUNITY.value,
                insight_title="Oportunidade de Preço",
                insight_description=f"'{top_opportunity.product_name}' tem variação de "
                                   f"{top_opportunity.variance_percentage:.0f}% entre fornecedores - vale comparar",
                insight_data={
                    "product": top_opportunity.product_name,
                    "min_price": top_opportunity.min_price,
                    "max_price": top_opportunity.max_price,
                    "variance": top_opportunity.variance_percentage,
                },
                confidence_score=0.8,
                display_priority=4,
            ))

        # Insight 5: High frequency products
        if result.top_products:
            high_freq = [p for p in result.top_products if (p.purchase_frequency or 0) > 5]
            if high_freq:
                product_names = ", ".join([p.product_name for p in high_freq[:3]])
                insights.append(AnalysisInsight(
                    insight_type=InsightType.PURCHASING_FREQUENCY.value,
                    insight_title="Alta Frequência de Compra",
                    insight_description=f"{product_names} são comprados frequentemente - "
                                       "considere negociar volume",
                    insight_data={
                        "products": [
                            {"name": p.product_name, "frequency": p.purchase_frequency}
                            for p in high_freq[:5]
                        ]
                    },
                    confidence_score=0.85,
                    display_priority=5,
                ))

        # Save insights to database
        for insight in insights:
            insight.session_id = session_id
            data = insight.to_dict()
            self.client.table(Tables.ONBOARDING_ANALYSIS_INSIGHTS).insert(data).execute()

        result.insights = insights
        logger.info(f"Generated {len(insights)} insights")

    # =========================================================================
    # SUMMARY FORMATTING
    # =========================================================================

    async def format_analysis_summary(self, session_id: UUID) -> str:
        """
        Format the analysis results as a user-friendly summary.

        Args:
            session_id: The session UUID

        Returns:
            Formatted summary string for display
        """
        # Get session and all data
        summary_data = await self.staging_service.get_session_summary(session_id)
        session = summary_data["session"]

        # Get analysis insights
        insights_result = self.client.table(Tables.ONBOARDING_ANALYSIS_INSIGHTS).select("*").eq(
            "session_id", str(session_id)
        ).order("display_priority").execute()
        insights = insights_result.data or []

        # Get products sorted by importance
        products = await self.staging_service.get_staged_products(session_id)
        products.sort(key=lambda p: p.inferred_importance_score or 0, reverse=True)

        # Get suppliers
        suppliers = await self.staging_service.get_staged_suppliers(session_id)
        suppliers.sort(key=lambda s: s.total_spend or 0, reverse=True)

        # Get preferences
        preferences = await self.staging_service.get_staged_preferences(session_id)

        # Calculate totals
        total_spend = sum(p.total_spend or 0 for p in products)
        photos = await self.staging_service.get_invoice_photos(session_id)

        # Build summary
        lines = [
            "📊 **Análise do seu Histórico de Compras**",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"🍽️ **Restaurante:** {session.get('restaurant_name', 'N/A')}",
            f"📍 **Cidade:** {session.get('city', 'N/A')}",
            f"📅 **Período analisado:** {len(photos)} notas fiscais",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "## 💰 DISTRIBUIÇÃO DE GASTOS",
            "",
            f"Total analisado: **R$ {total_spend:,.2f}**",
            "",
        ]

        # Category breakdown
        category_spend = defaultdict(float)
        for p in products:
            cat = p.inferred_category or "outros"
            category_spend[cat] += p.total_spend or 0

        category_emojis = {
            "proteinas": "🥩",
            "hortifruti": "🥬",
            "mercearia": "🛒",
            "laticinios": "🧈",
            "bebidas": "🍺",
            "padaria": "🥖",
            "congelados": "🧊",
            "limpeza": "🧹",
            "descartaveis": "📦",
            "outros": "📋",
        }

        sorted_categories = sorted(
            category_spend.items(),
            key=lambda x: x[1],
            reverse=True
        )

        lines.append("| Categoria | Gasto | % Total |")
        lines.append("|-----------|-------|---------|")
        for cat, spend in sorted_categories[:6]:
            emoji = category_emojis.get(cat, "📋")
            pct = (spend / total_spend * 100) if total_spend > 0 else 0
            lines.append(f"| {emoji} {cat.title()} | R$ {spend:,.0f} | {pct:.0f}% |")

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "## ⭐ TOP 10 PRODUTOS MAIS IMPORTANTES",
            "",
            "Baseado em frequência de compra e valor gasto:",
            "",
            "| # | Produto | Freq. | Gasto Total | Preço Médio |",
            "|---|---------|-------|-------------|-------------|",
        ])

        for i, product in enumerate(products[:10], 1):
            freq = product.purchase_frequency or 0
            spend = product.total_spend or 0
            avg = product.avg_unit_price or 0
            unit = "kg" if "kg" in str(product.specifications or "") else "un"
            lines.append(
                f"| {i} | {product.product_name[:20]} | {freq}x | R$ {spend:,.0f} | R$ {avg:.2f}/{unit} |"
            )

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "## 📦 FORNECEDORES IDENTIFICADOS",
            "",
            "| Fornecedor | Categoria Principal | Gasto | Produtos |",
            "|------------|---------------------|-------|----------|",
        ])

        rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
        for i, supplier in enumerate(suppliers[:5], 1):
            emoji = rank_emojis.get(i, f"{i}.")
            categories = supplier.product_categories or []
            main_cat = categories[0] if categories else "N/A"
            lines.append(
                f"| {emoji} {supplier.company_name[:20]} | {main_cat} | R$ {supplier.total_spend or 0:,.0f} | - |"
            )

        # Brand preferences
        brand_prefs = [p for p in preferences if p.preference_type == PreferenceType.BRAND.value]
        if brand_prefs:
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                "## 🎯 PREFERÊNCIAS DETECTADAS",
                "",
                "### Marcas Preferidas",
            ])
            for pref in brand_prefs[:5]:
                val = pref.preference_value
                brand = val.get("brand", "N/A")
                pct = val.get("percentage", 0)
                strength = "✅ Forte preferência" if pct > 80 else "✅ Preferência moderada"
                lines.append(f"- **{pref.staging_product_id}:** {brand} ({pct:.0f}%) {strength}")

        # Price ranges
        price_prefs = [p for p in preferences if p.preference_type == PreferenceType.PRICE_MAX.value]
        if price_prefs:
            lines.extend([
                "",
                "### Faixas de Preço Típicas",
                "| Produto | Preço Mín | Preço Máx | Limite Sugerido |",
                "|---------|-----------|-----------|-----------------|",
            ])
            for pref in price_prefs[:5]:
                val = pref.preference_value
                unit = val.get("unit", "un")
                lines.append(
                    f"| - | R$ {val.get('based_on_avg', 0)*0.9:.2f} | R$ {val.get('based_on_max', 0):.2f} | R$ {val.get('max_price', 0):.2f}/{unit} |"
                )

        # Delivery patterns
        delivery_prefs = [p for p in preferences if p.preference_type == PreferenceType.DELIVERY_DAY.value]
        if delivery_prefs:
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                "## 📅 PADRÕES DE ENTREGA IDENTIFICADOS",
                "",
                "| Categoria | Dias de Entrega | Frequência |",
                "|-----------|-----------------|------------|",
            ])
            for pref in delivery_prefs:
                val = pref.preference_value
                cat = val.get("category", "N/A")
                days = ", ".join(val.get("days", []))
                freq = val.get("frequency", "N/A")
                emoji = category_emojis.get(cat, "📋")
                lines.append(f"| {emoji} {cat.title()} | {days.title()} | {freq} |")

        # Insights
        if insights:
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                "## 📈 INSIGHTS ADICIONAIS",
                "",
            ])
            for insight in insights:
                lines.append(f"💡 **{insight.get('insight_title')}:** {insight.get('insight_description')}")
                lines.append("")

        # Confirmation section
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "## ✅ CONFIRMAR CADASTRO",
            "",
            "Com base nesta análise, vou configurar:",
            f"- ✅ {len(suppliers)} fornecedores",
            f"- ✅ {len(products)} produtos ({len([p for p in products if p.is_priority])} prioritários)",
            f"- ✅ {len(brand_prefs)} preferências de marca",
            f"- ✅ {len(price_prefs)} limites de preço",
            f"- ✅ {len(delivery_prefs)} padrões de entrega",
            "",
            "**Estas informações estão corretas?**",
            "",
            "Digite:",
            "- **sim** → Salvar tudo e iniciar",
            "- **ajustar** → Modificar alguma informação",
            "- **não** → Cancelar e recomeçar",
        ])

        return "\n".join(lines)
