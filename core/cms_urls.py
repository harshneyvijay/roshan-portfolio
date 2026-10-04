from django.urls import path
from . import cms_views as v

urlpatterns = [
    path("login/", v.login_view, name="cms_login"),
    path("logout/", v.logout_view, name="cms_logout"),
    path("", v.dashboard, name="cms_dashboard"),
    path("profile/", v.singleton, {"key": "profile"}, name="cms_profile"),
    path("settings/", v.singleton, {"key": "settings"}, name="cms_settings"),
    path("media/", v.media_library, name="cms_media"),
    path("media/upload/", v.media_upload, name="cms_media_upload"),
    path("media/delete/", v.media_delete, name="cms_media_delete"),
    path("messages/", v.messages_list, name="cms_messages"),
    path("messages/<int:pk>/<str:action>/", v.message_action, name="cms_message_action"),
    path("account/", v.account, name="cms_account"),
    path("users/", v.users, name="cms_users"),
    path("users/<int:pk>/delete/", v.user_delete, name="cms_user_delete"),
    path("blog/<int:pk>/preview/", v.preview, {"key": "blog"}, name="cms_blog_preview"),
    path("projects/<int:pk>/preview/", v.preview, {"key": "projects"}, name="cms_projects_preview"),
    path("<str:key>/", v.item_list, name="cms_list"),
    path("<str:key>/new/", v.item_form, name="cms_new"),
    path("<str:key>/<int:pk>/edit/", v.item_form, name="cms_edit"),
    path("<str:key>/<int:pk>/delete/", v.item_delete, name="cms_delete"),
    path("<str:key>/<int:pk>/move/<str:direction>/", v.item_move, name="cms_move"),
    path("<str:key>/<int:pk>/toggle/", v.item_toggle, name="cms_toggle"),
]
