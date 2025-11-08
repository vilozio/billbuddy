# Google Cloud Credentials

Place your Google Cloud service account JSON credentials file in this directory.

## Setup Instructions

1. Download your service account credentials JSON file from Google Cloud Console
2. Rename it to `service-account.json` (or any name you prefer)
3. Place it in this directory
4. Update the `GOOGLE_CREDENTIALS_PATH` in your `.env` file to point to this file

Example:
```
credentials/service-account.json
```

## Security Note

⚠️ **IMPORTANT**: Never commit credential files to version control!

This directory is already excluded in `.gitignore`, but please double-check before committing.

## What's Needed

Your service account needs access to:
- Google Drive API (to upload receipts)
- Google Sheets API (to log receipt data)

Make sure to:
1. Share your Google Drive folder with the service account email
2. Share your Google Sheet with the service account email

Both should have **Editor** permissions.

