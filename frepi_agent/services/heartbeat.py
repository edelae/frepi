"""
Heartbeat Service: Scheduled proactive checks using APScheduler.

Runs periodic tasks for the procurement agent:
- Stale price alerts
- Unconfirmed order follow-up
- Overdue delivery tracking
- Post-delivery feedback collection
- Weekly preference drip questions

Sends notifications via Telegram.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from frepi_agent.config import get_config
from frepi_agent.shared.supabase_client import (
    get_supabase_client,
    fetch_many,
    Tables,
)

logger = logging.getLogger(__name__)

# Global scheduler
_scheduler: AsyncIOScheduler = None
_telegram_bot = None


def init_heartbeat(telegram_bot):
    """Initialize the heartbeat scheduler with a Telegram bot instance."""
    global _scheduler, _telegram_bot
    _telegram_bot = telegram_bot

    _scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")

    # Job 1: Stale price alerts - daily at 8am BRT
    _scheduler.add_job(
        _check_stale_prices,
        CronTrigger(hour=8, timezone="America/Sao_Paulo"),
        id="stale_prices",
        name="Stale Price Check",
    )

    # Job 2: Unconfirmed orders - every 2 hours, 8am-8pm BRT
    _scheduler.add_job(
        _check_unconfirmed_orders,
        IntervalTrigger(hours=2),
        id="unconfirmed_orders",
        name="Unconfirmed Order Check",
    )

    # Job 3: Overdue deliveries - every 4 hours, 7am-9pm BRT
    _scheduler.add_job(
        _check_overdue_deliveries,
        IntervalTrigger(hours=4),
        id="overdue_deliveries",
        name="Overdue Delivery Check",
    )

    # Job 4: Delivery feedback - daily at 5pm BRT
    _scheduler.add_job(
        _request_delivery_feedback,
        CronTrigger(hour=17, timezone="America/Sao_Paulo"),
        id="delivery_feedback",
        name="Delivery Feedback Request",
    )

    # Job 5: Preference drip - weekly Monday 9am BRT
    _scheduler.add_job(
        _drip_preference_reminder,
        CronTrigger(day_of_week="mon", hour=9, timezone="America/Sao_Paulo"),
        id="preference_drip",
        name="Preference Drip Reminder",
    )

    _scheduler.start()
    logger.info("Heartbeat scheduler started with 5 jobs")


def stop_heartbeat():
    """Stop the heartbeat scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        _scheduler = None
        logger.info("Heartbeat scheduler stopped")


async def _get_restaurant_chat_ids() -> dict[int, list[str]]:
    """
    Get Telegram chat IDs for all active restaurant users.

    Returns:
        dict mapping restaurant_id -> list of chat_id strings
    """
    people = await fetch_many(Tables.RESTAURANT_PEOPLE)
    result: dict[int, list[str]] = {}
    for person in people:
        rid = person.get("restaurant_id")
        chat_id = person.get("whatsapp_number")  # stores Telegram chat_id as string
        if rid and chat_id:
            result.setdefault(rid, []).append(chat_id)
    return result


async def _send_telegram_message(chat_id, message: str):
    """Send a Telegram message using the bot instance."""
    if _telegram_bot:
        try:
            await _telegram_bot.send_message(
                chat_id=int(chat_id),
                text=message,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
    else:
        logger.warning(f"No Telegram bot configured for heartbeat message to {chat_id}")


async def _check_stale_prices():
    """Job 1: Alert restaurants about products with outdated pricing (>30 days)."""
    try:
        config = get_config()
        freshness_days = config.price_freshness_days
        client = get_supabase_client()

        # Get all current prices (end_date IS NULL)
        pricing_result = (
            client.table(Tables.PRICING_HISTORY)
            .select("id, effective_date, supplier_mapped_product_id")
            .is_("end_date", "null")
            .execute()
        )

        if not pricing_result.data:
            return

        now = datetime.now()
        stale_smp_ids = []

        for price in pricing_result.data:
            effective = datetime.fromisoformat(
                price["effective_date"].replace("Z", "+00:00")
            ).replace(tzinfo=None)
            days_old = (now - effective).days
            if days_old > freshness_days:
                stale_smp_ids.append(price["supplier_mapped_product_id"])

        if not stale_smp_ids:
            return

        # Get product names for stale prices
        smp_result = (
            client.table(Tables.SUPPLIER_MAPPED_PRODUCTS)
            .select("id, master_list_id, supplier_id")
            .in_("id", stale_smp_ids)
            .execute()
        )

        if not smp_result.data:
            return

        ml_ids = list(set(row["master_list_id"] for row in smp_result.data))
        ml_result = (
            client.table(Tables.MASTER_LIST)
            .select("id, product_name, restaurant_id")
            .in_("id", ml_ids)
            .execute()
        )

        if not ml_result.data:
            return

        # Group stale products by restaurant
        ml_map = {row["id"]: row for row in ml_result.data}
        stale_by_restaurant: dict[int, list[str]] = {}

        for smp in smp_result.data:
            ml = ml_map.get(smp["master_list_id"])
            if ml:
                rid = ml["restaurant_id"]
                product_name = ml["product_name"]
                stale_by_restaurant.setdefault(rid, []).append(product_name)

        # Send alerts
        chat_ids_map = await _get_restaurant_chat_ids()

        for rid, products in stale_by_restaurant.items():
            chat_ids = chat_ids_map.get(rid, [])
            if not chat_ids:
                continue

            unique_products = sorted(set(products))[:10]  # Cap at 10
            product_list = "\n".join(f"  • {p}" for p in unique_products)
            extra = ""
            if len(set(products)) > 10:
                extra = f"\n  ... e mais {len(set(products)) - 10} produtos"

            message = (
                f"⚠️ *Alerta de Preços Desatualizados*\n\n"
                f"{len(set(products))} produto(s) com preços há mais de {freshness_days} dias:\n\n"
                f"{product_list}{extra}\n\n"
                f"Digite 2️⃣ para atualizar preços."
            )

            for chat_id in chat_ids:
                await _send_telegram_message(chat_id, message)

        logger.info(f"Stale price check complete: {len(stale_by_restaurant)} restaurants alerted")

    except Exception as e:
        logger.error(f"Error in stale price check: {e}")


async def _check_unconfirmed_orders():
    """Job 2: Remind restaurants about orders sent >24h ago without supplier confirmation."""
    now = datetime.now()
    if now.hour < 8 or now.hour > 20:
        return  # Only during business hours

    try:
        client = get_supabase_client()
        cutoff = (now - timedelta(hours=24)).isoformat()

        # Get orders that are still 'sent' and older than 24h
        orders_result = (
            client.table(Tables.PURCHASE_ORDERS)
            .select("id, restaurant_id, supplier_id, created_at, order_summary")
            .eq("status", "sent")
            .lt("created_at", cutoff)
            .execute()
        )

        if not orders_result.data:
            return

        # Get supplier names
        supplier_ids = list(set(o["supplier_id"] for o in orders_result.data if o.get("supplier_id")))
        suppliers_map = {}
        if supplier_ids:
            suppliers_result = (
                client.table(Tables.SUPPLIERS)
                .select("id, company_name")
                .in_("id", supplier_ids)
                .execute()
            )
            suppliers_map = {s["id"]: s["company_name"] for s in (suppliers_result.data or [])}

        # Group by restaurant
        by_restaurant: dict[int, list[dict]] = {}
        for order in orders_result.data:
            rid = order.get("restaurant_id")
            if rid:
                by_restaurant.setdefault(rid, []).append(order)

        chat_ids_map = await _get_restaurant_chat_ids()

        for rid, orders in by_restaurant.items():
            chat_ids = chat_ids_map.get(rid, [])
            if not chat_ids:
                continue

            order_lines = []
            for o in orders[:5]:  # Cap at 5
                supplier_name = suppliers_map.get(o.get("supplier_id"), "Fornecedor")
                order_lines.append(f"  • Pedido #{o['id']} — {supplier_name}")

            order_list = "\n".join(order_lines)
            extra = ""
            if len(orders) > 5:
                extra = f"\n  ... e mais {len(orders) - 5} pedido(s)"

            message = (
                f"🔔 *Pedidos Sem Confirmação*\n\n"
                f"{len(orders)} pedido(s) enviados há mais de 24h sem confirmação:\n\n"
                f"{order_list}{extra}\n\n"
                f"Considere entrar em contato com o fornecedor."
            )

            for chat_id in chat_ids:
                await _send_telegram_message(chat_id, message)

        logger.info(f"Unconfirmed order check complete: {len(by_restaurant)} restaurants notified")

    except Exception as e:
        logger.error(f"Error in unconfirmed order check: {e}")


async def _check_overdue_deliveries():
    """Job 3: Alert restaurants about confirmed orders past expected delivery date."""
    now = datetime.now()
    if now.hour < 7 or now.hour > 21:
        return  # Only during business hours

    try:
        client = get_supabase_client()
        today = now.date().isoformat()

        # Get confirmed orders with past expected delivery date
        orders_result = (
            client.table(Tables.PURCHASE_ORDERS)
            .select("id, restaurant_id, supplier_id, expected_delivery_date, order_summary")
            .eq("status", "confirmed")
            .lt("expected_delivery_date", today)
            .execute()
        )

        if not orders_result.data:
            return

        # Get supplier info (name + phone for follow-up)
        supplier_ids = list(set(o["supplier_id"] for o in orders_result.data if o.get("supplier_id")))
        suppliers_map = {}
        if supplier_ids:
            suppliers_result = (
                client.table(Tables.SUPPLIERS)
                .select("id, company_name, contact_phone")
                .in_("id", supplier_ids)
                .execute()
            )
            suppliers_map = {s["id"]: s for s in (suppliers_result.data or [])}

        # Group by restaurant
        by_restaurant: dict[int, list[dict]] = {}
        for order in orders_result.data:
            rid = order.get("restaurant_id")
            if rid:
                by_restaurant.setdefault(rid, []).append(order)

        chat_ids_map = await _get_restaurant_chat_ids()

        for rid, orders in by_restaurant.items():
            chat_ids = chat_ids_map.get(rid, [])
            if not chat_ids:
                continue

            order_lines = []
            for o in orders[:5]:
                supplier = suppliers_map.get(o.get("supplier_id"), {})
                supplier_name = supplier.get("company_name", "Fornecedor")
                phone = supplier.get("contact_phone", "")
                phone_info = f" ({phone})" if phone else ""
                order_lines.append(
                    f"  • Pedido #{o['id']} — {supplier_name}{phone_info}"
                )

            order_list = "\n".join(order_lines)

            message = (
                f"🚨 *Entregas Atrasadas*\n\n"
                f"{len(orders)} entrega(s) com data prevista já passada:\n\n"
                f"{order_list}\n\n"
                f"Entre em contato com os fornecedores para atualização."
            )

            for chat_id in chat_ids:
                await _send_telegram_message(chat_id, message)

        logger.info(f"Overdue delivery check complete: {len(by_restaurant)} restaurants notified")

    except Exception as e:
        logger.error(f"Error in overdue delivery check: {e}")


async def _request_delivery_feedback():
    """Job 4: Ask for quality/delivery rating on recent deliveries (learning loop A1)."""
    try:
        client = get_supabase_client()
        now = datetime.now()
        cutoff = (now - timedelta(hours=48)).isoformat()

        # Get delivered orders without quality rating, delivered within last 48h
        orders_result = (
            client.table(Tables.PURCHASE_ORDERS)
            .select("id, restaurant_id, supplier_id, delivered_at")
            .eq("status", "delivered")
            .is_("quality_rating", "null")
            .gt("delivered_at", cutoff)
            .execute()
        )

        if not orders_result.data:
            return

        # Get supplier names
        supplier_ids = list(set(o["supplier_id"] for o in orders_result.data if o.get("supplier_id")))
        suppliers_map = {}
        if supplier_ids:
            suppliers_result = (
                client.table(Tables.SUPPLIERS)
                .select("id, company_name")
                .in_("id", supplier_ids)
                .execute()
            )
            suppliers_map = {s["id"]: s["company_name"] for s in (suppliers_result.data or [])}

        # Group by restaurant
        by_restaurant: dict[int, list[dict]] = {}
        for order in orders_result.data:
            rid = order.get("restaurant_id")
            if rid:
                by_restaurant.setdefault(rid, []).append(order)

        chat_ids_map = await _get_restaurant_chat_ids()

        for rid, orders in by_restaurant.items():
            chat_ids = chat_ids_map.get(rid, [])
            if not chat_ids:
                continue

            for o in orders[:3]:  # Max 3 feedback requests per day
                supplier_name = suppliers_map.get(o.get("supplier_id"), "Fornecedor")
                message = (
                    f"⭐ *Avaliação de Entrega*\n\n"
                    f"Como foi a entrega do pedido #{o['id']} ({supplier_name})?\n\n"
                    f"Avalie de 1 a 5:\n"
                    f"1️⃣ Péssima\n"
                    f"2️⃣ Ruim\n"
                    f"3️⃣ Regular\n"
                    f"4️⃣ Boa\n"
                    f"5️⃣ Excelente\n\n"
                    f"Responda com o número e um comentário opcional."
                )

                for chat_id in chat_ids:
                    await _send_telegram_message(chat_id, message)

        logger.info(f"Delivery feedback request complete: {len(by_restaurant)} restaurants asked")

    except Exception as e:
        logger.error(f"Error in delivery feedback request: {e}")


async def _drip_preference_reminder():
    """Job 5: Send next preference question from the collection queue."""
    try:
        client = get_supabase_client()

        # Get pending preference questions
        queue_result = (
            client.table(Tables.PREFERENCE_COLLECTION_QUEUE)
            .select("id, restaurant_id, question_text, product_name, preference_type")
            .eq("status", "pending")
            .order("priority", desc=True)
            .order("created_at")
            .limit(50)
            .execute()
        )

        if not queue_result.data:
            logger.debug("No pending preference questions in queue")
            return

        # Group by restaurant, take first per restaurant
        by_restaurant: dict[int, dict] = {}
        for item in queue_result.data:
            rid = item.get("restaurant_id")
            if rid and rid not in by_restaurant:
                by_restaurant[rid] = item

        chat_ids_map = await _get_restaurant_chat_ids()

        for rid, item in by_restaurant.items():
            chat_ids = chat_ids_map.get(rid, [])
            if not chat_ids:
                continue

            question = item.get("question_text", "")
            product = item.get("product_name", "")
            pref_type = item.get("preference_type", "")

            if question:
                message = (
                    f"💡 *Pergunta Rápida*\n\n"
                    f"{question}\n\n"
                    f"Sua resposta ajuda a melhorar as recomendações!"
                )
            else:
                message = (
                    f"💡 *Preferência: {product}*\n\n"
                    f"Gostaríamos de saber sua preferência de *{pref_type}* "
                    f"para *{product}*.\n\n"
                    f"Responda livremente — ex: marca, qualidade, faixa de preço."
                )

            for chat_id in chat_ids:
                await _send_telegram_message(chat_id, message)

            # Mark as sent
            client.table(Tables.PREFERENCE_COLLECTION_QUEUE).update(
                {"status": "sent", "sent_at": datetime.now().isoformat()}
            ).eq("id", item["id"]).execute()

        logger.info(f"Preference drip complete: {len(by_restaurant)} restaurants asked")

    except Exception as e:
        logger.error(f"Error in preference drip reminder: {e}")
