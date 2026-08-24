from django.contrib import admin
from django.urls import path
from recovery.views import (
    RevenueSummaryView,
    ExperimentListView,
    PolicyListView,
    ImpactView,
    AuditView
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/summary/', RevenueSummaryView.as_view(), name='revenue-summary'),
    path('api/experiments/', ExperimentListView.as_view(), name='experiments'),
    path('api/policies/', PolicyListView.as_view(), name='policies'),
    path('api/impact/', ImpactView.as_view(), name='impact'),
    path('api/audit/', AuditView.as_view(), name='audit'),
]
