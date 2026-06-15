"""Telegram bot commands"""
from telegram import Update
from telegram.ext import ContextTypes

from app.utils.logger import setup_logger
from app.config import Config

logger = setup_logger(__name__, Config.LOG_LEVEL)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")
    
    welcome_message = f"""👋 Welcome to BillBuddy, {user.first_name}!

I'm your personal receipt processing assistant. Here's what I can do:

📸 **Send me a receipt photo or PDF** and I will:
  • Extract all the details (date, merchant, amount, tax, items)
  • Automatically categorize the expense
  • Store the receipt in Google Drive
  • Log all information to Google Sheets

📊 **Send me a CSV statement** (bank/broker/mortgage exports) and I will:
  • Learn how to recognize this file by name (one-time setup)
  • Apply your column transformations (keep/rename/reorder)
  • Append rows to a Google Sheet tab and/or save the file to Drive
  • Process matching files automatically next time

Simply send me a photo/PDF receipt or a CSV file, and I'll take care of the rest!

💡 Use /help to see available commands."""
    
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    logger.info(f"User {update.effective_user.id} requested help")
    
    help_message = """📚 **BillBuddy Help**

**How to use:**
1. Take a photo of your receipt or have a PDF receipt ready
2. Send it to me directly in this chat
3. Wait for processing (usually takes 5-10 seconds)
4. I'll send you a summary and save everything automatically

**What I extract:**
• Date of transaction
• Merchant/store name
• Total amount
• Tax amount
• Payment method
• List of items purchased
• Automatic category (groceries, dining, etc.)

**CSV statements:**
Send a CSV file (bank/broker/mortgage statement). The first time, I'll ask:
1. A filename pattern to recognize it later (e.g. `statement_{date}_{any}.csv`)
2. How to transform the columns (just describe it in plain language)
3. Where to send the result (a Google Sheet tab and/or a Drive folder)
Matching files are then processed automatically.

**Available commands:**
/start - Start the bot and see welcome message
/help - Show this help message
/status - Check if the bot is working
/scenarios - List saved CSV statement scenarios
/delete\\_scenario <id> - Delete a saved scenario
/undo - Undo the last processed receipt or statement
/receipts\\_on - Enable receipt (photo/PDF) processing
/receipts\\_off - Disable receipt processing
/cancel - Abort the current CSV setup

**Supported formats:**
• Images: JPG, PNG, JPEG
• Documents: PDF (receipts), CSV (statements)

**Categories I use:**
• Groceries
• Dining
• Transportation
• Utilities
• Entertainment
• Healthcare
• Shopping
• Services
• Other

Need help? Contact the bot administrator."""
    
    await update.message.reply_text(help_message, parse_mode='Markdown')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    logger.info(f"User {update.effective_user.id} requested status")
    
    status_message = """✅ **Bot Status: Online**

All systems operational:
• ✅ Telegram Bot
• ✅ OpenAI API
• ✅ Google Drive
• ✅ Google Sheets

Ready to process your receipts! 📸"""
    
    await update.message.reply_text(status_message, parse_mode='Markdown')


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands"""
    logger.info(f"User {update.effective_user.id} sent unknown command: {update.message.text}")
    
    message = """❓ Unknown command.

Available commands:
/start - Start the bot
/help - Show help message
/status - Check bot status

Or simply send me a receipt photo or PDF! 📸"""
    
    await update.message.reply_text(message)

