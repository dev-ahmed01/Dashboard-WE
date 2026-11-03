import io
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from .config import get_settings


class ObjectStore:
    def __init__(self):
        s = get_settings()
        self.bucket = s.s3_bucket
        self.client = boto3.client('s3', endpoint_url=s.s3_endpoint_url, aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key, region_name='us-east-1',
            config=Config(signature_version='s3v4', connect_timeout=3, retries={'max_attempts': 2}))

    def ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, key: str, content: bytes, media_type: str):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=media_type)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)['Body'].read()
