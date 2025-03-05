import os
import uuid
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# File upload configuration
UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB file size limit

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_filename(filename):
    """Generate a unique filename to prevent overwriting"""
    ext = filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4()}.{ext}"
    return unique_filename

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
        
        # Optional: Send webhook (if webhook URL is provided)
        webhook_url = os.getenv('WEBHOOK_URL')
        if webhook_url:
            try:
                webhook_payload = {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "file_name": unique_filename
                }
                requests.post(webhook_url, json=webhook_payload, timeout=5)
            except Exception as webhook_error:
                logger.error(f"Webhook send error: {webhook_error}")
        
        # Prepare response
        return jsonify({
            "message": "Application submitted successfully!",
            "filename": unique_filename
        }), 200
    
    except Exception as e:
        logger.error(f"Submission error: {e}")
        return jsonify({"error": "Submission failed"}), 500

@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """
    Provide a download endpoint for uploaded files
    Only works if the filename is within the upload folder
    """
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

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy"}), 200

# Configure app for Railway
if __name__ == '__main__':
    # Railway automatically sets PORT environment variable
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)