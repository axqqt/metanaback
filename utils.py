import os
import requests
from PyPDF2 import PdfReader
from docx import Document
from datetime import datetime

# Upload file to S3 using pre-signed URLs (alternative to boto3)
def upload_to_s3(file_path):
    bucket_name = os.getenv('S3_BUCKET_NAME')
    file_name = os.path.basename(file_path)
    
    # Generate pre-signed URL for S3 upload
    url = f"https://{bucket_name}.s3.amazonaws.com/{file_name}"
    
    # Read file content
    with open(file_path, 'rb') as file:
        file_data = file.read()
    
    # Upload file to S3 using HTTP PUT
    headers = {
        'Content-Type': 'application/octet-stream',
        'x-amz-acl': 'public-read'
    }
    response = requests.put(url, data=file_data, headers=headers)
    
    if response.status_code != 200:
        raise Exception("Failed to upload file to S3")
    
    # Return public URL
    return url

# Parse CV using regex (alternative to spacy)
def parse_cv(file_path):
    if file_path.endswith('.pdf'):
        reader = PdfReader(file_path)
        text = ''.join(page.extract_text() or '' for page in reader.pages)  # Handle None values
    elif file_path.endswith('.docx'):
        doc = Document(file_path)
        text = '\n'.join([para.text for para in doc.paragraphs])
    else:
        raise ValueError("Unsupported file format. Only PDF and DOCX are allowed.")

    # Extract personal info using regex
    import re
    email_match = re.search(r"[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]+", text)
    phone_match = re.search(r"\+?\d[\d -]{8,}\d", text)
    name_match = re.search(r"([A-Z][a-z]+)\s([A-Z][a-z]+)", text)

    personal_info = {}
    if name_match:
        personal_info['NAME'] = name_match.group()
    if email_match:
        personal_info['EMAIL'] = email_match.group()
    if phone_match:
        personal_info['PHONE'] = phone_match.group()

    # Extract sections using keyword matching
    education = [line for line in text.split('\n') if any(keyword in line.lower() for keyword in ['education', 'degree'])]
    qualifications = [line for line in text.split('\n') if any(keyword in line.lower() for keyword in ['skills', 'qualifications'])]
    projects = [line for line in text.split('\n') if any(keyword in line.lower() for keyword in ['project', 'experience'])]

    return {
        "personal_info": personal_info,
        "education": education,
        "qualifications": qualifications,
        "projects": projects
    }

# Send webhook
def send_webhook(cv_data, metadata):
    url = os.getenv('WEBHOOK_URL')
    headers = {
        "X-Candidate-Email": os.getenv('CANDIDATE_EMAIL')
    }
    payload = {
        "cv_data": cv_data,
        "metadata": {
            "applicant_name": metadata.get("name", "Unknown"),
            "email": metadata.get("email", "Unknown"),
            "status": "prod",
            "cv_processed": True,
            "processed_timestamp": datetime.utcnow().isoformat()
        }
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.status_code

# Schedule follow-up email using SMTP (alternative to SES)
def schedule_followup_email(email, timezone="UTC"):
    import smtplib
    from email.mime.text import MIMEText

    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('EMAIL_PASSWORD')
    subject = 'Your CV is Under Review'
    body = 'Thank you for your application. Your CV is currently under review.'

    # Create email message
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = email

    try:
        # Connect to SMTP server (e.g., Gmail)
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email, msg.as_string())
        return 200
    except Exception as e:
        print(f"Error sending email: {e}")
        return 500