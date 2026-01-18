"""
Supplier Facing Agent - GPT-4 powered supplier assistant.

Handles all supplier interactions including quotations, orders, and deliveries.
"""

import json
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI

from frepi_agent.config import get_config
from .prompts.supplier_agent import SUPPLIER_AGENT_PROMPT
from .tools.quotation_request import (
    get_pending_quotations,
    get_quotation_details,
)
from .tools.price_submission import (
    submit_price,
    get_product_for_quotation,
)
from .tools.order_management import (
    get_pending_orders,
    confirm_order,
    reject_order,
)
from .tools.delivery_status import (
    get_active_deliveries,
    update_delivery_status,
    report_delivery_issue,
    DeliveryStatus,
)


# Define tools for GPT-4 function calling
SUPPLIER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_pending_quotations",
            "description": "Get pending quotation requests for the supplier. Use this when the supplier wants to see products they need to quote prices for.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_price",
            "description": "Submit a price quotation for a product. Use this when the supplier provides a price for a product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier_mapped_product_id": {
                        "type": "integer",
                        "description": "The ID of the supplier_mapped_product to quote"
                    },
                    "unit_price": {
                        "type": "number",
                        "description": "The price per unit in BRL (e.g., 42.90)"
                    },
                    "unit": {
                        "type": "string",
                        "description": "Unit of measure (kg, un, cx, etc.)",
                        "default": "kg"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes about the quotation"
                    }
                },
                "required": ["supplier_mapped_product_id", "unit_price"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_product_to_quote",
            "description": "Search for a product to quote by name. Use when the supplier mentions a product name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The product name to search for"
                    }
                },
                "required": ["product_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_orders",
            "description": "Get orders pending confirmation from the supplier. Use when the supplier wants to see orders awaiting their confirmation.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_order",
            "description": "Confirm a pending order. Use when the supplier accepts an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to confirm"
                    },
                    "estimated_delivery_date": {
                        "type": "string",
                        "description": "Estimated delivery date in ISO format (YYYY-MM-DD)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes"
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reject_order",
            "description": "Reject a pending order. Use when the supplier cannot fulfill an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to reject"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for rejecting the order"
                    }
                },
                "required": ["order_id", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_deliveries",
            "description": "Get active deliveries for the supplier. Use when the supplier wants to see orders in delivery process.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_delivery_status",
            "description": "Update the delivery status of an order. Use when the supplier updates delivery progress.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["preparing", "in_transit", "delivered", "delayed", "failed"],
                        "description": "The new delivery status"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes"
                    }
                },
                "required": ["order_id", "status"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "report_delivery_issue",
            "description": "Report a delivery issue. Use when there's a problem with a delivery.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID"
                    },
                    "issue_type": {
                        "type": "string",
                        "enum": ["delay", "partial", "damaged", "cancelled", "other"],
                        "description": "Type of delivery issue"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the issue"
                    }
                },
                "required": ["order_id", "issue_type", "description"]
            }
        }
    },
]


@dataclass
class Message:
    """A message in the conversation."""
    role: str  # 'user', 'assistant', 'system', 'tool'
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list] = None
    name: Optional[str] = None


@dataclass
class SupplierConversationContext:
    """Context for a supplier conversation session."""
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    messages: list[Message] = field(default_factory=list)

    def add_message(self, role: str, content: str, **kwargs):
        """Add a message to the conversation."""
        self.messages.append(Message(role=role, content=content, **kwargs))

    def to_openai_messages(self) -> list[dict]:
        """Convert to OpenAI message format."""
        result = []
        for msg in self.messages:
            m = {"role": msg.role, "content": msg.content}
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.name:
                m["name"] = msg.name
            result.append(m)
        return result


class SupplierAgent:
    """Main Supplier Agent powered by GPT-4."""

    def __init__(self):
        config = get_config()
        self.client = OpenAI(api_key=config.openai_api_key)
        self.model = config.chat_model
        self.system_prompt = SUPPLIER_AGENT_PROMPT

    async def process_message(
        self,
        user_message: str,
        context: SupplierConversationContext,
    ) -> str:
        """
        Process a supplier message and return the agent's response.

        Args:
            user_message: The supplier's message
            context: The conversation context

        Returns:
            The agent's response text
        """
        # Add system prompt if this is a new conversation
        if not context.messages:
            system_prompt = self.system_prompt
            if context.supplier_name:
                system_prompt = f"O fornecedor atual é: {context.supplier_name} (ID: {context.supplier_id})\n\n{system_prompt}"
            context.add_message("system", system_prompt)

        # Add user message
        context.add_message("user", user_message)

        # Call GPT-4
        response = await self._call_gpt4(context)

        # Handle tool calls if any
        while response.choices[0].message.tool_calls:
            tool_calls = response.choices[0].message.tool_calls

            # Add assistant message with tool calls
            context.messages.append(Message(
                role="assistant",
                content=response.choices[0].message.content or "",
                tool_calls=[{
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                } for tc in tool_calls]
            ))

            # Execute each tool call
            for tool_call in tool_calls:
                result = await self._execute_tool(
                    tool_call.function.name,
                    json.loads(tool_call.function.arguments),
                    context,
                )
                context.messages.append(Message(
                    role="tool",
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name,
                ))

            # Call GPT-4 again with tool results
            response = await self._call_gpt4(context)

        # Get final response
        assistant_message = response.choices[0].message.content or ""
        context.add_message("assistant", assistant_message)

        return assistant_message

    async def _call_gpt4(self, context: SupplierConversationContext):
        """Make a call to GPT-4."""
        messages = context.to_openai_messages()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=SUPPLIER_TOOLS,
            tool_choice="auto",
            temperature=0.7,
        )

        return response

    async def _execute_tool(
        self,
        tool_name: str,
        args: dict,
        context: SupplierConversationContext,
    ) -> dict:
        """Execute a tool and return the result."""
        supplier_id = context.supplier_id

        if not supplier_id:
            return {"error": "Fornecedor não identificado"}

        try:
            if tool_name == "get_pending_quotations":
                quotations = await get_pending_quotations(supplier_id)
                return {
                    "quotations": [q.to_dict() for q in quotations],
                    "count": len(quotations),
                }

            elif tool_name == "submit_price":
                result = await submit_price(
                    supplier_id=supplier_id,
                    supplier_mapped_product_id=args["supplier_mapped_product_id"],
                    unit_price=args["unit_price"],
                    unit=args.get("unit", "kg"),
                    notes=args.get("notes"),
                )
                return result.to_dict()

            elif tool_name == "search_product_to_quote":
                product = await get_product_for_quotation(
                    supplier_id=supplier_id,
                    product_name=args["product_name"],
                )
                if product:
                    return {
                        "found": True,
                        "product": product,
                    }
                return {
                    "found": False,
                    "message": f"Produto '{args['product_name']}' não encontrado.",
                }

            elif tool_name == "get_pending_orders":
                orders = await get_pending_orders(supplier_id)
                return {
                    "orders": [o.to_dict() for o in orders],
                    "count": len(orders),
                }

            elif tool_name == "confirm_order":
                delivery_date = None
                if args.get("estimated_delivery_date"):
                    try:
                        delivery_date = datetime.fromisoformat(args["estimated_delivery_date"])
                    except:
                        pass

                return await confirm_order(
                    supplier_id=supplier_id,
                    order_id=args["order_id"],
                    estimated_delivery_date=delivery_date,
                    notes=args.get("notes"),
                )

            elif tool_name == "reject_order":
                return await reject_order(
                    supplier_id=supplier_id,
                    order_id=args["order_id"],
                    reason=args["reason"],
                )

            elif tool_name == "get_active_deliveries":
                deliveries = await get_active_deliveries(supplier_id)
                return {
                    "deliveries": [d.to_dict() for d in deliveries],
                    "count": len(deliveries),
                }

            elif tool_name == "update_delivery_status":
                status_map = {
                    "preparing": DeliveryStatus.PREPARING,
                    "in_transit": DeliveryStatus.IN_TRANSIT,
                    "delivered": DeliveryStatus.DELIVERED,
                    "delayed": DeliveryStatus.DELAYED,
                    "failed": DeliveryStatus.FAILED,
                }
                status = status_map.get(args["status"], DeliveryStatus.PREPARING)

                return await update_delivery_status(
                    supplier_id=supplier_id,
                    order_id=args["order_id"],
                    status=status,
                    notes=args.get("notes"),
                )

            elif tool_name == "report_delivery_issue":
                return await report_delivery_issue(
                    supplier_id=supplier_id,
                    order_id=args["order_id"],
                    issue_type=args["issue_type"],
                    description=args["description"],
                )

            else:
                return {"error": f"Ferramenta desconhecida: {tool_name}"}

        except Exception as e:
            return {"error": str(e)}


# Global agent instance
_supplier_agent: Optional[SupplierAgent] = None


def get_supplier_agent() -> SupplierAgent:
    """Get the global supplier agent instance."""
    global _supplier_agent
    if _supplier_agent is None:
        _supplier_agent = SupplierAgent()
    return _supplier_agent


async def supplier_chat(
    user_message: str,
    context: SupplierConversationContext,
) -> str:
    """
    Convenience function to chat with the supplier agent.

    Args:
        user_message: The supplier's message
        context: The conversation context

    Returns:
        The agent's response
    """
    agent = get_supplier_agent()
    return await agent.process_message(user_message, context)
