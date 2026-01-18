"""
Delivery status tools for suppliers.

Handles tracking and updating delivery status for orders.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from frepi_agent.shared.supabase_client import (
    get_supabase_client,
    Tables,
    update_one,
)


class DeliveryStatus(str, Enum):
    """Delivery status options."""
    PREPARING = "preparing"  # Preparando
    IN_TRANSIT = "in_transit"  # Em trânsito
    DELIVERED = "delivered"  # Entregue
    DELAYED = "delayed"  # Atrasado
    FAILED = "failed"  # Falhou


@dataclass
class DeliveryInfo:
    """Information about a delivery."""

    order_id: str
    restaurant_id: int
    restaurant_name: str
    status: DeliveryStatus
    confirmed_delivery_date: Optional[datetime]
    actual_delivery_date: Optional[datetime]
    line_items: list[dict]
    total_items: int
    notes: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "restaurant_id": self.restaurant_id,
            "restaurant_name": self.restaurant_name,
            "status": self.status.value,
            "confirmed_delivery_date": self.confirmed_delivery_date.isoformat() if self.confirmed_delivery_date else None,
            "actual_delivery_date": self.actual_delivery_date.isoformat() if self.actual_delivery_date else None,
            "line_items": self.line_items,
            "total_items": self.total_items,
            "notes": self.notes,
        }


async def get_active_deliveries(supplier_id: int) -> list[DeliveryInfo]:
    """
    Get active deliveries for a supplier.

    Args:
        supplier_id: The supplier's ID

    Returns:
        List of DeliveryInfo objects
    """
    client = get_supabase_client()

    # Get confirmed orders that haven't been delivered yet
    result = (
        client.table(Tables.PURCHASE_ORDERS)
        .select("""
            order_id,
            restaurant_id,
            confirmed_delivery_date,
            actual_delivery_date,
            delivery_status,
            line_items,
            total_items,
            notes,
            restaurants(restaurant_name)
        """)
        .eq("supplier_id", supplier_id)
        .eq("order_status", "confirmed")
        .in_("delivery_status", ["pending", "preparing", "in_transit", "delayed"])
        .order("confirmed_delivery_date")
        .limit(20)
        .execute()
    )

    deliveries = []
    for row in result.data or []:
        restaurant = row.get("restaurants", {})

        confirmed_date = None
        if row.get("confirmed_delivery_date"):
            try:
                confirmed_date = datetime.fromisoformat(row["confirmed_delivery_date"].replace("Z", "+00:00"))
            except:
                pass

        actual_date = None
        if row.get("actual_delivery_date"):
            try:
                actual_date = datetime.fromisoformat(row["actual_delivery_date"].replace("Z", "+00:00"))
            except:
                pass

        # Map database status to enum
        status_map = {
            "pending": DeliveryStatus.PREPARING,
            "preparing": DeliveryStatus.PREPARING,
            "in_transit": DeliveryStatus.IN_TRANSIT,
            "delayed": DeliveryStatus.DELAYED,
        }
        status = status_map.get(row.get("delivery_status"), DeliveryStatus.PREPARING)

        deliveries.append(DeliveryInfo(
            order_id=row["order_id"],
            restaurant_id=row.get("restaurant_id", 0),
            restaurant_name=restaurant.get("restaurant_name", "Desconhecido"),
            status=status,
            confirmed_delivery_date=confirmed_date,
            actual_delivery_date=actual_date,
            line_items=row.get("line_items", []),
            total_items=row.get("total_items", 0),
            notes=row.get("notes"),
        ))

    return deliveries


async def update_delivery_status(
    supplier_id: int,
    order_id: str,
    status: DeliveryStatus,
    notes: Optional[str] = None,
) -> dict:
    """
    Update the delivery status of an order.

    Args:
        supplier_id: The supplier's ID
        order_id: The order ID
        status: New delivery status
        notes: Optional notes

    Returns:
        Result dict with success status and message
    """
    client = get_supabase_client()
    now = datetime.now()

    # Verify the order belongs to this supplier
    order_result = (
        client.table(Tables.PURCHASE_ORDERS)
        .select("order_id, supplier_id, order_status")
        .eq("order_id", order_id)
        .eq("supplier_id", supplier_id)
        .limit(1)
        .execute()
    )

    if not order_result.data:
        return {
            "success": False,
            "message": "Pedido não encontrado ou não pertence a este fornecedor.",
        }

    # Build update data
    update_data = {
        "delivery_status": status.value,
        "updated_at": now.isoformat(),
    }

    # If delivered, set actual delivery date and fulfillment status
    if status == DeliveryStatus.DELIVERED:
        update_data["actual_delivery_date"] = now.isoformat()
        update_data["fulfillment_status"] = "delivered"

    if notes:
        update_data["notes"] = notes

    try:
        result = await update_one(
            Tables.PURCHASE_ORDERS,
            {"order_id": order_id},
            update_data,
        )

        status_messages = {
            DeliveryStatus.PREPARING: "Status atualizado: Preparando pedido",
            DeliveryStatus.IN_TRANSIT: "Status atualizado: Em trânsito",
            DeliveryStatus.DELIVERED: "Entrega confirmada com sucesso!",
            DeliveryStatus.DELAYED: "Status atualizado: Entrega atrasada",
            DeliveryStatus.FAILED: "Status atualizado: Entrega falhou",
        }

        return {
            "success": True,
            "message": status_messages.get(status, "Status atualizado"),
            "order_id": order_id,
            "new_status": status.value,
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Erro ao atualizar status: {str(e)}",
        }


async def report_delivery_issue(
    supplier_id: int,
    order_id: str,
    issue_type: str,
    description: str,
) -> dict:
    """
    Report an issue with a delivery.

    Args:
        supplier_id: The supplier's ID
        order_id: The order ID
        issue_type: Type of issue (delay, partial, damaged, etc.)
        description: Description of the issue

    Returns:
        Result dict with success status and message
    """
    client = get_supabase_client()
    now = datetime.now()

    # Verify the order belongs to this supplier
    order_result = (
        client.table(Tables.PURCHASE_ORDERS)
        .select("order_id, supplier_id, issues_reported")
        .eq("order_id", order_id)
        .eq("supplier_id", supplier_id)
        .limit(1)
        .execute()
    )

    if not order_result.data:
        return {
            "success": False,
            "message": "Pedido não encontrado ou não pertence a este fornecedor.",
        }

    order = order_result.data[0]
    existing_issues = order.get("issues_reported") or []

    # Add new issue
    new_issue = {
        "type": issue_type,
        "description": description,
        "reported_at": now.isoformat(),
        "reported_by": "supplier",
    }
    existing_issues.append(new_issue)

    # Update the order
    update_data = {
        "issues_reported": existing_issues,
        "delivery_status": "delayed" if issue_type == "delay" else "failed",
        "issue_resolved": False,
        "updated_at": now.isoformat(),
    }

    try:
        result = await update_one(
            Tables.PURCHASE_ORDERS,
            {"order_id": order_id},
            update_data,
        )

        return {
            "success": True,
            "message": "Problema reportado. O restaurante será notificado.",
            "order_id": order_id,
            "issue_type": issue_type,
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Erro ao reportar problema: {str(e)}",
        }
