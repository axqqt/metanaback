import logging
import json
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()  # Load environment variables if needed


class GoogleSheetService:
    """Service for managing Google Sheets operations"""

    def __init__(self, spreadsheet_id, credentials_info):
        self.spreadsheet_id = spreadsheet_id
        self.scopes = ["https://www.googleapis.com/auth/spreadsheets"]

        try:
            # Ensure credentials are properly loaded
            self.credentials = service_account.Credentials.from_service_account_info(
                credentials_info, scopes=self.scopes
            )
            self.sheets_service = build(
                "sheets", "v4", credentials=self.credentials)
            logger.info("✅ Google Sheets API authenticated successfully!")
        except Exception as e:
            logger.error(f"❌ Failed to authenticate Google Sheets API: {e}")

    def add_entry(self, data, cv_link):
        """Add extracted CV data to Google Sheet"""
        try:
            row = [
                data.get("name", ""),
                data.get("email", ""),
                data.get("phone", ""),
                cv_link,
                json.dumps(data.get("cv_data", {}).get("education", [])),
                json.dumps(data.get("cv_data", {}).get("qualifications", [])),
                json.dumps(data.get("cv_data", {}).get("projects", [])),
                datetime.datetime.now().isoformat()  # Timestamp
            ]

            # Append data to the Google Sheet
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range="Sheet1!A:H",
                valueInputOption="RAW",
                body={"values": [row]},
            ).execute()

            logger.info("✅ Data successfully added to Google Sheets.")
            return True
        except Exception as e:
            logger.error(f"❌ Google Sheets API error: {e}")
            return False
