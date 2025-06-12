from functools import lru_cache
from io import BytesIO
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client
else:
    S3Client = object

from app.utils import get_settings, log


@lru_cache
def s3_client() -> S3Client:
    """Get the S3 client."""
    if get_settings().aws_profile_name:
        log.debug(f"Creating S3 client with profile: {get_settings().aws_profile_name}")
        session = boto3.Session(profile_name=get_settings().aws_profile_name)
    else:
        log.debug("Creating S3 client with default profile")
        session = boto3.Session()
    return session.client(
        "s3",
    ) 


def upload_file_bytes(
    file_bytes: bytes, bucket: str, object_name: str, content_type: str = None
) -> bool:
    """
    Upload a file as bytes to an S3 bucket.

    :param file_bytes: bytes to upload
    :param bucket: S3 bucket
    :param object_name: S3 key (path)
    :param content_type: MIME type (optional)
    :return: True if uploaded successfully, False otherwise
    """
    extra_args = {}
    if content_type: 
        extra_args["ContentType"] = content_type
    try:
        s3_client().upload_fileobj(
            BytesIO(file_bytes), bucket, object_name, ExtraArgs=extra_args
        )
    except ClientError as e:
        log.error(e)
        return False
    log.debug(f"Uploaded {object_name} to bucket {bucket}")
    return True


def get_file_bytes(bucket: str, object_name: str) -> bytes:
    """
    Download a file from S3 and return its bytes.

    :param bucket: S3 bucket
    :param object_name: S3 key (path)
    :return: file bytes
    :raises: Exception if file does not exist or can't be downloaded
    """
    try:
        file_stream = BytesIO()
        s3_client().download_fileobj(bucket, object_name, file_stream)
        file_stream.seek(0)
        return file_stream.read()
    except ClientError as e:
        log.error(e)
        raise FileNotFoundError(
            f"Could not fetch {object_name} from bucket {bucket}: {e}"
        )


def get_file_stream(bucket: str, object_name: str):
    try:
        return s3_client().get_object(Bucket=bucket, Key=object_name)
    except s3_client().exceptions.NoSuchKey as e:
        log.error(e)
        raise FileNotFoundError(
            f"Could not fetch {object_name} from bucket {bucket}: {e}"
        )

def list_bucket_items(bucket: str, continuation_token: str | None = None):

    listObjectsArgs = {k: v for k, v in {
        "Bucket": bucket,
        "ContinuationToken": continuation_token
    }.items() if v is not None}

    try:
        return s3_client().list_objects_v2(**listObjectsArgs)
    except ClientError as e:
        log.error(e)
        raise FileNotFoundError(
            f"Could not list items in bucket {bucket}: {e}"
        )