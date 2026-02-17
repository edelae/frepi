"""
Frepi Agent - GPT-4 powered restaurant purchasing assistant.

Uses OpenAI's function calling to interact with database tools.
"""

import json
from typing import Optional, AsyncGenerator
from dataclasses import dataclass, field

from openai import OpenAI

from frepi_agent.config import get_config
from .prompts.customer_agent import CUSTOMER_AGENT_PROMPT
from frepi_agent.shared.preference_drip import get_drip_service
from .tools.product_search import search_products, SearchResult
from .tools.pricing import (
    get_prices_for_product,
    validate_prices,
    get_best_price,
    PriceInfo,
)
from .tools.suppliers import (
    get_supplier_by_name,
    search_suppliers,
    check_supplier_exists,
    get_suppliers_for_product,
)


# Define tools for GPT-4 function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search for products in the master catalog using semantic similarity. Use this when the user mentions a product they want to buy or check prices for.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The product name or description to search for (e.g., 'picanha', 'arroz 5kg', 'óleo de soja')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 4)",
                        "default": 4
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_prices",
            "description": "Get all available prices for a product from different suppliers. Use this after finding a product to show pricing options.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "The product ID from the master_list"
                    }
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_product_prices",
            "description": "Check if prices exist and are fresh for a list of products before creating an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of product IDs to validate"
                    }
                },
                "required": ["product_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_supplier",
            "description": "Check if a supplier exists in the system by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier_name": {
                        "type": "string",
                        "description": "The supplier company name to check"
                    }
                },
                "required": ["supplier_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_suppliers_for_product",
            "description": "Get all suppliers that sell a specific product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "The product ID from the master_list"
                    }
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_preference_correction",
            "description": "Save when a user corrects a recommendation or suggestion. Always ask WHY before calling this tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The product name (optional for global corrections)"
                    },
                    "preference_type": {
                        "type": "string",
                        "enum": ["brand", "price_max", "quality", "supplier", "specification"],
                        "description": "Type of preference being corrected"
                    },
                    "original_value": {
                        "type": "string",
                        "description": "What the system suggested"
                    },
                    "corrected_value": {
                        "type": "string",
                        "description": "What the user wants instead"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why the user prefers this (key learning data)"
                    },
                    "context": {
                        "type": "string",
                        "enum": ["onboarding", "drip", "purchase", "manual"],
                        "description": "Where this correction happened"
                    }
                },
                "required": ["preference_type", "corrected_value", "context"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "answer_drip_question",
            "description": "Save the user's response to a drip preference question appended to a previous response.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The product being asked about"
                    },
                    "preference_type": {
                        "type": "string",
                        "enum": ["brand", "price_max", "quality", "supplier"],
                        "description": "Type of preference"
                    },
                    "value": {
                        "type": "string",
                        "description": "The user's answer"
                    },
                    "skip": {
                        "type": "boolean",
                        "description": "True if user wants to skip",
                        "default": False
                    }
                },
                "required": ["product_name", "preference_type"]
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
class ConversationContext:
    """Context for a conversation session."""
    restaurant_id: Optional[int] = None
    restaurant_name: Optional[str] = None
    person_name: Optional[str] = None
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


class FrepiAgent:
    """Main Frepi Agent powered by GPT-4."""

    def __init__(self):
        config = get_config()
        self.client = OpenAI(api_key=config.openai_api_key)
        self.model = config.chat_model
        self.system_prompt = CUSTOMER_AGENT_PROMPT

    async def process_message(
        self,
        user_message: str,
        context: ConversationContext,
    ) -> str:
        """
        Process a user message and return the agent's response.

        Args:
            user_message: The user's message
            context: The conversation context

        Returns:
            The agent's response text
        """
        # Add system prompt if this is a new conversation
        if not context.messages:
            context.add_message("system", self.system_prompt)

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

        # Append drip questions if applicable
        if context.restaurant_id:
            try:
                drip_service = get_drip_service()
                drip_questions = await drip_service.get_drip_questions(
                    context.restaurant_id
                )
                drip_text = drip_service.format_drip_questions(drip_questions)
                if drip_text:
                    assistant_message += drip_text
            except Exception:
                pass  # Don't let drip errors break normal flow

        context.add_message("assistant", assistant_message)

        return assistant_message

    async def _call_gpt4(self, context: ConversationContext):
        """Make a call to GPT-4."""
        messages = context.to_openai_messages()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.7,
        )

        return response

    async def _execute_tool(self, tool_name: str, args: dict) -> dict:
        """Execute a tool and return the result."""
        try:
            if tool_name == "search_products":
                result = await search_products(
                    args["query"],
                    limit=args.get("limit", 4),
                )
                return result.to_dict()

            elif tool_name == "get_product_prices":
                prices = await get_prices_for_product(args["product_id"])
                return {
                    "product_id": args["product_id"],
                    "prices": [p.to_dict() for p in prices],
                    "has_prices": len(prices) > 0,
                    "best_price": prices[0].to_dict() if prices else None,
                }

            elif tool_name == "validate_product_prices":
                result = await validate_prices(args["product_ids"])
                return result.to_dict()

            elif tool_name == "check_supplier":
                exists = await check_supplier_exists(args["supplier_name"])
                supplier = await get_supplier_by_name(args["supplier_name"]) if exists else None
                return {
                    "exists": exists,
                    "supplier": supplier.to_dict() if supplier else None,
                }

            elif tool_name == "get_suppliers_for_product":
                suppliers = await get_suppliers_for_product(args["product_id"])
                return {
                    "product_id": args["product_id"],
                    "suppliers": [s.to_dict() for s in suppliers],
                    "count": len(suppliers),
                }

            elif tool_name == "save_preference_correction":
                return await self._save_preference_correction(
                    context,
                    args.get("product_name"),
                    args["preference_type"],
                    args.get("original_value"),
                    args["corrected_value"],
                    args.get("reason"),
                    args["context"],
                )

            elif tool_name == "answer_drip_question":
                return await self._answer_drip_question(
                    context,
                    args["product_name"],
                    args["preference_type"],
                    args.get("value"),
                    args.get("skip", False),
                )

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"error": str(e)}


    async def _save_preference_correction(
        self,
        context: ConversationContext,
        product_name: Optional[str],
        preference_type: str,
        original_value: Optional[str],
        corrected_value: str,
        reason: Optional[str],
        correction_context: str,
    ) -> dict:
        """Save a preference correction with reasoning."""
        if not context.restaurant_id:
            return {"error": "No restaurant linked"}

        from frepi_agent.shared.supabase_client import get_supabase_client, Tables
        import json

        client = get_supabase_client()

        # Find master_list_id if product given
        master_list_id = None
        if product_name:
            result = client.table(Tables.MASTER_LIST).select("id").eq(
                "restaurant_id", context.restaurant_id
            ).ilike("product_name", f"%{product_name}%").limit(1).execute()
            if result.data:
                master_list_id = result.data[0]["id"]

        # Insert correction record
        correction_data = {
            "restaurant_id": context.restaurant_id,
            "master_list_id": master_list_id,
            "preference_type": preference_type,
            "original_value": json.dumps(original_value) if original_value else None,
            "corrected_value": json.dumps(corrected_value),
            "correction_reason": reason,
            "correction_context": correction_context,
        }

        client.table(Tables.PREFERENCE_CORRECTIONS).insert(correction_data).execute()

        # Update the actual preference if product found
        if master_list_id:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            pref_data = {}

            if preference_type == "brand":
                pref_data["brand_preferences"] = {"brand": corrected_value}
                pref_data["brand_preferences_source"] = "user_correction"
                pref_data["brand_preferences_added_at"] = now
            elif preference_type == "price_max":
                pref_data["price_preference"] = corrected_value
                pref_data["price_preference_source"] = "user_correction"
                pref_data["price_preference_added_at"] = now
            elif preference_type == "quality":
                pref_data["quality_preference"] = {"quality": corrected_value}
                pref_data["quality_preference_source"] = "user_correction"
                pref_data["quality_preference_added_at"] = now

            if pref_data:
                existing = client.table(
                    Tables.RESTAURANT_PRODUCT_PREFERENCES
                ).select("id").eq(
                    "restaurant_id", context.restaurant_id
                ).eq("master_list_id", master_list_id).limit(1).execute()

                if existing.data:
                    client.table(
                        Tables.RESTAURANT_PRODUCT_PREFERENCES
                    ).update(pref_data).eq("id", existing.data[0]["id"]).execute()
                else:
                    pref_data["restaurant_id"] = context.restaurant_id
                    pref_data["master_list_id"] = master_list_id
                    pref_data["is_active"] = True
                    client.table(
                        Tables.RESTAURANT_PRODUCT_PREFERENCES
                    ).insert(pref_data).execute()

        # Update engagement profile
        profile = client.table(Tables.ENGAGEMENT_PROFILE).select(
            "total_corrections, corrections_with_reason"
        ).eq("restaurant_id", context.restaurant_id).limit(1).execute()

        if profile.data:
            p = profile.data[0]
            updates = {"total_corrections": p["total_corrections"] + 1}
            if reason:
                updates["corrections_with_reason"] = p["corrections_with_reason"] + 1
            client.table(Tables.ENGAGEMENT_PROFILE).update(
                updates
            ).eq("restaurant_id", context.restaurant_id).execute()

        return {
            "success": True,
            "product": product_name,
            "type": preference_type,
            "corrected_to": corrected_value,
            "has_reason": bool(reason),
            "message": f"Anotado! Preferência de {preference_type} atualizada para {corrected_value}."
        }

    async def _answer_drip_question(
        self,
        context: ConversationContext,
        product_name: str,
        preference_type: str,
        value: Optional[str],
        skip: bool,
    ) -> dict:
        """Handle a drip question response."""
        if not context.restaurant_id:
            return {"error": "No restaurant linked"}

        drip_service = get_drip_service()

        # Find master_list_id
        from frepi_agent.shared.supabase_client import get_supabase_client, Tables
        client = get_supabase_client()

        result = client.table(Tables.MASTER_LIST).select("id").eq(
            "restaurant_id", context.restaurant_id
        ).ilike("product_name", f"%{product_name}%").limit(1).execute()

        if not result.data:
            return {"error": f"Product '{product_name}' not found"}

        master_list_id = result.data[0]["id"]

        await drip_service.record_drip_response(
            restaurant_id=context.restaurant_id,
            master_list_id=master_list_id,
            preference_type=preference_type,
            value=value,
            skipped=skip,
        )

        if skip:
            return {"success": True, "skipped": True, "product": product_name}

        return {
            "success": True,
            "product": product_name,
            "type": preference_type,
            "value": value,
            "message": f"Preferência de {preference_type} salva para {product_name}."
        }


# Global agent instance
_agent: Optional[FrepiAgent] = None


def get_agent() -> FrepiAgent:
    """Get the global agent instance."""
    global _agent
    if _agent is None:
        _agent = FrepiAgent()
    return _agent


async def chat(user_message: str, context: ConversationContext) -> str:
    """
    Convenience function to chat with the agent.

    Args:
        user_message: The user's message
        context: The conversation context

    Returns:
        The agent's response
    """
    agent = get_agent()
    return await agent.process_message(user_message, context)
