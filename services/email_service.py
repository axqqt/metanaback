import logging
import datetime
import pytz
import threading
import time
import schedule
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from a .env file


logger = logging.getLogger(__name__)

class EmailService:
    """Service for managing email operations"""
    
    def __init__(self, host, port, user, password):
        self.email_host = host
        self.email_port = port
        self.email_user = user
        self.email_password = password
        self.email_queue = []
    
    def queue_follow_up_email(self, applicant_data):
        """Queue follow-up email to be sent the next day"""
        # Get current time in UTC
        now = datetime.datetime.now(pytz.UTC)

        # Schedule for next day at 9:00 AM in the applicant's timezone (default to UTC)
        # In a real implementation, we would detect timezone from IP or ask in the form
        tomorrow = now + datetime.timedelta(days=1)
        send_time = datetime.datetime(
            tomorrow.year, tomorrow.month, tomorrow.day,
            9, 0, 0, tzinfo=pytz.UTC
        )

        self.email_queue.append({
            'recipient': applicant_data['email'],
            'name': applicant_data['name'],
            'send_time': send_time
        })

        logger.info(
            f"Queued follow-up email for {applicant_data['email']} at {send_time}")
    
    def send_email(self, recipient, name):
        """Send follow-up email to applicant"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = recipient
            msg['Subject'] = "Your Application is Under Review"

            body = f"""
            <html>
            <body>
                <p>Dear {name},</p>
                <p>Thank you for submitting your application. We have received your CV and it is currently under review by our team.</p>
                <p>We will get back to you soon with updates on your application.</p>
                <p>Best regards,<br>The Recruiting Team</p>
            </body>
            </html>
            """

            msg.attach(MIMEText(body, 'html'))

            server = smtplib.SMTP(self.email_host, self.email_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.send_message(msg)
            server.quit()

            logger.info(f"Follow-up email sent to {recipient}")
            return True
        except Exception as e:
            logger.error(f"Email sending error: {e}")
            return False
    
    def email_scheduler(self):
        """Check for emails that need to be sent"""
        now = datetime.datetime.now(pytz.UTC)

        # Find emails that should be sent
        emails_to_send = [
            email for email in self.email_queue if email['send_time'] <= now]

        # Remove emails to be sent from the queue
        for email in emails_to_send:
            self.email_queue.remove(email)
            self.send_email(email['recipient'], email['name'])
    
    def start_scheduler(self):
        """Start the email scheduler thread"""
        schedule.every(1).hours.do(self.email_scheduler)

        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)

        scheduler_thread = threading.Thread(target=run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()