"""Telegram bot message handlers for receipt processing"""
import os
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

from app.services.receipt_processor import ReceiptProcessor
from app.utils.logger import setup_logger
from app.config import Config

logger = setup_logger(__name__, Config.LOG_LEVEL)

# Initialize receipt processor
receipt_processor = ReceiptProcessor()

# Create temporary directory for downloads
TEMP_DIR = Path("temp_receipts")
TEMP_DIR.mkdir(exist_ok=True)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle receipt photo messages"""
    user = update.effective_user
    logger.info(f"Received photo from user {user.id} ({user.username})")
    
    try:
        # Send processing message
        status_message = await update.message.reply_text(
            "📸 Receipt received! Processing...\n⏳ This may take 5-10 seconds."
        )
        
        # Get the largest photo size
        photo = update.message.photo[-1]
        
        # Download the photo
        file = await context.bot.get_file(photo.file_id)
        file_path = TEMP_DIR / f"{user.id}_{photo.file_id}.jpg"
        await file.download_to_drive(str(file_path))
        
        logger.info(f"Photo downloaded to: {file_path}")
        
        # Process the receipt
        receipt = receipt_processor.process_receipt(str(file_path))
        
        # Clean up temporary file
        try:
            os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to remove temporary file: {e}")
        
        # Send result to user
        if receipt:
            summary = receipt_processor.get_receipt_summary(receipt)
            await status_message.edit_text(summary)
            logger.info(f"Successfully processed receipt for user {user.id}")
        else:
            await status_message.edit_text(
                "❌ Sorry, I couldn't process this receipt.\n\n"
                "Please make sure:\n"
                "• The image is clear and readable\n"
                "• The receipt is fully visible\n"
                "• There's good lighting\n\n"
                "Try taking another photo and send it again."
            )
            logger.warning(f"Failed to process receipt for user {user.id}")
            
    except Exception as e:
        logger.error(f"Error handling photo: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ An error occurred while processing your receipt. Please try again later."
        )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle receipt document (PDF) messages"""
    user = update.effective_user
    document = update.message.document
    
    logger.info(f"Received document from user {user.id} ({user.username}): {document.file_name}")
    
    try:
        # Check if it's a PDF
        if not document.file_name.lower().endswith('.pdf'):
            await update.message.reply_text(
                "⚠️ I can only process PDF documents.\n\n"
                "For other formats, please send them as photos."
            )
            return
        
        # Check file size (Telegram bot API limit is 20MB)
        if document.file_size > 20 * 1024 * 1024:
            await update.message.reply_text(
                "⚠️ File is too large. Maximum size is 20MB.\n\n"
                "Please send a smaller file or compress the PDF."
            )
            return
        
        # Send processing message
        status_message = await update.message.reply_text(
            "📄 PDF received! Processing...\n⏳ This may take 10-15 seconds."
        )
        
        # Download the document
        file = await context.bot.get_file(document.file_id)
        file_path = TEMP_DIR / f"{user.id}_{document.file_id}.pdf"
        await file.download_to_drive(str(file_path))
        
        logger.info(f"Document downloaded to: {file_path}")
        
        # Process the receipt
        receipt = receipt_processor.process_receipt(str(file_path))
        
        # Clean up temporary file
        try:
            os.remove(file_path)
            # Also remove any temporary image files created during PDF processing
            temp_image = file_path.with_suffix('.jpg')
            if temp_image.exists():
                os.remove(temp_image)
        except Exception as e:
            logger.warning(f"Failed to remove temporary file: {e}")
        
        # Send result to user
        if receipt:
            summary = receipt_processor.get_receipt_summary(receipt)
            await status_message.edit_text(summary)
            logger.info(f"Successfully processed PDF receipt for user {user.id}")
        else:
            await status_message.edit_text(
                "❌ Sorry, I couldn't process this PDF receipt.\n\n"
                "Please make sure:\n"
                "• The PDF is readable and not corrupted\n"
                "• The receipt information is visible\n"
                "• It's an actual receipt (not a blank document)\n\n"
                "Try sending another file."
            )
            logger.warning(f"Failed to process PDF receipt for user {user.id}")
            
    except Exception as e:
        logger.error(f"Error handling document: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ An error occurred while processing your PDF. Please try again later."
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages (not commands)"""
    user = update.effective_user
    logger.info(f"Received text message from user {user.id}: {update.message.text[:50]}")
    
    message = """📸 Please send me a receipt!

I can process:
• Photos of receipts (JPG, PNG)
• PDF receipts

Just send the image or PDF directly, and I'll extract all the information for you.

Use /help to learn more."""
    
    await update.message.reply_text(message)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the bot"""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    
    if update and update.message:
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again later.\n\n"
            "If the problem persists, contact the bot administrator."
        )

