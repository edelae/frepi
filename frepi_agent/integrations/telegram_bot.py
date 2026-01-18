"""
Telegram Bot Integration for Frepi Agent.

Handles incoming messages from Telegram and routes them to the agent.
"""

import logging
from typing import Dict

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from frepi_agent.config import get_config
from frepi_agent.agent import chat, ConversationContext

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Store conversation contexts per chat_id
_contexts: Dict[int, ConversationContext] = {}


def get_context(chat_id: int) -> ConversationContext:
    """Get or create a conversation context for a chat."""
    if chat_id not in _contexts:
        _contexts[chat_id] = ConversationContext()
    return _contexts[chat_id]


def clear_context(chat_id: int):
    """Clear the conversation context for a chat."""
    if chat_id in _contexts:
        del _contexts[chat_id]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    chat_id = update.effective_chat.id
    clear_context(chat_id)  # Start fresh

    welcome_message = """👋 Olá! Bem-vindo ao **Frepi**!

Sou seu assistente de compras para restaurantes. Posso ajudar você a:

1️⃣ **Fazer compras** - encontrar produtos e melhores preços
2️⃣ **Atualizar preços** - registrar cotações de fornecedores
3️⃣ **Gerenciar fornecedores** - cadastrar e atualizar
4️⃣ **Configurar preferências** - personalizar suas compras

Digite qualquer mensagem para começar! 🎯"""

    await update.message.reply_text(welcome_message, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command."""
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
    clear_context(chat_id)
    await update.message.reply_text(
        "✅ Histórico limpo! Pode começar uma nova conversa.",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    chat_id = update.effective_chat.id
    user_message = update.message.text

    logger.info(f"Message from {chat_id}: {user_message[:50]}...")

    # Get conversation context
    conv_context = get_context(chat_id)

    # Store user info in context if available
    if update.effective_user:
        conv_context.person_name = update.effective_user.first_name

    try:
        # Send typing indicator
        await update.message.chat.send_action("typing")

        # Get response from agent
        response = await chat(user_message, conv_context)

        # Send response (split if too long)
        if len(response) > 4096:
            # Split into chunks
            for i in range(0, len(response), 4096):
                chunk = response[i:i + 4096]
                await update.message.reply_text(chunk, parse_mode="Markdown")
        else:
            await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text(
            "❌ Desculpe, ocorreu um erro ao processar sua mensagem. "
            "Por favor, tente novamente.",
            parse_mode="Markdown",
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")


def create_application() -> Application:
    """Create and configure the Telegram application."""
    config = get_config()

    if not config.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not configured")

    # Create application
    application = Application.builder().token(config.telegram_bot_token).build()

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
