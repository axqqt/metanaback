import os
import uuid
import logging
import requests
import json
import datetime
import pytz
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pandas as pd
import docx2txt
import PyPDF2
import boto3
from botocore.exceptions import NoCredentialsError
import schedule
import time
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Constants
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
# Replace with your email used for Metana application
CANDIDATE_EMAIL = os.getenv('CANDIDATE_EMAIL')

# File upload configuration
UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB file size limit

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configure AWS S3
S3_BUCKET = os.getenv('S3_BUCKET_NAME')
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('AWS_SECRET_KEY')
)

# Configure Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
credentials_info = json.loads(os.getenv('GOOGLE_CREDENTIALS', '{}'))
google_creds = service_account.Credentials.from_service_account_info(
    credentials_info, scopes=SCOPES)
sheets_service = build('sheets', 'v4', credentials=google_creds)

# Email configuration
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# Pending emails queue
email_queue = []


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_unique_filename(filename):
    """Generate a unique filename to prevent overwriting"""
    ext = filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4()}.{ext}"
    return unique_filename


def upload_to_s3(file_path, file_name):
    """Upload file to S3 and return public URL"""
    try:
        s3_client.upload_file(
            file_path,
            S3_BUCKET,
            file_name,
            ExtraArgs={'ACL': 'public-read'}
        )
        return f"https://{S3_BUCKET}.s3.amazonaws.com/{file_name}"
    except NoCredentialsError:
        logger.error("S3 credentials not available")
        return None
    except Exception as e:
        logger.error(f"S3 upload error: {e}")
        return None


def extract_cv_info(file_path):
    """Extract information from CV"""
    text = ""
    file_ext = file_path.rsplit('.', 1)[1].lower()

    try:
        if file_ext == 'pdf':
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text()
        elif file_ext == 'docx':
            text = docx2txt.process(file_path)
    except Exception as e:
        logger.error(f"Error extracting text from CV: {e}")
        return {}

    # Simple parsing logic (can be enhanced with NLP/ML)
    sections = {
        'personal_info': {},
        'education': [],
        'qualifications': [],
        'projects': []
    }

    # Extract education (basic implementation)
    if "EDUCATION" in text.upper():
        education_section = text.upper().split("EDUCATION")[1].split(
            "QUALIFICATIONS" if "QUALIFICATIONS" in text.upper() else "PROJECTS" if "PROJECTS" in text.upper() else "")[0]
        education_entries = [e.strip()
                             for e in education_section.split('\n\n') if e.strip()]
        sections['education'] = education_entries[:5]  # Limit to 5 entries

    # Extract qualifications (basic implementation)
    if "QUALIFICATIONS" in text.upper() or "SKILLS" in text.upper():
        qual_keyword = "QUALIFICATIONS" if "QUALIFICATIONS" in text.upper() else "SKILLS"
        qual_section = text.upper().split(qual_keyword)[1].split(
            "PROJECTS" if "PROJECTS" in text.upper() else "EXPERIENCE" if "EXPERIENCE" in text.upper() else "")[0]
        qual_entries = [q.strip()
                        for q in qual_section.split('\n') if q.strip()]
        sections['qualifications'] = qual_entries[:10]  # Limit to 10 entries

    # Extract projects (basic implementation)
    if "PROJECTS" in text.upper():
        projects_section = text.upper().split("PROJECTS")[1].split(
            "EXPERIENCE" if "EXPERIENCE" in text.upper() else "REFERENCES" if "REFERENCES" in text.upper() else "")[0]
        project_entries = [p.strip()
                           for p in projects_section.split('\n\n') if p.strip()]
        sections['projects'] = project_entries[:5]  # Limit to 5 entries

    return sections


def add_to_google_sheet(data, cv_link):
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
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range='Sheet1!A:H',
            valueInputOption='RAW',
            body={'values': [row]}
        ).execute()

        return True
    except Exception as e:
        logger.error(f"Google Sheets API error: {e}")
        return False


def send_webhook(data, status="testing"):
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
            "X-Candidate-Email": CANDIDATE_EMAIL
        }

        response = requests.post(
            WEBHOOK_URL,
            headers=headers,
            json=payload,
            timeout=10
        )

        return response.status_code == 200
    except Exception as e:
        logger.error(f"Webhook send error: {e}")
        return False


def queue_follow_up_email(applicant_data):
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

    email_queue.append({
        'recipient': applicant_data['email'],
        'name': applicant_data['name'],
        'send_time': send_time
    })

    logger.info(
        f"Queued follow-up email for {applicant_data['email']} at {send_time}")


def send_email(recipient, name):
    """Send follow-up email to applicant"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
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

        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

        logger.info(f"Follow-up email sent to {recipient}")
        return True
    except Exception as e:
        logger.error(f"Email sending error: {e}")
        return False


def email_scheduler():
    """Check for emails that need to be sent"""
    now = datetime.datetime.now(pytz.UTC)

    # Find emails that should be sent
    emails_to_send = [
        email for email in email_queue if email['send_time'] <= now]

    # Remove emails to be sent from the queue
    for email in emails_to_send:
        email_queue.remove(email)
        send_email(email['recipient'], email['name'])


def start_scheduler():
    """Start the email scheduler thread"""
    schedule.every(1).hours.do(email_scheduler)

    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)

    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()


@app.route('/api/submit', methods=['POST'])
def submit_application():
    """Handle job application submission"""
    try:
        # Validate form fields
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')

        # Validate required fields
        if not all([name, email, phone]):
            return jsonify({"error": "Missing required fields"}), 400

        # Check if file is present
        if 'cv' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        cv_file = request.files['cv']

        # Validate file
        if cv_file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        if not allowed_file(cv_file.filename):
            return jsonify({"error": "Invalid file type. Only PDF and DOCX allowed."}), 400

        # Generate unique filename and save
        secure_filename_value = secure_filename(cv_file.filename)
        unique_filename = generate_unique_filename(secure_filename_value)
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        cv_file.save(file_path)

        # Upload to S3
        cv_link = upload_to_s3(file_path, unique_filename)
        if not cv_link:
            return jsonify({"error": "Failed to upload file to storage"}), 500

        # Extract CV information
        cv_data = extract_cv_info(file_path)

        # Prepare complete application data
        application_data = {
            'name': name,
            'email': email,
            'phone': phone,
            'cv_link': cv_link,
            'cv_data': cv_data
        }

        # Add to Google Sheet
        sheet_result = add_to_google_sheet(application_data, cv_link)
        if not sheet_result:
            logger.warning("Failed to add data to Google Sheet")

        # Send webhook notification
        webhook_result = send_webhook(application_data, status="prod")
        if not webhook_result:
            logger.warning("Failed to send webhook notification")

        # Queue follow-up email
        queue_follow_up_email({
            'email': email,
            'name': name
        })

        # Prepare response
        return jsonify({
            "message": "Application submitted successfully!",
            "cv_link": cv_link
        }), 200

    except Exception as e:
        logger.error(f"Submission error: {e}")
        return jsonify({"error": "Submission failed"}), 500


@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """Provide download endpoint for uploaded files (for testing)"""
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # Security check to prevent directory traversal
        if not os.path.normpath(file_path).startswith(UPLOAD_FOLDER):
            return jsonify({"error": "Invalid file path"}), 403

        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        logger.error(f"File download error: {e}")
        return jsonify({"error": "File download failed"}), 500


@app.route('/', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy"}), 200


# Start the email scheduler when app starts
start_scheduler()

# Configure app for deployment
if __name__ == '__main__':
    # Get port from environment variable (for cloud deployment)
    port = int(os.getenv('PORT'))
    app.run(host='0.0.0.0', port=port)
