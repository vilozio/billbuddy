# BillBuddy - Receipt & Statement Processing Telegram Bot

BillBuddy is an intelligent Telegram bot with two processing directions:

1. **Receipts** — send a photo or PDF of a receipt and BillBuddy extracts the details with GPT‑4 Vision, stores the file in Google Drive, and logs a row to Google Sheets.
2. **CSV statements** — send a CSV export (bank, broker/IBKR, mortgage, etc.). The first time it sees a new kind of file, BillBuddy runs a short setup wizard to learn how to recognize it, how to transform its columns, and where to send the result. Matching files are then processed **automatically**.

## Features

### Receipts
- 📸 **Receipt OCR**: Extract data from images and PDFs using GPT‑4 Vision API
- 🤖 **Auto-Categorization**: Automatically categorize expenses (groceries, dining, utilities, etc.)
- 📁 **Google Drive Storage**: Organize receipts by year/month folder structure
- 📊 **Google Sheets Logging**: Automatic logging of all receipt data

### CSV Statements
- 🧩 **Scenario setup wizard**: Teach the bot a new file kind once; it remembers and reuses the setup
- 🔎 **Filename recognition**: Recurring files are matched by a human-friendly pattern with `{date}` / `{any}` placeholders
- 🤖 **AI-assisted column mapping**: Describe the transformation in plain language; the bot proposes a mapping you confirm. The transformation itself runs in deterministic code
- 🔁 **Transformations**: keep / drop / rename / reorder columns, add constant columns (e.g. `Source = Revolut`), and sort rows by a column (numeric-aware, ascending or descending)
- 🎯 **Flexible destinations**: append rows to a Google Sheet tab and/or upload the transformed CSV to a Drive folder
- ⚡ **Automatic re-processing**: once a scenario exists, matching files are processed with no questions
- 🧭 **Multiple scenarios per pattern**: when one filename pattern needs different handling (e.g. the same export feeding two sheets), keep several scenarios under it and the bot asks which to run on upload

### General
- 💬 **Telegram Interface**: Easy-to-use bot interface
- 🔀 **Independent toggles**: receipt processing can be turned off (`/receipts_off`) so the bot can run as statements-only, and vice versa

## Receipt: Extracted Information

- Transaction date, merchant/store name, total, tax, payment method, list of items, automatic expense category

## CSV Statement: How a scenario works

When you send a new kind of CSV the bot asks three things:

1. **Filename pattern** — it proposes a template from the example, e.g.
   `account-statement_2026-06-01_2026-06-15_en_6d52ac.csv` → `account-statement_{date}_{date}_en_{any}.csv`.
   Placeholders: `{date}` = `YYYY-MM-DD`, `{any}` = any token. Send `ok` to accept or type your own.
2. **Transformation** — describe it in plain language, e.g.
   *"keep Completed Date and Amount, rename Completed Date to Date, add a column Source set to Revolut, sort by Date newest first"*. Supported operations: keep/drop, rename, reorder columns, add **constant columns**, and **sort rows by a column** (ascending/descending, numeric when the values are numbers). The bot shows the proposed mapping; send `yes` to confirm or type a new instruction to refine.
3. **Destination** — a Google Sheet tab, a Drive folder, or both. For a Sheet, it offers any spreadsheets you've used before (remembered in the local database); you can pick one, paste a new spreadsheet link/ID (saved for next time), or create a new one with `new <Title>`, then name the tab.

The scenario is saved to a local SQLite database. The file that triggered the setup is processed immediately, and future files matching the pattern are processed automatically.

### Multiple scenarios for one pattern

Sometimes the filename alone can't tell two cases apart (e.g. the same bank export should go to two different sheets). Use **`/add_scenario`** then upload the file: the bot reuses the matched pattern and asks only for a name, transformation, and destination. When an uploaded file matches more than one scenario, the bot lists them and you pick which to run (or choose "➕ Create a new scenario for this file").

## Project Structure

```
billbuddy/
├── app/
│   ├── main.py                       # Entry point (registers handlers, inits DB)
│   ├── config.py                     # Configuration management
│   ├── db.py                         # SQLite init (scenarios + settings)
│   ├── bot/
│   │   ├── handlers.py               # Receipt photo/PDF/text handlers
│   │   ├── commands.py               # /start, /help, /status
│   │   ├── csv_handlers.py           # CSV upload + scenario setup wizard
│   │   └── settings_commands.py      # /receipts_on|off, /scenarios, /delete_scenario
│   ├── services/
│   │   ├── receipt_processor.py      # Receipt processing orchestrator
│   │   ├── statement_processor.py    # CSV processing orchestrator
│   │   ├── openai_service.py         # OpenAI receipt OCR
│   │   ├── transform_ai_service.py   # NL instruction -> transform schema
│   │   ├── csv_transformer.py        # Deterministic CSV transform engine
│   │   ├── filename_matcher.py       # Pattern suggest/compile
│   │   ├── scenario_store.py         # Scenario + settings CRUD
│   │   ├── google_auth.py            # Google OAuth
│   │   ├── google_drive.py           # Google Drive integration
│   │   └── google_sheets.py          # Google Sheets integration
│   ├── models/
│   │   ├── receipt.py                # Receipt data model
│   │   └── scenario.py               # Statement scenario data model
│   └── utils/
│       └── logger.py                 # Logging configuration
├── tests/
│   └── test_statements.py            # Unit tests for the CSV pipeline
├── authenticate.py                   # One-time Google OAuth helper
├── data/                             # SQLite database (git-ignored)
├── .env                              # Environment variables (create from .env.example)
├── .env.example                      # Environment variables template
├── requirements.txt                  # Python dependencies
└── README.md                         # This file
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
2. Send `/newbot` and follow the instructions
3. Copy the **bot token** provided by BotFather

### 4. Set Up OpenAI API

1. Go to [OpenAI Platform](https://platform.openai.com/) and sign in
2. Navigate to [API Keys](https://platform.openai.com/api-keys)
3. Click "Create new secret key" and copy the **API key**

### 5. Set Up Google Cloud (OAuth)

BillBuddy authenticates to Google with **OAuth** (user credentials), not a service account. This works with personal Google accounts.

#### 5.1 Create a Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create/select a project

#### 5.2 Enable Required APIs
1. **APIs & Services** > **Library**
2. Enable **Google Drive API** and **Google Sheets API**

#### 5.3 Configure the OAuth Consent Screen
1. **APIs & Services** > **OAuth consent screen**
2. Choose **External**, fill in the basic app info
3. Add your Google account under **Test users**

#### 5.4 Create an OAuth Client ID
1. **APIs & Services** > **Credentials** > **Create Credentials** > **OAuth client ID**
2. Application type: **Desktop app**
3. Download the JSON and save it as `credentials/oauth-client.json`
   (or set `GOOGLE_OAUTH_CLIENT_PATH` to wherever you put it)

#### 5.5 Authorize (one-time)
Run the helper and complete the browser sign-in. This creates `credentials/token.pickle`:
```bash
python authenticate.py
```
> If you later see `invalid_grant` errors, the token expired or was revoked — delete `credentials/token.pickle` and re-run `python authenticate.py`.

### 6. Set Up Google Drive

1. Create (or pick) a Drive folder for receipts
2. Copy the **folder ID** from the URL: `https://drive.google.com/drive/folders/{FOLDER_ID}`
3. (Optional) Create a separate folder for transformed statements

### 7. Set Up Google Sheets

1. Create (or pick) a spreadsheet for receipt data
2. Copy the **spreadsheet ID** from the URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`
3. (Optional) Use a separate spreadsheet for statements

> With OAuth `drive.file` scope, the bot can read/write the files and folders it creates or that you open with it. Make sure the configured folder/spreadsheet are accessible to the signed-in account.

### 8. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o

# Google OAuth client JSON (run `python authenticate.py` once)
GOOGLE_OAUTH_CLIENT_PATH=credentials/oauth-client.json

# Google Drive folder ID (receipts)
GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id_here

# Google Sheets spreadsheet ID (receipt log)
GOOGLE_SHEET_ID=your_google_sheet_id_here

# Statement (CSV) Processing (optional)
# Leave blank to reuse the receipt Drive folder / spreadsheet above.
STATEMENTS_DRIVE_FOLDER_ID=
STATEMENTS_SHEET_ID=
# Local SQLite database for statement scenarios and runtime settings
DB_PATH=data/billbuddy.db

# Application Settings (optional)
LOG_LEVEL=INFO
MAX_RETRIES=3
RETRY_DELAY=2
```

### 9. Run the Bot

```bash
python -m app.main
```

You should see:
```
INFO - Starting BillBuddy bot...
INFO - Bot is running. Press Ctrl+C to stop.
```

## Usage

### Receipts
Send a photo or PDF of your receipt. The bot acknowledges it, processes it (5–15s), sends a summary, stores the file in Drive, and logs a row to Sheets. (Disabled if you ran `/receipts_off`.)

### CSV Statements
Send a `.csv` file:
- **First time** for a given file kind, the bot walks you through the setup wizard (pattern → transformation → destination), saves a scenario, and processes the file.
- **Next time** a file matches the saved pattern, it's processed automatically with no questions.

### Available Commands

- `/start` — Welcome message
- `/help` — Help and usage instructions
- `/status` — Check if the bot is operational
- `/scenarios` — List saved CSV statement scenarios
- `/add_scenario` — Add another scenario for a file (lets one pattern have several scenarios)
- `/delete_scenario <id>` — Delete a saved scenario
- `/undo` — Undo the last processed receipt or statement (removes the appended Sheet rows and deletes the uploaded Drive file). Run again to undo the one before it.
- `/receipts_on` — Enable receipt (photo/PDF) processing
- `/receipts_off` — Disable receipt processing (statements stay active)
- `/cancel` — Abort the current CSV setup wizard

### Supported Formats

- **Images**: JPG, JPEG, PNG (receipts)
- **Documents**: PDF (receipts), CSV (statements)

## Google Sheets Output

### Receipts
| Date | Merchant | Amount | Tax | Payment Method | Category | Items | Drive Link |
|------|----------|--------|-----|----------------|----------|-------|------------|

```
2024-11-08 | Walmart | 45.67 | 3.42 | Credit Card | Groceries | Milk, Bread, Eggs, ... | https://drive.google.com/...
```

### Statements
Each scenario writes to its own tab with the columns produced by its transformation. For example, a transform that keeps `Completed Date` and `Amount` (renaming `Completed Date` → `Date`) produces:

| Date | Amount |
|------|--------|
| 2026-06-07 14:54:46 | -3.46 |

## Expense Categories (Receipts)

Groceries, Dining, Transportation, Utilities, Entertainment, Healthcare, Shopping, Services, Other.

## Testing

Run the CSV pipeline unit tests (no Google/OpenAI/Telegram credentials required):

```bash
python -m tests.test_statements
```

## Troubleshooting

### Bot Not Responding
1. Check if the bot is running
2. Verify your Telegram bot token is correct
3. Check the logs in `logs/billbuddy.log`

### OpenAI Errors
1. Verify your API key is valid and you have credits
2. Ensure you're using a vision-capable model (`gpt-4o`)

### Google Drive/Sheets Errors (OAuth)
1. Make sure `python authenticate.py` completed and `credentials/token.pickle` exists
2. On `invalid_grant` / expired token: delete `credentials/token.pickle` and re-authorize
3. Verify the Drive folder ID and spreadsheet ID, and that the signed-in account can access them
4. Verify the Drive and Sheets APIs are enabled in Google Cloud Console

### CSV Statement Issues
1. The bot recognizes files by filename pattern — if a file isn't auto-processed, check `/scenarios` and the pattern; re-send to set up a new one if needed
2. If the AI mapping looks wrong, type a clearer instruction instead of `yes` to refine it
3. Column names in your instruction should match the CSV headers exactly

### PDF Processing Issues
1. Ensure `poppler` is installed
2. Check that the PDF is readable (not corrupted)

## Development

```bash
# Verbose logging
LOG_LEVEL=DEBUG python -m app.main
```

The receipt processor is initialized lazily, so the bot can run as a statements-only deployment (`/receipts_off`) without exercising the receipt pipeline.

## Security Notes

- **Never commit** your `.env`, `credentials/`, or `data/` to version control (they are git-ignored)
- Keep your API keys, bot token, and OAuth credentials secure
- Regularly rotate your credentials

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

**BillBuddy** - Making expense tracking effortless! 🧾✨
