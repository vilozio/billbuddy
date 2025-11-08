# BillBuddy - Receipt Processing Telegram Bot

BillBuddy is an intelligent Telegram bot that automatically processes receipt images and PDFs, extracts detailed information using ChatGPT, organizes receipts in Google Drive, and logs all data to Google Sheets.

## Features

- 📸 **Receipt OCR**: Extract data from images and PDFs using GPT-4 Vision API
- 🤖 **Auto-Categorization**: Automatically categorize expenses (groceries, dining, utilities, etc.)
- 📁 **Google Drive Storage**: Organize receipts by year/month folder structure
- 📊 **Google Sheets Logging**: Automatic logging of all receipt data
- 💬 **Telegram Interface**: Easy-to-use bot interface for submitting receipts

## Extracted Information

BillBuddy extracts the following from each receipt:
- Transaction date
- Merchant/store name
- Total amount
- Tax amount
- Payment method
- List of purchased items
- Automatic expense category

## Project Structure

```
billbuddy/
├── app/
│   ├── main.py                    # Entry point
│   ├── config.py                  # Configuration management
│   ├── bot/
│   │   ├── handlers.py            # Message handlers
│   │   └── commands.py            # Bot commands
│   ├── services/
│   │   ├── receipt_processor.py  # Processing orchestrator
│   │   ├── openai_service.py     # OpenAI integration
│   │   ├── google_drive.py       # Google Drive integration
│   │   └── google_sheets.py      # Google Sheets integration
│   ├── models/
│   │   └── receipt.py            # Receipt data model
│   └── utils/
│       └── logger.py             # Logging configuration
├── .env                          # Environment variables (create from .env.example)
├── .env.example                  # Environment variables template
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Prerequisites

- Python 3.8 or higher
- Telegram account
- OpenAI API account
- Google Cloud Platform account

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd billbuddy
```

### 2. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For PDF processing, you may also need to install `poppler`:
- **macOS**: `brew install poppler`
- **Ubuntu/Debian**: `sudo apt-get install poppler-utils`
- **Windows**: Download from [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases/)

### 3. Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the **bot token** provided by BotFather
5. Save this token for later

### 4. Set Up OpenAI API

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Create an account or sign in
3. Navigate to [API Keys](https://platform.openai.com/api-keys)
4. Click "Create new secret key"
5. Copy the **API key** and save it securely

### 5. Set Up Google Cloud Services

#### 5.1 Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your **Project ID**

#### 5.2 Enable Required APIs

1. Go to **APIs & Services** > **Library**
2. Search and enable:
   - **Google Drive API**
   - **Google Sheets API**

#### 5.3 Create Service Account

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **Service Account**
3. Fill in the service account details:
   - Name: `billbuddy-service`
   - ID: (auto-generated)
4. Click **Create and Continue**
5. Grant roles:
   - **Editor** (or specific Drive/Sheets permissions)
6. Click **Done**

#### 5.4 Generate Service Account Key

1. Click on the service account you just created
2. Go to **Keys** tab
3. Click **Add Key** > **Create new key**
4. Choose **JSON** format
5. Download the JSON file
6. Save it securely in your project directory (e.g., `credentials/service-account.json`)
7. **Important**: Note the service account email (e.g., `billbuddy-service@project-id.iam.gserviceaccount.com`)

### 6. Set Up Google Drive

1. Go to [Google Drive](https://drive.google.com/)
2. Create a new folder called "Receipts" (or any name you prefer)
3. Right-click the folder and select **Share**
4. Add the **service account email** (from step 5.4.7) with **Editor** permissions
5. Copy the **folder ID** from the URL:
   - URL format: `https://drive.google.com/drive/folders/{FOLDER_ID}`

### 7. Set Up Google Sheets

1. Go to [Google Sheets](https://sheets.google.com/)
2. Create a new spreadsheet called "Receipt Log" (or any name you prefer)
3. Click **Share** button
4. Add the **service account email** (from step 5.4.7) with **Editor** permissions
5. Copy the **spreadsheet ID** from the URL:
   - URL format: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`

### 8. Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and fill in all the values:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o

# Google Cloud Configuration
GOOGLE_CREDENTIALS_PATH=credentials/service-account.json

# Google Drive folder ID
GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id_here

# Google Sheets spreadsheet ID
GOOGLE_SHEET_ID=your_google_sheet_id_here

# Application Settings (optional)
LOG_LEVEL=INFO
MAX_RETRIES=3
RETRY_DELAY=2
```

### 9. Run the Bot

```bash
python app/main.py
```

Or from the app directory:
```bash
cd app
python main.py
```

You should see:
```
INFO - BillBuddy bot...
INFO - Bot is running. Press Ctrl+C to stop.
```

## Usage

### Starting the Bot

1. Open Telegram
2. Search for your bot (by the username you set with BotFather)
3. Send `/start` to begin

### Sending Receipts

Simply send a photo or PDF of your receipt to the bot. The bot will:
1. Acknowledge receipt of the image/PDF
2. Process the receipt (5-15 seconds)
3. Send you a detailed summary
4. Save the receipt to Google Drive
5. Log the data to Google Sheets

### Available Commands

- `/start` - Start the bot and see welcome message
- `/help` - Show help and usage instructions
- `/status` - Check if the bot is operational

### Supported Formats

- **Images**: JPG, JPEG, PNG
- **Documents**: PDF

## Google Sheets Output

The bot creates a spreadsheet with the following columns:

| Date | Merchant | Amount | Tax | Payment Method | Category | Items | Drive Link |
|------|----------|--------|-----|----------------|----------|-------|------------|

Example:
```
2024-11-08 | Walmart | 45.67 | 3.42 | Credit Card | Groceries | Milk, Bread, Eggs, ... | https://drive.google.com/...
```

## Expense Categories

The bot automatically categorizes receipts into:
- **Groceries** (supermarkets, food stores)
- **Dining** (restaurants, cafes)
- **Transportation** (gas, parking, transit)
- **Utilities** (electricity, water, internet)
- **Entertainment** (movies, events, subscriptions)
- **Healthcare** (pharmacy, medical)
- **Shopping** (retail, clothing, electronics)
- **Services** (repairs, cleaning, professional)
- **Other** (uncategorized)

## Troubleshooting

### Bot Not Responding

1. Check if the bot is running
2. Verify your Telegram bot token is correct
3. Check the logs in `logs/billbuddy.log`

### OpenAI Errors

1. Verify your API key is valid
2. Check if you have sufficient credits
3. Ensure you're using a model with vision capabilities (gpt-4o, gpt-4-vision-preview)

### Google Drive/Sheets Errors

1. Verify service account credentials file exists
2. Ensure the service account has been granted access to both Drive folder and Sheet
3. Check folder ID and spreadsheet ID are correct
4. Verify the APIs are enabled in Google Cloud Console

### PDF Processing Issues

1. Ensure `poppler` is installed
2. Check if the PDF is readable (not corrupted)
3. Try converting the PDF to an image first

## Development

### Running in Development Mode

```bash
# Set log level to DEBUG for more verbose output
LOG_LEVEL=DEBUG python app/main.py
```

### Testing Individual Components

```python
# Test OpenAI service
from app.services.openai_service import OpenAIService
service = OpenAIService()
receipt = service.process_receipt_image("path/to/receipt.jpg")

# Test Google Drive upload
from app.services.google_drive import GoogleDriveService
drive = GoogleDriveService()
link = drive.upload_receipt("path/to/file.jpg", "2024-11-08", "Test Store", 10.00)

# Test Google Sheets
from app.services.google_sheets import GoogleSheetsService
sheets = GoogleSheetsService()
sheets.append_receipt(receipt)
```

## Security Notes

- **Never commit** your `.env` file or credentials to version control
- Keep your API keys and tokens secure
- Regularly rotate your credentials
- Use environment-specific credentials for production

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or suggestions, please open an issue on GitHub or contact the maintainer.

---

**BillBuddy** - Making expense tracking effortless! 🧾✨

