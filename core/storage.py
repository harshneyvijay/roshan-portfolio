from django.conf import settings
from storages.backends.s3 import S3Storage


def _drop_expect(params, **kwargs):
    # Some S3-compatible gateways mishandle "Expect: 100-continue" on uploads.
    params["headers"].pop("Expect", None)


class ProxiedS3Storage(S3Storage):
    """S3-compatible storage whose files are served through this site's /media/ route.

    Works with private buckets (Neon Object Storage, R2, Supabase...) because the browser never talks to the
    bucket directly. If AWS_S3_CUSTOM_DOMAIN is set (public bucket/CDN) URLs point there instead.
    """
    @property
    def connection(self):
        conn = S3Storage.connection.fget(self)
        events = conn.meta.client.meta.events
        if not getattr(events, "_no_expect", False):
            events.register("before-call.s3.PutObject", _drop_expect)
            events.register("before-call.s3.UploadPart", _drop_expect)
            events._no_expect = True
        return conn

    def url(self, name, parameters=None, expire=None, http_method=None):
        if self.custom_domain:
            return super().url(name, parameters, expire, http_method)
        return settings.MEDIA_URL + name.lstrip("/")
