"""
User identification for message routing.

Determines whether an incoming message is from a restaurant user,
supplier, or unknown user that needs onboarding.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .supabase_client import get_supabase_client, Tables


class UserType(str, Enum):
    """Type of user interacting with the bot."""
    RESTAURANT = "restaurant"
    SUPPLIER = "supplier"
    UNKNOWN = "unknown"


@dataclass
class UserIdentification:
    """Result of user identification."""
    user_type: UserType
    user_id: Optional[int] = None  # restaurant_people.id or suppliers.id
    restaurant_id: Optional[int] = None
    supplier_id: Optional[int] = None
    name: Optional[str] = None
    is_new_user: bool = False


async def identify_user(telegram_chat_id: int) -> UserIdentification:
    """
    Identify a user by their Telegram chat ID.

    Checks both restaurant_people and suppliers tables to determine
    if this is a known user and what type they are.

    Args:
        telegram_chat_id: The Telegram chat ID of the sender

    Returns:
        UserIdentification with user type and details
    """
    client = get_supabase_client()
    chat_id_str = str(telegram_chat_id)

    # Check if this is a restaurant user
    # Look in restaurant_people table for matching whatsapp_number or telegram_chat_id
    restaurant_user = await _find_restaurant_user(client, chat_id_str)
    if restaurant_user:
        return UserIdentification(
            user_type=UserType.RESTAURANT,
            user_id=restaurant_user["id"],
            restaurant_id=restaurant_user.get("restaurant_id"),
            name=restaurant_user.get("first_name") or restaurant_user.get("full_name"),
            is_new_user=False,
        )

    # Check if this is a supplier
    # Look in suppliers table for matching whatsapp_number or telegram_chat_id
    supplier = await _find_supplier(client, chat_id_str)
    if supplier:
        return UserIdentification(
            user_type=UserType.SUPPLIER,
            user_id=supplier["id"],
            supplier_id=supplier["id"],
            name=supplier.get("company_name") or supplier.get("primary_contact_name"),
            is_new_user=False,
        )

    # Unknown user - needs onboarding
    return UserIdentification(
        user_type=UserType.UNKNOWN,
        is_new_user=True,
    )


async def _find_restaurant_user(client, chat_id_str: str) -> Optional[dict]:
    """Find a restaurant user by Telegram chat ID or WhatsApp number."""
    # Try to find by whatsapp_number (stored with chat ID)
    result = (
        client.table(Tables.RESTAURANT_PEOPLE)
        .select("id, restaurant_id, first_name, last_name, full_name, whatsapp_number")
        .or_(f"whatsapp_number.eq.{chat_id_str},telegram_chat_id.eq.{chat_id_str}")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    # Fallback: Try with + prefix for phone numbers
    result = (
        client.table(Tables.RESTAURANT_PEOPLE)
        .select("id, restaurant_id, first_name, last_name, full_name, whatsapp_number")
        .eq("whatsapp_number", f"+{chat_id_str}")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


async def _find_supplier(client, chat_id_str: str) -> Optional[dict]:
    """Find a supplier by Telegram chat ID or WhatsApp number."""
    # Try to find by whatsapp_number (stored with chat ID)
    result = (
        client.table(Tables.SUPPLIERS)
        .select("id, company_name, primary_contact_name, whatsapp_number")
        .or_(f"whatsapp_number.eq.{chat_id_str},telegram_chat_id.eq.{chat_id_str}")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    # Fallback: Try with + prefix for phone numbers
    result = (
        client.table(Tables.SUPPLIERS)
        .select("id, company_name, primary_contact_name, whatsapp_number")
        .eq("whatsapp_number", f"+{chat_id_str}")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


async def register_user_role(
    telegram_chat_id: int,
    user_type: UserType,
    name: Optional[str] = None,
) -> UserIdentification:
    """
    Register a new user with their chosen role.

    Called after an unknown user selects whether they are a
    restaurant or supplier.

    Args:
        telegram_chat_id: The Telegram chat ID
        user_type: The user's chosen role
        name: Optional name for initial registration

    Returns:
        UserIdentification for the newly registered user
    """
    if user_type == UserType.UNKNOWN:
        raise ValueError("Cannot register user as UNKNOWN type")

    # For now, return a placeholder - actual registration will be
    # handled by the respective onboarding subagents
    return UserIdentification(
        user_type=user_type,
        is_new_user=True,
        name=name,
    )


# Role selection message (Portuguese)
ROLE_SELECTION_MESSAGE = """
Olá! Bem-vindo ao Frepi!

Não encontrei seu cadastro. Você é:

1️⃣ **Restaurante** - Quero comprar produtos
2️⃣ **Fornecedor** - Quero fornecer produtos

Por favor, digite 1 ou 2 para continuar.
""".strip()


def get_role_selection_message() -> str:
    """Get the role selection prompt for unknown users."""
    return ROLE_SELECTION_MESSAGE
