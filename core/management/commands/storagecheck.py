"""Diagnose file-storage configuration: python manage.py storagecheck"""

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage as d
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Upload, read and delete a small test file to verify storage settings"

    def handle(self, *a, **o):
        opts = settings.STORAGES["default"].get("OPTIONS", {})
        self.stdout.write(f"Backend : {settings.STORAGES['default']['BACKEND']}")
        for k in ("bucket_name", "endpoint_url", "region_name", "addressing_style"):
            if k in opts:
                self.stdout.write(f"{k:17}: {opts[k]}")
        if "access_key" in opts:
            self.stdout.write(
                f"access_key set   : {bool(opts['access_key'])}   secret_key set: {bool(opts['secret_key'])}"
            )
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            ClientError = ()
        name = "_storagecheck/test.bin"
        try:
            d.save(name, ContentFile(b"x" * 3000))
            self.stdout.write("upload   : OK")
            self.stdout.write(
                f"read     : {'OK' if d.open(name).read() == b'x' * 3000 else 'MISMATCH'}"
            )
            d.delete(name)
            self.stdout.write(self.style.SUCCESS("delete   : OK  -> storage works."))
        except ClientError as e:
            meta = e.response.get("ResponseMetadata", {})
            self.stdout.write(self.style.ERROR(f"FAILED: {e}"))
            self.stdout.write(f"HTTP status : {meta.get('HTTPStatusCode')}")
            self.stdout.write(f"Error       : {e.response.get('Error')}")
            self.stdout.write(
                f"Headers     : { {k: v for k, v in meta.get('HTTPHeaders', {}).items() if k.lower() not in ('set-cookie',)} }"
            )
            code = meta.get("HTTPStatusCode")
            hint = {
                404: "Bucket not found: check AWS_STORAGE_BUCKET_NAME and that the bucket exists on this Supabase branch.",
                403: "Access denied: check the key/secret and that the credential has storage:read AND storage:write.",
                400: "Bad request: check AWS_S3_ENDPOINT_URL (must be the branch s3_endpoint) and AWS_S3_REGION_NAME.",
            }.get(
                code,
                "Unexpected response: compare endpoint and region with GET .../branches/BRANCH_ID/storage.",
            )
            self.stdout.write(self.style.WARNING(hint))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"FAILED: {type(e).__name__}: {e}"))
