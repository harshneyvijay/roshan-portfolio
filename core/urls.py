from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("contact/", views.contact, name="contact"),
    path("projects/", views.project_list, name="projects"),
    path("projects/<slug:slug>/", views.project_detail, name="project"),
    path("blog/", views.blog_list, name="blog"),
    path("blog/<slug:slug>/", views.blog_detail, name="post"),
    path("certifications/", views.cert_list, name="certs"),
    path("certifications/<int:pk>/", views.cert_detail, name="cert"),
    path("certifications/<int:pk>/download/", views.cert_download, name="cert_download"),
    path("resume/", views.resume, name="resume"),
    path("resume/download/", views.resume_download, name="resume_download"),
    path("files/pdf/<path:path>", views.pdf_file, name="pdf_file"),
    path("sitemap.xml", views.sitemap, name="sitemap"),
    path("robots.txt", views.robots, name="robots"),
]
