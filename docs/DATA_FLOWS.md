# Data Flow Registry — Frepi Procurement Agent

This document maps every data movement in the procurement agent: what triggers it, where data comes from, what transforms it, where it lands, and what preferences influence the outcome.

---

## Table of Contents

1. [Message Routing & User Identification](#1-message-routing--user-identification)
2. [Onboarding: Invoice Processing Pipeline](#2-onboarding-invoice-processing-pipeline)
3. [Onboarding: Staging to Production Commit](#3-onboarding-staging-to-production-commit)
4. [Product Search (Vector Similarity)](#4-product-search-vector-similarity)
5. [Price Queries & Validation](#5-price-queries--validation)
6. [Supplier Operations](#6-supplier-operations)
7. [Preference Correction Learning](#7-preference-correction-learning)
8. [Preference Drip System](#8-preference-drip-system)
9. [Engagement Scoring](#9-engagement-scoring)
10. [Supplier-Facing: Quotation Flow](#10-supplier-facing-quotation-flow)
11. [Supplier-Facing: Price Submission](#11-supplier-facing-price-submission)
12. [Supplier-Facing: Order Management](#12-supplier-facing-order-management)
13. [Supplier-Facing: Delivery Updates](#13-supplier-facing-delivery-updates)
14. [Table Read/Write Summary](#14-table-readwrite-summary)
15. [Preference Lifecycle Map](#15-preference-lifecycle-map)
16. [Critical Dependencies & Flow Gates](#16-critical-dependencies--flow-gates)

---

## 1. Message Routing & User Identification

```
Flow ID:       PROC-001
Trigger:        User sends any Telegram message
Source:         Telegram Bot API (polling)
Transform:      telegram_bot.py → identify_user() → user_identification.py
Destination:    In-memory _sessions dict
Conditions:     Always runs on first message per session
Preferences:    None
```

**Step-by-step:**

1. `handle_message()` receives Telegram Update
2. `get_session(chat_id)` retrieves or creates in-memory `UserSession`
3. If no cached user type → calls `identify_user(chat_id)`

**Database queries (READ only):**

| Query | Table | Filter | Returns |
|-------|-------|--------|---------|
| Find restaurant user | `restaurant_people` | `whatsapp_number = chat_id_str`, `is_active = True` | id, restaurant_id, name |
| Check onboarding | JOIN `restaurants` | `onboarding_completed_at` via FK | Timestamp or NULL |
| Fallback: +prefix | `restaurant_people` | `whatsapp_number = +{chat_id_str}` | Same fields |
| Find supplier | `suppliers` | `whatsapp_number = chat_id_str`, `is_active = True` | id, company_name |
| Fallback: +prefix | `suppliers` | `whatsapp_number = +{chat_id_str}` | Same fields |

**Routing decision:**

| Result | Route | Handler |
|--------|-------|---------|
| Found in restaurant_people + onboarding complete | Main restaurant agent | `restaurant_chat()` |
| Found in restaurant_people + onboarding incomplete | Onboarding subagent | `onboarding_chat()` |
| Found in suppliers | Supplier agent | `supplier_chat()` |
| Not found anywhere | Role selection prompt | `handle_role_selection()` |

---

## 2. Onboarding: Invoice Processing Pipeline

```
Flow ID:       PROC-002
Trigger:        User uploads photos + types "pronto"
Source:         Telegram photo files → GPT-4 Vision
Transform:      image_parser.py → staging_service.py → analysis_service.py
Destination:    onboarding_staging_* tables
Conditions:     Session needs_onboarding = True, photos uploaded
Preferences:    None (raw extraction)
```

**Sub-flows:**

### 2a. Photo Upload (PROC-002a)

| Step | Action | Source | Destination |
|------|--------|--------|-------------|
| 1 | User sends photo | Telegram | `handle_photo()` |
| 2 | Get file URL | `context.bot.get_file(file_id)` | `session.onboarding_context.uploaded_photos[]` |
| 3 | Confirm receipt | — | Telegram reply |

### 2b. Invoice Parsing (PROC-002b)

| Step | Action | API | Writes To |
|------|--------|-----|-----------|
| 1 | Download image | `download_image_as_base64(url)` → HTTP GET | In-memory |
| 2 | GPT-4 Vision extraction | OpenAI `gpt-4o` (temp=0.1) | In-memory ParsedInvoice |
| 3 | Save photo metadata | — | `onboarding_invoice_photos` |
| 4 | Stage suppliers | For each unique supplier | `onboarding_staging_suppliers` |
| 5 | Stage products | For each line item | `onboarding_staging_products` |
| 6 | Stage prices | For each price point | `onboarding_staging_prices` |

**GPT-4 Vision extracts:** supplier_name, CNPJ, invoice_date, items (product_name, quantity, unit, unit_price), total_amount, confidence_score.

### 2c. Analysis (PROC-002c)

| Step | Action | Reads | Writes |
|------|--------|-------|--------|
| 1 | Categorize products | `onboarding_staging_products` | In-memory |
| 2 | Spend analysis (Pareto) | `onboarding_staging_prices` | In-memory |
| 3 | Brand preference detection | All staging tables | In-memory |
| 4 | Price range analysis | `onboarding_staging_prices` | In-memory |
| 5 | Generate preferences | Analysis results | `onboarding_staging_preferences` |
| 6 | Store insights | Analysis results | `onboarding_analysis_insights` |

**Analysis outputs:** category_spend, product_importance (head/mid_tail/long_tail), brand_preferences (forte/moderada/fraca), price_ranges, delivery_patterns.

---

## 3. Onboarding: Staging to Production Commit

```
Flow ID:       PROC-003
Trigger:        GPT-4 calls confirm_and_commit_onboarding(user_confirmed=True)
Source:         onboarding_staging_* tables
Transform:      commit_service.py (11-step atomic commit)
Destination:    All production tables
Conditions:     Staging session exists, user confirmed
Preferences:    Staged preferences are committed with source tracking
```

**11-step commit sequence:**

| Step | Action | Reads | Writes |
|------|--------|-------|--------|
| 1 | Create restaurant | `onboarding_sessions` | `restaurants` |
| 2 | Create person (Telegram link) | `onboarding_sessions` | `restaurant_people` (whatsapp_number = chat_id) |
| 3 | Commit suppliers (fuzzy match existing) | `onboarding_staging_suppliers`, `suppliers` | `suppliers` |
| 4 | Generate embeddings | `onboarding_staging_products` | OpenAI API → in-memory vectors |
| 5 | Commit products | `onboarding_staging_products` | `master_list` (with embedding_vector_v2) |
| 6 | Commit supplier mappings | Staging + step 3/5 mappings | `supplier_mapped_products` |
| 7 | Commit prices | `onboarding_staging_prices` | `pricing_history` (end_date = NULL) |
| 8 | Commit preferences | `onboarding_staging_preferences` | `restaurant_product_preferences` (with source tracking) |
| 9 | Populate preference queue | Top 20% products (by spend) | `preference_collection_queue` |
| 10 | Create engagement profile | — | `engagement_profile` |
| 11 | Mark session committed | — | `onboarding_sessions` (status = "committed") |

**Key detail:** Step 8 writes preference source as `"invoice_extraction"` or `"user_stated"` depending on how each preference was derived.

---

## 4. Product Search (Vector Similarity)

```
Flow ID:       PROC-004
Trigger:        GPT-4 calls search_products(query)
Source:         User query text
Transform:      embeddings.py → product_search.py → Supabase RPC
Destination:    GPT-4 context (tool result)
Conditions:     Restaurant must have products in master_list
Preferences:    None (search is preference-agnostic; GPT-4 applies preferences after)
```

| Step | Action | API/Table |
|------|--------|-----------|
| 1 | Generate embedding | OpenAI `text-embedding-3-small` (1536 dims) |
| 2 | Vector similarity search | Supabase RPC `vector_search(embedding, limit)` |
| 3 | Calculate confidence | Cosine similarity → HIGH (>0.85) / MEDIUM (0.70-0.85) / LOW (<0.70) |
| 4 | Return matches | ProductMatch objects to GPT-4 |

**Fallback:** If RPC doesn't exist, queries `master_list` directly with `is_active = True`.

---

## 5. Price Queries & Validation

```
Flow ID:       PROC-005
Trigger:        GPT-4 calls get_product_prices(product_id) or validate_product_prices(ids)
Source:         pricing_history + supplier_mapped_products + suppliers
Transform:      pricing.py
Destination:    GPT-4 context (tool result)
Conditions:     Product must exist in master_list
Preferences:    GPT-4 system prompt instructs to apply brand/price/quality preferences when ranking
```

**Query structure:**

```
pricing_history
  JOIN supplier_mapped_products ON supplier_mapped_product_id
  JOIN suppliers ON supplier_id
  JOIN master_list ON master_list_id
WHERE master_list_id = product_id
  AND end_date IS NULL (current prices only)
ORDER BY unit_price ASC
```

**Validation checks:** `days_old <= PRICE_FRESHNESS_DAYS` (default 30). Returns fresh/stale classification per product.

---

## 6. Supplier Operations

```
Flow ID:       PROC-006
Trigger:        GPT-4 calls check_supplier(name) or get_suppliers_for_product(id)
Source:         suppliers, supplier_mapped_products
Transform:      suppliers.py
Destination:    GPT-4 context (tool result)
Conditions:     is_active = True filter on all queries
Preferences:    None (raw data; GPT-4 applies restaurant's preferred/blacklisted suppliers)
```

| Tool | Query | Returns |
|------|-------|---------|
| `check_supplier(name)` | `suppliers` WHERE `company_name ILIKE %name%` | exists + details |
| `get_suppliers_for_product(id)` | `supplier_mapped_products` → `suppliers` WHERE `master_list_id` | supplier list |
| `get_all_active_suppliers()` | `suppliers` WHERE `is_active = True` | all suppliers |

---

## 7. Preference Correction Learning

```
Flow ID:       PROC-007
Trigger:        GPT-4 calls save_preference_correction(type, value, reason, context)
Source:         User override during conversation (e.g., "Prefiro Friboi")
Transform:      Restaurant agent tool → preference_drip.py
Destination:    preference_corrections, restaurant_product_preferences, engagement_profile
Conditions:     Restaurant must be linked
Preferences:    Overwrites previous preference; source = "user_correction"
```

| Step | Action | Writes To |
|------|--------|-----------|
| 1 | Find product in master_list | READ `master_list` |
| 2 | Log correction | INSERT `preference_corrections` (audit trail) |
| 3 | Update preference | UPSERT `restaurant_product_preferences` (source = "user_correction") |
| 4 | Update engagement | UPDATE `engagement_profile` (increment total_corrections) |
| 5 | Recalculate score | UPDATE `engagement_profile` (new score/level) |

**Source tracking on write:**

```
brand_preferences_source = "user_correction"
brand_preferences_added_by = person_id
brand_preferences_added_at = NOW()
```

---

## 8. Preference Drip System

```
Flow ID:       PROC-008
Trigger:        Appended to every restaurant agent response (async)
Source:         preference_collection_queue + engagement_profile
Transform:      preference_drip.py → get_drip_questions()
Destination:    Appended text in agent response; queue status updated
Conditions:     Engagement level >= "low"; pending items in queue
Preferences:    Engagement level determines how many questions (0, 1, or 2)
```

### 8a. Question Selection

| Step | Reads | Logic |
|------|-------|-------|
| 1 | `engagement_profile` | Get level + drip_per_session |
| 2 | `preference_collection_queue` | Filter: status IN (pending, asked_drip), importance_tier matches level |
| 3 | `master_list` | Get product name for display |
| 4 | `restaurant_product_preferences` | Check what's already known |

**Engagement → drip mapping:**

| Level | drip_per_session | Tiers queried |
|-------|-----------------|---------------|
| dormant | 0 | — |
| low | 0 | — |
| medium | 1 | head only |
| high | 2 | head + mid_tail |

### 8b. Response Recording

```
Flow ID:       PROC-008b
Trigger:        GPT-4 calls answer_drip_question(product, type, value, skip)
```

| Outcome | Writes |
|---------|--------|
| Answered | `restaurant_product_preferences` (UPSERT), `preference_collection_queue` (status = "answered"), `engagement_profile` (drip_questions_answered++) |
| Skipped | `preference_collection_queue` (status = "skipped", skipped_count++), `engagement_profile` (drip_questions_skipped++) |
| Either | Triggers engagement recalculation (PROC-009) |

---

## 9. Engagement Scoring

```
Flow ID:       PROC-009
Trigger:        After any drip response or preference correction
Source:         engagement_profile counters
Transform:      engagement_scoring.py → recalculate_engagement()
Destination:    engagement_profile (score, level, drip_per_session)
Conditions:     Profile must exist for restaurant
Preferences:    Score determines future drip frequency
```

**Weighted formula:**

```
score = (
  0.15 * depth_signal          +    # onboarding_depth (how many products configured)
  0.30 * drip_response_rate    +    # answered / (answered + skipped)
  0.25 * correction_signal     +    # min(total_corrections / 5, 1.0)
  0.15 * session_frequency     +    # min(sessions_30d / 10, 1.0)
  0.15 * reasoning_signal           # corrections_with_reason / total_corrections
)
```

| Score Range | Level | drip_per_session |
|-------------|-------|-----------------|
| >= 0.65 | high | 2 |
| >= 0.35 | medium | 1 |
| >= 0.10 | low | 0 |
| < 0.10 | dormant | 0 |

---

## 10. Supplier-Facing: Quotation Flow

```
Flow ID:       PROC-010
Trigger:        Supplier asks for pending quotations via Telegram
Source:         supplier_mapped_products + master_list + pricing_history
Transform:      quotation_request.py → get_pending_quotations()
Destination:    GPT-4 context (supplier agent)
Conditions:     Supplier must be linked via whatsapp_number
Preferences:    None
```

**Logic:** For each product this supplier provides (`supplier_mapped_products`), check if there's a current price (`pricing_history WHERE end_date IS NULL`). Products without current prices are returned as pending quotations.

---

## 11. Supplier-Facing: Price Submission

```
Flow ID:       PROC-011
Trigger:        GPT-4 (supplier agent) calls submit_price(product_id, price, unit)
Source:         Supplier input via Telegram
Transform:      price_submission.py
Destination:    pricing_history
Conditions:     Supplier must own the product mapping
Preferences:    None
```

| Step | Action | Table |
|------|--------|-------|
| 1 | Verify supplier owns mapping | READ `supplier_mapped_products` |
| 2 | Close old price | UPDATE `pricing_history` SET `end_date = NOW()` |
| 3 | Insert new price | INSERT `pricing_history` (end_date = NULL, effective_date = NOW()) |

---

## 12. Supplier-Facing: Order Management

```
Flow ID:       PROC-012
Trigger:        Supplier asks for pending orders / confirms / rejects
Source:         purchase_orders
Transform:      order_management.py
Destination:    purchase_orders (status updates)
Conditions:     Order must belong to this supplier
Preferences:    None
```

| Action | Status Change | Fields Updated |
|--------|--------------|----------------|
| View pending | — (read only) | — |
| Confirm | → "confirmed" | supplier_confirmed_at, estimated_delivery_date |
| Reject | → "rejected" | rejection_reason |

---

## 13. Supplier-Facing: Delivery Updates

```
Flow ID:       PROC-013
Trigger:        Supplier updates delivery status
Source:         Supplier input via Telegram
Transform:      delivery_status.py
Destination:    purchase_orders
Conditions:     Order must be in delivery-eligible status
Preferences:    None
```

| Action | Status Options |
|--------|---------------|
| Update status | in_transit, delivered, delayed, issue |
| Report issue | Sets delivery_status = "issue" + issue_report JSON |

---

## 14. Table Read/Write Summary

### Production Tables

| Table | Read By | Written By |
|-------|---------|------------|
| `restaurants` | user_identification (JOIN) | commit_service (step 1) |
| `restaurant_people` | user_identification | commit_service (step 2) |
| `suppliers` | user_identification, supplier tools, commit_service (match) | commit_service (step 3), supplier_registration |
| `master_list` | product_search, pricing, drip questions | commit_service (step 5) |
| `supplier_mapped_products` | pricing, quotation_request | commit_service (step 6) |
| `pricing_history` | pricing, price_submission (close old) | commit_service (step 7), price_submission (new) |
| `restaurant_product_preferences` | drip questions, correction learning | commit_service (step 8), correction learning, drip response |
| `purchase_orders` | order_management, delivery_status | order_management (confirm/reject), delivery_status |

### Staging Tables (Onboarding Only)

| Table | Written By | Read By |
|-------|-----------|---------|
| `onboarding_sessions` | staging_service | commit_service, analysis_service |
| `onboarding_staging_suppliers` | staging_service | analysis_service, commit_service |
| `onboarding_staging_products` | staging_service | analysis_service, commit_service |
| `onboarding_staging_prices` | staging_service | analysis_service, commit_service |
| `onboarding_staging_preferences` | analysis_service, onboarding agent | commit_service |
| `onboarding_invoice_photos` | staging_service | analysis_service |
| `onboarding_analysis_insights` | analysis_service | onboarding agent (display) |

### Shared Preference/Engagement Tables

| Table | Written By | Read By |
|-------|-----------|---------|
| `preference_collection_queue` | commit_service (step 9), drip responses | drip question selection |
| `engagement_profile` | commit_service (step 10), engagement scoring | drip question selection |
| `preference_corrections` | correction learning | — (audit log) |

---

## 15. Preference Lifecycle Map

Each preference field in `restaurant_product_preferences` tracks its own lifecycle:

```
BIRTH (where a preference is created)
├── invoice_extraction    → Analysis detects brand pattern from invoices
├── onboarding           → User states preference during setup
├── user_stated          → User explicitly tells the bot
├── user_correction      → User overrides a recommendation
├── drip                 → User answers a drip question
└── inferred             → System infers from purchase patterns

STORAGE (where it lives)
├── restaurant_product_preferences.brand_preferences         (JSONB)
├── restaurant_product_preferences.price_preference          (JSONB)
├── restaurant_product_preferences.quality_preference        (JSONB)
├── restaurant_product_preferences.specification_preferences (JSONB)
├── restaurant_product_preferences.payment_preference        (JSONB)
│
├── Each field has companion columns:
│   ├── *_source       → Where it came from
│   ├── *_added_by     → FK to restaurant_people
│   └── *_added_at     → Timestamp

APPLICATION (where preferences influence output)
├── Product search ranking    → GPT-4 system prompt instructs preference application
├── Supplier recommendation   → Preferred/blacklisted suppliers filter results
├── Price validation          → Max price thresholds flag expensive options
└── Order creation            → All preferences applied to final recommendation

EVOLUTION (how preferences change)
├── User correction          → Replaces with source="user_correction"
├── Drip question answer     → Fills in missing preference, source="drip"
├── Invoice re-extraction    → May update inferred preferences
└── Priority: user_correction > user_stated > drip > invoice_extraction > inferred
```

---

## 16. Critical Dependencies & Flow Gates

### Gate 1: Onboarding Must Complete Before Main Agent

```
Blocker:   restaurants.onboarding_completed_at IS NULL
Effect:    User stuck in onboarding subagent
Requires:  PROC-003 (commit) must succeed
```

### Gate 2: master_list Must Have Products Before Search Works

```
Blocker:   master_list empty for restaurant
Effect:    search_products returns nothing
Requires:  PROC-003 step 5 (commit products)
```

### Gate 3: Engagement Profile Required for Drip Questions

```
Blocker:   No engagement_profile row for restaurant
Effect:    No drip questions appended to responses
Requires:  PROC-003 step 10 (create engagement profile)
```

### Gate 4: Supplier Mapping Required Before Price Submission

```
Blocker:   No supplier_mapped_products for supplier+product
Effect:    Supplier cannot submit prices
Requires:  PROC-003 step 6 (commit supplier mappings) or manual creation
```

### Gate 5: Current Prices Required for Purchase Recommendations

```
Blocker:   pricing_history.end_date IS NOT NULL (all expired)
Effect:    validate_product_prices flags as stale
Requires:  PROC-003 step 7 (initial prices) or PROC-011 (supplier submission)
```
