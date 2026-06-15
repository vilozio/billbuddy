"""Telegram handlers for CSV statement processing and the scenario setup wizard."""

import os
from datetime import datetime
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.config import Config
from app.models.scenario import Scenario
from app.services import filename_matcher, scenario_store
from app.services.csv_transformer import read_headers
from app.services.statement_processor import StatementProcessor, TEMP_DIR
from app.services.transform_ai_service import TransformAIService, describe_transform
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)

# Conversation states
ASK_PATTERN, ASK_TRANSFORM, CONFIRM_TRANSFORM, ASK_DESTINATION, ASK_SHEET_TAB = range(5)

statement_processor = StatementProcessor()
transform_ai = None  # lazily initialized (avoids needing OPENAI key just to import)


def _ai() -> TransformAIService:
    global transform_ai
    if transform_ai is None:
        transform_ai = TransformAIService()
    return transform_ai


def _default_name(pattern: str) -> str:
    """Derive a scenario name from the literal prefix of a pattern."""
    prefix = pattern.split("{", 1)[0].strip("_-. ")
    return prefix or pattern


async def on_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: a CSV document was uploaded."""
    user = update.effective_user
    document = update.message.document
    filename = document.file_name
    logger.info(f"Received CSV from user {user.id}: {filename}")

    file = await context.bot.get_file(document.file_id)
    file_path = TEMP_DIR / f"{user.id}_{document.file_id}.csv"
    await file.download_to_drive(str(file_path))

    # Already known file kind? Process automatically, no questions.
    scenario = scenario_store.find_matching(filename)
    if scenario:
        status = await update.message.reply_text(
            f"📥 Recognized this as *{scenario.name}*. Processing…",
            parse_mode="Markdown",
        )
        summary = statement_processor.process(str(file_path), filename, scenario)
        _cleanup(str(file_path))
        await status.edit_text(
            summary or "❌ Failed to process this file.", parse_mode="Markdown"
        )
        return ConversationHandler.END

    # New kind of file -> start the setup wizard.
    headers = read_headers(str(file_path), has_header=True)
    context.user_data["csv"] = {
        "file_path": str(file_path),
        "filename": filename,
        "headers": headers,
        "has_header": True,
    }
    suggestion = filename_matcher.suggest_pattern(filename)
    context.user_data["csv"]["suggested_pattern"] = suggestion

    await update.message.reply_text(
        "🆕 I haven't seen this kind of file before. Let's set it up.\n\n"
        "*1. Filename pattern* — how should I recognize this file again?\n"
        f"Suggested:\n`{suggestion}`\n\n"
        "Placeholders: `{date}` = YYYY-MM-DD, `{any}` = any token.\n"
        "Send *ok* to accept, or type your own pattern. /cancel to abort.",
        parse_mode="Markdown",
    )
    return ASK_PATTERN


async def ask_pattern(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: confirm or edit the filename pattern."""
    data = context.user_data["csv"]
    text = update.message.text.strip()
    pattern = data["suggested_pattern"] if text.lower() in ("ok", "/ok") else text
    data["pattern"] = pattern
    data["pattern_regex"] = filename_matcher.compile_pattern(pattern)

    cols = ", ".join(data["headers"])
    await update.message.reply_text(
        f"Pattern saved: `{pattern}`\n\n"
        f"*2. Transformations* — the file has these columns:\n`{cols}`\n\n"
        "Describe what to do in plain language, e.g.\n"
        "_keep Completed Date and Amount, rename Completed Date to Date_.",
        parse_mode="Markdown",
    )
    return ASK_TRANSFORM


async def ask_transform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2: turn the instruction into a proposed transform schema."""
    data = context.user_data["csv"]
    instruction = update.message.text.strip()
    try:
        schema = _ai().propose_transform(data["headers"], instruction)
    except Exception as e:
        logger.error(f"AI transform proposal failed: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ I couldn't interpret that. Please rephrase the transformation."
        )
        return ASK_TRANSFORM

    data["transform"] = schema
    await update.message.reply_text(
        describe_transform(schema)
        + "\n\nSend *yes* to confirm, or type a new instruction to refine.",
        parse_mode="Markdown",
    )
    return CONFIRM_TRANSFORM


async def confirm_transform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 3: confirm the mapping, or treat input as a refined instruction."""
    text = update.message.text.strip()
    if text.lower() not in ("yes", "/yes"):
        return await ask_transform(update, context)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Sheet tab", callback_data="dest:sheet"),
                InlineKeyboardButton("Drive folder", callback_data="dest:drive"),
                InlineKeyboardButton("Both", callback_data="dest:both"),
            ]
        ]
    )
    await update.message.reply_text(
        "*3. Destination* — where should the result go?", parse_mode="Markdown", reply_markup=keyboard
    )
    return ASK_DESTINATION


async def choose_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 4: handle the destination button choice."""
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    data = context.user_data["csv"]
    data["dest_sheet"] = choice in ("sheet", "both")
    data["dest_drive"] = choice in ("drive", "both")

    if data["dest_sheet"]:
        await query.edit_message_text(
            "Which Google Sheet *tab* should I append rows to? Send the tab name.",
            parse_mode="Markdown",
        )
        return ASK_SHEET_TAB

    # Drive only — no further input needed.
    await query.edit_message_text("Setting up…")
    return await _finalize(update, context)


async def ask_sheet_tab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 4b: capture the sheet tab name, then finalize."""
    context.user_data["csv"]["sheet_tab"] = update.message.text.strip()
    return await _finalize(update, context)


async def _finalize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Persist the scenario and immediately process the file that started the wizard."""
    import json

    data = context.user_data["csv"]
    drive_folder = Config.STATEMENTS_DRIVE_FOLDER_ID or Config.GOOGLE_DRIVE_FOLDER_ID
    sheet_id = Config.STATEMENTS_SHEET_ID or Config.GOOGLE_SHEET_ID

    scenario = Scenario(
        name=_default_name(data["pattern"]),
        filename_pattern=data["pattern"],
        pattern_regex=data["pattern_regex"],
        transform_json=json.dumps(data["transform"]),
        has_header=data["has_header"],
        dest_sheet=data.get("dest_sheet", False),
        sheet_spreadsheet_id=sheet_id if data.get("dest_sheet") else None,
        sheet_tab=data.get("sheet_tab"),
        dest_drive=data.get("dest_drive", False),
        drive_folder_id=drive_folder if data.get("dest_drive") else None,
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
    scenario_store.add_scenario(scenario)

    # The message object differs between a callback and a text reply.
    reply_target = update.message or update.callback_query.message
    summary = statement_processor.process(data["file_path"], data["filename"], scenario)
    _cleanup(data["file_path"])
    context.user_data.pop("csv", None)

    await reply_target.reply_text(
        f"✅ Scenario *{scenario.name}* saved. Future matching files are processed automatically.\n\n"
        + (summary or "❌ Failed to process this file."),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abort the wizard."""
    data = context.user_data.pop("csv", None)
    if data:
        _cleanup(data.get("file_path"))
    await update.message.reply_text("Setup cancelled.")
    return ConversationHandler.END


def _cleanup(file_path):
    if not file_path:
        return
    try:
        os.remove(file_path)
    except OSError:
        pass


def build_csv_conversation() -> ConversationHandler:
    """Construct the ConversationHandler for CSV upload + scenario setup."""
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Document.FileExtension("csv"), on_csv)
        ],
        states={
            ASK_PATTERN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_pattern)],
            ASK_TRANSFORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_transform)],
            CONFIRM_TRANSFORM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_transform)
            ],
            ASK_DESTINATION: [CallbackQueryHandler(choose_destination, pattern=r"^dest:")],
            ASK_SHEET_TAB: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_sheet_tab)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
