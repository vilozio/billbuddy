#!/usr/bin/env python3
"""One-time script to authenticate with Google"""
from app.services.google_auth import GoogleAuthService

if __name__ == "__main__":
    print("Starting Google OAuth authentication...")
    print("A browser window will open. Please sign in and authorize the application.")
    print()

    try:
        creds = GoogleAuthService.get_credentials()

        print("\n✓ Authentication successful!")
        print("Token saved to credentials/token.pickle")
        print("You can now run the bot with: ./run.sh")
    except Exception as e:
        print(f"\n✗ Authentication failed: {e}")
        print("Please check your oauth-client.json file and try again.")
        exit(1)
