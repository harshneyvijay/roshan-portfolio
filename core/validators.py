import os
from django.conf import settings
from django.core.exceptions import ValidationError

def validate_image(f):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".ico"):
        raise ValidationError("Upload a JPG, PNG, WebP, GIF or ICO image.")
    if f.size > settings.MAX_IMAGE_MB * 1024 * 1024:
        raise ValidationError(f"Image is larger than {settings.MAX_IMAGE_MB} MB.")

def validate_pdf(f):
    if os.path.splitext(f.name)[1].lower() != ".pdf":
        raise ValidationError("Upload a PDF file.")
    if f.size > settings.MAX_PDF_MB * 1024 * 1024:
        raise ValidationError(f"PDF is larger than {settings.MAX_PDF_MB} MB.")
    pos = f.tell() if hasattr(f, "tell") else 0
    head = f.read(5)
    f.seek(pos)
    if head != b"%PDF-":
        raise ValidationError("This file is not a valid PDF.")
