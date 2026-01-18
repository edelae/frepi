# Frepi Agent

AI-powered restaurant purchasing assistant for Brazilian restaurants. Processes natural language requests via Telegram to help restaurants compare prices, manage suppliers, and optimize purchasing decisions.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM BOT                                     │
│                    (python-telegram-bot)                                 │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              RESTAURANT FACING AGENT (Main Orchestrator - GPT-4)        │
│                                                                         │
│  • Routes conversations to specialized subagents                        │
│  • Maintains conversation context and state                             │
│  • Handles 4-option menu navigation                                     │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
      ┌──────────────────────┼──────────────────────┐
      │                      │                      │
      ▼                      ▼                      ▼
┌───────────────┐   ┌─────────────────┐   ┌──────────────────┐
│  ONBOARDING   │   │ SUPPLIER PRICE  │   │ PURCHASE ORDER   │
│   SUBAGENT    │   │    UPDATER      │   │    SUBAGENTS     │
│               │   │                 │   │                  │
│ • New user    │   │ • Verify        │   │ • ORDER CREATOR  │
│   registration│   │   supplier      │   │   - Product      │
│ • Invoice     │   │ • Collect       │   │     search       │
│   parsing     │   │   prices        │   │   - Price        │
│ • Preference  │   │ • Update        │   │     comparison   │
│   collection  │   │   history       │   │   - Order        │
│               │   │                 │   │     creation     │
│ Tools:        │   │ Tools:          │   │                  │
│ • image_parser│   │ • check_supplier│   │ • ORDER FOLLOWUP │
│ • product_pref│   │ • update_price  │   │   - Status track │
│ • supplier_reg│   │                 │   │   - History      │
└───────────────┘   └─────────────────┘   └──────────────────┘
      │                      │                      │
      └──────────────────────┼──────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     SHARED TOOLS (Database Layer)                       │
│                                                                         │
│  • product_search (vector similarity with embeddings)                   │
│  • pricing (price queries, validation, best price)                      │
│  • suppliers (supplier operations and lookups)                          │
│  • embeddings (OpenAI text-embedding-3-small)                           │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SUPABASE (PostgreSQL + pgvector)                     │
│                                                                         │
│  Tables: master_list, supplier_mapped_products, pricing_history,        │
│          suppliers, restaurants, restaurant_product_preferences,        │
│          telegram_users, restaurant_people                              │
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
│   ├── restaurant_facing_agent/       # Main customer-facing agent
│   │   ├── __init__.py
│   │   ├── agent.py                   # GPT-4 agent with function calling
│   │   ├── prompts/
│   │   │   └── customer_agent.py      # Portuguese system prompt
│   │   │
│   │   ├── subagents/                 # Specialized sub-agents
│   │   │   ├── onboarding_subagent/   # New user registration
│   │   │   │   ├── __init__.py
│   │   │   │   ├── agent.py
│   │   │   │   └── tools/
│   │   │   │       ├── image_parser.py        # GPT-4 Vision invoice parsing
│   │   │   │       ├── product_preference.py  # Preference collection
│   │   │   │       └── supplier_registration.py
│   │   │   │
│   │   │   ├── supplier_price_updater/    # Price update flow
│   │   │   │   ├── __init__.py
│   │   │   │   └── agent.py
│   │   │   │
│   │   │   ├── purchase_order_creator/    # Order creation flow
│   │   │   │   ├── __init__.py
│   │   │   │   └── agent.py
│   │   │   │
│   │   │   └── purchase_order_followup/   # Order tracking
│   │   │       ├── __init__.py
│   │   │       └── agent.py
│   │   │
│   │   └── tools/                     # Shared tools for main agent
│   │       ├── supabase_client.py     # Database connection
│   │       ├── embeddings.py          # OpenAI embeddings
│   │       ├── product_search.py      # Vector similarity search
│   │       ├── pricing.py             # Price queries & validation
│   │       └── suppliers.py           # Supplier operations
│   │
│   └── integrations/
│       └── telegram_bot.py            # Telegram bot handler
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
