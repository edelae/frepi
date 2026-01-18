"""
Quotation Subagent.

Handles receiving and processing price quotations from suppliers.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from frepi_agent.supplier_facing_agent.tools.quotation_request import (
    get_pending_quotations,
    get_quotation_details,
    QuotationRequest,
)
from frepi_agent.supplier_facing_agent.tools.price_submission import (
    submit_price,
    get_product_for_quotation,
    PriceSubmission,
)


class QuotationSubagent:
    """
    Handles quotation requests and price submissions.

    Responsibilities:
    - Show pending quotation requests
    - Accept price submissions from suppliers
    - Validate and store prices
    """

    async def get_pending(self, supplier_id: int) -> list[QuotationRequest]:
        """
        Get all pending quotation requests for a supplier.

        Args:
            supplier_id: The supplier ID

        Returns:
            List of pending quotation requests
        """
        return await get_pending_quotations(supplier_id)

    async def submit_quotation(
        self,
        supplier_id: int,
        product_id: int,
        unit_price: float,
        unit: str = "kg",
        notes: Optional[str] = None,
    ) -> PriceSubmission:
        """
        Submit a price quotation for a product.

        Args:
            supplier_id: The supplier ID
            product_id: The supplier_mapped_product ID
            unit_price: Price per unit
            unit: Unit of measure
            notes: Optional notes

        Returns:
            PriceSubmission result
        """
        return await submit_price(
            supplier_id=supplier_id,
            supplier_mapped_product_id=product_id,
            unit_price=unit_price,
            unit=unit,
            notes=notes,
        )

    async def find_product(
        self,
        supplier_id: int,
        product_name: str,
    ) -> Optional[dict]:
        """
        Search for a product to quote.

        Args:
            supplier_id: The supplier ID
            product_name: Product name to search

        Returns:
            Product dict if found
        """
        return await get_product_for_quotation(supplier_id, product_name)

    def format_pending_quotations(self, quotations: list[QuotationRequest]) -> str:
        """
        Format pending quotations for display.

        Args:
            quotations: List of quotation requests

        Returns:
            Formatted string for display
        """
        if not quotations:
            return """
✨ Você não tem cotações pendentes no momento.

Quando restaurantes solicitarem preços, você verá aqui.

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()

        lines = ["📋 **Cotações Pendentes**\n"]

        for i, q in enumerate(quotations, 1):
            lines.append(f"{i}. **{q.product_name}**")
            if q.quantity and q.unit:
                lines.append(f"   Quantidade: {q.quantity} {q.unit}")
            lines.append(f"   Restaurante: {q.restaurant_name}")
            lines.append(f"   ID do Produto: {q.id}")
            lines.append("")

        lines.append("\nPara enviar cotação, informe:")
        lines.append("- ID do produto")
        lines.append("- Preço por unidade (ex: 42.90)")
        lines.append("- Unidade (kg, un, cx)")

        return "\n".join(lines)

    def format_submission_result(self, result: PriceSubmission) -> str:
        """
        Format price submission result for display.

        Args:
            result: The submission result

        Returns:
            Formatted string for display
        """
        if result.success:
            return f"""
✅ **Cotação Registrada!**

📦 Produto: {result.product_name}
💰 Preço: R$ {result.unit_price:.2f}/{result.unit}
📅 Data: {result.effective_date.strftime('%d/%m/%Y')}

O restaurante será notificado sobre sua cotação.

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()
        else:
            return f"""
❌ **Erro ao registrar cotação**

{result.message}

Por favor, verifique os dados e tente novamente.

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()
