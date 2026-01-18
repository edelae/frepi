"""
Order management tools for suppliers.

Handles viewing, confirming, and rejecting purchase orders.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from frepi_agent.shared.supabase_client import (
    get_supabase_client,
    Tables,
    fetch_many,
    update_one,
)


@dataclass
class PendingOrder:
    """A pending order awaiting supplier confirmation."""

    order_id: str
    restaurant_id: int
    restaurant_name: str
    order_date: datetime
    requested_delivery_date: Optional[datetime]
    line_items: list[dict]
    total_items: int
    total_amount: float
    notes: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "restaurant_id": self.restaurant_id,
            "restaurant_name": self.restaurant_name,
            "order_date": self.order_date.isoformat() if self.order_date else None,
            "requested_delivery_date": self.requested_delivery_date.isoformat() if self.requested_delivery_date else None,
            "line_items": self.line_items,
            "total_items": self.total_items,
            "total_amount": self.total_amount,
            "notes": self.notes,
        }


async def get_pending_orders(supplier_id: int) -> list[PendingOrder]:
    """
    Get orders pending confirmation from this supplier.

    Args:
        supplier_id: The supplier's ID

    Returns:
        List of PendingOrder objects
    """
    client = get_supabase_client()

    # Get orders with status 'pending' or 'awaiting_confirmation'
    result = (
        client.table(Tables.PURCHASE_ORDERS)
        .select("""
            order_id,
            restaurant_id,
            order_date,
            requested_delivery_date,
            line_items,
            total_items,
            total_amount,
            notes,
            restaurants(restaurant_name)
        """)
        .eq("supplier_id", supplier_id)
        .in_("order_status", ["pending", "awaiting_confirmation", "submitted"])
        .order("order_date", desc=True)
        .limit(20)
        .execute()
    )

    orders = []
    for row in result.data or []:
        restaurant = row.get("restaurants", {})

        order_date = None
        if row.get("order_date"):
            try:
                order_date = datetime.fromisoformat(row["order_date"].replace("Z", "+00:00"))
            except:
                pass

        delivery_date = None
        if row.get("requested_delivery_date"):
            try:
                delivery_date = datetime.fromisoformat(row["requested_delivery_date"].replace("Z", "+00:00"))
            except:
                pass

        orders.append(PendingOrder(
            order_id=row["order_id"],
            restaurant_id=row.get("restaurant_id", 0),
            restaurant_name=restaurant.get("restaurant_name", "Desconhecido"),
            order_date=order_date or datetime.now(),
            requested_delivery_date=delivery_date,
            line_items=row.get("line_items", []),
            total_items=row.get("total_items", 0),
            total_amount=float(row.get("total_amount", 0)),
            notes=row.get("notes"),
        ))

    return orders


async def confirm_order(
    supplier_id: int,
    order_id: str,
    estimated_delivery_date: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Confirm a pending order.

    Args:
        supplier_id: The supplier's ID
        order_id: The order ID to confirm
        estimated_delivery_date: Estimated delivery date
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

    order = order_result.data[0]
    if order.get("order_status") not in ["pending", "awaiting_confirmation", "submitted"]:
        return {
            "success": False,
            "message": f"Pedido não pode ser confirmado. Status atual: {order.get('order_status')}",
        }

    # Update the order
    update_data = {
        "order_status": "confirmed",
        "fulfillment_status": "processing",
        "updated_at": now.isoformat(),
    }

    if estimated_delivery_date:
        update_data["confirmed_delivery_date"] = estimated_delivery_date.isoformat()

    if notes:
        update_data["notes"] = notes

    try:
        result = await update_one(
            Tables.PURCHASE_ORDERS,
            {"order_id": order_id},
            update_data,
        )

        return {
            "success": True,
            "message": "Pedido confirmado com sucesso!",
            "order_id": order_id,
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Erro ao confirmar pedido: {str(e)}",
        }


async def reject_order(
    supplier_id: int,
    order_id: str,
    reason: str,
) -> dict:
    """
    Reject a pending order.

    Args:
        supplier_id: The supplier's ID
        order_id: The order ID to reject
        reason: Reason for rejection

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

    # Update the order
    update_data = {
        "order_status": "rejected",
        "fulfillment_status": "cancelled",
        "updated_at": now.isoformat(),
        "notes": f"Rejeitado pelo fornecedor: {reason}",
    }

    try:
        result = await update_one(
            Tables.PURCHASE_ORDERS,
            {"order_id": order_id},
            update_data,
        )

        return {
            "success": True,
            "message": "Pedido rejeitado.",
            "order_id": order_id,
            "reason": reason,
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Erro ao rejeitar pedido: {str(e)}",
        }
