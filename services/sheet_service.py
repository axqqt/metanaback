import logging
import json
import datetime
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class GoogleSheetService:
    """Service for managing Google Sheets operations"""

    def __init__(self, spreadsheet_id=None):
        """Initialize Google Sheets service with credentials from environment variables"""
        # Use spreadsheet_id from parameters or environment
        self.spreadsheet_id = spreadsheet_id or os.getenv('SPREADSHEET_ID')
        if not self.spreadsheet_id:
            raise ValueError("Spreadsheet ID is required")
            
        self.scopes = ["https://www.googleapis.com/auth/spreadsheets"]

        try:
            # Check if file-based credentials exist
            credentials_path = os.getenv('GOOGLE_CREDENTIALS')
            if credentials_path and os.path.exists(credentials_path):
                logger.info(f"Loading credentials from file: {credentials_path}")
                self.credentials = service_account.Credentials.from_service_account_file(
                    credentials_path, scopes=self.scopes
                )
            else:
                # Construct credentials from individual environment variables
                logger.info("Loading credentials from environment variables")
                credentials_info = {
                    "type": os.getenv('GOOGLE_CREDENTIALS_TYPE'),
                    "project_id": os.getenv('GOOGLE_CREDENTIALS_PROJECT_ID'),
                    "private_key_id": os.getenv('GOOGLE_CREDENTIALS_PRIVATE_KEY_ID'),
                    "private_key": os.getenv('GOOGLE_CREDENTIALS_PRIVATE_KEY').replace('\\n', '\n'),
                    "client_email": os.getenv('GOOGLE_CREDENTIALS_CLIENT_EMAIL'),
                    "client_id": os.getenv('GOOGLE_CREDENTIALS_CLIENT_ID'),
                    "auth_uri": os.getenv('GOOGLE_CREDENTIALS_AUTH_URI'),
                    "token_uri": os.getenv('GOOGLE_CREDENTIALS_TOKEN_URI'),
                    "auth_provider_x509_cert_url": os.getenv('GOOGLE_CREDENTIALS_AUTH_PROVIDER_X509_CERT_URL'),
                    "client_x509_cert_url": os.getenv('GOOGLE_CREDENTIALS_CLIENT_X509_CERT_URL'),
                    "universe_domain": os.getenv('GOOGLE_CREDENTIALS_UNIVERSE_DOMAIN')
                }
                
                # Check if all required fields are present
                required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 
                                   'client_email', 'client_id', 'auth_uri', 'token_uri']
                missing_fields = [field for field in required_fields if not credentials_info.get(field)]
                
                if missing_fields:
                    raise ValueError(f"Missing required credential fields: {', '.join(missing_fields)}")
                
                self.credentials = service_account.Credentials.from_service_account_info(
                    credentials_info, scopes=self.scopes
                )
                
            # Build the sheets service
            self.sheets_service = build("sheets", "v4", credentials=self.credentials)
            logger.info("✅ Google Sheets API authenticated successfully!")
            
            # Test connection
            self.test_connection()
            
        except Exception as e:
            logger.error(f"❌ Failed to authenticate Google Sheets API: {e}")
            raise

    def add_entry(self, data, cv_link=None):
        """Add extracted CV data to Google Sheet"""
        try:
            # Validate input data
            if not isinstance(data, dict):
                logger.error("❌ Data must be a dictionary")
                return False
                
            row = [
                data.get("name", ""),
                data.get("email", ""),
                data.get("phone", ""),
                cv_link if cv_link else "",
                json.dumps(data.get("cv_data", {}).get("education", [])),
                json.dumps(data.get("cv_data", {}).get("qualifications", [])),
                json.dumps(data.get("cv_data", {}).get("projects", [])),
                datetime.datetime.now().isoformat()  # Timestamp
            ]

            # Append data to the Google Sheet
            response = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range="Sheet1!A:H",
                valueInputOption="RAW",
                body={"values": [row]},
            ).execute()

            logger.info(f"✅ Data successfully added to Google Sheets. Updated range: {response.get('updates', {}).get('updatedRange', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"❌ Google Sheets API error: {e}")
            return False
            
    def test_connection(self):
        """Test the connection to Google Sheets API"""
        try:
            # Try to get the spreadsheet metadata to verify connection
            response = self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            sheet_title = response.get('properties', {}).get('title', 'Unknown')
            logger.info(f"✅ Google Sheets connection test successful. Connected to: {sheet_title}")
            return True
        except Exception as e:
            logger.error(f"❌ Google Sheets connection test failed: {e}")
            return False