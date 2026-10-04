from .models import Profile, SiteSettings, SocialLink

NAV = [("home","Home"),("about","About"),("education","Education"),("skills","Skills"),("projects","Projects"),("journey","Journey"),("blog","Blog"),("certifications","Certifications"),("resume","Resume"),("contact","Contact")]

def site(request):
    if request.path.startswith("/static/") or request.path.startswith("/media/"):
        return {}
    return {"site": SiteSettings.load(), "profile": Profile.load(),
            "socials": SocialLink.objects.filter(is_active=True), "nav": NAV}
