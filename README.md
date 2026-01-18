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
│                      FREPI AGENT (GPT-4)                                │
│                                                                         │
│  • System prompt with Portuguese instructions                           │
│  • 4-option menu navigation                                             │
│  • Function calling for tool execution                                  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
   │   Product   │   │   Pricing   │   │  Supplier   │
   │   Search    │   │   Tools     │   │   Tools     │
   │             │   │             │   │             │
   │ • Vector    │   │ • Get       │   │ • Check     │
   │   search    │   │   prices    │   │   exists    │
   │ • Embedding │   │ • Validate  │   │ • Search    │
   │   matching  │   │   freshness │   │ • Get by    │
   │             │   │ • Best      │   │   product   │
   │             │   │   price     │   │             │
   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
          │                 │                  │
          └─────────────────┼──────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SUPABASE (PostgreSQL + pgvector)                     │
│                                                                         │
│  Tables: master_list, supplier_mapped_products, pricing_history,        │
│          suppliers, restaurants, restaurant_product_preferences         │
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
│   ├── main.py                    # CLI entry point
│   ├── agent.py                   # GPT-4 agent with function calling
│   ├── config.py                  # Environment configuration
│   ├── prompts/
│   │   └── customer_agent.py      # Portuguese system prompt
│   ├── tools/
│   │   ├── supabase_client.py     # Database connection
│   │   ├── embeddings.py          # OpenAI embeddings
│   │   ├── product_search.py      # Vector similarity search
│   │   ├── pricing.py             # Price queries & validation
│   │   └── suppliers.py           # Supplier operations
│   └── integrations/
│       └── telegram_bot.py        # Telegram bot handler
│
├── tests/
│   ├── test_matrix.yaml           # 13 test cases (YAML)
│   ├── test_agent.py              # Parametrized test runner
│   ├── conftest.py                # Fixtures and mocks
│   ├── helpers/
│   │   ├── test_loader.py         # YAML parser
│   │   ├── assertions.py          # Custom assertions
│   │   └── report_generator.py    # HTML/JSON reports
│   └── fixtures/
│       ├── sample_products.json
│       ├── sample_suppliers.json
│       └── sample_prices.json
│
├── deploy/
│   ├── setup.sh                   # GCP VM setup script
│   ├── frepi-agent.service        # systemd service file
│   └── GCP_DEPLOYMENT.md          # Deployment guide
│
├── pyproject.toml
├── requirements.txt
└── .env                           # Environment variables (not committed)
```

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
| `master_list` | Product catalog with embeddings |
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
