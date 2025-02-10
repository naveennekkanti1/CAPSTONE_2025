import os
from google.oauth2 import service_account
import googleapiclient.discovery

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Ensure the path to your JSON file is correct
SERVICE_ACCOUNT_FILE = os.path.join(os.getcwd(), "templates/credentials.json")

# Load credentials from service account JSON
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

service = googleapiclient.discovery.build("calendar", "v3", credentials=credentials)

print("Google Calendar API connected successfully!")