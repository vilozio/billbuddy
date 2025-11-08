# BillBuddy Quick Setup Guide

Follow these steps to get BillBuddy up and running quickly.

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Additional Dependencies (for PDF support)

- **macOS**: `brew install poppler`
- **Ubuntu/Debian**: `sudo apt-get install poppler-utils`
- **Windows**: Download from [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases/)

## Step 2: Get API Credentials

### Telegram Bot Token
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the bot token

### OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create new secret key
3. Copy the API key

### Google Cloud Setup
1. Create project at [Google Cloud Console](https://console.cloud.google.com/)
2. Enable **Google Drive API** and **Google Sheets API**
3. Create service account:
   - Go to **APIs & Services** > **Credentials**
   - Click **Create Credentials** > **Service Account**
   - Download JSON key file
4. Note the service account email (looks like: `name@project.iam.gserviceaccount.com`)

## Step 3: Prepare Google Drive & Sheets

### Google Drive
1. Create a folder called "Receipts"
2. Share with service account email (Editor access)
3. Copy folder ID from URL: `https://drive.google.com/drive/folders/{FOLDER_ID}`

### Google Sheets
1. Create new spreadsheet called "Receipt Log"
2. Share with service account email (Editor access)
3. Copy sheet ID from URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`

## Step 4: Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Place Google credentials
# Save your service account JSON to credentials/service-account.json

# Edit .env file with your credentials
nano .env  # or use your favorite editor
```

Fill in:
- `TELEGRAM_BOT_TOKEN` - from BotFather
- `OPENAI_API_KEY` - from OpenAI Platform
- `GOOGLE_CREDENTIALS_PATH` - path to JSON file (e.g., `credentials/service-account.json`)
- `GOOGLE_DRIVE_FOLDER_ID` - from Drive folder URL
- `GOOGLE_SHEET_ID` - from Sheets URL

## Step 5: Run the Bot

### Option 1: Direct Python
```bash
python app/main.py
```

### Option 2: Using run script (Unix/Mac)
```bash
./run.sh
```

## Step 6: Test the Bot

1. Open Telegram
2. Search for your bot
3. Send `/start`
4. Send a receipt photo or PDF
5. Wait for processing
6. Check Google Drive and Sheets!

## Troubleshooting

### "Configuration error: Missing required environment variables"
- Check your `.env` file has all required values
- Make sure there are no extra spaces or quotes

### "Failed to initialize Google Drive/Sheets service"
- Verify credentials file path is correct
- Check if service account has access to Drive folder and Sheet
- Ensure APIs are enabled in Google Cloud Console

### "Failed to extract data from receipt"
- Make sure receipt image is clear and well-lit
- Check OpenAI API key is valid and has credits
- Try with a different receipt

### Bot not responding
- Check if bot is running
- Verify Telegram bot token is correct
- Look at logs in `logs/billbuddy.log`

## Getting Help

- Check full documentation in [README.md](README.md)
- Review logs in `logs/billbuddy.log`
- Ensure all prerequisites are installed

---

Happy receipt tracking! 🧾✨

