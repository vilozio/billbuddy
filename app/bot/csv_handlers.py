"""Telegram handlers for CSV statement processing and the scenario setup wizard."""

import os
import re
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import (
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
(
    ASK_PATTERN,
    ASK_NAME,
    ASK_TRANSFORM,
    CONFIRM_TRANSFORM,
    ASK_DESTINATION,
    ASK_SPREADSHEET,
    ASK_SHEET_TAB,
    ASK_SCENARIO_CHOICE,
) = range(8)

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

    matches = scenario_store.find_matches(filename)
    # /add_scenario sets this so we always create a new scenario for this file.
    force_new = context.user_data.pop("force_new_scenario", False)

    # Auto-process / choose only when NOT explicitly adding a new scenario.
    if matches and not force_new:
        if len(matches) == 1:
            scenario = matches[0]
            status = await update.message.reply_text(
                f"📥 Recognized this as *{scenario.name}*. Processing…",
                parse_mode="Markdown",
            )
            summary = statement_processor.process(
                str(file_path), filename, scenario, user_id=user.id
            )
            _cleanup(str(file_path))
            await status.edit_text(
                summary or "❌ Failed to process this file.", parse_mode="Markdown"
            )
            return ConversationHandler.END

        # Several scenarios share this pattern -> ask which one.
        context.user_data["csv"] = {
            "file_path": str(file_path),
            "filename": filename,
            "headers": read_headers(str(file_path), has_header=True),
            "has_header": True,
            "candidates": matches,
        }
        lines = ["🔀 This file matches several scenarios. Which should I run?"]
        for i, s in enumerate(matches, 1):
            lines.append(f"{i}. *{s.name}* → {s.destination_summary()}")
        lines.append(f"{len(matches) + 1}. ➕ Create a new scenario for this file")
        lines.append("\nReply with a number. /cancel to abort.")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return ASK_SCENARIO_CHOICE

    # Otherwise we're creating a new scenario (new pattern, or /add_scenario).
    context.user_data["csv"] = {
        "file_path": str(file_path),
        "filename": filename,
        "headers": read_headers(str(file_path), has_header=True),
        "has_header": True,
    }

    if force_new and matches:
        # Reuse the existing pattern; skip straight to naming the new scenario.
        pattern = matches[0].filename_pattern
        context.user_data["csv"]["pattern"] = pattern
        context.user_data["csv"]["pattern_regex"] = matches[0].pattern_regex
        await update.message.reply_text(
            f"➕ Adding a new scenario for the existing pattern:\n`{pattern}`",
            parse_mode="Markdown",
        )
        return await _begin_name_step(update, context)

    # Brand-new pattern.
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


async def choose_scenario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Multiple scenarios matched: run the chosen one, or start a new scenario."""
    text = update.message.text.strip()
    data = context.user_data["csv"]
    candidates = data["candidates"]

    if text.isdigit() and 1 <= int(text) <= len(candidates) + 1:
        choice = int(text)
        if choice <= len(candidates):
            scenario = candidates[choice - 1]
            status = await update.message.reply_text(
                f"Processing with *{scenario.name}*…", parse_mode="Markdown"
            )
            summary = statement_processor.process(
                data["file_path"], data["filename"], scenario,
                user_id=update.effective_user.id,
            )
            _cleanup(data["file_path"])
            context.user_data.pop("csv", None)
            await status.edit_text(
                summary or "❌ Failed to process this file.", parse_mode="Markdown"
            )
            return ConversationHandler.END

        # Last option: create a new scenario reusing this pattern.
        data["pattern"] = candidates[0].filename_pattern
        data["pattern_regex"] = candidates[0].pattern_regex
        return await _begin_name_step(update, context)

    await update.message.reply_text(
        f"Please reply with a number between 1 and {len(candidates) + 1}."
    )
    return ASK_SCENARIO_CHOICE


async def ask_pattern(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: confirm or edit the filename pattern."""
    data = context.user_data["csv"]
    text = update.message.text.strip()
    pattern = data["suggested_pattern"] if text.lower() in ("ok", "/ok") else text
    data["pattern"] = pattern
    data["pattern_regex"] = filename_matcher.compile_pattern(pattern)
    await update.message.reply_text(
        f"Pattern saved: `{pattern}`", parse_mode="Markdown"
    )
    return await _begin_name_step(update, context)


async def _begin_name_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for a scenario name (used to tell scenarios of one pattern apart)."""
    data = context.user_data["csv"]
    suggestion = _default_name(data["pattern"])
    data["suggested_name"] = suggestion
    await update.message.reply_text(
        "*2. Scenario name* — used to pick this scenario when a file matches "
        "more than one.\n"
        f"Suggested: `{suggestion}`\n"
        "Send *ok* to accept, or type a name.",
        parse_mode="Markdown",
    )
    return ASK_NAME


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Capture the scenario name, then move on to the transformation step."""
    data = context.user_data["csv"]
    text = update.message.text.strip()
    data["name"] = data["suggested_name"] if text.lower() in ("ok", "/ok") else text

    cols = ", ".join(data["headers"])
    await update.message.reply_text(
        f"*3. Transformations* — the file has these columns:\n`{cols}`\n\n"
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

    await update.message.reply_text(
        "*3. Destination* — where should the result go?\n"
        "Reply with one of: *sheet*, *drive*, or *both*.",
        parse_mode="Markdown",
    )
    return ASK_DESTINATION


async def choose_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 4: parse the destination choice (sheet / drive / both)."""
    choice = update.message.text.strip().lower()
    if choice not in ("sheet", "drive", "both"):
        await update.message.reply_text(
            "Please reply with one of: *sheet*, *drive*, or *both*.",
            parse_mode="Markdown",
        )
        return ASK_DESTINATION

    data = context.user_data["csv"]
    data["dest_sheet"] = choice in ("sheet", "both")
    data["dest_drive"] = choice in ("drive", "both")

    if data["dest_sheet"]:
        return await _prompt_spreadsheet(update, context)

    # Drive only — no further input needed.
    return await _finalize(update, context)


def _extract_spreadsheet_id(text: str):
    """Pull a spreadsheet id out of a Google Sheets URL or a raw id, else None."""
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9-_]+)", text) or re.search(
        r"/d/([A-Za-z0-9-_]+)", text
    )
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9-_]{20,}", text):
        return text
    return None


async def _prompt_spreadsheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask which spreadsheet to append to, offering previously-used ones."""
    known = scenario_store.list_known_sheets()
    context.user_data["csv"]["known_sheets"] = known

    lines = ["*Which spreadsheet should I append to?*"]
    if known:
        for i, (_sid, label) in enumerate(known, 1):
            lines.append(f"{i}. {label}")
        lines.append(
            "\nReply with a number, paste a spreadsheet link/ID, "
            "or send `new <Title>` to create one."
        )
    else:
        lines.append(
            "Paste a spreadsheet link or ID, or send `new <Title>` to create one."
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    return ASK_SPREADSHEET


async def choose_spreadsheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resolve the spreadsheet choice (saved entry / pasted link-ID / new)."""
    text = update.message.text.strip()
    data = context.user_data["csv"]
    known = data.get("known_sheets", [])

    ssid = None
    label = None

    if text.lower().startswith("new "):
        title = text[4:].strip() or "BillBuddy Statements"
        try:
            ssid = statement_processor.create_spreadsheet(title)
            label = title
        except Exception as e:
            logger.error(f"Failed to create spreadsheet: {e}", exc_info=True)
            await update.message.reply_text(
                "⚠️ Couldn't create that spreadsheet. Try again, or paste an existing link/ID."
            )
            return ASK_SPREADSHEET
    elif text.isdigit() and 1 <= int(text) <= len(known):
        ssid, label = known[int(text) - 1]
    else:
        ssid = _extract_spreadsheet_id(text)
        if ssid:
            try:
                label = statement_processor.get_spreadsheet_title(ssid)
            except Exception as e:
                logger.warning(f"Couldn't read spreadsheet title for {ssid}: {e}")
                label = ssid

    if not ssid:
        await update.message.reply_text(
            "I couldn't read that. Reply with a number from the list, "
            "a spreadsheet link/ID, or `new <Title>`.",
            parse_mode="Markdown",
        )
        return ASK_SPREADSHEET

    data["sheet_spreadsheet_id"] = ssid
    scenario_store.add_known_sheet(ssid, label or ssid)

    await update.message.reply_text(
        f"Using *{label or ssid}*.\n\n"
        "Which *tab* should I append rows to? Send the tab name.",
        parse_mode="Markdown",
    )
    return ASK_SHEET_TAB


async def ask_sheet_tab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 4b: capture the sheet tab name, then finalize."""
    context.user_data["csv"]["sheet_tab"] = update.message.text.strip()
    return await _finalize(update, context)


async def _finalize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Persist the scenario and immediately process the file that started the wizard."""
    import json

    data = context.user_data["csv"]
    drive_folder = Config.STATEMENTS_DRIVE_FOLDER_ID or Config.GOOGLE_DRIVE_FOLDER_ID
    # The spreadsheet chosen during setup; fall back to env config only if unset.
    sheet_id = (
        data.get("sheet_spreadsheet_id")
        or Config.STATEMENTS_SHEET_ID
        or Config.GOOGLE_SHEET_ID
    )

    scenario = Scenario(
        name=data.get("name") or _default_name(data["pattern"]),
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

    summary = statement_processor.process(
        data["file_path"], data["filename"], scenario, user_id=update.effective_user.id
    )
    _cleanup(data["file_path"])
    context.user_data.pop("csv", None)

    # If other scenarios already share this pattern, future files will prompt a choice.
    shares_pattern = len(scenario_store.find_matches(data["filename"])) > 1
    follow_up = (
        "Future matching files will let you choose among the scenarios for this pattern."
        if shares_pattern
        else "Future matching files are processed automatically."
    )
    await update.message.reply_text(
        f"✅ Scenario *{scenario.name}* saved. {follow_up}\n\n"
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
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_TRANSFORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_transform)],
            CONFIRM_TRANSFORM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_transform)
            ],
            ASK_DESTINATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_destination)],
            ASK_SPREADSHEET: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_spreadsheet)],
            ASK_SHEET_TAB: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_sheet_tab)],
            ASK_SCENARIO_CHOICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_scenario)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
