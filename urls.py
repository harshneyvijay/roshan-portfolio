import mimetypes
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.urls import include, path, re_path


def media(request, path):
    """Serve uploads inline (so PDFs open in the browser viewer). Put nginx/CDN in front for heavy traffic."""
    try:
        f = default_storage.open(path, "rb")
    except (FileNotFoundError, OSError, ValueError):
        raise Http404
    except Exception:  # SuspiciousFileOperation (path traversal) etc.
        raise Http404
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    resp = FileResponse(f, content_type=ctype)
    resp["Cache-Control"] = "public, max-age=3600"
    return resp


urlpatterns = [
    path("cms/", include("core.cms_urls")),
    path("", include("core.urls")),
]
urlpatterns += [re_path(r"^media/(?P<path>.+)$", media)]
