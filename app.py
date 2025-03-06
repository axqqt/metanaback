from services.email_service import EmailService
from services.webhook_service import WebhookService
from services.sheet_service import GoogleSheetService
from services.storage_service import S3StorageService
from services.cv_parser import CVParser
from services.file_service import FileService
import os
import uuid
import logging
import json
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from a .env file

# Import from our modules

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

# Initialize services
file_service = FileService(UPLOAD_FOLDER, ALLOWED_EXTENSIONS)
cv_parser = CVParser()
s3_service = S3StorageService(
    os.getenv('S3_BUCKET_NAME'),
    os.getenv('AWS_ACCESS_KEY'),
    os.getenv('AWS_SECRET_KEY')
)

# Fetch Google credentials from file instead of environment
google_credentials_path = "google-credentials.json"
print(f"Loading credentials from: {google_credentials_path}")

# Read the credentials from the file
try:
    with open(google_credentials_path, 'r') as f:
        google_credentials = f.read()
except FileNotFoundError:
    raise ValueError(f"Google credentials file not found at: {google_credentials_path}")

# Check if the credentials are not empty
if not google_credentials:
    raise ValueError(
        "Google credentials file is empty.")

# Parse the credentials string into a dictionary
try:
    google_credentials_dict = json.loads(google_credentials)
except json.JSONDecodeError as e:
    raise ValueError(f"Failed to decode Google credentials: {e}")

# Now pass the credentials to GoogleSheetService
google_sheet_service = GoogleSheetService(
    os.getenv('SPREADSHEET_ID'),
    credentials_info=google_credentials_dict
)
# Initialize webhook service
webhook_service = WebhookService(WEBHOOK_URL, CANDIDATE_EMAIL)

# Initialize email service
email_service = EmailService(
    os.getenv('EMAIL_HOST', 'smtp.gmail.com'),
    int(os.getenv('EMAIL_PORT', 587)),
    os.getenv('EMAIL_USER'),
    os.getenv('EMAIL_PASSWORD')
)


@app.route('/', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy"}), 200


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

        if not file_service.allowed_file(cv_file.filename):
            return jsonify({"error": "Invalid file type. Only PDF and DOCX allowed."}), 400

        # Generate unique filename and save
        unique_filename = file_service.save_file(cv_file)
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

        # Upload to S3
        cv_link = s3_service.upload_file(file_path, unique_filename)
        if not cv_link:
            return jsonify({"error": "Failed to upload file to storage"}), 500

        # Extract CV information
        cv_data = cv_parser.extract_cv_info(file_path)

        # Prepare complete application data
        application_data = {
            'name': name,
            'email': email,
            'phone': phone,
            'cv_link': cv_link,
            'cv_data': cv_data
        }

        # Add to Google Sheet
        sheet_result = google_sheet_service.add_entry(
            application_data, cv_link)
        if not sheet_result:
            logger.warning("Failed to add data to Google Sheet")

        # Send webhook notification
        webhook_result = webhook_service.send_notification(
            application_data, status="prod")
        if not webhook_result:
            logger.warning("Failed to send webhook notification")

        # Queue follow-up email
        email_service.queue_follow_up_email({
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


# Configure app for deployment
if __name__ == '__main__':
    # Start the email scheduler when app starts
    email_service.start_scheduler()

    # Get port from environment variable (for cloud deployment)
    port = int(os.getenv('PORT'))
    app.run(host='0.0.0.0', port=port)