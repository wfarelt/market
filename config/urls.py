from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.dashboard.urls")),
    path("auth/", include("apps.users.urls")),
    path("branches/", include("apps.branches.urls")),
    path("settings/", include("apps.settings_app.urls")),
    path("products/", include("apps.products.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("transfers/", include("apps.transfers.urls")),
    path("cash/", include("apps.cash.urls")),
    path("customers/", include("apps.customers.urls")),
    path("purchases/", include("apps.purchases.urls")),
    path("sales/", include("apps.sales.urls")),
    path("reports/", include("apps.reports.urls")),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
