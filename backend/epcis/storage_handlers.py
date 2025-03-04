import os
import logging
from enum import Enum
from typing import Dict, Any, BinaryIO, Optional
from abc import ABC, abstractmethod
import shutil
from pathlib import Path
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StorageType(Enum):
    """Enum for different storage types"""
    LOCAL = "local"
    S3 = "s3"
    FTP = "ftp"

class StorageHandler(ABC):
    """Abstract base class for storage handlers"""
    
    @abstractmethod
    def store_file(self, file_content: bytes, file_name: str, supplier_id: str) -> str:
        """Store a file and return the file location"""
        pass
    
    @abstractmethod
    def retrieve_file(self, file_location: str) -> bytes:
        """Retrieve a file's content"""
        pass
    
    @abstractmethod
    def generate_presigned_url(self, file_location: str, expiration: int = 3600) -> str:
        """Generate a pre-signed URL for file access"""
        pass

class LocalStorageHandler(StorageHandler):
    """Handler for local file storage"""
    
    def __init__(self, config: Dict[str, Any]):
        self.base_path = config.get('base_path', 'storage/epcis')
        self.base_path = os.path.abspath(self.base_path)
        logger.info(f"Initializing local storage handler with base path: {self.base_path}")
        os.makedirs(self.base_path, exist_ok=True)
    
    def store_file(self, file_content: bytes, file_name: str, supplier_id: str) -> str:
        """Store a file in the local filesystem"""
        try:
            # Create supplier directory
            supplier_dir = os.path.join(self.base_path, supplier_id)
            os.makedirs(supplier_dir, exist_ok=True)
            logger.info(f"Storing file in directory: {supplier_dir}")
            
            # Store file
            file_path = os.path.join(supplier_dir, file_name)
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            logger.info(f"File successfully stored at: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error storing file locally: {str(e)}")
            raise
    
    def retrieve_file(self, file_location: str) -> bytes:
        """Retrieve a file from the local filesystem"""
        try:
            logger.info(f"Retrieving file from: {file_location}")
            if not os.path.exists(file_location):
                logger.error(f"File not found: {file_location}")
                raise FileNotFoundError(f"File not found: {file_location}")
                
            with open(file_location, 'rb') as f:
                content = f.read()
            return content
        except Exception as e:
            logger.error(f"Error retrieving file: {str(e)}")
            raise
    
    def generate_presigned_url(self, file_location: str, expiration: int = 3600) -> str:
        """For local files, just return the absolute path"""
        # For local storage, we can't generate a pre-signed URL
        # Just return the absolute path
        if not os.path.exists(file_location):
            logger.warning(f"File not found when generating URL: {file_location}")
        return os.path.abspath(file_location)

class S3StorageHandler(StorageHandler):
    """Handler for S3 file storage"""
    
    def __init__(self, config: Dict[str, Any]):
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError
            
            self.bucket_name = config.get('bucket_name')
            self.region = config.get('region', 'us-east-1')
            
            # Initialize S3 client
            aws_access_key = config.get('aws_access_key')
            aws_secret_key = config.get('aws_secret_key')
            
            if not self.bucket_name:
                raise ValueError("S3 bucket name must be provided")
            
            # If keys are provided, use them, otherwise use the AWS credentials provider chain
            if aws_access_key and aws_secret_key:
                self.s3_client = boto3.client(
                    's3',
                    region_name=self.region,
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key
                )
            else:
                self.s3_client = boto3.client('s3', region_name=self.region)
                
        except (ImportError, NoCredentialsError) as e:
            logger.error(f"Error initializing S3 storage handler: {e}")
            raise
    
    def store_file(self, file_content: bytes, file_name: str, supplier_id: str) -> str:
        """Store a file in S3"""
        try:
            # Create S3 key
            s3_key = f"epcis/{supplier_id}/{file_name}"
            
            # Upload file
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content
            )
            
            return f"s3://{self.bucket_name}/{s3_key}"
            
        except Exception as e:
            logger.error(f"Error storing file in S3: {e}")
            raise
    
    def retrieve_file(self, file_location: str) -> bytes:
        """Retrieve a file from S3"""
        try:
            # Parse S3 URI
            if file_location.startswith('s3://'):
                path = file_location[5:]  # Remove s3:// prefix
                bucket_name = path.split('/')[0]
                s3_key = '/'.join(path.split('/')[1:])
            else:
                raise ValueError(f"Invalid S3 URI: {file_location}")
            
            # Download file
            response = self.s3_client.get_object(
                Bucket=bucket_name,
                Key=s3_key
            )
            
            return response['Body'].read()
            
        except Exception as e:
            logger.error(f"Error retrieving file from S3: {e}")
            raise
    
    def generate_presigned_url(self, file_location: str, expiration: int = 3600) -> str:
        """Generate a pre-signed URL for S3 file access"""
        try:
            # Parse S3 URI
            if file_location.startswith('s3://'):
                path = file_location[5:]  # Remove s3:// prefix
                bucket_name = path.split('/')[0]
                s3_key = '/'.join(path.split('/')[1:])
            else:
                raise ValueError(f"Invalid S3 URI: {file_location}")
            
            # Generate presigned URL
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            
            return url
            
        except Exception as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise

class FTPStorageHandler(StorageHandler):
    """Handler for FTP file storage"""
    
    def __init__(self, config: Dict[str, Any]):
        self.host = config.get('host')
        self.username = config.get('username')
        self.password = config.get('password')
        self.base_dir = config.get('base_dir', '/')
        
        # Local cache directory for temporary files
        self.cache_dir = config.get('cache_dir', 'storage/ftp_cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        if not self.host:
            raise ValueError("FTP host must be provided")
    
    def store_file(self, file_content: bytes, file_name: str, supplier_id: str) -> str:
        """Store a file in FTP server"""
        try:
            import ftplib
            
            # Create FTP connection
            ftp = ftplib.FTP(self.host)
            ftp.login(self.username, self.password)
            
            # Navigate to target directory
            target_dir = os.path.join(self.base_dir, 'epcis', supplier_id).replace('\\', '/')
            
            # Create directories if they don't exist
            dirs_to_create = target_dir.split('/')
            current_dir = ''
            
            for directory in dirs_to_create:
                if not directory:
                    continue
                    
                current_dir += '/' + directory
                
                try:
                    ftp.cwd(current_dir)
                except ftplib.error_perm:
                    ftp.mkd(current_dir)
                    ftp.cwd(current_dir)
            
            # Upload file
            ftp.storbinary(f"STOR {file_name}", BytesIO(file_content))
            
            # Close connection
            ftp.quit()
            
            return f"ftp://{self.host}/{target_dir}/{file_name}"
            
        except ImportError:
            logger.error("ftplib is required for FTP storage")
            raise
        except Exception as e:
            logger.error(f"Error storing file in FTP: {e}")
            raise
    
    def retrieve_file(self, file_location: str) -> bytes:
        """Retrieve a file from FTP server"""
        try:
            import ftplib
            from io import BytesIO
            
            # Parse FTP URI
            if file_location.startswith('ftp://'):
                path = file_location[6:]  # Remove ftp:// prefix
                host = path.split('/')[0]
                ftp_path = '/' + '/'.join(path.split('/')[1:])
            else:
                raise ValueError(f"Invalid FTP URI: {file_location}")
            
            # Create FTP connection
            ftp = ftplib.FTP(host)
            ftp.login(self.username, self.password)
            
            # Download file
            buffer = BytesIO()
            ftp.retrbinary(f"RETR {ftp_path}", buffer.write)
            
            # Close connection
            ftp.quit()
            
            return buffer.getvalue()
            
        except ImportError:
            logger.error("ftplib is required for FTP storage")
            raise
        except Exception as e:
            logger.error(f"Error retrieving file from FTP: {e}")
            raise
    
    def generate_presigned_url(self, file_location: str, expiration: int = 3600) -> str:
        """FTP doesn't support presigned URLs, so download to cache and return local path"""
        try:
            # Parse FTP path
            if file_location.startswith('ftp://'):
                path = file_location[6:]  # Remove ftp:// prefix
                file_name = path.split('/')[-1]
            else:
                file_name = os.path.basename(file_location)
            
            # Download to cache
            content = self.retrieve_file(file_location)
            cache_path = os.path.join(self.cache_dir, file_name)
            
            with open(cache_path, 'wb') as f:
                f.write(content)
            
            return os.path.abspath(cache_path)
            
        except Exception as e:
            logger.error(f"Error generating URL for FTP file: {e}")
            raise

def get_storage_handler(storage_type: StorageType, config: Dict[str, Any]) -> StorageHandler:
    """Factory function to get the appropriate storage handler"""
    if storage_type == StorageType.LOCAL:
        return LocalStorageHandler(config)
    elif storage_type == StorageType.S3:
        return S3StorageHandler(config)
    elif storage_type == StorageType.FTP:
        return FTPStorageHandler(config)
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")