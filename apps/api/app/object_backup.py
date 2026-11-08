"""Stream the application S3 bucket to/from a TAR stream for age-encrypted backup.

EXPORT writes ONLY tar bytes to stdout. IMPORT accepts only a new, EMPTY
bucket and refuses corrupt, duplicated or extraneous archive entries.
Start with website writes frozen to keep SQL and object backup consistent.
Do not publish or run this as an HTTP endpoint.
"""
import argparse
import hashlib
import io
import json
import sys
import tarfile

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


from .config import get_settings


def _settings():
    s = get_settings()
    return {"bucket": s.s3_bucket, "endpoint": s.s3_endpoint_url,
            "access_key": s.s3_access_key, "secret_key": s.s3_secret_key}


def _storage():
    config = _settings()
    bucket = config["bucket"]
    if not bucket or not config["access_key"] or not config["secret_key"]:
        raise RuntimeError("Configured private object-store credentials required")
    client = boto3.client(
        "s3",
        endpoint_url=config["endpoint"],
        aws_access_key_id=config["access_key"],
        aws_secret_access_key=config["secret_key"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4", connect_timeout=10,
                      read_timeout=120, retries={"max_attempts": 2}),
    )
    return client, bucket


def _keys(client, bucket):
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for item in page.get("Contents", ()):
            yield item["Key"]


class _HashingReader:
    def __init__(self, raw):
        self.raw = raw
        self.digest = hashlib.sha256()
        self.bytes_read = 0

    def read(self, size=-1):
        chunk = self.raw.read(size)
        if chunk:
            self.digest.update(chunk)
            self.bytes_read += len(chunk)
        return chunk


def export():
    client, bucket = _storage()
    # Read keys before starting the tar stream; an inaccessible bucket is a
    # fatal error, not an empty successful backup.
    client.head_bucket(Bucket=bucket)
    keys = sorted(_keys(client, bucket))
    entries = []
    with tarfile.open(mode="w|", fileobj=sys.stdout.buffer, format=tarfile.PAX_FORMAT) as tar:
        for key in keys:
            response = client.get_object(Bucket=bucket, Key=key)
            raw = response["Body"]
            try:
                reader = _HashingReader(raw)
                item = tarfile.TarInfo("objects/" + key.encode("utf-8").hex())
                item.size = int(response["ContentLength"])
                item.mtime = 0
                item.pax_headers = {"s3-content-type": str(response.get("ContentType") or "application/octet-stream")}
                tar.addfile(item, reader)
                if reader.bytes_read != item.size:
                    raise RuntimeError("Object length changed during backup")
                entries.append({"key": key, "size": item.size, "sha256": reader.digest.hexdigest()})
            finally:
                raw.close()
        manifest = json.dumps({"format": 1, "objects": entries}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest)
        info.mtime = 0
        tar.addfile(info, io.BytesIO(manifest))
    print(f"Exported {len(entries)} S3 objects; archive requires encryption and offsite retention.", file=sys.stderr)


def restore():
    client, bucket = _storage()
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status != 404:
            raise
        client.create_bucket(Bucket=bucket)
    if next(_keys(client, bucket), None) is not None:
        raise RuntimeError("Refusing import into a nonempty S3 bucket")
    observed = {}
    expected = None
    with tarfile.open(mode="r|", fileobj=sys.stdin.buffer) as tar:
        for member in tar:
            if not member.isfile() or member.size < 0:
                raise RuntimeError("Archive contains an unsupported non-file entry")
            stream = tar.extractfile(member)
            if stream is None:
                raise RuntimeError("Unreadable S3 archive entry")
            if member.name == "manifest.json":
                if expected is not None or member.size > 16_000_000:
                    raise RuntimeError("Invalid repeated or oversized manifest")
                manifest = json.loads(stream.read())
                if manifest.get("format") != 1 or not isinstance(manifest.get("objects"), list):
                    raise RuntimeError("Unsupported object backup version")
                expected = manifest["objects"]
                continue
            if expected is not None or not member.name.startswith("objects/"):
                raise RuntimeError("Unexpected object archive entry")
            try:
                key = bytes.fromhex(member.name[8:]).decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                raise RuntimeError("Invalid encoded object key") from exc
            if not key or key in observed or member.size > 536_870_912:
                raise RuntimeError("Duplicated, oversized or invalid S3 object")
            data = stream.read(member.size)
            if len(data) != member.size:
                raise RuntimeError("Truncated object archive")
            content_type = member.pax_headers.get("s3-content-type", "application/octet-stream")
            if not isinstance(content_type, str) or len(content_type) > 255:
                raise RuntimeError("Invalid object content type")
            client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
            observed[key] = {"key": key, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if not isinstance(expected, list) or expected != [observed[k] for k in sorted(observed)]:
        raise RuntimeError("Restore manifest/sha256 mismatch: dispose of isolated target")
    if sorted(_keys(client, bucket)) != sorted(observed):
        raise RuntimeError("Restored bucket key counts do not match")
    print(f"Restored and verified {len(observed)} S3 objects into empty isolated bucket.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Private S3 archive stream for disaster recovery")
    parser.add_argument("action", choices=("export", "import"))
    arg = parser.parse_args()
    if arg.action == "export":
        export()
    else:
        restore()


if __name__ == "__main__":
    main()
