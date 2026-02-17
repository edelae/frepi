"""Image Parser Tool - GPT-4 Vision invoice parsing.

This tool processes invoice photos using GPT-4 Vision to extract:
- Supplier name and contact info
- Product list with quantities and prices
- Invoice date and number
"""

import json
import logging
import base64
import httpx
from typing import Optional, List
from dataclasses import dataclass

from openai import OpenAI

from frepi_agent.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class InvoiceItem:
    """Single item from an invoice."""
    product_name: str
    quantity: float = 1.0
    unit: str = "un"
    unit_price: float = 0.0


@dataclass
class ParsedInvoice:
    """Structured data extracted from an invoice image."""

    supplier_name: str
    supplier_cnpj: Optional[str] = None
    invoice_date: Optional[str] = None
    invoice_number: Optional[str] = None
    items: List[InvoiceItem] = None
    total_amount: Optional[float] = None
    confidence_score: float = 0.0
    raw_response: Optional[str] = None

    def __post_init__(self):
        if self.items is None:
            self.items = []


def get_openai_client() -> OpenAI:
    """Get the OpenAI client instance."""
    config = get_config()
    return OpenAI(api_key=config.openai_api_key)


async def download_image_as_base64(image_url: str) -> str:
    """Download an image and convert to base64."""
    async with httpx.AsyncClient() as client:
        response = await client.get(image_url)
        response.raise_for_status()
        return base64.b64encode(response.content).decode("utf-8")


async def parse_invoice_image(
    image_url: str,
    restaurant_id: Optional[int] = None,
) -> ParsedInvoice:
    """
    Parse an invoice image using GPT-4 Vision.

    Args:
        image_url: URL of the invoice image (from Telegram)
        restaurant_id: Optional ID of the restaurant uploading the invoice

    Returns:
        ParsedInvoice with extracted data
    """
    logger.info(f"Parsing invoice image: {image_url[:50]}...")

    try:
        # Download image and convert to base64
        image_base64 = await download_image_as_base64(image_url)

        # Get OpenAI client
        client = get_openai_client()
        config = get_config()

        # Build the prompt
        prompt = _build_vision_prompt()

        # Call GPT-4 Vision API
        response = client.chat.completions.create(
            model=config.chat_model,  # gpt-4o supports vision
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all product information from this Brazilian invoice (Nota Fiscal). Return ONLY valid JSON, no markdown formatting."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4096,
            temperature=0.1,  # Low temperature for accurate extraction
        )

        # Extract the response text
        response_text = response.choices[0].message.content
        logger.info(f"GPT-4 Vision response received, length: {len(response_text)}")

        # Parse JSON from response (handle potential markdown wrapping)
        json_text = response_text
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0]
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0]

        data = json.loads(json_text.strip())

        # Convert items to InvoiceItem objects
        items = []
        for item in data.get("items", []):
            items.append(InvoiceItem(
                product_name=item.get("product_name", "Unknown"),
                quantity=float(item.get("quantity", 1)),
                unit=item.get("unit", "un"),
                unit_price=float(item.get("unit_price", 0)),
            ))

        return ParsedInvoice(
            supplier_name=data.get("supplier_name", "Unknown"),
            supplier_cnpj=data.get("supplier_cnpj"),
            invoice_date=data.get("invoice_date"),
            invoice_number=data.get("invoice_number"),
            items=items,
            total_amount=data.get("total_amount"),
            confidence_score=data.get("confidence_score", 0.8),
            raw_response=response_text,
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from GPT-4 Vision response: {e}")
        return ParsedInvoice(
            supplier_name="Parse Error",
            confidence_score=0.0,
            raw_response=str(e),
        )
    except Exception as e:
        logger.error(f"Error parsing invoice image: {e}")
        return ParsedInvoice(
            supplier_name="Error",
            confidence_score=0.0,
            raw_response=str(e),
        )


async def parse_multiple_invoices(image_urls: List[str]) -> List[ParsedInvoice]:
    """Parse multiple invoice images and return combined results."""
    results = []
    for url in image_urls:
        result = await parse_invoice_image(url)
        if result.supplier_name != "Error" and result.supplier_name != "Parse Error":
            results.append(result)
    return results


def format_parsed_invoices_for_display(invoices: List[ParsedInvoice]) -> str:
    """Format parsed invoices for display to user."""
    if not invoices:
        return "Nenhum produto encontrado nas notas fiscais."

    # Collect all unique products and suppliers
    products_by_supplier = {}
    for invoice in invoices:
        supplier = invoice.supplier_name
        if supplier not in products_by_supplier:
            products_by_supplier[supplier] = []
        for item in invoice.items:
            products_by_supplier[supplier].append(item)

    # Build display string
    lines = ["🔍 **Produtos encontrados nas notas fiscais:**\n"]

    for supplier, items in products_by_supplier.items():
        lines.append(f"📦 **{supplier}**")
        for item in items[:10]:  # Limit to 10 items per supplier
            price_str = f"R$ {item.unit_price:.2f}/{item.unit}" if item.unit_price > 0 else ""
            lines.append(f"  • {item.product_name} {price_str}")
        if len(items) > 10:
            lines.append(f"  ... e mais {len(items) - 10} produtos")
        lines.append("")

    total_products = sum(len(items) for items in products_by_supplier.values())
    lines.append(f"📊 **Total:** {total_products} produtos de {len(products_by_supplier)} fornecedor(es)")

    return "\n".join(lines)


def _build_vision_prompt() -> str:
    """Build the system prompt for invoice parsing."""
    return """You are an expert at extracting data from Brazilian invoice photos (Nota Fiscal / NF-e / Cupom Fiscal).

Your task is to extract ALL product information from the invoice image.

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{
    "supplier_name": "Company name from the invoice header",
    "supplier_cnpj": "XX.XXX.XXX/XXXX-XX or null if not visible",
    "invoice_date": "DD/MM/YYYY or null",
    "invoice_number": "Invoice number or null",
    "items": [
        {
            "product_name": "Full product description as written",
            "quantity": 10.0,
            "unit": "kg",
            "unit_price": 45.90
        }
    ],
    "total_amount": 459.00,
    "confidence_score": 0.9
}

Important rules:
1. Extract ALL line items from the invoice, not just a few
2. Keep product names exactly as written (don't translate or simplify)
3. Parse quantities carefully - look for "QTD", "QTDE" columns
4. Unit prices are usually in columns like "VL UNIT", "P.UNIT"
5. Common units: kg, un, cx (caixa), pc (pacote), lt, ml
6. If price is per kg but quantity is in grams, convert appropriately
7. CNPJ format: XX.XXX.XXX/XXXX-XX
8. Set confidence_score between 0-1 based on image clarity"""
