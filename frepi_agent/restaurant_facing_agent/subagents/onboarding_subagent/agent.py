"""Onboarding Subagent - GPT-4 driven user registration flow.

This subagent handles new restaurant user registration using GPT-4 function calling.
It collects:
- Restaurant basic info (name, city)
- Product preferences (via invoice photos OR manual entry)
- Supplier information from invoices
- Performs intelligent analysis of buying patterns
- Presents insights for user confirmation before committing to production
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List
from dataclasses import dataclass, field
from uuid import UUID

from openai import OpenAI

from frepi_agent.config import get_config
from frepi_agent.shared.supabase_client import get_supabase_client, Tables
from .tools.image_parser import parse_multiple_invoices, format_parsed_invoices_for_display
from .staging_service import OnboardingStagingService
from .analysis_service import OnboardingAnalysisService
from .commit_service import OnboardingCommitService
from .models import (
    SessionPhase, DataSource, PreferenceType,
    StagedSupplier, StagedProduct, StagedPrice, StagedPreference,
)

logger = logging.getLogger(__name__)


@dataclass
class OnboardingContext:
    """Context for onboarding conversation."""
    telegram_chat_id: int = None
    restaurant_id: Optional[int] = None
    person_name: Optional[str] = None
    restaurant_name: Optional[str] = None
    city: Optional[str] = None
    uploaded_photos: List[str] = field(default_factory=list)
    parsed_invoices: list = field(default_factory=list)
    products_list: List[str] = field(default_factory=list)
    onboarding_complete: bool = False
    messages: List[dict] = field(default_factory=list)
    # Staging session for persistent data storage
    staging_session_id: Optional[UUID] = None
    # Analysis results cache
    analysis_result: Optional[dict] = None


# Tool definitions for GPT-4 function calling
ONBOARDING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_restaurant_info",
            "description": "Save the restaurant's basic information (name and city). Call this after collecting both pieces of information from the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurant_name": {
                        "type": "string",
                        "description": "Name of the restaurant"
                    },
                    "city": {
                        "type": "string",
                        "description": "City where the restaurant is located"
                    }
                },
                "required": ["restaurant_name", "city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_uploaded_photos",
            "description": "Get the list of invoice photos that the user has uploaded. Use this to check if there are photos to process.",
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
            "name": "process_invoice_photos",
            "description": "Process all uploaded invoice photos using GPT-4 Vision to extract products, suppliers, and prices. Call this after the user has uploaded photos and said they are done (e.g., 'pronto').",
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
            "name": "save_products_manually",
            "description": "Save a list of products provided manually by the user (when they don't have invoice photos).",
            "parameters": {
                "type": "object",
                "properties": {
                    "products": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of product names that the restaurant purchases"
                    }
                },
                "required": ["products"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_analysis",
            "description": "Run intelligent analysis on all staged data (products, suppliers, prices) to detect buying patterns, preferences, and insights. Call this after processing invoice photos and before showing the summary to the user.",
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
            "name": "show_analysis_summary",
            "description": "Display the comprehensive analysis summary including spend distribution, top products, supplier rankings, detected preferences, and actionable insights. Call this after run_analysis to show results to the user for confirmation.",
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
            "name": "modify_preference",
            "description": "Modify a specific preference that was detected during analysis. Use this when the user wants to adjust an inferred preference (brand, price threshold, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "preference_type": {
                        "type": "string",
                        "enum": ["brand", "price_max", "quality", "supplier", "delivery_day"],
                        "description": "Type of preference to modify"
                    },
                    "product_name": {
                        "type": "string",
                        "description": "Name of the product to modify preference for (optional for global preferences)"
                    },
                    "new_value": {
                        "type": "string",
                        "description": "New preference value (e.g., brand name, max price, quality tier)"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["confirm", "reject", "modify"],
                        "description": "Action to take: confirm the detected preference, reject it, or modify to new value"
                    }
                },
                "required": ["preference_type", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_engagement_choice",
            "description": "Save the user's engagement choice after showing the analysis summary. Call this when the user picks how many products they want to configure preferences for: 1=Top 5, 2=Top 10, 3=Skip.",
            "parameters": {
                "type": "object",
                "properties": {
                    "choice": {
                        "type": "integer",
                        "enum": [1, 2, 3],
                        "description": "1=Top 5 (quick), 2=Top 10 (complete), 3=Skip"
                    }
                },
                "required": ["choice"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "collect_product_preferences",
            "description": "Save preferences collected for a specific product during targeted preference collection. Call this after asking the user about a product and receiving their preferences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The product name"
                    },
                    "brand": {
                        "type": "string",
                        "description": "Preferred brand (if any)"
                    },
                    "quality": {
                        "type": "string",
                        "description": "Quality preference (premium, standard, economy)"
                    },
                    "price_max": {
                        "type": "number",
                        "description": "Maximum acceptable price per unit"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Any additional specifications or notes"
                    }
                },
                "required": ["product_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_and_commit_onboarding",
            "description": "Commit all staged data to production tables after user confirms. This creates the restaurant, suppliers, products, prices, and preferences in the production database. Call this ONLY after the engagement gauge step (and optionally preference collection) and receiving user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_confirmed": {
                        "type": "boolean",
                        "description": "Whether the user explicitly confirmed the summary"
                    }
                },
                "required": ["user_confirmed"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_onboarding",
            "description": "Mark the onboarding process as complete and show the main menu. Call this AFTER confirm_and_commit_onboarding has successfully committed the data.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


# System prompt for the onboarding agent
ONBOARDING_SYSTEM_PROMPT = """Você é o assistente de cadastro do Frepi, um sistema inteligente de compras para restaurantes.

## Seu Objetivo
Completar o cadastro de um novo restaurante coletando informações e analisando padrões de compra:
1. **Informações básicas**: Nome do restaurante e cidade
2. **Produtos e fornecedores**: Via fotos de notas fiscais OU lista manual
3. **Análise inteligente**: Padrões de compra, preferências e tendências
4. **Confirmação**: Apresentar análise completa para confirmação do usuário

## Fluxo de Cadastro

### Passo 1: Boas-vindas e Informações Básicas
- Dê boas-vindas ao usuário
- Pergunte o nome do restaurante
- Pergunte a cidade onde está localizado
- Use a ferramenta `save_restaurant_info` para salvar

### Passo 2: Coleta de Produtos e Fornecedores
Ofereça duas opções ao usuário:
- **Opção 1 (Recomendada)**: "Você tem fotos de notas fiscais dos últimos 30 dias?"
  - Explique que com as notas, você vai:
    - ✅ Cadastrar automaticamente **fornecedores, produtos e preços**
    - ✅ Analisar **padrões de compra e preferências**
    - ✅ Identificar **produtos mais importantes**
    - ✅ Detectar **tendências de marca e preço**
- **Opção 2**: Se não tiver fotos, peça uma lista dos principais produtos

Se o usuário escolher enviar fotos:
1. Peça para enviar as fotos
2. Diga que quando terminar, deve digitar "pronto"
3. Use `get_uploaded_photos` para verificar quantas fotos foram enviadas
4. Use `process_invoice_photos` para analisar as fotos
5. Informe que vai analisar os padrões de compra

Se o usuário preferir lista manual:
1. Peça para listar os principais produtos que compra
2. Use `save_products_manually` para salvar

### Passo 3: Análise Inteligente (OBRIGATÓRIO após processar fotos)
Após processar as fotos com sucesso:
1. Use `run_analysis` para analisar todos os dados coletados
2. Use `show_analysis_summary` para mostrar a análise completa ao usuário

A análise inclui:
- 💰 **Distribuição de gastos** por categoria
- ⭐ **Top 10 produtos mais importantes** (por frequência e valor)
- 📦 **Ranking de fornecedores** por categoria
- 🎯 **Preferências detectadas**: marcas, faixas de preço
- 📅 **Padrões de entrega** por dia da semana
- 📈 **Insights acionáveis** (concentração de gastos, oportunidades)

### Passo 4: Engajamento - Quantos produtos configurar?
IMEDIATAMENTE após mostrar a análise, pergunte:

"Identifiquei seus X produtos mais importantes. Quer configurar preferências detalhadas?"
1️⃣ Top 5 (rápido ~2 min)
2️⃣ Top 10 (completo ~5 min)
3️⃣ Pular por agora

Use `save_engagement_choice` para salvar a escolha.

### Passo 5: Coleta de Preferências Direcionada (se escolheu 1 ou 2)
Para cada produto (na ordem de importância):
1. Mostre o que já foi inferido das notas fiscais (marca detectada, preço médio)
2. Pergunte de forma conversacional:
   "Sobre a **[Produto]** (seu produto #X):
   - Tem marca preferida? (ex: Friboi, Marfrig)
   - Preço máximo aceitável por kg?
   - Alguma especificação importante?"
3. Use `collect_product_preferences` para salvar cada resposta
4. Se o usuário disser "chega", "próximo", ou "pular", passe para o próximo ou finalize

### Passo 6: Confirmação Final
Após coletar preferências (ou se pulou):
```
Pronto! Vou salvar tudo. Confirma?
• sim → Salvar tudo e iniciar
• ajustar → Modificar alguma informação
```

Se o usuário quiser ajustar:
- Use `modify_preference` para ajustar preferências específicas

Se o usuário confirmar ("sim"):
- Use `confirm_and_commit_onboarding` com user_confirmed=true
- Use `complete_onboarding` para finalizar

### Passo 7: Finalização
- Mostre um **resumo final** do que foi salvo
- Mostre o menu principal do Frepi

## Regras Importantes
- SEMPRE responda em Português (Brasil)
- Use emojis estrategicamente: 👍 ✅ 📦 📸 🎉 🛒 ⭐ 💰 📊
- Seja conversacional, amigável e prestativo
- Se o usuário enviar fotos, elas ficam disponíveis via `get_uploaded_photos`
- Quando o usuário disser "pronto", "ok", ou "terminei", processe as fotos
- SEMPRE execute `run_analysis` e `show_analysis_summary` após processar fotos
- NUNCA pule a etapa de análise - ela é essencial para o cadastro inteligente
- NÃO invente informações - use apenas os dados das ferramentas
- Se algo der errado, ofereça a alternativa de lista manual
- A análise detecta preferências automaticamente - deixe claro que o usuário pode ajustar

## Menu Principal (mostrar após completar onboarding)
```
1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências
```
"""


class OnboardingAgent:
    """GPT-4 powered onboarding agent."""

    def __init__(self):
        config = get_config()
        self.client = OpenAI(api_key=config.openai_api_key)
        self.model = config.chat_model
        # Initialize services
        self.staging_service = OnboardingStagingService()
        self.analysis_service = OnboardingAnalysisService()
        self.commit_service = OnboardingCommitService()

    async def process_message(
        self,
        user_message: str,
        context: OnboardingContext,
    ) -> str:
        """
        Process a user message and return the agent's response.

        Args:
            user_message: The user's message
            context: The onboarding context with state

        Returns:
            The agent's response string
        """
        logger.info(f"═══════════════════════════════════════════════════════════")
        logger.info(f"📩 USER MESSAGE: {user_message}")
        logger.info(f"═══════════════════════════════════════════════════════════")

        # Add system prompt on first message
        if not context.messages:
            logger.info("🆕 First message - adding system prompt")
            context.messages.append({
                "role": "system",
                "content": ONBOARDING_SYSTEM_PROMPT
            })

        # Add user message
        context.messages.append({
            "role": "user",
            "content": user_message
        })

        try:
            # Call GPT-4 with tools
            logger.info(f"🤖 Calling GPT-4 ({self.model})...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=context.messages,
                tools=ONBOARDING_TOOLS,
                tool_choice="auto",
                temperature=0.7,
            )
            logger.info(f"✅ GPT-4 response received")

            # Handle tool calls loop
            loop_count = 0
            while response.choices[0].message.tool_calls:
                loop_count += 1
                tool_calls = response.choices[0].message.tool_calls
                logger.info(f"🔧 TOOL CALLS (loop {loop_count}): {[tc.function.name for tc in tool_calls]}")

                # Add assistant message with tool calls
                assistant_message = {
                    "role": "assistant",
                    "content": response.choices[0].message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }
                        for tc in tool_calls
                    ]
                }
                context.messages.append(assistant_message)

                # Execute each tool and add results
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    logger.info(f"   🔹 Executing: {tool_name}")
                    logger.info(f"      Args: {json.dumps(tool_args, ensure_ascii=False)}")

                    result = await self._execute_tool(tool_name, tool_args, context)

                    logger.info(f"      Result: {json.dumps(result, ensure_ascii=False)[:200]}...")

                    # Add tool result to messages
                    context.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })

                # Call GPT-4 again with tool results
                logger.info(f"🤖 Calling GPT-4 again with tool results...")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=context.messages,
                    tools=ONBOARDING_TOOLS,
                    tool_choice="auto",
                    temperature=0.7,
                )
                logger.info(f"✅ GPT-4 response received")

            # Get final response
            final_response = response.choices[0].message.content or ""
            context.messages.append({
                "role": "assistant",
                "content": final_response
            })

            logger.info(f"───────────────────────────────────────────────────────────")
            logger.info(f"💬 AGENT RESPONSE: {final_response[:200]}...")
            logger.info(f"───────────────────────────────────────────────────────────")

            return final_response

        except Exception as e:
            logger.error(f"❌ Error in onboarding agent: {e}", exc_info=True)
            return (
                "❌ Desculpe, ocorreu um erro. Vamos tentar novamente?\n\n"
                "Por favor, me diga o nome do seu restaurante."
            )

    async def _execute_tool(
        self,
        tool_name: str,
        args: dict,
        context: OnboardingContext,
    ) -> dict:
        """Execute a tool and return the result."""
        try:
            if tool_name == "save_restaurant_info":
                return await self._save_restaurant_info(
                    context,
                    args["restaurant_name"],
                    args["city"]
                )

            elif tool_name == "get_uploaded_photos":
                return await self._get_uploaded_photos(context)

            elif tool_name == "process_invoice_photos":
                return await self._process_invoice_photos(context)

            elif tool_name == "save_products_manually":
                return await self._save_products_manually(context, args["products"])

            elif tool_name == "run_analysis":
                return await self._run_analysis(context)

            elif tool_name == "show_analysis_summary":
                return await self._show_analysis_summary(context)

            elif tool_name == "save_engagement_choice":
                return await self._save_engagement_choice(context, args["choice"])

            elif tool_name == "collect_product_preferences":
                return await self._collect_product_preferences(
                    context,
                    args["product_name"],
                    args.get("brand"),
                    args.get("quality"),
                    args.get("price_max"),
                    args.get("notes"),
                )

            elif tool_name == "modify_preference":
                return await self._modify_preference(
                    context,
                    args["preference_type"],
                    args["action"],
                    args.get("product_name"),
                    args.get("new_value")
                )

            elif tool_name == "confirm_and_commit_onboarding":
                return await self._confirm_and_commit_onboarding(
                    context,
                    args["user_confirmed"]
                )

            elif tool_name == "complete_onboarding":
                return await self._complete_onboarding(context)

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {"error": str(e)}

    async def _save_restaurant_info(
        self,
        context: OnboardingContext,
        name: str,
        city: str,
    ) -> dict:
        """Save restaurant basic info to context and staging table."""
        context.restaurant_name = name
        context.city = city

        logger.info(f"Saving restaurant info to staging: {name} in {city}")

        try:
            # Create or get staging session
            session_id = await self.staging_service.get_or_create_session(
                telegram_chat_id=context.telegram_chat_id
            )
            context.staging_session_id = session_id

            # Save restaurant basic info
            await self.staging_service.save_restaurant_basic_info(
                session_id=session_id,
                restaurant_name=name,
                city=city,
                contact_name=context.person_name
            )

            logger.info(f"Created/updated staging session {session_id} for {name} in {city}")

            return {
                "status": "success",
                "message": f"Restaurant '{name}' in '{city}' saved to staging",
                "restaurant_name": name,
                "city": city,
                "session_id": str(session_id)
            }
        except Exception as e:
            logger.error(f"Error saving restaurant to staging: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Failed to save: {str(e)}. Please try again.",
                "restaurant_name": name,
                "city": city
            }

    async def _get_uploaded_photos(self, context: OnboardingContext) -> dict:
        """Get list of uploaded photos."""
        photo_count = len(context.uploaded_photos)
        return {
            "photo_count": photo_count,
            "has_photos": photo_count > 0,
            "message": f"{photo_count} photo(s) uploaded" if photo_count > 0 else "No photos uploaded yet"
        }

    async def _process_invoice_photos(self, context: OnboardingContext) -> dict:
        """Process uploaded invoice photos with GPT-4 Vision and stage all data."""
        if not context.uploaded_photos:
            return {
                "status": "error",
                "message": "No photos uploaded. Ask the user to upload invoice photos first."
            }

        # Ensure we have a staging session
        if not context.staging_session_id:
            return {
                "status": "error",
                "message": "No staging session. Please provide restaurant info first."
            }

        try:
            # Parse all invoices with GPT-4 Vision
            invoices = await parse_multiple_invoices(context.uploaded_photos)
            context.parsed_invoices = invoices

            if not invoices:
                return {
                    "status": "error",
                    "message": "Could not extract information from the photos. The images may be unclear or not invoices."
                }

            # Stage all extracted data
            products_staged = 0
            suppliers_staged = 0
            prices_staged = 0
            supplier_ids = {}  # Map supplier name to staged supplier ID

            for invoice_index, invoice in enumerate(invoices):
                # Save photo metadata
                if invoice_index < len(context.uploaded_photos):
                    await self.staging_service.save_photo_metadata(
                        session_id=context.staging_session_id,
                        telegram_file_id=f"photo_{invoice_index}",
                        telegram_file_url=context.uploaded_photos[invoice_index],
                        photo_index=invoice_index
                    )

                # Stage supplier
                if invoice.supplier_name and invoice.supplier_name not in supplier_ids:
                    supplier = StagedSupplier(
                        company_name=invoice.supplier_name,
                        cnpj=invoice.supplier_cnpj,
                        source=DataSource.INVOICE_EXTRACTION.value,
                        source_invoice_index=invoice_index,
                        extraction_confidence=0.85
                    )
                    supplier_id = await self.staging_service.stage_supplier(
                        session_id=context.staging_session_id,
                        supplier=supplier
                    )
                    supplier_ids[invoice.supplier_name] = supplier_id
                    suppliers_staged += 1

                supplier_id = supplier_ids.get(invoice.supplier_name)

                # Stage products and prices
                for item in invoice.items:
                    # Stage product (brand is extracted from product_name if present)
                    product = StagedProduct(
                        product_name=item.product_name,
                        brand=None,  # Brand extraction done in analysis phase
                        staging_supplier_id=supplier_id,
                        source=DataSource.INVOICE_EXTRACTION.value,
                        source_invoice_index=invoice_index,
                        extraction_confidence=0.85
                    )
                    product_id = await self.staging_service.stage_product(
                        session_id=context.staging_session_id,
                        product=product
                    )
                    products_staged += 1

                    # Stage price if available
                    if item.unit_price:
                        # Calculate total line amount
                        total_amount = item.quantity * item.unit_price if item.quantity else None
                        # Parse invoice date from string (DD/MM/YYYY format)
                        parsed_date = None
                        if invoice.invoice_date:
                            try:
                                parsed_date = datetime.strptime(invoice.invoice_date, "%d/%m/%Y").date()
                            except ValueError:
                                logger.warning(f"Could not parse invoice date: {invoice.invoice_date}")
                        price = StagedPrice(
                            staging_product_id=product_id,
                            staging_supplier_id=supplier_id,
                            unit_price=item.unit_price,
                            quantity_purchased=item.quantity,
                            total_line_amount=total_amount,
                            invoice_date=parsed_date,
                            invoice_number=invoice.invoice_number,
                            source=DataSource.INVOICE_EXTRACTION.value,
                            source_invoice_index=invoice_index,
                            extraction_confidence=0.85
                        )
                        await self.staging_service.stage_price(
                            session_id=context.staging_session_id,
                            price=price
                        )
                        prices_staged += 1

            # Update session phase
            await self.staging_service.update_session_phase(
                context.staging_session_id,
                SessionPhase.PRODUCTS_COLLECTED
            )

            # Collect for local context
            products = []
            suppliers = set()
            for invoice in invoices:
                suppliers.add(invoice.supplier_name)
                for item in invoice.items:
                    products.append(item.product_name)
            context.products_list = products

            # Format for display
            display_text = format_parsed_invoices_for_display(invoices)

            return {
                "status": "success",
                "suppliers_found": list(suppliers),
                "supplier_count": suppliers_staged,
                "products_found": products[:30],
                "product_count": products_staged,
                "prices_count": prices_staged,
                "display_text": display_text,
                "message": f"Extraídos e salvos: {products_staged} produtos, {suppliers_staged} fornecedores, {prices_staged} preços. Agora vou analisar os padrões de compra."
            }

        except Exception as e:
            logger.error(f"Error processing invoices: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error processing photos: {str(e)}. Suggest manual product entry."
            }

    async def _save_products_manually(
        self,
        context: OnboardingContext,
        products: List[str],
    ) -> dict:
        """Save manually entered products to staging."""
        context.products_list = products

        logger.info(f"Saving {len(products)} products manually to staging")

        # Ensure we have a staging session
        if not context.staging_session_id:
            return {
                "status": "error",
                "message": "No staging session. Please provide restaurant info first."
            }

        try:
            products_staged = 0
            for product_name in products:
                await self.staging_service.stage_product(
                    session_id=context.staging_session_id,
                    product_name=product_name,
                    source=DataSource.USER_STATED,
                    extraction_confidence=1.0
                )
                products_staged += 1

            # Update session phase
            await self.staging_service.update_session_phase(
                context.staging_session_id,
                SessionPhase.PRODUCTS_COLLECTED
            )

            return {
                "status": "success",
                "product_count": products_staged,
                "products": products,
                "message": f"Salvos {products_staged} produtos. Agora você pode adicionar mais informações ou finalizar o cadastro."
            }
        except Exception as e:
            logger.error(f"Error saving products to staging: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error saving products: {str(e)}"
            }

    async def _run_analysis(self, context: OnboardingContext) -> dict:
        """Run intelligent analysis on all staged data."""
        if not context.staging_session_id:
            return {
                "status": "error",
                "message": "No staging session. Please process invoice photos first."
            }

        try:
            logger.info(f"Running analysis for session {context.staging_session_id}")

            # Run full analysis
            analysis_result = await self.analysis_service.run_full_analysis(
                context.staging_session_id
            )

            # Cache result in context
            # Calculate total preferences from all preference types
            preferences_count = (
                len(analysis_result.brand_preferences) +
                len(analysis_result.price_ranges) +
                len(analysis_result.delivery_patterns)
            )

            context.analysis_result = {
                "total_spend": analysis_result.total_spend,
                "product_count": analysis_result.product_count,
                "supplier_count": analysis_result.supplier_count,
                "top_products_count": len(analysis_result.top_products),
                "preferences_count": preferences_count,
                "insights_count": len(analysis_result.insights),
            }

            # Update session phase
            await self.staging_service.update_session_phase(
                context.staging_session_id,
                SessionPhase.ANALYSIS_COMPLETE
            )

            return {
                "status": "success",
                "total_spend": analysis_result.total_spend,
                "product_count": analysis_result.product_count,
                "supplier_count": analysis_result.supplier_count,
                "top_products_count": len(analysis_result.top_products),
                "preferences_inferred": preferences_count,
                "insights_count": len(analysis_result.insights),
                "message": f"Análise completa! Encontrei {analysis_result.product_count} produtos, {analysis_result.supplier_count} fornecedores, e inferi {preferences_count} preferências. Use show_analysis_summary para mostrar os detalhes ao usuário."
            }

        except Exception as e:
            logger.error(f"Error running analysis: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error running analysis: {str(e)}"
            }

    async def _show_analysis_summary(self, context: OnboardingContext) -> dict:
        """Display the comprehensive analysis summary."""
        if not context.staging_session_id:
            return {
                "status": "error",
                "message": "No staging session. Please process invoice photos first."
            }

        try:
            logger.info(f"Generating analysis summary for session {context.staging_session_id}")

            # Format the analysis summary
            summary = await self.analysis_service.format_analysis_summary(
                context.staging_session_id
            )

            return {
                "status": "success",
                "summary": summary,
                "message": "Summary generated. Display this to the user and ask for confirmation."
            }

        except Exception as e:
            logger.error(f"Error generating summary: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error generating summary: {str(e)}"
            }

    async def _save_engagement_choice(
        self,
        context: OnboardingContext,
        choice: int,
    ) -> dict:
        """Save user's engagement choice (how many products to configure)."""
        if not context.staging_session_id:
            return {"status": "error", "message": "No staging session found."}

        try:
            now = datetime.now(timezone.utc).isoformat()
            client = get_supabase_client()

            # Save to onboarding session
            client.table(Tables.ONBOARDING_SESSIONS).update({
                "engagement_choice": choice,
                "engagement_choice_at": now,
                "current_phase": SessionPhase.ENGAGEMENT_GAUGE.value,
                "updated_at": now,
            }).eq("id", str(context.staging_session_id)).execute()

            choice_labels = {1: "Top 5 (rápido)", 2: "Top 10 (completo)", 3: "Pular"}
            label = choice_labels.get(choice, "Unknown")

            if choice in (1, 2):
                # Get top N products for preference collection
                count = 5 if choice == 1 else 10
                products = await self.staging_service.get_staged_products(
                    context.staging_session_id
                )
                products.sort(
                    key=lambda p: p.inferred_importance_score or 0, reverse=True
                )
                top_products = products[:count]

                # Update phase
                await self.staging_service.update_session_phase(
                    context.staging_session_id,
                    SessionPhase.TARGETED_PREFERENCES,
                )

                return {
                    "status": "success",
                    "choice": choice,
                    "label": label,
                    "products_to_configure": [
                        {
                            "name": p.product_name,
                            "rank": i + 1,
                            "tier": p.importance_tier or "unknown",
                            "avg_price": p.avg_unit_price,
                            "brand_detected": p.brand,
                            "total_spend": p.total_spend,
                        }
                        for i, p in enumerate(top_products)
                    ],
                    "message": f"Escolha salva: {label}. Agora vamos configurar preferências para os top {count} produtos, um por vez."
                }
            else:
                # Skip - go directly to confirmation
                await self.staging_service.update_session_phase(
                    context.staging_session_id,
                    SessionPhase.SUMMARY,
                )
                return {
                    "status": "success",
                    "choice": choice,
                    "label": label,
                    "message": "Preferências puladas. Vou aprender com o tempo baseado nas suas compras. Vamos confirmar o cadastro."
                }

        except Exception as e:
            logger.error(f"Error saving engagement choice: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def _collect_product_preferences(
        self,
        context: OnboardingContext,
        product_name: str,
        brand: Optional[str] = None,
        quality: Optional[str] = None,
        price_max: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Collect and save preferences for a specific product."""
        if not context.staging_session_id:
            return {"status": "error", "message": "No staging session found."}

        try:
            # Find the product in staging
            products = await self.staging_service.get_staged_products(
                context.staging_session_id
            )
            target_product = None
            for p in products:
                if product_name.lower() in p.product_name.lower():
                    target_product = p
                    break

            if not target_product:
                return {
                    "status": "error",
                    "message": f"Produto '{product_name}' não encontrado no staging."
                }

            saved_prefs = []

            # Save brand preference
            if brand:
                pref = StagedPreference(
                    staging_product_id=target_product.id,
                    preference_type=PreferenceType.BRAND.value,
                    preference_value={"brand": brand},
                    confidence_score=1.0,
                    source=DataSource.USER_STATED.value,
                    inference_reasoning="Preferência declarada durante onboarding",
                )
                await self.staging_service.stage_preference(
                    context.staging_session_id, pref
                )
                saved_prefs.append("brand")

            # Save quality preference
            if quality:
                pref = StagedPreference(
                    staging_product_id=target_product.id,
                    preference_type=PreferenceType.QUALITY.value,
                    preference_value={"quality": quality},
                    confidence_score=1.0,
                    source=DataSource.USER_STATED.value,
                    inference_reasoning="Preferência declarada durante onboarding",
                )
                await self.staging_service.stage_preference(
                    context.staging_session_id, pref
                )
                saved_prefs.append("quality")

            # Save price max preference
            if price_max:
                pref = StagedPreference(
                    staging_product_id=target_product.id,
                    preference_type=PreferenceType.PRICE_MAX.value,
                    preference_value={
                        "max_price": price_max,
                        "unit": target_product.specifications.get("unit", "un")
                        if target_product.specifications else "un",
                    },
                    confidence_score=1.0,
                    source=DataSource.USER_STATED.value,
                    inference_reasoning="Limite de preço declarado durante onboarding",
                )
                await self.staging_service.stage_preference(
                    context.staging_session_id, pref
                )
                saved_prefs.append("price_max")

            # Save specification notes
            if notes:
                pref = StagedPreference(
                    staging_product_id=target_product.id,
                    preference_type=PreferenceType.SPECIFICATION.value,
                    preference_value={"notes": notes},
                    confidence_score=1.0,
                    source=DataSource.USER_STATED.value,
                    inference_reasoning="Especificação declarada durante onboarding",
                )
                await self.staging_service.stage_preference(
                    context.staging_session_id, pref
                )
                saved_prefs.append("specification")

            # Update preferences_configured counter
            client = get_supabase_client()
            client.table(Tables.ONBOARDING_SESSIONS).update({
                "preferences_configured": len(saved_prefs),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", str(context.staging_session_id)).execute()

            return {
                "status": "success",
                "product": product_name,
                "preferences_saved": saved_prefs,
                "message": f"Preferências salvas para {product_name}: {', '.join(saved_prefs)}"
            }

        except Exception as e:
            logger.error(f"Error collecting preferences: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def _modify_preference(
        self,
        context: OnboardingContext,
        preference_type: str,
        action: str,
        product_name: Optional[str] = None,
        new_value: Optional[str] = None,
    ) -> dict:
        """Modify a detected preference."""
        if not context.staging_session_id:
            return {
                "status": "error",
                "message": "No staging session found."
            }

        try:
            logger.info(f"Modifying preference: {preference_type} action={action}")

            # Find the preference to modify
            preferences = await self.staging_service.get_staged_preferences(
                context.staging_session_id
            )

            # Filter by type and optionally by product
            matching_prefs = [
                p for p in preferences
                if p.preference_type.value == preference_type
            ]

            if product_name:
                # Need to find product by name first
                products = await self.staging_service.get_staged_products(
                    context.staging_session_id
                )
                product_id = None
                for p in products:
                    if product_name.lower() in p.product_name.lower():
                        product_id = p.id
                        break

                if product_id:
                    matching_prefs = [
                        p for p in matching_prefs
                        if p.staging_product_id == product_id
                    ]

            if not matching_prefs:
                return {
                    "status": "error",
                    "message": f"No {preference_type} preference found" + (f" for {product_name}" if product_name else "")
                }

            # Update the preference based on action
            pref = matching_prefs[0]
            client = get_supabase_client()

            if action == "confirm":
                client.table(Tables.ONBOARDING_STAGING_PREFERENCES).update({
                    "user_feedback": "confirmed",
                    "source": "user_confirmed"
                }).eq("id", str(pref.id)).execute()
                message = f"Preferência de {preference_type} confirmada"

            elif action == "reject":
                client.table(Tables.ONBOARDING_STAGING_PREFERENCES).update({
                    "user_feedback": "rejected"
                }).eq("id", str(pref.id)).execute()
                message = f"Preferência de {preference_type} rejeitada"

            elif action == "modify" and new_value:
                # Update the preference value
                new_pref_value = {"value": new_value}
                if preference_type == "brand":
                    new_pref_value = {"brands": [new_value]}
                elif preference_type == "price_max":
                    new_pref_value = {"max_price": float(new_value)}

                client.table(Tables.ONBOARDING_STAGING_PREFERENCES).update({
                    "preference_value": new_pref_value,
                    "user_feedback": "modified",
                    "source": "user_stated"
                }).eq("id", str(pref.id)).execute()
                message = f"Preferência de {preference_type} modificada para: {new_value}"

            else:
                return {
                    "status": "error",
                    "message": "Invalid action or missing new_value for modify action"
                }

            return {
                "status": "success",
                "message": message
            }

        except Exception as e:
            logger.error(f"Error modifying preference: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error modifying preference: {str(e)}"
            }

    async def _confirm_and_commit_onboarding(
        self,
        context: OnboardingContext,
        user_confirmed: bool,
    ) -> dict:
        """Commit all staged data to production tables."""
        if not user_confirmed:
            return {
                "status": "cancelled",
                "message": "User did not confirm. Ask what they want to adjust."
            }

        if not context.staging_session_id:
            return {
                "status": "error",
                "message": "No staging session found."
            }

        try:
            logger.info(f"Committing onboarding for session {context.staging_session_id}")

            # Commit to production
            commit_result = await self.commit_service.commit_onboarding(
                session_id=context.staging_session_id,
                telegram_chat_id=context.telegram_chat_id,
            )

            if commit_result.success:
                # Update context with committed IDs
                context.restaurant_id = commit_result.restaurant_id

                return {
                    "status": "success",
                    "restaurant_id": commit_result.restaurant_id,
                    "person_id": commit_result.person_id,
                    "suppliers_committed": commit_result.suppliers_committed,
                    "products_committed": commit_result.products_committed,
                    "prices_committed": commit_result.prices_committed,
                    "preferences_committed": commit_result.preferences_committed,
                    "message": f"🎉 Cadastro salvo com sucesso! {commit_result.products_committed} produtos, {commit_result.suppliers_committed} fornecedores, {commit_result.preferences_committed} preferências."
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error committing: {', '.join(commit_result.errors)}"
                }

        except Exception as e:
            logger.error(f"Error committing onboarding: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error committing: {str(e)}"
            }

    async def _complete_onboarding(self, context: OnboardingContext) -> dict:
        """Mark onboarding as complete and show main menu."""
        context.onboarding_complete = True

        logger.info(f"Completing onboarding for {context.restaurant_name}")

        # Update restaurant record with completion timestamp
        try:
            if context.restaurant_id:
                client = get_supabase_client()
                client.table(Tables.RESTAURANTS).update({
                    "onboarding_completed_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", context.restaurant_id).execute()
                logger.info(f"Set onboarding_completed_at for restaurant {context.restaurant_id}")

            return {
                "status": "complete",
                "restaurant_name": context.restaurant_name,
                "city": context.city,
                "product_count": len(context.products_list),
                "message": "Onboarding completed successfully! Show the main menu to the user."
            }
        except Exception as e:
            logger.error(f"Error updating onboarding status: {e}", exc_info=True)
            return {
                "status": "complete",
                "restaurant_name": context.restaurant_name,
                "city": context.city,
                "product_count": len(context.products_list),
                "message": "Onboarding completed (database update failed). Show the main menu to the user."
            }


# Singleton agent instance
_agent: Optional[OnboardingAgent] = None


def get_onboarding_agent() -> OnboardingAgent:
    """Get or create the onboarding agent instance."""
    global _agent
    if _agent is None:
        _agent = OnboardingAgent()
    return _agent


async def onboarding_chat(
    message: str,
    context: OnboardingContext,
) -> str:
    """
    Main entry point for onboarding chat.

    Args:
        message: User's message
        context: Onboarding context

    Returns:
        Agent's response
    """
    agent = get_onboarding_agent()
    return await agent.process_message(message, context)
