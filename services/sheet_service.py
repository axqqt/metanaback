import logging
import json
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from a .env file


class GoogleSheetService:
    """Service for managing Google Sheets operations"""
    
    def __init__(self, spreadsheet_id, credentials_info):
        self.spreadsheet_id = spreadsheet_id
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets']
        
        # Set up Google Sheets API service
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info, scopes=self.scopes)
        self.sheets_service = build('sheets', 'v4', credentials=credentials)
    
    def add_entry(self, data, cv_link):
        """Add extracted CV data to Google Sheet"""
        try:
            # Prepare data for insertion
            row = [
                data.get('name', ''),
                data.get('email', ''),
                data.get('phone', ''),
                cv_link,
                json.dumps(data.get('cv_data', {}).get('education', [])),
                json.dumps(data.get('cv_data', {}).get('qualifications', [])),
                json.dumps(data.get('cv_data', {}).get('projects', [])),
                datetime.datetime.now().isoformat()
            ]

            # Append to sheet
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A:H',
                valueInputOption='RAW',
                body={'values': [row]}
            ).execute()

            return True
        except Exception as e:
            logger.error(f"Google Sheets API error: {e}")
            return False