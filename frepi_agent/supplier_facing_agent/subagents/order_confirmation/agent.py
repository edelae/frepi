"""
Order Confirmation Subagent.

Handles order confirmations and rejections from suppliers.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from frepi_agent.supplier_facing_agent.tools.order_management import (
    get_pending_orders,
    confirm_order,
    reject_order,
    PendingOrder,
)


class OrderConfirmationSubagent:
    """
    Handles order confirmation workflow.

    Responsibilities:
    - Show pending orders awaiting confirmation
    - Accept order confirmations with delivery estimates
    - Handle order rejections with reasons
    """

    async def get_pending(self, supplier_id: int) -> list[PendingOrder]:
        """
        Get all pending orders for a supplier.

        Args:
            supplier_id: The supplier ID

        Returns:
            List of pending orders
        """
        return await get_pending_orders(supplier_id)

    async def confirm(
        self,
        supplier_id: int,
        order_id: str,
        estimated_delivery_date: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Confirm an order.

        Args:
            supplier_id: The supplier ID
            order_id: The order ID to confirm
            estimated_delivery_date: Estimated delivery date
            notes: Optional notes

        Returns:
            Result dict
        """
        return await confirm_order(
            supplier_id=supplier_id,
            order_id=order_id,
            estimated_delivery_date=estimated_delivery_date,
            notes=notes,
        )

    async def reject(
        self,
        supplier_id: int,
        order_id: str,
        reason: str,
    ) -> dict:
        """
        Reject an order.

        Args:
            supplier_id: The supplier ID
            order_id: The order ID to reject
            reason: Reason for rejection

        Returns:
            Result dict
        """
        return await reject_order(
            supplier_id=supplier_id,
            order_id=order_id,
            reason=reason,
        )

    def format_pending_orders(self, orders: list[PendingOrder]) -> str:
        """
        Format pending orders for display.

        Args:
            orders: List of pending orders

        Returns:
            Formatted string for display
        """
        if not orders:
            return """
✨ Você não tem pedidos pendentes no momento.

Quando restaurantes fizerem pedidos, você verá aqui.

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()

        lines = ["📦 **Pedidos Pendentes**\n"]

        for i, order in enumerate(orders, 1):
            lines.append(f"**{i}. Pedido {order.order_id}**")
            lines.append(f"   Restaurante: {order.restaurant_name}")
            lines.append(f"   Data: {order.order_date.strftime('%d/%m/%Y')}")
            lines.append(f"   Itens: {order.total_items}")
            lines.append(f"   Total: R$ {order.total_amount:,.2f}")

            if order.requested_delivery_date:
                lines.append(f"   Entrega solicitada: {order.requested_delivery_date.strftime('%d/%m/%Y')}")

            if order.line_items:
                lines.append("   Produtos:")
                for item in order.line_items[:3]:  # Show first 3 items
                    name = item.get("product_name", "Produto")
                    qty = item.get("quantity", 0)
                    unit = item.get("unit", "un")
                    lines.append(f"     • {name}: {qty} {unit}")
                if len(order.line_items) > 3:
                    lines.append(f"     ... +{len(order.line_items) - 3} itens")

            lines.append("")

        lines.append("\nPara confirmar um pedido, digite:")
        lines.append("'confirmar [ID do pedido]'")
        lines.append("\nPara rejeitar:")
        lines.append("'rejeitar [ID do pedido] [motivo]'")

        return "\n".join(lines)

    def format_confirmation_result(self, result: dict) -> str:
        """
        Format order confirmation result.

        Args:
            result: Confirmation result dict

        Returns:
            Formatted string for display
        """
        if result.get("success"):
            return f"""
✅ **Pedido Confirmado!**

📦 Pedido: {result.get('order_id')}

O restaurante será notificado sobre a confirmação.

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()
        else:
            return f"""
❌ **Erro ao confirmar pedido**

{result.get('message', 'Erro desconhecido')}

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()

    def format_rejection_result(self, result: dict) -> str:
        """
        Format order rejection result.

        Args:
            result: Rejection result dict

        Returns:
            Formatted string for display
        """
        if result.get("success"):
            return f"""
⚠️ **Pedido Rejeitado**

📦 Pedido: {result.get('order_id')}
📝 Motivo: {result.get('reason')}

O restaurante será notificado.

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()
        else:
            return f"""
❌ **Erro ao rejeitar pedido**

{result.get('message', 'Erro desconhecido')}

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()
