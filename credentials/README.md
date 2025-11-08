# Google OAuth Credentials Setup

This directory contains the OAuth credentials needed for BillBuddy to access Google Drive and Google Sheets.

## Required Files

### 1. oauth-client.json (Required - You must create this)

This file contains your OAuth 2.0 client credentials.

**How to get it:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create a new one)
3. Enable the following APIs:
   - Google Drive API
   - Google Sheets API
4. Go to **APIs & Services** → **Credentials**
5. Click **Create Credentials** → **OAuth 2.0 Client ID**
6. Choose **Desktop app** as the application type
7. Name it "BillBuddy Desktop"
8. Click **Create**
9. Download the JSON file
10. Save it as `oauth-client.json` in this directory

### 2. token.pickle (Auto-generated - Do NOT create manually)

This file is automatically created after your first authentication. It stores your access token and refresh token for future use.

## First-Time Setup

After placing your `oauth-client.json` file, run the authentication script:

```bash
python -m authenticate
```

This will:
1. Open your default web browser
2. Ask you to sign in with your Google account
3. Request permission to access Drive and Sheets
4. Save the authentication token to `token.pickle`

**Important:** Make sure to sign in with the Google account that owns the Google Drive folder and Google Sheets spreadsheet you want to use.

## Security Notes

- **Never commit these files to git** - They are already in `.gitignore`
- The `oauth-client.json` contains your OAuth client secret
- The `token.pickle` contains your access tokens
- Keep both files secure and private

## Troubleshooting

### "OAuth client file not found" error
- Make sure `oauth-client.json` exists in this directory
- Check that the filename is exactly `oauth-client.json`

### Authentication browser window doesn't open
- The script will print a URL - copy and paste it into your browser manually

### "Access denied" or permission errors
- Make sure you're signing in with the correct Google account
- Ensure the account has access to the Drive folder and Sheet you specified in `.env`

### Token expired
- Just run the authentication script again: `python -m authenticate`
- The old token will be automatically refreshed

## What's Being Accessed?

The OAuth token grants BillBuddy permission to:
- **Google Drive:** Upload files to folders you specify
- **Google Sheets:** Read and write to spreadsheets you specify

BillBuddy only accesses the specific folders and sheets you configure in your `.env` file.
