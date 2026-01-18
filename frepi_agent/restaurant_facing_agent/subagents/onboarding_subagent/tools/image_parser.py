"""Image Parser Tool - GPT-4 Vision invoice parsing.

This tool processes invoice photos using GPT-4 Vision to extract:
- Supplier name and contact info
- Product list with quantities and prices
- Invoice date and number
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class ParsedInvoice:
    """Structured data extracted from an invoice image."""

    supplier_name: str
    supplier_cnpj: Optional[str] = None
    invoice_date: Optional[str] = None
    invoice_number: Optional[str] = None
    items: list = None  # List of {product_name, quantity, unit, unit_price}
    total_amount: Optional[float] = None
    confidence_score: float = 0.0

    def __post_init__(self):
        if self.items is None:
            self.items = []


async def parse_invoice_image(
    openai_client,
    image_url: str,
    restaurant_id: int,
) -> ParsedInvoice:
    """
    Parse an invoice image using GPT-4 Vision.

    Args:
        openai_client: OpenAI client instance
        image_url: URL of the invoice image (from Telegram or Supabase Storage)
        restaurant_id: ID of the restaurant uploading the invoice

    Returns:
        ParsedInvoice with extracted data

    Database interactions:
        - Creates/updates suppliers table if new supplier detected
        - Creates entries in master_list for new products
        - Creates supplier_mapped_products entries
        - Creates pricing_history entries with invoice prices
    """
    # TODO: Implement GPT-4 Vision API call
    # TODO: Parse JSON response into ParsedInvoice
    # TODO: Save to database tables
    pass


def _build_vision_prompt() -> str:
    """Build the system prompt for invoice parsing."""
    return """You are an expert at extracting data from Brazilian invoice photos (Nota Fiscal).

Extract the following information in JSON format:
{
    "supplier_name": "Company name",
    "supplier_cnpj": "XX.XXX.XXX/XXXX-XX",
    "invoice_date": "DD/MM/YYYY",
    "invoice_number": "Invoice number",
    "items": [
        {
            "product_name": "Product description",
            "quantity": 10.0,
            "unit": "kg",
            "unit_price": 45.90
        }
    ],
    "total_amount": 459.00
}

Be precise with numbers and product names. If uncertain, include confidence notes."""
