import logging
import datetime
import pytz
import threading
import time
import schedule
import os
import resend as Resend  # Resend API SDK
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()  # Load environment variables

# Initialize Resend API
resend = Resend(os.getenv("RESEND_API_KEY"))

class EmailService:
    """Service for managing email operations"""

    def __init__(self):
        self.email_queue = []
        self.queue_lock = threading.Lock()  # Prevents race conditions

    def queue_follow_up_email(self, applicant_data):
        """Queue follow-up email to be sent the next day at 9 AM in the applicant's timezone"""
        now = datetime.datetime.now(pytz.UTC)
        applicant_timezone = pytz.timezone(applicant_data.get("timezone", "UTC"))  # Default to UTC

        # Schedule email for 9 AM the next day in applicant's timezone
        tomorrow = now.astimezone(applicant_timezone) + datetime.timedelta(days=1)
        send_time = applicant_timezone.localize(datetime.datetime(
            tomorrow.year, tomorrow.month, tomorrow.day, 9, 0, 0
        ))

        with self.queue_lock:
            self.email_queue.append({
                "recipient": applicant_data["email"],
                "name": applicant_data["name"],
                "send_time": send_time
            })

        logger.info(f"✅ Queued follow-up email for {applicant_data['email']} at {send_time}")

    def send_email(self, recipient, name):
        """Send follow-up email using Resend API"""
        try:
            response = resend.emails.send({
                "from": "Recruiting Team <no-reply@yourdomain.com>",
                "to": [recipient],
                "subject": "Your Application is Under Review",
                "html": f"""
                <html>
                <body>
                    <p>Dear {name},</p>
                    <p>Thank you for submitting your application. We have received your CV and it is currently under review.</p>
                    <p>We will get back to you soon with updates.</p>
                    <p>Best regards,<br>The Recruiting Team</p>
                </body>
                </html>
                """
            })

            if response.get("id"):
                logger.info(f"✅ Follow-up email successfully sent to {recipient}")
                return True
            else:
                logger.error(f"❌ Failed to send email to {recipient}")
                return False
        except Exception as e:
            logger.error(f"❌ Email sending error: {e}")
            return False

    def email_scheduler(self):
        """Check and send scheduled emails"""
        now = datetime.datetime.now(pytz.UTC)
        emails_to_send = []

        with self.queue_lock:
            emails_to_send = [email for email in self.email_queue if email["send_time"] <= now]
            self.email_queue = [email for email in self.email_queue if email["send_time"] > now]

        for email in emails_to_send:
            self.send_email(email["recipient"], email["name"])

    def start_scheduler(self):
        """Start the email scheduler in a separate thread"""
        schedule.every(1).hour.do(self.email_scheduler)

        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute

        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
