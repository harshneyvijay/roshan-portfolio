from django.contrib import messages
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from .models import (
    BlogPost,
    Certification,
    ContactMessage,
    Education,
    JourneyEntry,
    Project,
    Resume,
    Skill,
)


def home(request):
    skills = {}
    for s in Skill.objects.all():
        skills.setdefault(s.category, []).append(s)
    ctx = dict(
        education=Education.objects.all(),
        skills=skills,
        projects=Project.objects.filter(published=True)[:6],
        project_total=Project.objects.filter(published=True).count(),
        journey=JourneyEntry.objects.filter(published=True),
        posts=BlogPost.objects.filter(status="published")[:3],
        certs=Certification.objects.filter(published=True)[:6],
        resume=Resume.objects.filter(is_active=True).first(),
        home=True,
    )
    return render(request, "public/home.html", ctx)


def contact(request):
    if request.method == "POST":
        if request.POST.get("website"):  # honeypot
            return redirect("/#contact")
        name = request.POST.get("name", "").strip()[:120]
        email = request.POST.get("email", "").strip()[:254]
        msg = request.POST.get("message", "").strip()[:5000]
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email

        try:
            validate_email(email)
            if not name or not msg:
                raise ValidationError("missing")
        except ValidationError:
            messages.error(
                request, "Please enter your name, a valid email address and a message."
            )
            return redirect("/#contact")
        ContactMessage.objects.create(name=name, email=email, message=msg)
        messages.success(request, "Thanks — your message has been sent.")
    return redirect("/#contact")


def project_list(request):
    return render(
        request,
        "public/projects.html",
        {"projects": Project.objects.filter(published=True)},
    )


def project_detail(request, slug, preview=False):
    qs = Project.objects.all() if preview else Project.objects.filter(published=True)
    p = get_object_or_404(qs, slug=slug)
    return render(request, "public/project.html", {"p": p, "preview": preview})


def blog_list(request):
    return render(
        request,
        "public/blogs.html",
        {"posts": BlogPost.objects.filter(status="published")},
    )


def blog_detail(request, slug, preview=False):
    qs = (
        BlogPost.objects.all()
        if preview
        else BlogPost.objects.filter(status="published")
    )
    post = get_object_or_404(qs, slug=slug)
    return render(request, "public/post.html", {"post": post, "preview": preview})


def cert_list(request):
    return render(
        request,
        "public/certs.html",
        {"certs": Certification.objects.filter(published=True)},
    )


def cert_detail(request, pk):
    c = get_object_or_404(Certification, pk=pk, published=True)
    return render(
        request,
        "public/cert.html",
        {"c": c, "download_url": reverse("cert_download", args=[pk])},
    )


def _download(f, name):
    if not f:
        raise Http404
    return FileResponse(f.open("rb"), as_attachment=True, filename=name)


def cert_download(request, pk):
    c = get_object_or_404(Certification, pk=pk, published=True)
    return _download(c.pdf, f"{c.title}.pdf")


def resume(request):
    r = Resume.objects.filter(is_active=True).first()
    return render(
        request,
        "public/resume.html",
        {"r": r, "download_url": reverse("resume_download")},
    )


def resume_download(request):
    r = Resume.objects.filter(is_active=True).first()
    if not r:
        raise Http404
    return _download(r.pdf, f"{r.title}.pdf")


def sitemap(request):
    base = request.build_absolute_uri("/").rstrip("/")
    urls = ["/", "/projects/", "/blog/", "/certifications/", "/resume/"]
    urls += [p.get_absolute_url() for p in Project.objects.filter(published=True)]
    urls += [b.get_absolute_url() for b in BlogPost.objects.filter(status="published")]
    urls += [
        f"/certifications/{c.pk}/" for c in Certification.objects.filter(published=True)
    ]
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    xml += "".join(f"<url><loc>{base}{u}</loc></url>" for u in urls) + "</urlset>"
    return HttpResponse(xml, content_type="application/xml")


def robots(request):
    base = request.build_absolute_uri("/").rstrip("/")
    return HttpResponse(
        f"User-agent: *\nDisallow: /cms/\nSitemap: {base}/sitemap.xml\n",
        content_type="text/plain",
    )


def pdf_file(request, path):
    """Stream a stored PDF inline from our own origin so the browser viewer works with any storage backend."""
    if not path.lower().endswith(".pdf") or ".." in path:
        raise Http404
    try:
        f = default_storage.open(path, "rb")
    except Exception:
        raise Http404
    resp = FileResponse(f, content_type="application/pdf")
    resp["Content-Disposition"] = "inline"
    resp["Cache-Control"] = "public, max-age=3600"
    return resp
