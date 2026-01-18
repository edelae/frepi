"""Pytest configuration and fixtures for Frepi Agent tests."""

import json
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

# Load fixture data
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_products():
    """Load sample product data."""
    with open(FIXTURES_DIR / "sample_products.json") as f:
        return json.load(f)


@pytest.fixture
def sample_suppliers():
    """Load sample supplier data."""
    with open(FIXTURES_DIR / "sample_suppliers.json") as f:
        return json.load(f)


@pytest.fixture
def sample_prices():
    """Load sample pricing data."""
    with open(FIXTURES_DIR / "sample_prices.json") as f:
        return json.load(f)


@dataclass
class MockToolTracker:
    """Tracks tool calls during test execution."""
    calls: list = field(default_factory=list)

    def record_call(self, tool_name: str, args: dict):
        """Record a tool call."""
        self.calls.append({"name": tool_name, "args": args})

    def get_calls(self, tool_name: str = None):
        """Get all calls or filter by tool name."""
        if tool_name:
            return [c for c in self.calls if c["name"] == tool_name]
        return self.calls

    def reset(self):
        """Clear recorded calls."""
        self.calls = []


@pytest.fixture
def tool_tracker():
    """Create a tool call tracker."""
    return MockToolTracker()


@pytest.fixture
def mock_search_result(sample_products):
    """Create a mock search result from fixture data."""
    from frepi_agent.tools.product_search import SearchResult, ProductMatch

    products = sample_products[:2]  # Get first two products (picanhas)
    matches = [
        ProductMatch(
            id=p["id"],
            product_name=p["product_name"],
            brand=p["brand"],
            specifications=p["specifications"],
            similarity=0.92 - (i * 0.04),  # 0.92, 0.88
            confidence="HIGH" if i == 0 else "HIGH",
        )
        for i, p in enumerate(products)
    ]

    return SearchResult(
        query="picanha",
        matches=matches,
        has_high_confidence=True,
        best_match=matches[0] if matches else None,
    )


@pytest.fixture
def mock_price_info(sample_prices):
    """Create mock price info from fixture data."""
    from frepi_agent.tools.pricing import PriceInfo

    prices_for_product_1 = [p for p in sample_prices if p["product_id"] == 1]

    return [
        PriceInfo(
            product_id=p["product_id"],
            product_name=p["product_name"],
            supplier_id=p["supplier_id"],
            supplier_name=p["supplier_name"],
            unit_price=p["unit_price"],
            unit=p["unit"],
            effective_date=datetime.strptime(p["effective_date"], "%Y-%m-%d"),
            days_old=p["days_old"],
            is_fresh=p["is_fresh"],
        )
        for p in prices_for_product_1
    ]


@pytest.fixture
def mock_supplier(sample_suppliers):
    """Create a mock supplier from fixture data."""
    from frepi_agent.tools.suppliers import Supplier

    s = sample_suppliers[0]
    return Supplier(
        id=s["id"],
        company_name=s["company_name"],
        contact_person=s["contact_person"],
        phone=s["phone"],
        email=s["email"],
        cnpj=s["cnpj"],
        address=s["address"],
        is_active=s["is_active"],
        reliability_score=s["reliability_score"],
        response_time_avg=s["response_time_avg"],
    )


def create_mock_gpt4_response(content: str, tool_calls: Optional[list] = None):
    """Create a mock GPT-4 response object."""
    mock_message = MagicMock()
    mock_message.content = content
    mock_message.tool_calls = tool_calls

    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_choice.finish_reason = "stop" if not tool_calls else "tool_calls"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def create_mock_tool_call(call_id: str, name: str, arguments: dict):
    """Create a mock tool call object."""
    mock_function = MagicMock()
    mock_function.name = name
    mock_function.arguments = json.dumps(arguments)

    mock_tool_call = MagicMock()
    mock_tool_call.id = call_id
    mock_tool_call.function = mock_function
    return mock_tool_call


@pytest.fixture
def default_menu_response():
    """Default Portuguese menu response."""
    return """Olá! 👋 Bem-vindo ao Frepi, seu assistente de compras!

Como posso ajudar você hoje?

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências

Digite o número da opção desejada ou me conte o que você precisa! 🛒"""


@pytest.fixture
def price_check_response():
    """Sample price check response."""
    return """Encontrei preços para Picanha! 🥩

**Melhores opções:**

✅ **Friboi Direto** - R$ 41,90/kg
   • Melhor preço disponível
   • Alta confiabilidade (97%)
   • Entrega em 1-2 dias

📦 **Frigorífico Central** - R$ 43,50/kg
   • Seu fornecedor frequente
   • Confiabilidade 95%

💰 Para 10kg de picanha:
• Friboi Direto: R$ 419,00
• Frigorífico Central: R$ 435,00

Quer que eu prepare o pedido? 🛒

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências"""


@pytest.fixture
def no_price_response():
    """Response when no pricing available."""
    return """⚠️ Não encontrei preços atualizados para este produto.

Os fornecedores cadastrados não têm cotação recente para este item.

O que você gostaria de fazer?
• Posso contatar os fornecedores para solicitar cotação
• Você pode informar um preço que conhece
• Podemos tentar um produto similar

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências"""


@pytest.fixture
def supplier_not_found_response():
    """Response when supplier not registered."""
    return """⚠️ O fornecedor "NovoBrasil" não está cadastrado no sistema.

Quer cadastrar este fornecedor agora? Vou precisar de:
• Nome da empresa
• Telefone de contato
• CNPJ (opcional)

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências"""


# Pytest hooks for report generation
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "high: high priority tests")
    config.addinivalue_line("markers", "medium: medium priority tests")
    config.addinivalue_line("markers", "low: low priority tests")
    config.addinivalue_line("markers", "group_a: onboarding tests")
    config.addinivalue_line("markers", "group_b: pre-purchase tests")
    config.addinivalue_line("markers", "group_c: core purchasing tests")
    config.addinivalue_line("markers", "group_d: post-purchase tests")
    config.addinivalue_line("markers", "group_e: management tests")
    config.addinivalue_line("markers", "group_f: error handling tests")
    config.addinivalue_line("markers", "critical: critical priority tests")
