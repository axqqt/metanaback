from services.email_service import EmailService
from services.webhook_service import WebhookService
from services.sheet_service import GoogleSheetService
from services.storage_service import S3StorageService
from services.cv_parser import CVParser
from services.file_service import FileService
import os
import json
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Constants
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
CANDIDATE_EMAIL = os.getenv("CANDIDATE_EMAIL")

# File upload configuration
UPLOAD_FOLDER = "/tmp/uploads"
ALLOWED_EXTENSIONS = {"pdf", "docx"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB file size limit

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize services
file_service = FileService(UPLOAD_FOLDER, ALLOWED_EXTENSIONS)
cv_parser = CVParser()
s3_service = S3StorageService(
    os.getenv("S3_BUCKET_NAME"),
    os.getenv("AWS_ACCESS_KEY"),
    os.getenv("AWS_SECRET_KEY"),
)

# Load Google credentials
google_credentials_path = "google-credentials.json"
try:
    with open(google_credentials_path, "r") as f:
        google_credentials = f.read()
    google_credentials_dict = json.loads(google_credentials)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logger.error(f"Error loading Google credentials: {e}")
    raise ValueError(f"Invalid Google credentials: {e}")

google_sheet_service = GoogleSheetService(
    os.getenv("SPREADSHEET_ID"), credentials_info=google_credentials_dict
)
webhook_service = WebhookService(WEBHOOK_URL, CANDIDATE_EMAIL)
email_service = EmailService()


@app.route("/", methods=["GET"])
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy"}), 200


@app.route("/api/submit", methods=["POST"])
def submit_application():
    """Handle job application submission"""
    try:
        logger.info("Processing application submission...")

        # Validate form fields
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")

        if not all([name, email, phone]):
            logger.warning("Missing required fields")
            return jsonify({"error": "Missing required fields"}), 400

        # Validate file upload
        if "cv" not in request.files:
            logger.warning("No file uploaded")
            return jsonify({"error": "No file uploaded"}), 400

        cv_file = request.files["cv"]
        if cv_file.filename == "" or not file_service.allowed_file(cv_file.filename):
            logger.warning(f"Invalid file: {cv_file.filename}")
            return jsonify({"error": "Invalid file type. Only PDF and DOCX allowed."}), 400

        # Save file and upload to S3
        unique_filename = file_service.save_file(cv_file)
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        cv_link = s3_service.upload_file(file_path, unique_filename)

        if not cv_link:
            logger.error("Failed to upload file to S3")
            return jsonify({"error": "Failed to upload file to storage"}), 500

        logger.info(f"File uploaded to S3: {cv_link}")

        # Extract CV information
        logger.info("Extracting CV information...")
        cv_data = cv_parser.extract_cv_info(file_path)
        if not cv_data:
            logger.warning("CV data extraction failed.")
            return jsonify({"error": "CV parsing failed"}), 500
        logger.info("CV data extracted successfully")

        # Prepare application data
        application_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "cv_link": cv_link,
            "cv_data": cv_data,
        }

        # Add to Google Sheet
        google_sheet_service.add_entry(application_data, cv_link)

        # Send webhook notification
        webhook_service.send_notification(application_data, status="prod")

        # Queue follow-up email
        try:
            email_service.queue_follow_up_email({"email": email, "name": name})
        except Exception as e:
            logger.error(f"Error queueing follow-up email: {e}")

        logger.info("Application submission successful!")
        return jsonify({"message": "Application submitted successfully!", "cv_link": cv_link}), 200

    except Exception as e:
        logger.error(f"Submission error: {e}")
        return jsonify({"error": "Submission failed"}), 500


@app.route("/api/download/<filename>", methods=["GET"])
def download_file(filename):
    """Provide download endpoint for uploaded files"""
    try:
        safe_filename = os.path.basename(filename)  # Prevent directory traversal
        file_path = os.path.join(UPLOAD_FOLDER, safe_filename)

        if not os.path.exists(file_path):
            logger.warning(f"File not found: {safe_filename}")
            return jsonify({"error": "File not found"}), 404

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        logger.error(f"File download error: {e}")
        return jsonify({"error": "File download failed"}), 500


if __name__ == "__main__":
    # Start the email scheduler when app starts
    email_service.start_scheduler()

    # Get port from environment variable with a fallback
    port = os.getenv("PORT", None)
    if port is None:
        port = 5000  # Default port if not specified
    else:
        try:
            port = int(port)
        except ValueError:
            print(f"Invalid PORT value: {port}. Using default port 5000 instead.")
            port = 5000
            
    print(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port)