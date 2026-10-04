import io, tempfile
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from . import models as m
from .management.commands.seed import sample_pdf, placeholder

TMP = tempfile.mkdtemp()


def img(name="a.png"):
    b = io.BytesIO(); Image.new("RGB", (40, 30), "orange").save(b, "PNG")
    return SimpleUploadedFile(name, b.getvalue(), "image/png")


def pdf(name="a.pdf"):
    return SimpleUploadedFile(name, sample_pdf("t").read(), "application/pdf")


@override_settings(MEDIA_ROOT=TMP, STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                                             "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class PortfolioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("boss", "boss@x.test", "Str0ng-pass-123")
        cls.editor = User.objects.create_user("ed", "", "Str0ng-pass-123", is_staff=True)

    def login(self, u="boss"):
        self.assertTrue(self.client.login(username=u, password="Str0ng-pass-123"))

    def test_public_pages_with_empty_db(self):
        for url in ["/", "/projects/", "/blog/", "/certifications/", "/resume/", "/sitemap.xml", "/robots.txt"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_cms_requires_login(self):
        for url in ["/cms/", "/cms/projects/", "/cms/media/", "/cms/profile/", "/cms/messages/"]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302); self.assertIn("/cms/login/", r["Location"])

    def test_login_logout_and_email_login(self):
        self.assertEqual(self.client.post("/cms/login/", {"username": "boss@x.test", "password": "Str0ng-pass-123"}).status_code, 302)
        self.assertEqual(self.client.get("/cms/").status_code, 200)
        self.client.post("/cms/logout/")
        self.assertEqual(self.client.get("/cms/").status_code, 302)
        r = self.client.post("/cms/login/", {"username": "boss", "password": "bad"})
        self.assertContains(r, "incorrect")

    def test_open_redirect_blocked(self):
        r = self.client.post("/cms/login/", {"username": "boss", "password": "Str0ng-pass-123", "next": "https://evil.test"})
        self.assertEqual(r["Location"], "/cms/")

    def test_project_crud_and_screenshots(self):
        self.login()
        r = self.client.post("/cms/projects/new/", {"title": "Demo", "short_description": "d", "published": "on",
                             "thumbnail": img(), "screenshots": [img("s1.png"), img("s2.png")], "technologies": "A, B"})
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors)
        p = m.Project.objects.get(title="Demo"); self.assertEqual(p.images.count(), 2)
        self.assertContains(self.client.get("/projects/demo/"), "screenshot 2")
        self.assertContains(self.client.get("/"), "Demo")
        first = p.images.first()
        self.client.post(f"/cms/projects/{p.pk}/edit/", {"title": "Demo2", "short_description": "d", "slug": "demo", "published": "on", f"delete_img_{first.pk}": "on"})
        p.refresh_from_db(); self.assertEqual(p.images.count(), 1); self.assertEqual(p.title, "Demo2")
        self.client.post(f"/cms/projects/{p.pk}/toggle/", {"attr": "published"})
        self.assertEqual(self.client.get("/projects/demo/").status_code, 404)   # unpublished -> hidden
        self.assertEqual(self.client.get(f"/cms/projects/{p.pk}/preview/").status_code, 200)
        self.assertEqual(self.client.post(f"/cms/projects/{p.pk}/delete/").status_code, 302)
        self.assertFalse(m.Project.objects.exists())

    def test_blog_draft_hidden_and_publish(self):
        self.login()
        self.client.post("/cms/blog/new/", {"title": "Post A", "excerpt": "e", "content": "Hello\n\n## H", "author": "x",
                         "category": "c", "published_at": "2025-01-01", "reading_time": 0, "status": "draft"})
        b = m.BlogPost.objects.get(); self.assertEqual(b.reading_time, 1)
        self.assertEqual(self.client.get("/blog/post-a/").status_code, 404)
        self.assertNotContains(self.client.get("/blog/"), "Post A")
        self.assertContains(self.client.get(f"/cms/blog/{b.pk}/preview/"), "Post A")
        self.client.post(f"/cms/blog/{b.pk}/toggle/", {"attr": "status"})
        self.assertContains(self.client.get("/blog/post-a/"), "<h2>H</h2>")
        self.assertContains(self.client.get("/cms/blog/?q=Post&status=published"), "Post A")

    def test_blog_content_escaped(self):
        b = m.BlogPost.objects.create(title="X", excerpt="e", content="<script>alert(1)</script>", status="published")
        self.assertNotContains(self.client.get(b.get_absolute_url()), "<script>alert(1)</script>")

    def test_certification_pdf_viewer_and_download(self):
        self.login()
        r = self.client.post("/cms/certifications/new/", {"title": "Cert", "organization": "Org", "published": "on", "pdf": pdf(), "image": img()})
        self.assertEqual(r.status_code, 302)
        c = m.Certification.objects.get()
        page = self.client.get(f"/certifications/{c.pk}/")
        self.assertContains(page, "<object"); self.assertContains(page, "Open in new tab"); self.assertContains(page, "Download PDF")
        d = self.client.get(f"/certifications/{c.pk}/download/")
        self.assertIn("attachment", d["Content-Disposition"])
        self.assertEqual(self.client.get(c.pdf.url).status_code, 200)
        self.assertContains(page, f"/files/pdf/{c.pdf.name}")
        v = self.client.get(f"/files/pdf/{c.pdf.name}")
        self.assertEqual(v["Content-Type"], "application/pdf"); self.assertEqual(v["Content-Disposition"], "inline")
        self.assertEqual(self.client.get("/files/pdf/../../etc/passwd").status_code, 404)
        self.assertEqual(self.client.get("/files/pdf/nope.pdf").status_code, 404)

    def test_fake_pdf_rejected(self):
        self.login()
        bad = SimpleUploadedFile("evil.pdf", b"<html>not a pdf</html>", "application/pdf")
        r = self.client.post("/cms/certifications/new/", {"title": "C", "organization": "O", "pdf": bad})
        self.assertEqual(r.status_code, 200); self.assertFalse(m.Certification.objects.exists())
        r = self.client.post("/cms/certifications/new/", {"title": "C", "organization": "O", "image": SimpleUploadedFile("x.svg", b"<svg/>")})
        self.assertFalse(m.Certification.objects.exists())

    def test_single_active_resume(self):
        self.login()
        for v in ("v1", "v2"):
            self.client.post("/cms/resume/new/", {"title": "R", "version": v, "pdf": pdf(), "is_active": "on", "uploaded_at": "2025-01-01 10:00:00"})
        self.assertEqual(m.Resume.objects.filter(is_active=True).count(), 1)
        self.assertEqual(m.Resume.objects.get(is_active=True).version, "v2")
        page = self.client.get("/resume/"); self.assertContains(page, "<object")
        self.assertEqual(self.client.get("/resume/download/").status_code, 200)
        old = m.Resume.objects.get(version="v1")
        self.client.post(f"/cms/resume/{old.pk}/toggle/", {"attr": "is_active"})
        self.assertEqual(m.Resume.objects.get(is_active=True).version, "v1")

    def test_journey_order_controls_public(self):
        self.login()
        a = m.JourneyEntry.objects.create(date="2020-01-01", title="Alpha"); b = m.JourneyEntry.objects.create(date="2021-01-01", title="Beta")
        self.client.post(f"/cms/journey/{b.pk}/move/up/")
        html = self.client.get("/").content.decode()
        self.assertLess(html.index("Beta"), html.index("Alpha"))

    def test_education_skills_social_profile_settings(self):
        self.login()
        self.client.post("/cms/education/new/", {"institution": "Inst", "degree": "Deg"})
        self.client.post("/cms/skills/new/", {"name": "Skill1", "category": "backend"})
        self.client.post("/cms/social/new/", {"label": "GH", "url": "https://example.com/x", "is_active": "on"})
        pr = m.Profile.load()
        data = {f: getattr(pr, f) for f in ("name", "title", "tagline", "intro", "about", "focus", "interests", "email", "phone", "location")}
        data["name"] = "Jane Placeholder"
        self.client.post("/cms/profile/", data)
        s = m.SiteSettings.load()
        self.client.post("/cms/settings/", {"site_name": "My Site", "description": "d", "seo_title": "T", "seo_description": "D", "footer_text": "F", "primary_email": "a@b.co"})
        home = self.client.get("/").content.decode()
        for needle in ("Inst", "Skill1", "https://example.com/x", "Jane Placeholder", "My Site", "mailto:a@b.co"):
            self.assertIn(needle, home)

    def test_media_library_upload_delete_and_in_use(self):
        self.login()
        self.client.post("/cms/media/upload/", {"files": [img("lib.png"), pdf("doc.pdf")]})
        self.assertEqual(m.MediaFile.objects.count(), 2)
        page = self.client.get("/cms/media/")
        self.assertContains(page, "lib"); self.assertContains(page, "doc")
        self.assertContains(self.client.get("/cms/media/?type=pdf"), "doc")
        f = m.MediaFile.objects.first()
        self.client.post("/cms/media/delete/", {"path": f.file.name}); self.assertEqual(m.MediaFile.objects.count(), 1)
        p = m.Project.objects.create(title="U", short_description="s"); p.thumbnail.save("t.png", img(), save=True)
        self.client.post("/cms/media/delete/", {"path": p.thumbnail.name})
        p.refresh_from_db(); self.assertTrue(p.thumbnail)                      # protected: still in use
        self.assertEqual(self.client.post("/cms/media/delete/", {"path": "../../etc/passwd"}).status_code, 404)

    def test_files_removed_with_row(self):
        p = m.Project.objects.create(title="Z", short_description="s"); p.thumbnail.save("t.png", img(), save=True)
        path = p.thumbnail.path; import os; self.assertTrue(os.path.exists(path))
        p.delete(); self.assertFalse(os.path.exists(path))

    def test_contact_form_and_messages(self):
        r = self.client.post("/contact/", {"name": "A", "email": "a@b.co", "message": "Hi"})
        self.assertEqual(r.status_code, 302); self.assertEqual(m.ContactMessage.objects.count(), 1)
        self.client.post("/contact/", {"name": "Bot", "email": "a@b.co", "message": "x", "website": "spam"})
        self.client.post("/contact/", {"name": "A", "email": "bad", "message": "x"})
        self.assertEqual(m.ContactMessage.objects.count(), 1)
        self.login()
        self.assertContains(self.client.get("/cms/"), "Unread messages")
        msg = m.ContactMessage.objects.get()
        self.client.post(f"/cms/messages/{msg.pk}/read/"); msg.refresh_from_db(); self.assertTrue(msg.is_read)
        self.client.post(f"/cms/messages/{msg.pk}/unread/"); msg.refresh_from_db(); self.assertFalse(msg.is_read)
        self.client.post(f"/cms/messages/{msg.pk}/delete/"); self.assertEqual(m.ContactMessage.objects.count(), 0)

    def test_roles(self):
        self.login("ed")
        self.assertEqual(self.client.get("/cms/projects/").status_code, 200)
        self.assertEqual(self.client.get("/cms/users/").status_code, 302)
        self.client.logout(); self.login("boss")
        self.assertEqual(self.client.get("/cms/users/").status_code, 200)
        self.client.post("/cms/users/", {"username": "new", "password": "Another-strong-1", "role": "editor"})
        self.assertTrue(User.objects.get(username="new").is_staff)
        self.assertFalse(User.objects.get(username="new").is_superuser)

    def test_seed_and_all_public_pages(self):
        from django.core.management import call_command
        call_command("seed", admin_user="seeded", admin_password="Seed-pass-12345", verbosity=0)
        html = self.client.get("/").content.decode()
        for needle in ("[PERSON_NAME]" if False else "[SHORT_TAGLINE]" if False else "[PROJECT_TITLE_01]", "[JOURNEY_TITLE_04]", "[CERTIFICATION_TITLE_01]", "[INSTITUTION_NAME_01]", "tl-item"):
            self.assertIn(needle, html)
        self.assertNotIn("[BLOG_TITLE_03]", html)   # draft
        for p in m.Project.objects.all(): self.assertEqual(self.client.get(p.get_absolute_url()).status_code, 200)
        for c in m.Certification.objects.all(): self.assertEqual(self.client.get(f"/certifications/{c.pk}/").status_code, 200)
        self.login()
        for key in ("education", "skills", "projects", "journey", "blog", "certifications", "resume", "social"):
            self.assertEqual(self.client.get(f"/cms/{key}/").status_code, 200, key)
            self.assertEqual(self.client.get(f"/cms/{key}/new/").status_code, 200, key)
        for url in ("/cms/", "/cms/media/", "/cms/messages/", "/cms/account/", "/cms/profile/", "/cms/settings/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
