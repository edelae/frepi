"""Onboarding Subagent - New user registration flow.

This subagent handles:
- Detection of new users (telegram_chat_id not in database)
- Restaurant vs Supplier registration choice
- Basic info collection (name, contact, address, city, cuisine type)
- Invoice photo upload and processing
- Top 10 product preference configuration

Triggers:
- Automatic: New user detected
- Menu option 3: Register/Update supplier
- Menu option 4: Configure preferences
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class OnboardingState:
    """Tracks the current state of the onboarding flow."""

    phase: str = "detection"  # detection, basic_info, invoices, preferences, complete
    restaurant_id: Optional[int] = None
    person_id: Optional[int] = None
    invoices_processed: int = 0
    preferences_configured: int = 0


class OnboardingSubagent:
    """Subagent for handling new user onboarding."""

    def __init__(self, supabase_client, openai_client):
        self.supabase = supabase_client
        self.openai = openai_client
        self.state = OnboardingState()

    async def is_new_user(self, telegram_chat_id: int) -> bool:
        """Check if the telegram_chat_id exists in telegram_users table."""
        # TODO: Implement database check
        pass

    async def start_onboarding(self, telegram_chat_id: int) -> str:
        """Begin the onboarding flow for a new user."""
        # TODO: Implement onboarding start
        pass

    async def collect_basic_info(self, user_input: str) -> str:
        """Collect basic restaurant information."""
        # TODO: Implement basic info collection
        pass

    async def process_invoice_photo(self, photo_url: str) -> dict:
        """Process an invoice photo using GPT-4 Vision."""
        # TODO: Implement invoice processing
        pass

    async def configure_product_preference(self, product_id: int, preferences: dict) -> str:
        """Configure preferences for a specific product."""
        # TODO: Implement preference configuration
        pass

    async def complete_onboarding(self) -> str:
        """Finalize the onboarding process."""
        # TODO: Implement onboarding completion
        pass
