"""
Delivery Update Subagent.

Handles delivery status updates and issue reporting.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from frepi_agent.supplier_facing_agent.tools.delivery_status import (
    get_active_deliveries,
    update_delivery_status,
    report_delivery_issue,
    DeliveryInfo,
    DeliveryStatus,
)


class DeliveryUpdateSubagent:
    """
    Handles delivery tracking and updates.

    Responsibilities:
    - Show active deliveries
    - Update delivery status
    - Report delivery issues
    """

    async def get_active(self, supplier_id: int) -> list[DeliveryInfo]:
        """
        Get all active deliveries for a supplier.

        Args:
            supplier_id: The supplier ID

        Returns:
            List of active deliveries
        """
        return await get_active_deliveries(supplier_id)

    async def update_status(
        self,
        supplier_id: int,
        order_id: str,
        status: DeliveryStatus,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Update delivery status.

        Args:
            supplier_id: The supplier ID
            order_id: The order ID
            status: New delivery status
            notes: Optional notes

        Returns:
            Result dict
        """
        return await update_delivery_status(
            supplier_id=supplier_id,
            order_id=order_id,
            status=status,
            notes=notes,
        )

    async def report_issue(
        self,
        supplier_id: int,
        order_id: str,
        issue_type: str,
        description: str,
    ) -> dict:
        """
        Report a delivery issue.

        Args:
            supplier_id: The supplier ID
            order_id: The order ID
            issue_type: Type of issue
            description: Issue description

        Returns:
            Result dict
        """
        return await report_delivery_issue(
            supplier_id=supplier_id,
            order_id=order_id,
            issue_type=issue_type,
            description=description,
        )

    def format_active_deliveries(self, deliveries: list[DeliveryInfo]) -> str:
        """
        Format active deliveries for display.

        Args:
            deliveries: List of active deliveries

        Returns:
            Formatted string for display
        """
        if not deliveries:
            return """
✨ Você não tem entregas em andamento no momento.

Quando houver pedidos confirmados para entregar, você verá aqui.

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()

        status_icons = {
            DeliveryStatus.PREPARING: "📦",
            DeliveryStatus.IN_TRANSIT: "🚚",
            DeliveryStatus.DELIVERED: "✅",
            DeliveryStatus.DELAYED: "⚠️",
            DeliveryStatus.FAILED: "❌",
        }

        status_names = {
            DeliveryStatus.PREPARING: "Preparando",
            DeliveryStatus.IN_TRANSIT: "Em Trânsito",
            DeliveryStatus.DELIVERED: "Entregue",
            DeliveryStatus.DELAYED: "Atrasado",
            DeliveryStatus.FAILED: "Falhou",
        }

        lines = ["🚚 **Entregas em Andamento**\n"]

        for i, delivery in enumerate(deliveries, 1):
            icon = status_icons.get(delivery.status, "📦")
            status_name = status_names.get(delivery.status, "Desconhecido")

            lines.append(f"**{i}. Pedido {delivery.order_id}**")
            lines.append(f"   {icon} Status: {status_name}")
            lines.append(f"   Restaurante: {delivery.restaurant_name}")

            if delivery.confirmed_delivery_date:
                lines.append(f"   Entrega prevista: {delivery.confirmed_delivery_date.strftime('%d/%m/%Y')}")

            lines.append(f"   Itens: {delivery.total_items}")
            lines.append("")

        lines.append("\nPara atualizar status:")
        lines.append("• 'em transito [ID]' - Saiu para entrega")
        lines.append("• 'entregue [ID]' - Entrega concluída")
        lines.append("• 'atrasado [ID]' - Entrega atrasada")
        lines.append("\nPara reportar problema:")
        lines.append("• 'problema [ID] [descrição]'")

        return "\n".join(lines)

    def format_update_result(self, result: dict) -> str:
        """
        Format status update result.

        Args:
            result: Update result dict

        Returns:
            Formatted string for display
        """
        if result.get("success"):
            status_messages = {
                "preparing": "📦 Status: Preparando",
                "in_transit": "🚚 Status: Em Trânsito",
                "delivered": "✅ Entrega Concluída!",
                "delayed": "⚠️ Status: Atrasado",
                "failed": "❌ Status: Falhou",
            }

            status = result.get("new_status", "")
            msg = status_messages.get(status, result.get("message", "Status atualizado"))

            return f"""
{msg}

📦 Pedido: {result.get('order_id')}

O restaurante será notificado.

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()
        else:
            return f"""
❌ **Erro ao atualizar status**

{result.get('message', 'Erro desconhecido')}

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()

    def format_issue_result(self, result: dict) -> str:
        """
        Format issue report result.

        Args:
            result: Issue report result dict

        Returns:
            Formatted string for display
        """
        if result.get("success"):
            return f"""
⚠️ **Problema Reportado**

📦 Pedido: {result.get('order_id')}
📝 Tipo: {result.get('issue_type')}

O restaurante será notificado sobre o problema.

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()
        else:
            return f"""
❌ **Erro ao reportar problema**

{result.get('message', 'Erro desconhecido')}

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega
            """.strip()
