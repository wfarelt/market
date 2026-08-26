from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="users/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("users/", views.UserListView.as_view(), name="list"),
    path("users/create/", views.UserCreateView.as_view(), name="create"),
    path("users/<int:pk>/edit/", views.UserUpdateView.as_view(), name="update"),
]

