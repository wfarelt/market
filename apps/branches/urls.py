from django.urls import path

from . import views

app_name = "branches"

urlpatterns = [
    path("", views.BranchListView.as_view(), name="list"),
    path("create/", views.BranchCreateView.as_view(), name="create"),
    path("<int:pk>/", views.BranchDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.BranchUpdateView.as_view(), name="update"),
    path("<int:pk>/users/add/", views.UserBranchAddView.as_view(), name="user-add"),
    path(
        "<int:pk>/users/<int:user_branch_pk>/remove/",
        views.UserBranchRemoveView.as_view(),
        name="user-remove",
    ),
]

