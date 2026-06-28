import os
import argparse
from google_auth_oauthlib.flow import InstalledAppFlow

# Google Drive API Scope
SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    parser = argparse.ArgumentParser(description="Obtain Google Drive API Refresh Token")
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to the Google API OAuth 2.0 client credentials JSON file."
    )
    args = parser.parse_args()

    if not os.path.exists(args.credentials):
        print(f"Error: Credentials file not found at '{args.credentials}'")
        print("Please download the desktop app credentials from Google Cloud Console and place them there, or specify the path using --credentials.")
        return

    # Initialize the flow using the credentials JSON file
    flow = InstalledAppFlow.from_client_secrets_file(args.credentials, SCOPES)
    
    # Run the local server flow to authenticate
    credentials = flow.run_local_server(port=0)

    print("\nAuthorization successful!")
    print(f"Refresh Token: {credentials.refresh_token}")
    print(f"Client ID: {credentials.client_id}")
    print(f"Client Secret: {credentials.client_secret}")
    print("\nYou can update your .env file with the following:")
    print(f"GOOGLE_CLIENT_ID={credentials.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={credentials.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={credentials.refresh_token}")

if __name__ == "__main__":
    main()
