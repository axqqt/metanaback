import logging
import boto3
from botocore.exceptions import NoCredentialsError

logger = logging.getLogger(__name__)
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from a .env file


class S3StorageService:
    """Service for handling S3 storage operations"""
    
    def __init__(self, bucket_name, access_key, secret_key):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
    def upload_file(self, file_path, file_name):
        """Upload file to S3 and return public URL"""
        try:
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                file_name,
                ExtraArgs={'ACL': 'public-read'}
            )
            return f"https://{self.bucket_name}.s3.amazonaws.com/{file_name}"
        except NoCredentialsError:
            logger.error("S3 credentials not available")
            return None
        except Exception as e:
            logger.error(f"S3 upload error: {e}")
            return None