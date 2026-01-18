"""
Frepi Agent CLI - Main entry point.

Provides CLI commands for running the agent in different modes.
"""

import asyncio
import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from frepi_agent.config import get_config
from frepi_agent.restaurant_facing_agent.agent import chat, ConversationContext, get_agent


console = Console()


@click.group()
def cli():
    """Frepi Agent - Restaurant Purchasing Assistant"""
    pass


@cli.command()
def test():
    """Test the agent configuration and connections."""
    import subprocess
    import sys
    from pathlib import Path

    script_path = Path(__file__).parent.parent / "scripts" / "test_connection.py"
    subprocess.run([sys.executable, str(script_path)])


@cli.command()
def chat_cli():
    """Start an interactive chat session with the agent."""
    asyncio.run(_chat_session())


async def _chat_session():
    """Run an interactive chat session."""
    console.print(Panel.fit(
        "[bold green]Frepi Agent[/bold green] - Assistente de Compras\n"
        "Digite 'sair' para encerrar a conversa.",
        title="🎯 Bem-vindo!",
    ))

    # Validate config
    config = get_config()
    missing = config.validate()
    if missing:
        console.print(f"[red]❌ Configuração incompleta. Faltam: {', '.join(missing)}[/red]")
        return

    # Initialize context
    context = ConversationContext(
        restaurant_name="Restaurante Teste",
        person_name="Usuário",
    )

    # Initialize agent
    try:
        agent = get_agent()
        console.print("[green]✅ Agente inicializado com sucesso![/green]\n")
    except Exception as e:
        console.print(f"[red]❌ Erro ao inicializar agente: {e}[/red]")
        return

    # Chat loop
    while True:
        try:
            user_input = console.input("[bold blue]Você:[/bold blue] ")
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("sair", "exit", "quit", "q"):
            console.print("\n[yellow]Até logo! 👋[/yellow]")
            break

        if not user_input.strip():
            continue

        try:
            with console.status("[bold green]Pensando..."):
                response = await chat(user_input, context)

            console.print()
            console.print("[bold green]Frepi:[/bold green]")
            console.print(Markdown(response))
            console.print()

        except Exception as e:
            console.print(f"[red]❌ Erro: {e}[/red]")


@cli.command()
@click.option("--message", "-m", required=True, help="Message to send to the agent")
def send(message: str):
    """Send a single message to the agent and get a response."""
    asyncio.run(_send_message(message))


async def _send_message(message: str):
    """Send a single message and print the response."""
    config = get_config()
    missing = config.validate()
    if missing:
        console.print(f"[red]❌ Configuração incompleta. Faltam: {', '.join(missing)}[/red]")
        return

    context = ConversationContext()

    try:
        with console.status("[bold green]Processando..."):
            response = await chat(message, context)

        console.print(Markdown(response))

    except Exception as e:
        console.print(f"[red]❌ Erro: {e}[/red]")


@cli.command()
def info():
    """Show configuration information."""
    config = get_config()

    console.print(Panel.fit(
        f"[bold]Modelo:[/bold] {config.chat_model}\n"
        f"[bold]Supabase:[/bold] {config.supabase_url[:30]}...\n"
        f"[bold]Telegram:[/bold] {'Configurado' if config.telegram_bot_token else 'Não configurado'}\n"
        f"[bold]Ambiente:[/bold] {config.environment}",
        title="🔧 Configuração",
    ))

    missing = config.validate()
    if missing:
        console.print(f"[yellow]⚠️ Faltam: {', '.join(missing)}[/yellow]")
    else:
        console.print("[green]✅ Configuração completa![/green]")


@cli.command()
def telegram():
    """Start the Telegram bot (polling mode for development)."""
    from frepi_agent.integrations.telegram_bot import run_polling

    config = get_config()
    if not config.telegram_bot_token:
        console.print("[red]❌ TELEGRAM_BOT_TOKEN não configurado![/red]")
        return

    console.print(Panel.fit(
        "Iniciando bot do Telegram...\n"
        "Pressione Ctrl+C para parar.",
        title="🤖 Frepi Telegram Bot",
    ))

    run_polling()


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
