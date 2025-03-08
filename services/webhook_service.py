import logging
import datetime
import requests
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class WebhookService:
    """Service for sending webhook notifications"""

    def __init__(self, webhook_url, candidate_email):
        self.webhook_url = webhook_url
        self.candidate_email = candidate_email

    def send_notification(self, data, status="prod"):
        """Send webhook notification after processing CV"""
        try:
            payload = {
                "cv_data": data.get("cv_data", {}),
                "personal_info": {  # Added required field
                    "name": data.get("name", ""),
                    "email": data.get("email", "")
                },
                "metadata": {
                    "applicant_name": data.get("name", ""),
                    "email": data.get("email", ""),
                    # "testing" (during testing) or "prod" (final submission)
                    "status": status,
                    "cv_processed": True,
                    "processed_timestamp": datetime.datetime.utcnow().isoformat()
                }
            }

            # Add CV link if available
            if "cv_link" in data:
                payload["cv_data"]["cv_public_link"] = data["cv_link"]

            headers = {
                "Content-Type": "application/json",
                # Unique email for submission tracking
                "X-Candidate-Email": self.candidate_email
            }

            response = requests.post(
                self.webhook_url,
                headers=headers,
                json=payload,
                timeout=10  # Avoid hanging indefinitely
            )

            if response.status_code == 200:
                logger.info("✅ Webhook successfully sent.")
                return True
            else:
                logger.error(
                    f"❌ Webhook failed! Status: {response.status_code}, Response: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Webhook send error: {e}")
            return False
