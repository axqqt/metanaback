import os
import uuid
from werkzeug.utils import secure_filename

class FileService:
    """Service for handling file operations"""
    
    def __init__(self, upload_folder, allowed_extensions):
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        
    def allowed_file(self, filename):
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
               
    def generate_unique_filename(self, filename):
        """Generate a unique filename to prevent overwriting"""
        ext = filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{ext}"
        return unique_filename
        
    def save_file(self, file_obj):
        """Save file to upload folder and return the unique filename"""
        secure_filename_value = secure_filename(file_obj.filename)
        unique_filename = self.generate_unique_filename(secure_filename_value)
        file_path = os.path.join(self.upload_folder, unique_filename)
        file_obj.save(file_path)
        return unique_filename