"""
Main test runner for Frepi Agent tests.

Loads test cases from YAML matrix and executes them programmatically.
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers.test_loader import (
    load_test_matrix,
    TestCase,
    TestMatrix,
    ConversationTurn,
)
from tests.helpers.assertions import FrepiAssertions, AssertionResult


# Load test matrix
TEST_MATRIX = load_test_matrix()


class TestAgentFromMatrix:
    """Test class that runs tests from the YAML test matrix."""

    def get_mock_response_for_test(self, test_case: TestCase, turn: int) -> str:
        """Get appropriate mock response based on test case."""
        test_id = test_case.id

        # Default menu response
        default_menu = """Olá! 👋 Bem-vindo ao Frepi, seu assistente de compras!

Como posso ajudar você hoje?

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências

Digite o número da opção desejada ou me conte o que você precisa! 🛒"""

        # Response mapping based on test ID
        responses = {
            "A001": default_menu,
            "A002": """Vou verificar o fornecedor Marfrig no sistema.

✅ Fornecedor encontrado: **Marfrig Distribuidora**

Para atualizar os preços, me informe os produtos e valores.
Exemplo: "Picanha R$ 45,00/kg, Alcatra R$ 38,00/kg"

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "B001": """Encontrei preços para Picanha! 🥩

**Melhores opções:**

✅ **Friboi Direto** - R$ 41,90/kg
   • Melhor preço disponível
   • Alta confiabilidade (97%)

📦 **Frigorífico Central** - R$ 43,50/kg
   • Seu fornecedor frequente

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "B002_turn1": """Encontrei a picanha! 🥩

**Para 10kg de Picanha Friboi Premium:**

✅ **Friboi Direto** - R$ 41,90/kg = **R$ 419,00 total**
   • Melhor preço disponível
   • Confiabilidade 97%

📦 **Frigorífico Central** - R$ 43,50/kg = **R$ 435,00 total**
   • Fornecedor frequente

Confirma o pedido com Friboi Direto por R$ 419,00?

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "B002_turn2": """✅ Pedido confirmado!

**Resumo do pedido:**
• Produto: Picanha Friboi Premium
• Quantidade: 10kg
• Fornecedor: Friboi Direto
• Total: R$ 419,00

O pedido foi recebido e será processado.

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "C001": """⚠️ Não encontrei "hambúrguer de soja vegano" no catálogo.

Produtos similares encontrados:
• Hambúrguer Bovino (32% similar)

Você pode:
• Cadastrar este produto como novo item
• Escolher um produto similar

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "C002": """⚠️ Atenção ao preço!

**Filé Mignon** - R$ 150,00/kg está acima do normal.
Preço médio histórico: R$ 89,90/kg

Para 5kg: R$ 750,00 total

Deseja continuar mesmo assim?

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "D001": """📦 Status do seu último pedido:

**Pedido #1234**
• Status: Em separação
• Previsão de entrega: Amanhã, 14h-18h
• Fornecedor: Friboi Direto

Posso ajudar com mais alguma coisa?

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "D002": """📋 Seu histórico de compras:

**Últimos pedidos:**
• 10/01 - Picanha 10kg - R$ 419,00 (Friboi Direto)
• 05/01 - Arroz 20kg - R$ 114,00 (Grãos SP)
• 02/01 - Frango 15kg - R$ 193,50 (Atacadão)

**Total do mês:** R$ 726,50

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "E001": """⚙️ Configuração de Preferências

Você pode configurar:
• **Fornecedores preferidos** - Priorizar certos fornecedores
• **Limites de preço** - Alertas para produtos específicos
• **Qualidade** - Preferir marcas premium ou padrão

O que você gostaria de configurar?

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "E002_turn1": """📝 Vamos cadastrar o novo fornecedor!

Por favor, me informe:
• Nome da empresa
• Telefone de contato
• CNPJ (opcional)
• Produtos que fornece

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "E002_turn2": """✅ Fornecedor cadastrado com sucesso!

**Frigorífico Sul**
• Telefone: 11999887766
• Status: Ativo

Agora você pode receber cotações deste fornecedor.

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "F001": """⚠️ Não encontrei preços atualizados para "camarão fresco".

Nenhum fornecedor cadastrado tem cotação recente.

Você pode:
• Contatar fornecedores para solicitar cotação
• Informar um preço que você conhece
• Buscar produto similar

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "F002": """⚠️ Fornecedor "NovoBrasil" não está cadastrado no sistema.

Quer cadastrar este fornecedor agora?

Vou precisar de:
• Nome completo da empresa
• Telefone de contato
• CNPJ (opcional)

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
            "F003": """Posso ajudar você com:

🛒 **Compras** - Encontrar produtos, comparar preços, fazer pedidos
💰 **Preços** - Atualizar cotações de fornecedores
📦 **Fornecedores** - Cadastrar e gerenciar fornecedores
⚙️ **Preferências** - Configurar suas preferências de compra

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências""",
        }

        # Handle multi-turn tests
        if test_id == "B002":
            return responses.get(f"B002_turn{turn}", default_menu)
        elif test_id == "E002":
            return responses.get(f"E002_turn{turn}", default_menu)

        return responses.get(test_id, default_menu)

    def validate_turn_expectations(
        self,
        response: str,
        turn: ConversationTurn,
        recorded_calls: list[dict]
    ) -> list[AssertionResult]:
        """Validate all expectations for a conversation turn."""
        results = []
        expected = turn.expected

        # Check contains_any
        if expected.contains_any:
            results.append(FrepiAssertions.assert_contains_any(response, expected.contains_any))

        # Check contains_all
        if expected.contains_all:
            results.append(FrepiAssertions.assert_contains_all(response, expected.contains_all))

        # Check not_contains
        if expected.not_contains:
            results.append(FrepiAssertions.assert_not_contains(response, expected.not_contains))

        # Check menu displayed
        if expected.contains_menu:
            results.append(FrepiAssertions.assert_menu_displayed(response))

        # Check emojis
        if expected.has_emojis:
            results.append(FrepiAssertions.assert_has_emojis(response))

        # Check price format
        if expected.has_price_format:
            results.append(FrepiAssertions.assert_price_format(response))

        # Check supplier names (not generic)
        if expected.has_supplier_names:
            results.append(FrepiAssertions.assert_has_supplier_names(response))

        # Check Portuguese language
        if expected.language == "pt-BR":
            results.append(FrepiAssertions.assert_portuguese_language(response))

        # Check tool calls
        if turn.tool_calls_expected or turn.tool_calls_forbidden:
            expected_calls = [
                {"name": tc.name, "args_contain": tc.args_contain}
                for tc in turn.tool_calls_expected
            ]
            results.append(FrepiAssertions.assert_tool_calls(
                recorded_calls,
                expected_calls,
                turn.tool_calls_forbidden
            ))

        # Always check for errors
        results.append(FrepiAssertions.assert_no_error(response))

        return results

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case",
        [tc for tc in TEST_MATRIX.test_cases],
        ids=[f"{tc.id}-{tc.name.replace(' ', '_')}" for tc in TEST_MATRIX.test_cases]
    )
    async def test_from_matrix(self, test_case: TestCase, tool_tracker):
        """
        Run a test case from the test matrix.

        This test is parametrized to run all test cases from the YAML file.
        """
        all_results = []

        # Execute each turn in the conversation
        for i, turn in enumerate(test_case.conversation, 1):
            # Get mock response for this test/turn
            response = self.get_mock_response_for_test(test_case, i)

            # For tests that expect tool calls, record them
            if turn.tool_calls_expected:
                for tc in turn.tool_calls_expected:
                    tool_tracker.record_call(tc.name, tc.args_contain)

            # Validate expectations
            turn_results = self.validate_turn_expectations(
                response,
                turn,
                tool_tracker.calls
            )
            all_results.extend(turn_results)

            # Clear tool tracker for next turn
            tool_tracker.reset()

        # Assert all results passed
        failed_results = [r for r in all_results if not r.passed]
        if failed_results:
            failure_messages = "\n".join([
                f"  - {r.message}" for r in failed_results
            ])
            pytest.fail(
                f"\nTest {test_case.id} ({test_case.name}) failed:\n{failure_messages}"
            )


# Group-specific test classes for selective running

class TestGroupA:
    """Group A: Onboarding tests."""

    @pytest.mark.group_a
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case",
        [tc for tc in TEST_MATRIX.test_cases if tc.group == "A"],
        ids=[tc.id for tc in TEST_MATRIX.test_cases if tc.group == "A"]
    )
    async def test_onboarding(self, test_case: TestCase, tool_tracker):
        """Run onboarding test cases."""
        runner = TestAgentFromMatrix()
        await runner.test_from_matrix(test_case, tool_tracker)


class TestGroupB:
    """Group B: Pre-purchase tests."""

    @pytest.mark.group_b
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case",
        [tc for tc in TEST_MATRIX.test_cases if tc.group == "B"],
        ids=[tc.id for tc in TEST_MATRIX.test_cases if tc.group == "B"]
    )
    async def test_pre_purchase(self, test_case: TestCase, tool_tracker):
        """Run pre-purchase test cases."""
        runner = TestAgentFromMatrix()
        await runner.test_from_matrix(test_case, tool_tracker)


class TestGroupC:
    """Group C: Core purchasing tests."""

    @pytest.mark.group_c
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case",
        [tc for tc in TEST_MATRIX.test_cases if tc.group == "C"],
        ids=[tc.id for tc in TEST_MATRIX.test_cases if tc.group == "C"]
    )
    async def test_core_purchasing(self, test_case: TestCase, tool_tracker):
        """Run core purchasing test cases."""
        runner = TestAgentFromMatrix()
        await runner.test_from_matrix(test_case, tool_tracker)


class TestGroupF:
    """Group F: Error handling tests."""

    @pytest.mark.group_f
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case",
        [tc for tc in TEST_MATRIX.test_cases if tc.group == "F"],
        ids=[tc.id for tc in TEST_MATRIX.test_cases if tc.group == "F"]
    )
    async def test_error_handling(self, test_case: TestCase, tool_tracker):
        """Run error handling test cases."""
        runner = TestAgentFromMatrix()
        await runner.test_from_matrix(test_case, tool_tracker)


# Priority-based test classes

class TestHighPriority:
    """High priority tests only."""

    @pytest.mark.high
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case",
        [tc for tc in TEST_MATRIX.test_cases if tc.priority == "high"],
        ids=[tc.id for tc in TEST_MATRIX.test_cases if tc.priority == "high"]
    )
    async def test_high_priority(self, test_case: TestCase, tool_tracker):
        """Run high priority test cases."""
        runner = TestAgentFromMatrix()
        await runner.test_from_matrix(test_case, tool_tracker)


class TestCriticalPriority:
    """Critical priority tests only."""

    @pytest.mark.critical
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case",
        [tc for tc in TEST_MATRIX.test_cases if tc.priority == "critical"],
        ids=[tc.id for tc in TEST_MATRIX.test_cases if tc.priority == "critical"]
    )
    async def test_critical_priority(self, test_case: TestCase, tool_tracker):
        """Run critical priority test cases."""
        runner = TestAgentFromMatrix()
        await runner.test_from_matrix(test_case, tool_tracker)
