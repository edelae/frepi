# Frepi Agent

AI-powered restaurant purchasing assistant for Brazilian restaurants. Processes natural language requests via Telegram to help restaurants compare prices, manage suppliers, and optimize purchasing decisions.

**Key Innovation**: A single Telegram number serves BOTH restaurants AND suppliers, with intelligent routing based on user identification.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM BOT                                     │
│                    (python-telegram-bot)                                 │
│                                                                         │
│         Single number serves BOTH restaurants AND suppliers             │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      MESSAGE ROUTER                                      │
│                 (shared/user_identification.py)                         │
│                                                                         │
│  1. Check restaurant_people by telegram_chat_id → Restaurant Agent      │
│  2. Check suppliers by telegram_chat_id → Supplier Agent                │
│  3. Unknown → Ask: "Are you a restaurant (1) or supplier (2)?"          │
└──────────┬─────────────────────────────────────────┬────────────────────┘
           │                                         │
           ▼                                         ▼
┌──────────────────────────────┐     ┌──────────────────────────────┐
│  RESTAURANT FACING AGENT     │     │   SUPPLIER FACING AGENT      │
│                              │     │                              │
│  4 Menu Options:             │     │  4 Menu Options:             │
│  1️⃣ Fazer uma compra         │     │  1️⃣ Ver cotações pendentes   │
│  2️⃣ Atualizar preços         │     │  2️⃣ Enviar cotação           │
│  3️⃣ Registrar fornecedor     │     │  3️⃣ Confirmar pedido         │
│  4️⃣ Configurar preferências  │     │  4️⃣ Atualizar entrega        │
│                              │     │                              │
│  Subagents:                  │     │  Subagents:                  │
│  • Onboarding                │     │  • Supplier Onboarding       │
│  • Price Updater             │     │  • Quotation                 │
│  • Order Creator             │     │  • Order Confirmation        │
│  • Order Followup            │     │  • Delivery Update           │
└──────────────┬───────────────┘     └──────────────┬───────────────┘
               │                                    │
               └────────────────┬───────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     SHARED INFRASTRUCTURE                                │
│                     (frepi_agent/shared/)                               │
│                                                                         │
│  • supabase_client.py - Database connection (single source of truth)    │
│  • user_identification.py - User type detection and routing             │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SUPABASE (PostgreSQL + pgvector)                     │
│                                                                         │
│  Tables: master_list, supplier_mapped_products, pricing_history,        │
│          suppliers, restaurants, restaurant_product_preferences,        │
│          purchase_orders, restaurant_people                             │
└─────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| **AI Agent** | OpenAI GPT-4 with function calling |
| **Embeddings** | OpenAI text-embedding-3-small (1536 dims) |
| **Database** | Supabase PostgreSQL + pgvector |
| **Messaging** | Telegram Bot API (python-telegram-bot) |
| **CLI** | Click + Rich |
| **Language** | Python 3.10+ |
| **Deployment** | GCP Compute Engine (systemd service) |

## Project Structure

```
frepi-agent/
├── frepi_agent/
│   ├── __init__.py
│   ├── main.py                        # CLI entry point
│   ├── config.py                      # Environment configuration
│   │
│   ├── shared/                        # Shared utilities for all agents
│   │   ├── __init__.py
│   │   ├── supabase_client.py         # Database connection (single source)
│   │   └── user_identification.py     # User type detection & routing
│   │
│   ├── restaurant_facing_agent/       # Customer-facing agent
│   │   ├── __init__.py
│   │   ├── agent.py                   # GPT-4 agent with function calling
│   │   ├── prompts/
│   │   │   └── customer_agent.py      # Portuguese system prompt
│   │   │
│   │   ├── subagents/                 # Specialized sub-agents
│   │   │   ├── onboarding_subagent/   # New user registration
│   │   │   │   ├── agent.py
│   │   │   │   └── tools/
│   │   │   │       ├── image_parser.py        # GPT-4 Vision invoice parsing
│   │   │   │       ├── product_preference.py  # Preference collection
│   │   │   │       └── supplier_registration.py
│   │   │   │
│   │   │   ├── supplier_price_updater/    # Price update flow
│   │   │   ├── purchase_order_creator/    # Order creation flow
│   │   │   └── purchase_order_followup/   # Order tracking
│   │   │
│   │   └── tools/                     # Restaurant agent tools
│   │       ├── supabase_client.py     # Re-exports from shared/
│   │       ├── embeddings.py          # OpenAI embeddings
│   │       ├── product_search.py      # Vector similarity search
│   │       ├── pricing.py             # Price queries & validation
│   │       └── suppliers.py           # Supplier operations
│   │
│   ├── supplier_facing_agent/         # Supplier-facing agent (NEW)
│   │   ├── __init__.py
│   │   ├── agent.py                   # GPT-4 agent with function calling
│   │   ├── prompts/
│   │   │   └── supplier_agent.py      # Portuguese system prompt
│   │   │
│   │   ├── subagents/                 # Specialized sub-agents
│   │   │   ├── supplier_onboarding/   # New supplier registration
│   │   │   ├── quotation_subagent/    # Quotation handling
│   │   │   ├── order_confirmation/    # Order confirmation
│   │   │   └── delivery_update/       # Delivery tracking
│   │   │
│   │   └── tools/                     # Supplier agent tools
│   │       ├── quotation_request.py   # Pending quotations
│   │       ├── price_submission.py    # Submit prices
│   │       ├── order_management.py    # Confirm/reject orders
│   │       └── delivery_status.py     # Update deliveries
│   │
│   └── integrations/
│       └── telegram_bot.py            # Telegram bot with routing logic
│
├── docs/
│   └── UX_GUIDE.md                    # User experience documentation
│
├── tests/
│   ├── test_matrix.yaml               # Test cases (YAML)
│   ├── test_agent.py                  # Parametrized test runner
│   ├── conftest.py                    # Fixtures and mocks
│   ├── helpers/
│   │   ├── test_loader.py             # YAML parser
│   │   ├── assertions.py              # Custom assertions
│   │   └── report_generator.py        # HTML/JSON reports
│   └── fixtures/
│       ├── sample_products.json
│       ├── sample_suppliers.json
│       └── sample_prices.json
│
├── deploy/
│   ├── setup.sh                       # GCP VM setup script
│   ├── frepi-agent.service            # systemd service file
│   └── GCP_DEPLOYMENT.md              # Deployment guide
│
├── pyproject.toml
├── requirements.txt
└── .env                               # Environment variables (not committed)
```

### Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TELEGRAM BOT (Entry Point)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              RESTAURANT FACING AGENT (Main Orchestrator)         │
│                                                                  │
│  • Routes conversations to appropriate subagent                  │
│  • Maintains conversation context                                │
│  • Handles 4-option menu navigation                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   ONBOARDING    │ │  PRICE UPDATER  │ │ PURCHASE ORDER  │
│    SUBAGENT     │ │    SUBAGENT     │ │    SUBAGENT     │
│                 │ │                 │ │                 │
│ • New user reg  │ │ • Supplier      │ │ • Order creation│
│ • Invoice parse │ │   price updates │ │ • Order followup│
│ • Preferences   │ │ • Price history │ │ • Status track  │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 SHARED TOOLS (Database Layer)                    │
│                                                                  │
│  • product_search (vector similarity)                            │
│  • pricing (price queries & validation)                          │
│  • suppliers (supplier operations)                               │
│  • embeddings (OpenAI text-embedding-3-small)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 SUPABASE (PostgreSQL + pgvector)                 │
└─────────────────────────────────────────────────────────────────┘
```

## Subagent System

The main Restaurant Facing Agent orchestrates **4 specialized subagents**, each responsible for a specific domain of functionality.

### Menu → Subagent Mapping

| Menu Option | Subagent | Trigger |
|-------------|----------|---------|
| (New user detected) | Onboarding Subagent | Automatic |
| 1️⃣ Fazer uma compra | Purchase Order Creator | User selection |
| 2️⃣ Atualizar preços | Supplier Price Updater | User selection |
| 3️⃣ Registrar fornecedor | Onboarding Subagent | User selection |
| 4️⃣ Configurar preferências | Onboarding Subagent | User selection |
| (After order created) | Purchase Order Followup | Automatic |

### 1. Onboarding Subagent

**Location**: `frepi_agent/restaurant_facing_agent/subagents/onboarding_subagent/`

**Trigger**: New user detected (`telegram_chat_id` not in database) OR menu options 3️⃣, 4️⃣

**Responsibilities**:
- User registration (restaurant or supplier)
- Invoice photo parsing with GPT-4 Vision
- Product preference collection (top 10 products)
- Supplier auto-registration from invoices

**Tools**:
| Tool | File | Purpose |
|------|------|---------|
| `image_parser` | `tools/image_parser.py` | GPT-4 Vision invoice parsing |
| `product_preference` | `tools/product_preference.py` | Preference collection & storage |
| `supplier_registration` | `tools/supplier_registration.py` | New supplier creation |

### 2. Supplier Price Updater Subagent

**Location**: `frepi_agent/restaurant_facing_agent/subagents/supplier_price_updater/`

**Trigger**: Menu option 2️⃣ or user mentions price update

**Responsibilities**:
- Verify supplier exists in system
- Collect price updates from user/supplier
- Validate and store in `pricing_history`
- Track price freshness

**Tools**:
| Tool | Purpose |
|------|---------|
| `check_supplier` | Verify supplier exists |
| `update_price` | Insert/update pricing_history |

### 3. Purchase Order Creator Subagent

**Location**: `frepi_agent/restaurant_facing_agent/subagents/purchase_order_creator/`

**Trigger**: Menu option 1️⃣ or user wants to buy

**Responsibilities**:
- Product search and semantic matching
- Price comparison across suppliers
- Order creation and confirmation
- Price validation before order acceptance

**Tools** (uses shared tools):
| Tool | Purpose |
|------|---------|
| `search_products` | Vector similarity search |
| `get_product_prices` | Get prices by supplier |
| `validate_product_prices` | Check price freshness |
| `get_suppliers_for_product` | List available suppliers |

### 4. Purchase Order Followup Subagent

**Location**: `frepi_agent/restaurant_facing_agent/subagents/purchase_order_followup/`

**Trigger**: After order creation or user asks about order status

**Responsibilities**:
- Order status tracking
- Delivery updates
- Order history retrieval

**Tools**:
| Tool | Purpose |
|------|---------|
| `get_order_status` | Current order status |
| `get_order_history` | Past orders list |

---

## Supplier Facing Agent

The Supplier Facing Agent handles all interactions with suppliers who contact the same Telegram number. It enables suppliers to respond to quotation requests, confirm orders, and update delivery statuses.

### Supplier Menu → Subagent Mapping

| Menu Option | Subagent | Trigger |
|-------------|----------|---------|
| (New supplier detected) | Supplier Onboarding | Automatic |
| 1️⃣ Ver cotações pendentes | Quotation Subagent | User selection |
| 2️⃣ Enviar cotação | Quotation Subagent | User selection |
| 3️⃣ Confirmar pedido | Order Confirmation | User selection |
| 4️⃣ Atualizar entrega | Delivery Update | User selection |

### 1. Supplier Onboarding Subagent

**Location**: `frepi_agent/supplier_facing_agent/subagents/supplier_onboarding/`

**Trigger**: New supplier detected (`telegram_chat_id` not in `suppliers` table)

**Responsibilities**:
- Collect company information (name, CNPJ, contact)
- Register new supplier in database
- Link to existing restaurant relationships

**Tools**:
| Tool | Purpose |
|------|---------|
| `check_supplier_exists` | Verify if supplier already registered |
| `register_supplier` | Create new supplier record |

### 2. Quotation Subagent

**Location**: `frepi_agent/supplier_facing_agent/subagents/quotation_subagent/`

**Trigger**: Menu options 1️⃣ or 2️⃣, or supplier mentions prices

**Responsibilities**:
- Show pending quotation requests from restaurants
- Accept price submissions for products
- Validate and store prices in `pricing_history`

**Tools**:
| Tool | File | Purpose |
|------|------|---------|
| `get_pending_quotations` | `tools/quotation_request.py` | List products awaiting price |
| `submit_price` | `tools/price_submission.py` | Record a price quotation |
| `search_product_to_quote` | `tools/price_submission.py` | Find product to submit price |

### 3. Order Confirmation Subagent

**Location**: `frepi_agent/supplier_facing_agent/subagents/order_confirmation/`

**Trigger**: Menu option 3️⃣ or supplier mentions order

**Responsibilities**:
- Show pending orders awaiting supplier confirmation
- Accept/reject orders with delivery estimates
- Update order status in database

**Tools**:
| Tool | File | Purpose |
|------|------|---------|
| `get_pending_orders` | `tools/order_management.py` | List orders awaiting confirmation |
| `confirm_order` | `tools/order_management.py` | Accept order with delivery date |
| `reject_order` | `tools/order_management.py` | Decline order with reason |

### 4. Delivery Update Subagent

**Location**: `frepi_agent/supplier_facing_agent/subagents/delivery_update/`

**Trigger**: Menu option 4️⃣ or supplier mentions delivery

**Responsibilities**:
- Track active deliveries in progress
- Update delivery status (preparing, in transit, delivered)
- Report delivery issues or delays

**Tools**:
| Tool | File | Purpose |
|------|------|---------|
| `get_active_deliveries` | `tools/delivery_status.py` | List deliveries in progress |
| `update_delivery_status` | `tools/delivery_status.py` | Update status (preparing/in_transit/delivered/delayed) |
| `report_delivery_issue` | `tools/delivery_status.py` | Log problems with delivery |

### Supplier Agent Tools Summary

| Tool | Module | Description |
|------|--------|-------------|
| `get_pending_quotations` | quotation_request | Get products awaiting pricing from this supplier |
| `get_quotation_details` | quotation_request | Get details of a specific quotation request |
| `submit_price` | price_submission | Submit a price for a product |
| `search_product_to_quote` | price_submission | Search for product to quote by name |
| `get_pending_orders` | order_management | List orders awaiting supplier confirmation |
| `confirm_order` | order_management | Confirm order with delivery estimate |
| `reject_order` | order_management | Reject order with reason |
| `get_active_deliveries` | delivery_status | List deliveries in progress |
| `update_delivery_status` | delivery_status | Update delivery status |
| `report_delivery_issue` | delivery_status | Report delivery problem |

---

## Quick Start

### Local Development

```bash
# Clone and setup
cd frepi-agent
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Test connection
frepi test

# Interactive CLI chat
frepi chat-cli

# Run Telegram bot
frepi telegram
```

### Environment Variables

```bash
# .env
OPENAI_API_KEY=sk-...              # Required: GPT-4 and embeddings
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...                # Service role key
TELEGRAM_BOT_TOKEN=123456:ABC...   # From @BotFather

# Optional
CHAT_MODEL=gpt-4o                  # Default: gpt-4o
ENVIRONMENT=development
LOG_LEVEL=INFO
```

## Testing

The testing framework uses a YAML-based test matrix that validates bot responses.

```bash
# Run all tests
pytest tests/test_agent.py -v

# Run specific group
pytest tests/test_agent.py -k "TestGroupA"

# Run high priority tests
pytest tests/test_agent.py -k "TestHighPriority"

# Generate HTML report
pytest tests/test_agent.py --html=tests/reports/report.html
```

### Test Matrix Groups

| Group | Description | Test Cases |
|-------|-------------|------------|
| A | Onboarding | A001 (greeting), A002 (price update) |
| B | Pre-Purchase | B001 (price check), B002 (purchase flow) |
| C | Core Purchasing | C001 (low confidence), C002 (abnormal price) |
| D | Post-Purchase | D001 (tracking), D002 (history) |
| E | Management | E001 (preferences), E002 (supplier registration) |
| F | Error Handling | F001 (no pricing), F002 (unknown supplier), F003 (help) |

### Adding New Test Cases

Add to `tests/test_matrix.yaml`:

```yaml
- id: "A003"
  name: "New test case"
  group: "A"
  priority: "high"
  conversation:
    - turn: 1
      user_message: "Test input"
      expected:
        contains_any: ["expected", "terms"]
        language: "pt-BR"
```

## Deployment

### Current Status

- **VM**: `frepi-agent-vm` on GCP (southamerica-east1-c)
- **IP**: 34.39.166.178
- **Service**: systemd (`frepi-agent.service`)
- **Project**: trax-report-automation (renamed to "Frepi")

### Useful Commands

```bash
# SSH to VM
gcloud compute ssh frepi-agent-vm --zone=southamerica-east1-c

# Check service status
sudo systemctl status frepi-agent

# View logs
sudo journalctl -u frepi-agent -f

# Restart service
sudo systemctl restart frepi-agent
```

### Deploy Updates

```bash
# From local machine
cd frepi-agent
zip -r frepi-agent.zip frepi_agent scripts deploy requirements.txt

# Upload to VM
gcloud compute scp frepi-agent.zip frepi-agent-vm:~ --zone=southamerica-east1-c

# On VM
unzip -o frepi-agent.zip
sudo cp -r frepi_agent /opt/frepi-agent/
sudo systemctl restart frepi-agent
```

## Key Features

### 4-Option Menu (Always Displayed)

```
1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências
```

### Product Matching

- Uses OpenAI embeddings + pgvector for semantic search
- Confidence levels: HIGH (>0.85), MEDIUM (0.70-0.85), LOW (<0.70)
- Returns top 4 matches with similarity scores

### Price Validation

- Never accepts orders without price validation
- Warns if prices are >30 days old
- Shows specific supplier names (not generic "os fornecedores")

## Database Schema

| Table | Purpose |
|-------|---------|
| `master_list` | Restaurant's product list with embeddings, preferences, and specifications |
| `supplier_mapped_products` | SKU mappings to master list |
| `pricing_history` | Historical prices with validity |
| `suppliers` | Supplier profiles and metrics |
| `restaurants` | Customer profiles |
| `restaurant_product_preferences` | Learned preferences |

## Related Documentation

- **PRD**: See the detailed Product Requirements Document in the repo
- **CLAUDE.md**: Project context and development guidelines
- **GCP_DEPLOYMENT.md**: Step-by-step deployment guide

## API Keys Required

1. **OpenAI**: For GPT-4 chat and embeddings
2. **Supabase**: For database access
3. **Telegram**: For bot integration

## Common Issues

### Telegram Token Conflict

If you see "409 Conflict" errors, another service is using the same bot token.
- Stop other services (n8n workflows)
- Or create a new bot with @BotFather

### Price Not Found

Products need entries in `pricing_history` with `end_date IS NULL`.
Check freshness threshold in config (default: 30 days).

---

*Built for Brazilian restaurant procurement optimization*
*Language: Portuguese (BR) with emoji-enhanced responses*
