"""Populate the site with placeholder content. Safe to re-run: skips if data exists unless --reset."""

import io, secrets
from datetime import date
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont
from core import models as m

ORANGES = ["#F97316", "#C2410C", "#FDBA74", "#EA580C", "#FB923C", "#9A3412"]


def placeholder(label, size=(1200, 750), i=0):
    img = Image.new("RGB", size, "#FFF7ED")
    d = ImageDraw.Draw(img)
    c = ORANGES[i % len(ORANGES)]
    d.rectangle([0, size[1] * 0.68, size[0], size[1]], fill=c)
    for k in range(0, size[0], 60):
        d.line([(k, 0), (k + size[1], size[1])], fill="#FFE8D2", width=2)
    d.rectangle([40, 40, size[0] - 40, size[1] - 40], outline="#111111", width=3)
    try:
        f = ImageFont.load_default(size=max(18, size[0] // 22))
    except TypeError:
        f = ImageFont.load_default()
    d.text((size[0] * 0.07, size[1] * 0.38), label, fill="#111111", font=f)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return ContentFile(buf.getvalue())


def sample_pdf(title):
    text = f"({title} - placeholder PDF. Replace in the CMS.) Tj"
    stream = f"BT /F1 20 Tf 72 700 Td {text} ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offs = b"%PDF-1.4\n", []
    for n, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{n} 0 obj\n{o}\nendobj\n".encode()
    x = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
    out += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF".encode()
    return ContentFile(out)


class Command(BaseCommand):
    help = "Create placeholder content and an admin user"

    def add_arguments(self, p):
        p.add_argument(
            "--reset", action="store_true", help="Delete existing content first"
        )
        p.add_argument("--admin-user", default="admin")
        p.add_argument("--admin-password", default="")

    def handle(self, *a, **o):
        if o["reset"]:
            for M in (
                m.Project,
                m.BlogPost,
                m.JourneyEntry,
                m.Certification,
                m.Resume,
                m.Education,
                m.Skill,
                m.SocialLink,
                m.ContactMessage,
            ):
                for obj in M.objects.all():
                    obj.delete()
        elif m.Project.objects.exists():
            self.stdout.write("Content already exists – use --reset to replace it.")
            return self.make_admin(o)

        pr = m.Profile.load()
        pr.image.save(
            "profile.jpg", placeholder("PROFILE_IMAGE", (800, 1000), 0), save=False
        )
        pr.intro = (
            "SHORT_INTRODUCTION] A sentence or two about what you do and who you help."
        )
        pr.about = (
            "ABOUT_DESCRIPTION]\n\nReplace this text from CMS → Profile. Use a blank line to start a new paragraph. "
            "Describe your background, what you care about and what you are working on."
        )
        pr.save()
        s = m.SiteSettings.load()
        s.favicon.save("favicon.png", placeholder("P", (128, 128), 0), save=False)
        s.og_image.save("og.jpg", placeholder("SITE_NAME", (1200, 630), 1), save=False)
        s.save()

        for i, (label, url) in enumerate(
            [
                ("GitHub", "GITHUB_URL"),
                ("LinkedIn", "LINKEDIN_URL"),
                ("Instagram", "INSTAGRAM_URL"),
                ("Twitter", "TWITTER_URL"),
                ("Other", "OTHER_SOCIAL_URL"),
            ],
            1,
        ):
            m.SocialLink.objects.create(label=label, url=url, order=i)

        for i in (1, 2):
            e = m.Education(
                institution=f"INSTITUTION_NAME_0{i}",
                degree=f"DEGREE_NAME_0{i}",
                field="FIELD_OF_STUDY",
                start_year="START_YEAR",
                end_year="END_YEAR",
                grade="GRADE",
                location="LOCATION",
                description="EDUCATION_DESCRIPTION",
            )
            e.logo.save(f"edu{i}.jpg", placeholder("LOGO", (300, 300), i), save=False)
            e.save()

        cats = {"languages": ["SKILL_01"]}
        for c, names in cats.items():
            for n in names:
                m.Skill.objects.create(name=n, category=c)

        for i in (1, 2, 3):
            p = m.Project(
                title=f"PROJECT_TITLE_0{i}",
                short_description="PROJECT_SHORT_DESCRIPTION",
                full_description="PROJECT_FULL_DESCRIPTION",
                technologies="PROJECT_TECHNOLOGIES], TECH_02, TECH_03",
                problem="PROJECT_PROBLEM",
                solution="PROJECT_SOLUTION",
                implementation="PROJECT_IMPLEMENTATION",
                features="FEATURE_01\nFEATURE_02\nFEATURE_03",
                github_url="PROJECT_GITHUB_URL",
                live_url="PROJECT_LIVE_URL",
                year="YEAR",
                featured=i == 1,
            )
            p.thumbnail.save(
                f"project{i}.jpg",
                placeholder(f"PROJECT_THUMBNAIL_0{i}", i=i),
                save=False,
            )
            p.save()
            for k in (1, 2):
                pi = m.ProjectImage(
                    project=p, order=k, caption=f"SCREENSHOT_CAPTION_{k}"
                )
                pi.image.save(
                    f"shot{i}{k}.jpg",
                    placeholder(f"SCREENSHOT_{k}", i=i + k),
                    save=False,
                )
                pi.save()

        for i in (1, 2, 3):
            b = m.BlogPost(
                title=f"BLOG_TITLE_0{i}",
                excerpt="BLOG_EXCERPT",
                author="Antony Roshan",
                category="General",
                published_at=date(2025, i, 10),
                status="published" if i < 3 else "draft",
                content="Content\n\n## A heading\n\nWrite with blank lines between paragraphs. Use **bold** and `code`.\n\n- First point\n- Second point\n\nReplace this from CMS → Blog.",
            )
            b.thumbnail.save(
                f"blog{i}.jpg",
                placeholder(f"BLOG_THUMBNAIL_0{i}", i=i + 2),
                save=False,
            )
            b.save()

        for i in range(1, 5):
            j = m.JourneyEntry(
                date=date(2021 + i, 3, 1),
                title=f"JOURNEY_TITLE_0{i}",
                description="JOURNEY_DESCRIPTION",
                category=["education", "project", "event", "achievement"][i - 1],
                location="JOURNEY_LOCATION",
                link="JOURNEY_LINK",
            )
            j.image.save(
                f"journey{i}.jpg", placeholder(f"JOURNEY_IMAGE_0{i}", i=i), save=False
            )
            j.save()

        for i in (1, 2, 3):
            c = m.Certification(
                title=f"CERTIFICATION_TITLE_0{i}",
                organization="ISSUING_ORGANIZATION",
                issue_date=date(2024, i, 1),
                credential_id="CREDENTIAL_ID",
                credential_url="CREDENTIAL_URL",
                description="CERTIFICATION_DESCRIPTION",
                featured=i == 1,
            )
            c.image.save(
                f"cert{i}.jpg",
                placeholder(f"CERTIFICATION_IMAGE_0{i}", (900, 1200), i),
                save=False,
            )
            c.pdf.save(
                f"cert{i}.pdf", sample_pdf(f"CERTIFICATION_PDF_0{i}"), save=False
            )
            c.save()

        r = m.Resume(title="RESUME_TITLE", version="v1", is_active=True)
        r.pdf.save("resume.pdf", sample_pdf("RESUME_PDF"), save=False)
        r.preview_image.save(
            "resume.jpg",
            placeholder("RESUME_PREVIEW_IMAGE", (900, 1200), 0),
            save=False,
        )
        r.save()
        self.stdout.write(self.style.SUCCESS("Placeholder content created."))
        self.make_admin(o)

    def make_admin(self, o):
        if User.objects.filter(is_superuser=True).exists():
            return
        pw = o["admin_password"] or secrets.token_urlsafe(12)
        User.objects.create_superuser(o["admin_user"], "", pw)
        self.stdout.write(
            self.style.WARNING(
                f"Admin created → username: {o['admin_user']}  password: {pw}"
            )
        )
