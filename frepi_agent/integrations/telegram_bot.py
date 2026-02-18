"""
Telegram Bot Integration for Frepi Agent.

Handles incoming messages from Telegram and routes them to the appropriate agent
based on user type (restaurant or supplier).
"""

import logging
from typing import Dict, Union
from dataclasses import dataclass, field

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from frepi_agent.config import get_config
from frepi_agent.shared.user_identification import (
    identify_user,
    UserType,
    UserIdentification,
    get_role_selection_message,
)
from frepi_agent.restaurant_facing_agent.agent import (
    chat as restaurant_chat,
    ConversationContext as RestaurantContext,
)
from frepi_agent.supplier_facing_agent.agent import (
    supplier_chat,
    SupplierConversationContext,
)
from frepi_agent.restaurant_facing_agent.subagents.onboarding_subagent.agent import (
    OnboardingContext,
    onboarding_chat,
)

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """Tracks user session information including type and context."""
    user_type: UserType = UserType.UNKNOWN
    user_id: int = None
    restaurant_id: int = None
    supplier_id: int = None
    name: str = None
    awaiting_role_selection: bool = False
    needs_onboarding: bool = False  # True if onboarding not yet completed
    onboarding_context: OnboardingContext = field(default_factory=OnboardingContext)  # GPT-4 subagent context
    restaurant_context: RestaurantContext = field(default_factory=RestaurantContext)
    supplier_context: SupplierConversationContext = field(default_factory=SupplierConversationContext)


# Store user sessions per chat_id
_sessions: Dict[int, UserSession] = {}


def get_session(chat_id: int) -> UserSession:
    """Get or create a user session for a chat."""
    if chat_id not in _sessions:
        _sessions[chat_id] = UserSession()
    return _sessions[chat_id]


def clear_session(chat_id: int):
    """Clear the user session for a chat."""
    if chat_id in _sessions:
        del _sessions[chat_id]


async def identify_and_setup_session(chat_id: int, session: UserSession) -> UserIdentification:
    """
    Identify the user and set up the session.

    Args:
        chat_id: Telegram chat ID
        session: The user session

    Returns:
        UserIdentification result
    """
    identification = await identify_user(chat_id)

    session.user_type = identification.user_type
    session.user_id = identification.user_id
    session.restaurant_id = identification.restaurant_id
    session.supplier_id = identification.supplier_id
    session.name = identification.name

    # Set up context based on user type
    if identification.user_type == UserType.RESTAURANT:
        session.restaurant_context.restaurant_id = identification.restaurant_id
        session.restaurant_context.restaurant_name = identification.name
        # Check onboarding status from database
        session.needs_onboarding = not identification.onboarding_complete
        if session.needs_onboarding:
            # Set up onboarding context for GPT-4 subagent
            session.onboarding_context.telegram_chat_id = chat_id
            session.onboarding_context.restaurant_id = identification.restaurant_id
    elif identification.user_type == UserType.SUPPLIER:
        session.supplier_context.supplier_id = identification.supplier_id
        session.supplier_context.supplier_name = identification.name

    return identification


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    chat_id = update.effective_chat.id
    clear_session(chat_id)  # Start fresh

    session = get_session(chat_id)

    # Identify the user
    identification = await identify_and_setup_session(chat_id, session)

    if identification.user_type == UserType.RESTAURANT:
        # Known restaurant user
        welcome_message = f"""👋 Olá{', ' + identification.name if identification.name else ''}! Bem-vindo ao **Frepi**!

Sou seu assistente de compras para restaurantes. Posso ajudar você a:

1️⃣ **Fazer compras** - encontrar produtos e melhores preços
2️⃣ **Atualizar preços** - registrar cotações de fornecedores
3️⃣ **Gerenciar fornecedores** - cadastrar e atualizar
4️⃣ **Configurar preferências** - personalizar suas compras

Digite qualquer mensagem para começar! 🎯"""

    elif identification.user_type == UserType.SUPPLIER:
        # Known supplier
        welcome_message = f"""👋 Olá{', ' + identification.name if identification.name else ''}! Bem-vindo ao **Frepi**!

Sou seu assistente para fornecedores. Posso ajudar você a:

1️⃣ **Ver cotações pendentes** - produtos aguardando seu preço
2️⃣ **Enviar cotação** - informar preços de produtos
3️⃣ **Confirmar pedidos** - aceitar pedidos recebidos
4️⃣ **Atualizar entregas** - status de entregas em andamento

Como posso ajudar hoje? 🚚"""

    else:
        # Unknown user - ask for role
        session.awaiting_role_selection = True
        welcome_message = get_role_selection_message()

    await update.message.reply_text(welcome_message, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command."""
    chat_id = update.effective_chat.id
    session = get_session(chat_id)

    if session.user_type == UserType.SUPPLIER:
        help_text = """🆘 **Ajuda do Frepi - Fornecedor**

**Comandos disponíveis:**
/start - Iniciar conversa
/help - Ver esta ajuda
/limpar - Limpar histórico da conversa

**Como usar:**
• Digite 1 para ver cotações pendentes
• Digite 2 para enviar uma cotação
• Digite 3 para ver pedidos a confirmar
• Digite 4 para atualizar entregas

**Dicas:**
• Informe preços no formato: R$ 42,90/kg
• Confirme pedidos informando data de entrega
• Atualize status de entregas regularmente"""
    else:
        help_text = """🆘 **Ajuda do Frepi**

**Comandos disponíveis:**
/start - Iniciar conversa
/help - Ver esta ajuda
/limpar - Limpar histórico da conversa

**Como usar:**
• Digite o que você precisa em linguagem natural
• Exemplo: "Preciso de 10kg de picanha"
• Exemplo: "Quanto custa arroz?"
• Exemplo: "Cotação do Friboi: picanha R$ 47/kg"

**Dicas:**
• Seja específico com quantidades e unidades
• Mencione o nome do fornecedor ao atualizar preços
• Use /limpar se quiser recomeçar a conversa"""

    await update.message.reply_text(help_text, parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /limpar command to clear conversation history."""
    chat_id = update.effective_chat.id
    session = get_session(chat_id)

    # Clear only the conversation context, not the user identification
    session.restaurant_context = RestaurantContext()
    session.supplier_context = SupplierConversationContext()

    # Re-setup context with user info
    if session.user_type == UserType.RESTAURANT:
        session.restaurant_context.restaurant_id = session.restaurant_id
        session.restaurant_context.restaurant_name = session.name
    elif session.user_type == UserType.SUPPLIER:
        session.supplier_context.supplier_id = session.supplier_id
        session.supplier_context.supplier_name = session.name

    await update.message.reply_text(
        "✅ Histórico limpo! Pode começar uma nova conversa.",
        parse_mode="Markdown",
    )


async def handle_role_selection(
    update: Update,
    session: UserSession,
    user_message: str,
) -> str:
    """
    Handle role selection for unknown users.

    Args:
        update: Telegram update
        session: User session
        user_message: The user's message

    Returns:
        Response message
    """
    message_lower = user_message.lower().strip()

    if message_lower in ("1", "restaurante", "restaurant"):
        session.user_type = UserType.RESTAURANT
        session.awaiting_role_selection = False
        session.needs_onboarding = True
        # Set up onboarding context for GPT-4 subagent
        session.onboarding_context.telegram_chat_id = update.effective_chat.id
        # Let the subagent handle the welcome message
        return await onboarding_chat("Olá, quero me cadastrar", session.onboarding_context)

    elif message_lower in ("2", "fornecedor", "supplier"):
        session.user_type = UserType.SUPPLIER
        session.awaiting_role_selection = False
        return """
✅ Perfeito! Você está cadastrado como **Fornecedor**.

Agora posso te ajudar com:

1️⃣ Ver pedidos de cotação pendentes
2️⃣ Enviar cotação de preços
3️⃣ Confirmar pedido recebido
4️⃣ Atualizar status de entrega

Como posso ajudar? 🚚
        """.strip()

    else:
        return """
Por favor, escolha uma opção:

1️⃣ **Restaurante** - Quero comprar produtos
2️⃣ **Fornecedor** - Quero fornecer produtos

Digite 1 ou 2 para continuar.
        """.strip()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages with routing based on user type."""
    chat_id = update.effective_chat.id
    user_message = update.message.text

    logger.info(f"")
    logger.info(f"{'='*60}")
    logger.info(f"📨 INCOMING MESSAGE from chat_id={chat_id}")
    logger.info(f"   Text: {user_message}")
    logger.info(f"{'='*60}")

    # Get or create session
    session = get_session(chat_id)
    logger.info(f"   Session: user_type={session.user_type}, needs_onboarding={session.needs_onboarding}, awaiting_role={session.awaiting_role_selection}")

    # If this is the first message, identify the user
    if session.user_type == UserType.UNKNOWN and not session.awaiting_role_selection:
        logger.info(f"   🔍 Identifying user...")
        await identify_and_setup_session(chat_id, session)
        logger.info(f"   ✅ Identified: user_type={session.user_type}, needs_onboarding={session.needs_onboarding}")

        # If still unknown after identification, prompt for role
        if session.user_type == UserType.UNKNOWN:
            session.awaiting_role_selection = True

    try:
        # Send typing indicator
        await update.message.chat.send_action("typing")

        # Handle based on user type
        if session.awaiting_role_selection:
            # User needs to select their role
            logger.info(f"   🚦 ROUTING → Role Selection")
            response = await handle_role_selection(update, session, user_message)

        elif session.user_type == UserType.RESTAURANT:
            # Check if onboarding is needed
            if session.needs_onboarding:
                # Route to GPT-4 onboarding subagent
                logger.info(f"   🚦 ROUTING → Onboarding Subagent (GPT-4)")
                response = await onboarding_chat(user_message, session.onboarding_context)
                # Check if onboarding completed
                if session.onboarding_context.onboarding_complete:
                    session.needs_onboarding = False
                    # Transfer info to restaurant context
                    session.restaurant_context.restaurant_name = session.onboarding_context.restaurant_name
                    logger.info(f"   ✅ Onboarding completed!")
            else:
                # Route to main restaurant agent
                logger.info(f"   🚦 ROUTING → Main Restaurant Agent")
                if update.effective_user:
                    session.restaurant_context.person_name = update.effective_user.first_name

                response = await restaurant_chat(user_message, session.restaurant_context)

        elif session.user_type == UserType.SUPPLIER:
            # Route to supplier agent
            response = await supplier_chat(user_message, session.supplier_context)

        else:
            # Fallback - shouldn't happen
            session.awaiting_role_selection = True
            response = get_role_selection_message()

        # Send response (split if too long)
        if len(response) > 4096:
            # Split into chunks
            for i in range(0, len(response), 4096):
                chunk = response[i:i + 4096]
                await update.message.reply_text(chunk, parse_mode="Markdown")
        else:
            await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Desculpe, ocorreu um erro ao processar sua mensagem. "
            "Por favor, tente novamente.",
            parse_mode="Markdown",
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photo messages (for invoice uploads)."""
    chat_id = update.effective_chat.id
    session = get_session(chat_id)

    # Only process photos during onboarding (the subagent handles when photos are relevant)
    if not session.needs_onboarding:
        await update.message.reply_text(
            "📷 Recebi sua foto! No momento só processo fotos durante o cadastro inicial. "
            "Use /start para recomeçar se precisar enviar notas fiscais.",
            parse_mode="Markdown",
        )
        return

    try:
        # Get the largest photo (best quality)
        photo = update.message.photo[-1]
        file_id = photo.file_id

        # Get the file URL from Telegram
        file = await context.bot.get_file(file_id)
        file_url = file.file_path

        # Store the photo URL in the onboarding context
        session.onboarding_context.uploaded_photos.append(file_url)

        photo_count = len(session.onboarding_context.uploaded_photos)
        await update.message.reply_text(
            f"📸 Foto {photo_count} recebida!\n\n"
            f"Envie mais fotos ou digite **\"pronto\"** quando terminar.",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error handling photo: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Erro ao processar a foto. Por favor, tente novamente.",
            parse_mode="Markdown",
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")


async def _post_init(application: Application):
    """Called after the application is initialized (inside the event loop)."""
    try:
        from frepi_agent.services.heartbeat import init_heartbeat
        init_heartbeat(application.bot)
        logger.info("🔔 Heartbeat scheduler started")
    except Exception as e:
        logger.warning(f"Heartbeat setup failed (continuing without): {e}")


def create_application() -> Application:
    """Create and configure the Telegram application."""
    config = get_config()

    if not config.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not configured")

    # Create application with post_init for heartbeat (needs running event loop)
    application = Application.builder().token(config.telegram_bot_token).post_init(_post_init).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ajuda", help_command))
    application.add_handler(CommandHandler("limpar", clear_command))
    application.add_handler(CommandHandler("clear", clear_command))

    # Message handler for text messages
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Photo handler for invoice uploads
    application.add_handler(
        MessageHandler(filters.PHOTO, handle_photo)
    )

    # Error handler
    application.add_error_handler(error_handler)

    return application


def run_polling():
    """Run the bot using polling (for development)."""
    logger.info("Starting Frepi Telegram bot (polling mode)...")

    application = create_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)


async def run_webhook(webhook_url: str, port: int = 8443):
    """Run the bot using webhooks (for production)."""
    logger.info(f"Starting Frepi Telegram bot (webhook mode) on port {port}...")

    application = create_application()

    # Set webhook
    await application.bot.set_webhook(url=webhook_url)

    # Start webhook server
    await application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=webhook_url,
    )
