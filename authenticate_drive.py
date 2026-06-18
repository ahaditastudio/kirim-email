"""One-time Google Drive authentication script.

Run this once to authorize the app to access your Google Drive.
After authentication, the token is saved and reused automatically.

Prerequisites:
1. Create OAuth 2.0 Client ID at https://console.cloud.google.com/apis/credentials
   - Application type: Desktop app
   - Download the JSON file
2. Rename it to 'client_secrets.json' and place it in the project root
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import os
import sys

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CLIENT_SECRETS = "client_secrets.json"
TOKEN_FILE = "drive_token.json"


def main():
    if not os.path.exists(CLIENT_SECRETS):
        print("ERROR: client_secrets.json not found!")
        print()
        print("Steps to create it:")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Click '+ CREATE CREDENTIALS' -> 'OAuth client ID'")
        print("3. Application type: 'Desktop app'")
        print("4. Click Create")
        print("5. Download the JSON file")
        print("6. Rename it to 'client_secrets.json' and put it in this folder")
        sys.exit(1)

    print("Opening browser for Google authorization...")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
    creds = flow.run_local_server(port=8080)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print(f"\nAuthorization successful! Token saved to {TOKEN_FILE}")
    print("You can now use the app to upload PDFs to Google Drive.")


if __name__ == "__main__":
    main()
