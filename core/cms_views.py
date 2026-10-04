from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db.models import FileField, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import models as m
from .validators import validate_image, validate_pdf

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".ico")


# ---------------- access control ----------------
def cms_required(view):
    @wraps(view)
    def wrapper(request, *a, **kw):
        if not (request.user.is_authenticated and request.user.is_staff):
            return redirect(f"{reverse('cms_login')}?next={request.path}")
        return view(request, *a, **kw)

    return wrapper


def admin_required(view):
    @wraps(view)
    @cms_required
    def wrapper(request, *a, **kw):
        if not request.user.is_superuser:
            messages.error(request, "Only administrators can open that page.")
            return redirect("cms_dashboard")
        return view(request, *a, **kw)

    return wrapper


def page(request, template, ctx=None, active=""):
    ctx = dict(ctx or {})
    ctx.update(
        active=active,
        unread=m.ContactMessage.objects.filter(is_read=False).count(),
        is_admin=request.user.is_superuser,
    )
    return render(request, template, ctx)


def log(request, text):
    m.Activity.objects.create(user=request.user.get_username(), text=text[:300])


# ---------------- auth ----------------
def login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("cms_dashboard")
    error = ""
    if request.method == "POST":
        ident = request.POST.get("username", "").strip()
        ip = request.META.get("REMOTE_ADDR", "")
        key = f"login-fail:{ip}:{ident.lower()}"
        if cache.get(key, 0) >= 5:
            error = "Too many failed attempts. Try again in 10 minutes."
        else:
            u = (
                User.objects.filter(email__iexact=ident).first()
                if "@" in ident
                else None
            )
            user = authenticate(
                request,
                username=u.username if u else ident,
                password=request.POST.get("password", ""),
            )
            if user and user.is_staff:
                cache.delete(key)
                login(request, user)
                nxt = request.POST.get("next") or request.GET.get("next") or ""
                if not url_has_allowed_host_and_scheme(
                    nxt, allowed_hosts={request.get_host()}
                ) or not nxt.startswith("/cms/"):
                    nxt = reverse("cms_dashboard")
                return redirect(nxt)
            cache.set(key, cache.get(key, 0) + 1, 600)
            error = "Username or password is incorrect."
    return render(
        request,
        "cms/login.html",
        {
            "error": error,
            "site": m.SiteSettings.load(),
            "next": request.GET.get("next", ""),
        },
    )


@require_POST
def logout_view(request):
    logout(request)
    return redirect("cms_login")


# ---------------- form helpers ----------------
class BaseForm(forms.ModelForm):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for f in self.fields.values():
            w = f.widget
            if isinstance(f, forms.DateField):
                f.widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
            elif isinstance(w, forms.Textarea):
                w.attrs.setdefault("rows", 5)
            if isinstance(f, forms.ImageField):
                w.attrs["accept"] = "image/*"
            elif isinstance(f, forms.FileField):
                w.attrs["accept"] = (
                    "application/pdf" if "pdf" in str(f.validators) else "*/*"
                )


def make_form(model, exclude=()):
    meta = type("Meta", (), {"model": model, "exclude": tuple(exclude)})
    return type(f"{model.__name__}Form", (BaseForm,), {"Meta": meta})


def fmt_date(d):
    return d.strftime("%b %Y") if d else "—"


# ---------------- registry ----------------
CONFIG = {
    "education": dict(
        model=m.Education,
        title="Education",
        singular="education entry",
        orderable=True,
        thumb=lambda o: o.logo,
        exclude=["order"],
        cols=[
            ("Institution", lambda o: o.institution),
            ("Degree", lambda o: o.degree),
            ("Years", lambda o: o.years),
            ("Grade", lambda o: o.grade),
        ],
    ),
    "skills": dict(
        model=m.Skill,
        title="Skills",
        singular="skill",
        orderable=True,
        exclude=["order"],
        cols=[("Name", lambda o: o.name), ("Category", lambda o: o.category)],
        filter=("category", None),
        search=("name", "category"),
    ),
    "projects": dict(
        model=m.Project,
        title="Projects",
        singular="project",
        orderable=True,
        thumb=lambda o: o.thumbnail,
        exclude=["order"],
        cols=[
            ("Title", lambda o: o.title),
            ("Technologies", lambda o: o.technologies),
            ("Year", lambda o: o.year),
        ],
        toggles=[("Featured", "featured"), ("Published", "published")],
        search=("title", "technologies"),
        view=lambda o: f"/cms/projects/{o.pk}/preview/",
    ),
    "journey": dict(
        model=m.JourneyEntry,
        title="Journey",
        singular="journey entry",
        orderable=True,
        thumb=lambda o: o.image,
        exclude=["order"],
        cols=[
            ("Title", lambda o: o.title),
            ("Date", lambda o: fmt_date(o.date)),
            ("Category", lambda o: o.get_category_display()),
            ("Location", lambda o: o.location),
        ],
        toggles=[("Published", "published")],
        filter=("category", m.JourneyEntry.CATEGORIES),
        search=("title", "location"),
    ),
    "blog": dict(
        model=m.BlogPost,
        title="Blog",
        singular="post",
        thumb=lambda o: o.thumbnail,
        cols=[
            ("Title", lambda o: o.title),
            ("Category", lambda o: o.category),
            ("Date", lambda o: o.published_at.strftime("%d %b %Y")),
            ("Author", lambda o: o.author),
        ],
        toggles=[("Featured", "featured"), ("Status", "status")],
        search=("title", "excerpt", "category"),
        view=lambda o: f"/cms/blog/{o.pk}/preview/",
        filter=("category", None),
        exclude=["created_at"],
    ),
    "certifications": dict(
        model=m.Certification,
        title="Certifications",
        singular="certification",
        orderable=True,
        thumb=lambda o: o.image,
        exclude=["order"],
        cols=[
            ("Name", lambda o: o.title),
            ("Organization", lambda o: o.organization),
            ("Date", lambda o: fmt_date(o.issue_date)),
            ("PDF", lambda o: "Uploaded" if o.pdf else "None"),
        ],
        toggles=[("Published", "published")],
        search=("title", "organization"),
        view=lambda o: f"/certifications/{o.pk}/",
    ),
    "resume": dict(
        model=m.Resume,
        title="Resume",
        singular="resume version",
        thumb=lambda o: o.preview_image,
        cols=[
            ("Title", lambda o: o.title),
            ("Version", lambda o: o.version),
            ("Uploaded", lambda o: o.uploaded_at.strftime("%d %b %Y")),
        ],
        toggles=[("Active", "is_active")],
        view=lambda o: o.pdf.url,
    ),
    "social": dict(
        model=m.SocialLink,
        title="Social links",
        singular="social link",
        orderable=True,
        exclude=["order"],
        cols=[("Label", lambda o: o.label), ("URL", lambda o: o.url)],
        toggles=[("Visible", "is_active")],
    ),
}
SINGLETONS = {
    "profile": (m.Profile, "Profile"),
    "settings": (m.SiteSettings, "Site settings"),
}


def get_cfg(key):
    cfg = CONFIG.get(key)
    if not cfg:
        raise Http404
    return cfg


def is_on(obj, attr):
    v = getattr(obj, attr)
    return v == "published" if attr == "status" else bool(v)


# ---------------- dashboard ----------------
@cms_required
def dashboard(request):
    stats = [
        ("Projects", m.Project.objects.count(), "projects"),
        ("Blog posts", m.BlogPost.objects.count(), "blog"),
        ("Certifications", m.Certification.objects.count(), "certifications"),
        ("Journey entries", m.JourneyEntry.objects.count(), "journey"),
        ("Education", m.Education.objects.count(), "education"),
        ("Skills", m.Skill.objects.count(), "skills"),
        (
            "Unread messages",
            m.ContactMessage.objects.filter(is_read=False).count(),
            "messages",
        ),
    ]
    return page(
        request,
        "cms/dashboard.html",
        dict(
            stats=stats,
            projects=m.Project.objects.order_by("-created_at")[:5],
            posts=m.BlogPost.objects.order_by("-created_at")[:5],
            msgs=m.ContactMessage.objects.all()[:5],
            activity=m.Activity.objects.all()[:8],
        ),
        "dashboard",
    )


# ---------------- generic CRUD ----------------
@cms_required
def item_list(request, key):
    if key in SINGLETONS:
        return singleton(request, key)
    cfg = get_cfg(key)
    qs = cfg["model"].objects.all()
    q = request.GET.get("q", "").strip()
    if q and cfg.get("search"):
        cond = Q()
        for f in cfg["search"]:
            cond |= Q(**{f"{f}__icontains": q})
        qs = qs.filter(cond)
    flt, flt_val, flt_choices = cfg.get("filter"), request.GET.get("f", ""), None
    if flt:
        flt_choices = flt[1] or [
            (c, c)
            for c in cfg["model"].objects.values_list(flt[0], flat=True).distinct()
        ]
        if flt_val:
            qs = qs.filter(**{flt[0]: flt_val})
    if key == "blog" and request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])
    rows = []
    for o in qs:
        t = cfg.get("thumb")
        rows.append(
            dict(
                obj=o,
                thumb=(t(o).url if t and t(o) else ""),
                cells=[fn(o) for _, fn in cfg["cols"]],
                toggles=[
                    (lab, attr, is_on(o, attr)) for lab, attr in cfg.get("toggles", [])
                ],
                view=cfg["view"](o) if cfg.get("view") else "",
            )
        )
    return page(
        request,
        "cms/list.html",
        dict(
            cfg=cfg,
            key=key,
            rows=rows,
            q=q,
            flt_val=flt_val,
            flt_choices=flt_choices,
            status=request.GET.get("status", ""),
            headers=[h for h, _ in cfg["cols"]],
        ),
        key,
    )


def save_screenshots(request, project):
    for f in request.FILES.getlist("screenshots"):
        validate_image(f)
        m.ProjectImage.objects.create(
            project=project, image=f, order=project.images.count() + 1
        )
    for img in project.images.all():
        if request.POST.get(f"delete_img_{img.pk}"):
            img.delete()
            continue
        try:
            img.order = int(request.POST.get(f"order_img_{img.pk}", img.order))
        except ValueError:
            pass
        img.caption = request.POST.get(f"caption_img_{img.pk}", img.caption)[:200]
        img.save()


@cms_required
def item_form(request, key, pk=None):
    cfg = get_cfg(key)
    obj = get_object_or_404(cfg["model"], pk=pk) if pk else None
    Form = make_form(cfg["model"], cfg.get("exclude", ()))
    form = Form(request.POST or None, request.FILES or None, instance=obj)
    shots_error = ""
    category_options = None
    if (
        key == "skills"
    ):  # free-text category with suggestions (presets + categories already in use)
        used = list(
            m.Skill.objects.order_by("category")
            .values_list("category", flat=True)
            .distinct()
        )
        category_options = used + [
            c
            for c in m.Skill.PRESET_CATEGORIES
            if c.lower() not in {u.lower() for u in used}
        ]
        form.fields["category"].widget.attrs.update(
            {
                "list": "category-options",
                "autocomplete": "off",
                "placeholder": "Pick from the list or type a new category",
            }
        )
    if request.method == "POST" and form.is_valid():
        try:
            for f in request.FILES.getlist("screenshots"):
                validate_image(f)
        except forms.ValidationError as e:
            shots_error = e.messages[0]
        if not shots_error:
            saved = form.save()
            if key == "projects":
                save_screenshots(request, saved)
            log(
                request, f"{'Updated' if obj else 'Created'} {cfg['singular']}: {saved}"
            )
            messages.success(request, f"{cfg['singular'].capitalize()} saved.")
            return redirect("cms_list", key=key)
    return page(
        request,
        "cms/form.html",
        dict(
            form=form,
            cfg=cfg,
            key=key,
            obj=obj,
            shots_error=shots_error,
            category_options=category_options,
            images=obj.images.all() if obj and key == "projects" else None,
            title=("Edit " if obj else "New ") + cfg["singular"],
        ),
        key,
    )


@cms_required
def item_delete(request, key, pk):
    cfg = get_cfg(key)
    obj = get_object_or_404(cfg["model"], pk=pk)
    if request.method == "POST":
        name = str(obj)
        obj.delete()
        log(request, f"Deleted {cfg['singular']}: {name}")
        messages.success(request, f"Deleted “{name}”.")
        return redirect("cms_list", key=key)
    return page(request, "cms/confirm.html", dict(obj=obj, cfg=cfg, key=key), key)


@cms_required
@require_POST
def item_move(request, key, pk, direction):
    cfg = get_cfg(key)
    if not cfg.get("orderable"):
        raise Http404
    items = list(cfg["model"].objects.all())
    for i, it in enumerate(items, 1):  # normalise
        if it.order != i:
            it.order = i
            it.save(update_fields=["order"])
    idx = next((i for i, it in enumerate(items) if it.pk == pk), None)
    swap = idx - 1 if direction == "up" else idx + 1
    if idx is not None and 0 <= swap < len(items):
        a, b = items[idx], items[swap]
        a.order, b.order = b.order, a.order
        a.save(update_fields=["order"])
        b.save(update_fields=["order"])
    return redirect("cms_list", key=key)


@cms_required
@require_POST
def item_toggle(request, key, pk):
    cfg = get_cfg(key)
    obj = get_object_or_404(cfg["model"], pk=pk)
    attr = request.POST.get("attr")
    if attr not in [a for _, a in cfg.get("toggles", [])]:
        raise Http404
    if attr == "status":
        obj.status = "draft" if obj.status == "published" else "published"
    else:
        setattr(obj, attr, not getattr(obj, attr))
    obj.save()
    log(request, f"Changed {attr} on {cfg['singular']}: {obj}")
    return redirect(request.POST.get("next") or reverse("cms_list", args=[key]))


@cms_required
def preview(request, key, pk):
    from . import views

    if key == "blog":
        return views.blog_detail(
            request, m.BlogPost.objects.get(pk=pk).slug, preview=True
        )
    return views.project_detail(
        request, get_object_or_404(m.Project, pk=pk).slug, preview=True
    )


@cms_required
def singleton(request, key):
    model, title = SINGLETONS[key]
    obj = model.load()
    Form = make_form(model)
    form = Form(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        log(request, f"Updated {title.lower()}")
        messages.success(request, f"{title} saved.")
        return redirect(request.path)
    return page(
        request,
        "cms/form.html",
        dict(form=form, title=title, key=key, singleton=True, cfg={"title": title}),
        key,
    )


# ---------------- media library ----------------
def walk(storage, path=""):
    try:
        dirs, files = storage.listdir(path)
    except (FileNotFoundError, NotADirectoryError):
        return
    for f in files:
        yield f"{path}/{f}" if path else f
    for d in dirs:
        yield from walk(storage, f"{path}/{d}" if path else d)


def usage_map():
    use = {}
    for model in (
        m.Profile,
        m.SiteSettings,
        m.Education,
        m.Project,
        m.ProjectImage,
        m.BlogPost,
        m.JourneyEntry,
        m.Certification,
        m.Resume,
    ):
        names = [f.name for f in model._meta.get_fields() if isinstance(f, FileField)]
        for o in model.objects.all():
            for n in names:
                fl = getattr(o, n)
                if fl:
                    label = f"{model._meta.verbose_name.title()}: {getattr(o, 'title', None) or getattr(o, 'name', None) or getattr(getattr(o, 'project', None), 'title', None) or o}"
                    use[fl.name] = label
    return use


@cms_required
def media_library(request):
    use, items = usage_map(), []
    q, typ = request.GET.get("q", "").lower(), request.GET.get("type", "")
    for path in walk(default_storage):
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        kind = "image" if ext in IMAGE_EXT else "pdf" if ext == ".pdf" else "other"
        if (typ and kind != typ) or (q and q not in path.lower()):
            continue
        try:
            size, mod = default_storage.size(path), default_storage.get_modified_time(
                path
            )
        except Exception:
            size, mod = 0, None
        items.append(
            dict(
                path=path,
                name=path.rsplit("/", 1)[-1],
                url=default_storage.url(path),
                kind=kind,
                ext=ext.strip(".").upper(),
                size=size,
                mod=mod,
                used=use.get(path, ""),
            )
        )
    items.sort(key=lambda i: i["mod"].timestamp() if i["mod"] else 0, reverse=True)
    return page(
        request,
        "cms/media.html",
        dict(
            items=items,
            q=q,
            typ=typ,
            max_img=settings.MAX_IMAGE_MB,
            max_pdf=settings.MAX_PDF_MB,
        ),
        "media",
    )


@cms_required
@require_POST
def media_upload(request):
    ok = 0
    for f in request.FILES.getlist("files"):
        try:
            (validate_pdf if f.name.lower().endswith(".pdf") else validate_image)(f)
            m.MediaFile.objects.create(file=f, title=f.name[:200])
            ok += 1
        except forms.ValidationError as e:
            messages.error(request, f"{f.name}: {e.messages[0]}")
    if ok:
        log(request, f"Uploaded {ok} file(s) to the media library")
        messages.success(request, f"Uploaded {ok} file(s).")
    elif not request.FILES:
        messages.error(request, "Choose at least one file.")
    return redirect("cms_media")


@cms_required
@require_POST
def media_delete(request):
    path = request.POST.get("path", "")
    if ".." in path or path.startswith("/") or not default_storage.exists(path):
        raise Http404
    used = usage_map().get(path)
    if used:
        messages.error(
            request,
            f"Can't delete: this file is used by {used}. Replace it there first.",
        )
    else:
        lib = m.MediaFile.objects.filter(file=path).first()
        lib.delete() if lib else default_storage.delete(path)
        log(request, f"Deleted file {path}")
        messages.success(request, "File deleted.")
    return redirect("cms_media")


# ---------------- messages ----------------
@cms_required
def messages_list(request):
    return page(
        request,
        "cms/messages.html",
        dict(msgs=m.ContactMessage.objects.all()),
        "messages",
    )


@cms_required
@require_POST
def message_action(request, pk, action):
    msg = get_object_or_404(m.ContactMessage, pk=pk)
    if action == "delete":
        msg.delete()
        messages.success(request, "Message deleted.")
    elif action in ("read", "unread"):
        msg.is_read = action == "read"
        msg.save(update_fields=["is_read"])
    return redirect("cms_messages")


# ---------------- account & users ----------------
@cms_required
def account(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Password changed.")
        return redirect("cms_account")
    return page(request, "cms/account.html", dict(form=form), "account")


class UserForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(
        widget=forms.PasswordInput, help_text="At least 10 characters."
    )
    role = forms.ChoiceField(
        choices=[
            ("editor", "Editor – manages content"),
            ("admin", "Administrator – full access"),
        ]
    )

    def clean_username(self):
        u = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError("That username is taken.")
        return u

    def clean_password(self):
        from django.contrib.auth.password_validation import validate_password

        validate_password(self.cleaned_data["password"])
        return self.cleaned_data["password"]


@admin_required
def users(request):
    form = UserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        u = User.objects.create_user(
            d["username"],
            d["email"],
            d["password"],
            is_staff=True,
            is_superuser=d["role"] == "admin",
        )
        log(request, f"Created {d['role']} user {u.username}")
        messages.success(request, "User created.")
        return redirect("cms_users")
    return page(
        request,
        "cms/users.html",
        dict(form=form, users=User.objects.filter(is_staff=True)),
        "users",
    )


@admin_required
@require_POST
def user_delete(request, pk):
    u = get_object_or_404(User, pk=pk)
    if u == request.user:
        messages.error(request, "You can't delete your own account.")
    else:
        u.delete()
        messages.success(request, "User deleted.")
    return redirect("cms_users")
