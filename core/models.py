import math, uuid
from datetime import date
from django.conf import settings
from django.db import models
from django.db.models import Max
from django.utils import timezone
from django.utils.text import slugify
from .validators import validate_image, validate_pdf


def up(folder):
    def _path(instance, filename):
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        stem = slugify(filename.rsplit(".", 1)[0])[:40] or "file"
        return f"{folder}/{stem}-{uuid.uuid4().hex[:8]}.{ext}"

    _path.__qualname__ = f"up_{folder}"
    return _path


# Named wrappers (migration-serialisable)
def p_profile(i, f):
    return up("profile")(i, f)


def p_site(i, f):
    return up("site")(i, f)


def p_edu(i, f):
    return up("education")(i, f)


def p_proj(i, f):
    return up("projects")(i, f)


def p_shot(i, f):
    return up("projects/screenshots")(i, f)


def p_blog(i, f):
    return up("blog")(i, f)


def p_journey(i, f):
    return up("journey")(i, f)


def p_cert_img(i, f):
    return up("certifications/images")(i, f)


def p_cert_pdf(i, f):
    return up("certifications/pdf")(i, f)


def p_resume_pdf(i, f):
    return up("resume/pdf")(i, f)


def p_resume_img(i, f):
    return up("resume/previews")(i, f)


def p_library(i, f):
    return up("library")(i, f)


IMG = dict(validators=[validate_image], blank=True)


class Singleton(models.Model):
    class Meta:
        abstract = True

    @classmethod
    def load(cls):
        obj = cls.objects.first()
        return obj or cls.objects.create()


class Profile(Singleton):
    name = models.CharField(max_length=120, default="[PERSON_NAME]")
    title = models.CharField(
        "Professional title", max_length=160, default="[PROFESSIONAL_TITLE]"
    )
    tagline = models.CharField(max_length=240, default="[SHORT_TAGLINE]", blank=True)
    intro = models.TextField(
        "Short introduction", default="[SHORT_INTRODUCTION]", blank=True
    )
    about = models.TextField(
        "About description", default="[ABOUT_DESCRIPTION]", blank=True
    )
    focus = models.CharField(
        "Professional focus", max_length=240, default="[PROFESSIONAL_FOCUS]", blank=True
    )
    interests = models.CharField(
        max_length=240, default="[INTERESTS]", blank=True, help_text="Comma separated"
    )
    email = models.CharField(max_length=160, default="[EMAIL_ADDRESS]", blank=True)
    phone = models.CharField(max_length=60, default="[PHONE_NUMBER]", blank=True)
    location = models.CharField(max_length=160, default="[LOCATION]", blank=True)
    image = models.ImageField("Profile image", upload_to=p_profile, **IMG)

    def __str__(self):
        return self.name

    @property
    def interest_list(self):
        return [i.strip() for i in self.interests.split(",") if i.strip()]


class SiteSettings(Singleton):
    site_name = models.CharField(max_length=120, default="Antony Roshan")
    description = models.CharField(max_length=300, default="Portfolio", blank=True)
    seo_title = models.CharField(
        "SEO title", max_length=160, default="Antony Roshan", blank=True
    )
    seo_description = models.CharField(
        "SEO description", max_length=300, default="Personal Portfolio", blank=True
    )
    favicon = models.ImageField(upload_to=p_site, **IMG)
    og_image = models.ImageField("Open Graph image", upload_to=p_site, **IMG)
    footer_text = models.CharField(
        max_length=300, default="© 2026 Antony Roshan. All rights reserved.", blank=True
    )
    primary_email = models.CharField(
        max_length=160,
        default="[EMAIL_ADDRESS]",
        blank=True,
        help_text="Shown in the footer.",
    )

    def __str__(self):
        return self.site_name


class Ordered(models.Model):
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True

    def save(self, *a, **kw):
        if not self.pk and not self.order:
            self.order = (type(self).objects.aggregate(m=Max("order"))["m"] or 0) + 1
        super().save(*a, **kw)


class SocialLink(Ordered):
    label = models.CharField(max_length=60, help_text="e.g. GitHub, LinkedIn")
    url = models.CharField("URL", max_length=300)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.label


class Education(Ordered):
    institution = models.CharField(max_length=200)
    degree = models.CharField(max_length=200)
    field = models.CharField("Field of study", max_length=200, blank=True)
    start_year = models.CharField(max_length=12, blank=True)
    end_year = models.CharField(
        max_length=12, blank=True, help_text="Year or 'Present'"
    )
    grade = models.CharField(max_length=80, blank=True)
    location = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField("Image / logo", upload_to=p_edu, **IMG)

    class Meta:
        ordering = ["order", "id"]
        verbose_name_plural = "education"

    def __str__(self):
        return f"{self.degree} – {self.institution}"

    @property
    def years(self):
        return " – ".join(x for x in (self.start_year, self.end_year) if x)


class Skill(Ordered):
    PRESET_CATEGORIES = [
        "Languages",
        "Tools",
        "Other",
    ]
    name = models.CharField(max_length=80)
    category = models.CharField(
        max_length=60,
        default="Other",
        help_text="Pick an existing category or type a new one.",
    )
    icon = models.CharField(
        max_length=40, blank=True, help_text="Optional short text/ icon"
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name

    def save(self, *a, **kw):
        cat = " ".join((self.category or "").split()) or "Other"
        # Reuse the spelling of an existing category (case-insensitive)
        existing = (
            Skill.objects.filter(category__iexact=cat)
            .exclude(pk=self.pk)
            .values_list("category", flat=True)
            .first()
        )
        self.category = existing or cat
        super().save(*a, **kw)


class Project(Ordered):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    thumbnail = models.ImageField(upload_to=p_proj, **IMG)
    short_description = models.CharField("One-line description", max_length=240)
    full_description = models.TextField("Overview", blank=True)
    technologies = models.CharField(
        max_length=400, blank=True, help_text="Comma separated"
    )
    problem = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    features = models.TextField(blank=True, help_text="One feature per line")
    implementation = models.TextField(blank=True)
    github_url = models.CharField("GitHub URL", max_length=300, blank=True)
    live_url = models.CharField("Live URL", max_length=300, blank=True)
    year = models.CharField(max_length=12, blank=True)
    featured = models.BooleanField(default=False)
    published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-id"]

    def __str__(self):
        return self.title

    def save(self, *a, **kw):
        self.slug = unique_slug(self, self.slug or self.title)
        super().save(*a, **kw)

    @property
    def tech_list(self):
        return [t.strip() for t in self.technologies.split(",") if t.strip()]

    @property
    def feature_list(self):
        return [l.strip() for l in self.features.splitlines() if l.strip()]

    def get_absolute_url(self):
        return f"/projects/{self.slug}/"


class ProjectImage(models.Model):
    project = models.ForeignKey(
        Project, related_name="images", on_delete=models.CASCADE
    )
    image = models.ImageField(upload_to=p_shot, validators=[validate_image])
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class BlogPost(models.Model):
    DRAFT, PUBLISHED = "draft", "published"
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    thumbnail = models.ImageField(upload_to=p_blog, **IMG)
    excerpt = models.CharField("One-line description", max_length=300)
    content = models.TextField(
        help_text="Blank line = new paragraph. '## ' = heading. '- ' = list item."
    )
    author = models.CharField(max_length=120, default="Antony Roshan")
    category = models.CharField(max_length=80, default="General")
    published_at = models.DateField("Publication date", default=date.today)
    reading_time = models.PositiveIntegerField(
        "Reading time (min)", default=0, help_text="0 = calculate automatically"
    )
    featured = models.BooleanField(default=False)
    status = models.CharField(
        max_length=10,
        choices=[(DRAFT, "Draft"), (PUBLISHED, "Published")],
        default=DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at", "-id"]

    def __str__(self):
        return self.title

    def save(self, *a, **kw):
        self.slug = unique_slug(self, self.slug or self.title)
        if not self.reading_time:
            self.reading_time = max(1, math.ceil(len(self.content.split()) / 200))
        super().save(*a, **kw)

    @property
    def is_published(self):
        return self.status == self.PUBLISHED

    def get_absolute_url(self):
        return f"/blog/{self.slug}/"


class JourneyEntry(Ordered):
    CATEGORIES = [
        (c.lower(), c)
        for c in (
            "Education",
            "Internship",
            "Project",
            "Event",
            "Hackathon",
            "Achievement",
            "Certification",
            "Activity",
            "Other",
        )
    ]
    date = models.DateField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to=p_journey, **IMG)
    category = models.CharField(max_length=20, choices=CATEGORIES, default="other")
    location = models.CharField(max_length=160, blank=True)
    link = models.CharField("External link", max_length=300, blank=True)
    published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "-date"]
        verbose_name_plural = "journey entries"

    def __str__(self):
        return self.title

    @property
    def year(self):
        return self.date.year


class Certification(Ordered):
    title = models.CharField(max_length=200)
    organization = models.CharField("Issuing organization", max_length=200)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    credential_id = models.CharField(max_length=120, blank=True)
    credential_url = models.CharField(max_length=300, blank=True)
    image = models.ImageField("Preview image", upload_to=p_cert_img, **IMG)
    pdf = models.FileField(
        "PDF", upload_to=p_cert_pdf, validators=[validate_pdf], blank=True
    )
    description = models.TextField(blank=True)
    featured = models.BooleanField(default=False)
    published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "-issue_date"]

    def __str__(self):
        return self.title


class Resume(models.Model):
    title = models.CharField(max_length=160, default="[RESUME_TITLE]")
    version = models.CharField(max_length=40, blank=True, default="v1")
    pdf = models.FileField(
        "Resume PDF", upload_to=p_resume_pdf, validators=[validate_pdf]
    )
    preview_image = models.ImageField(upload_to=p_resume_img, **IMG)
    uploaded_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.title} ({self.version})"

    def save(self, *a, **kw):
        super().save(*a, **kw)
        if self.is_active:  # only one active resume
            Resume.objects.exclude(pk=self.pk).filter(is_active=True).update(
                is_active=False
            )


class MediaFile(models.Model):
    file = models.FileField(upload_to=p_library)
    title = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    message = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.message[:40]}"


class Activity(models.Model):
    user = models.CharField(max_length=150)
    text = models.CharField(max_length=300)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]
        verbose_name_plural = "activities"


def unique_slug(obj, source):
    base = slugify(source)[:200] or "item"
    slug, n = base, 2
    qs = type(obj).objects.exclude(pk=obj.pk)
    while qs.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


# ---- File housekeeping: remove files from storage when rows are deleted or files replaced ----
from django.db.models.signals import post_delete, pre_save  # noqa: E402
from django.db.models import FileField  # noqa: E402


def _file_fields(instance):
    return [f for f in instance._meta.get_fields() if isinstance(f, FileField)]


def _cleanup_deleted(sender, instance, **kw):
    if sender._meta.app_label != "core":
        return
    for f in _file_fields(instance):
        fl = getattr(instance, f.name)
        if fl:
            fl.delete(save=False)


def _cleanup_replaced(sender, instance, **kw):
    if sender._meta.app_label != "core" or not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    for f in _file_fields(instance):
        o, n = getattr(old, f.name), getattr(instance, f.name)
        if o and o.name != (n.name if n else None):
            o.delete(save=False)


post_delete.connect(_cleanup_deleted)
pre_save.connect(_cleanup_replaced)
