"""
Supplier Onboarding Subagent.

Handles registration of new suppliers, collecting company information
and initial product catalog setup.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from frepi_agent.shared.supabase_client import (
    get_supabase_client,
    Tables,
    insert_one,
    fetch_one,
)


@dataclass
class SupplierRegistration:
    """Result of supplier registration."""
    success: bool
    supplier_id: Optional[int]
    company_name: Optional[str]
    message: str


class SupplierOnboardingSubagent:
    """
    Handles new supplier onboarding.

    Responsibilities:
    - Collect company information (name, CNPJ, contact)
    - Register supplier in the database
    - Link to restaurants they supply
    """

    async def check_supplier_exists(
        self,
        company_name: Optional[str] = None,
        cnpj: Optional[str] = None,
        whatsapp_number: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Check if a supplier already exists.

        Args:
            company_name: Company name to search
            cnpj: CNPJ (Brazilian tax ID) to search
            whatsapp_number: WhatsApp number to search

        Returns:
            Supplier dict if found, None otherwise
        """
        client = get_supabase_client()

        # Try to find by CNPJ first (most unique)
        if cnpj:
            result = (
                client.table(Tables.SUPPLIERS)
                .select("*")
                .eq("company_registration", cnpj)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]

        # Try by WhatsApp number
        if whatsapp_number:
            result = (
                client.table(Tables.SUPPLIERS)
                .select("*")
                .eq("whatsapp_number", whatsapp_number)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]

        # Try by company name (fuzzy match)
        if company_name:
            result = (
                client.table(Tables.SUPPLIERS)
                .select("*")
                .ilike("company_name", f"%{company_name}%")
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]

        return None

    async def register_supplier(
        self,
        company_name: str,
        whatsapp_number: str,
        telegram_chat_id: Optional[int] = None,
        cnpj: Optional[str] = None,
        primary_contact_name: Optional[str] = None,
        primary_email: Optional[str] = None,
        primary_phone: Optional[str] = None,
        street_address: Optional[str] = None,
        city: Optional[str] = None,
    ) -> SupplierRegistration:
        """
        Register a new supplier.

        Args:
            company_name: Company name (required)
            whatsapp_number: WhatsApp number (required for contact)
            telegram_chat_id: Telegram chat ID for bot communication
            cnpj: CNPJ (Brazilian tax ID)
            primary_contact_name: Main contact person name
            primary_email: Contact email
            primary_phone: Contact phone
            street_address: Address
            city: City

        Returns:
            SupplierRegistration result
        """
        # Check if supplier already exists
        existing = await self.check_supplier_exists(
            company_name=company_name,
            cnpj=cnpj,
            whatsapp_number=whatsapp_number,
        )

        if existing:
            return SupplierRegistration(
                success=False,
                supplier_id=existing["id"],
                company_name=existing["company_name"],
                message=f"Fornecedor '{existing['company_name']}' já está cadastrado.",
            )

        # Prepare supplier data
        supplier_data = {
            "company_name": company_name,
            "whatsapp_number": whatsapp_number,
            "is_active": True,
            "created_at": datetime.now().isoformat(),
        }

        # Add optional fields
        if telegram_chat_id:
            supplier_data["telegram_chat_id"] = str(telegram_chat_id)
        if cnpj:
            supplier_data["company_registration"] = cnpj
        if primary_contact_name:
            supplier_data["primary_contact_name"] = primary_contact_name
        if primary_email:
            supplier_data["primary_email"] = primary_email
        if primary_phone:
            supplier_data["primary_phone"] = primary_phone
        if street_address:
            supplier_data["street_address"] = street_address
        if city:
            supplier_data["city"] = city

        try:
            # Insert supplier
            result = await insert_one(Tables.SUPPLIERS, supplier_data)

            return SupplierRegistration(
                success=True,
                supplier_id=result["id"],
                company_name=company_name,
                message=f"Fornecedor '{company_name}' cadastrado com sucesso!",
            )

        except Exception as e:
            return SupplierRegistration(
                success=False,
                supplier_id=None,
                company_name=company_name,
                message=f"Erro ao cadastrar fornecedor: {str(e)}",
            )

    async def update_supplier_telegram_id(
        self,
        supplier_id: int,
        telegram_chat_id: int,
    ) -> bool:
        """
        Update the Telegram chat ID for a supplier.

        Args:
            supplier_id: The supplier ID
            telegram_chat_id: The Telegram chat ID

        Returns:
            True if successful, False otherwise
        """
        client = get_supabase_client()

        try:
            client.table(Tables.SUPPLIERS).update({
                "telegram_chat_id": str(telegram_chat_id),
                "updated_at": datetime.now().isoformat(),
            }).eq("id", supplier_id).execute()

            return True

        except Exception:
            return False

    def get_onboarding_prompt(self, step: str = "start") -> str:
        """
        Get the appropriate onboarding message.

        Args:
            step: Current onboarding step

        Returns:
            Message to send to the supplier
        """
        prompts = {
            "start": """
Olá! Bem-vindo ao Frepi!

Vou te ajudar a se cadastrar como fornecedor.

Por favor, me informe o **nome da sua empresa**:
            """.strip(),

            "ask_contact": """
Ótimo! Agora preciso de algumas informações de contato:

• **Nome do responsável**
• **Telefone** (se diferente do WhatsApp)
• **Email**

Me envie essas informações:
            """.strip(),

            "ask_cnpj": """
Perfeito! Por último, poderia informar o **CNPJ** da empresa?

(Se preferir pular, digite "pular")
            """.strip(),

            "confirm": """
Excelente! Vou confirmar os dados:

📋 **Dados do Cadastro**
• Empresa: {company_name}
• Contato: {contact_name}
• Telefone: {phone}
• Email: {email}
• CNPJ: {cnpj}

Os dados estão corretos? (sim/não)
            """.strip(),

            "success": """
✅ **Cadastro Concluído!**

Bem-vindo ao Frepi, {company_name}!

Agora você pode:
1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega

Como posso ajudar?
            """.strip(),
        }

        return prompts.get(step, prompts["start"])
