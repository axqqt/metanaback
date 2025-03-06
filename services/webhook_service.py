import logging
import datetime
import requests

logger = logging.getLogger(__name__)

class WebhookService:
    """Service for sending webhook notifications"""
    
    def __init__(self, webhook_url, candidate_email):
        self.webhook_url = webhook_url
        self.candidate_email = candidate_email
    
    def send_notification(self, data, status="testing"):
        """Send webhook notification"""
        try:
            payload = {
                "cv_data": data.get('cv_data', {}),
                "metadata": {
                    "applicant_name": data.get('name', ''),
                    "email": data.get('email', ''),
                    "status": status,
                    "cv_processed": True,
                    "processed_timestamp": datetime.datetime.now().isoformat()
                }
            }

            # Add CV link if available
            if 'cv_link' in data:
                payload["cv_data"]["cv_public_link"] = data['cv_link']

            headers = {
                "Content-Type": "application/json",
                "X-Candidate-Email": self.candidate_email
            }

            response = requests.post(
                self.webhook_url,
                headers=headers,
                json=payload,
                timeout=10
            )

            return response.status_code == 200
        except Exception as e:
            logger.error(f"Webhook send error: {e}")
            return False