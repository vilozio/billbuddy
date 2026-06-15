"""Telegram commands for runtime settings and scenario management."""

from telegram import Update
from telegram.ext import ContextTypes

from app.config import Config
from app.services import scenario_store
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


async def receipts_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable receipt (photo/PDF) processing."""
    scenario_store.set_receipts_enabled(True)
    logger.info(f"User {update.effective_user.id} enabled receipt processing")
    await update.message.reply_text("✅ Receipt processing enabled.")


async def receipts_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable receipt (photo/PDF) processing."""
    scenario_store.set_receipts_enabled(False)
    logger.info(f"User {update.effective_user.id} disabled receipt processing")
    await update.message.reply_text(
        "🛑 Receipt processing disabled. CSV statement processing stays active."
    )


async def scenarios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List saved CSV scenarios."""
    scenarios = scenario_store.list_scenarios()
    if not scenarios:
        await update.message.reply_text(
            "No statement scenarios yet. Send a CSV file to create one."
        )
        return

    lines = ["*Saved statement scenarios:*"]
    for s in scenarios:
        lines.append(
            f"\n*#{s.id} {s.name}*\n"
            f"  pattern: `{s.filename_pattern}`\n"
            f"  → {s.destination_summary()}"
        )
    lines.append("\n\nDelete one with /delete\\_scenario <id>.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def delete_scenario_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a scenario by id: /delete_scenario <id>."""
    if not context.args:
        await update.message.reply_text("Usage: /delete_scenario <id>")
        return
    try:
        scenario_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a numeric scenario id.")
        return

    if scenario_store.delete_scenario(scenario_id):
        await update.message.reply_text(f"🗑️ Deleted scenario #{scenario_id}.")
    else:
        await update.message.reply_text(f"No scenario found with id #{scenario_id}.")
