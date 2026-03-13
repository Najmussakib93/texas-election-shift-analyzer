from django.urls import path
from .views import CountyListView, CountyDetailView, ShiftsView

urlpatterns = [
    path("counties/", CountyListView.as_view(), name="county-list"),
    path("counties/<str:fips>/", CountyDetailView.as_view(), name="county-detail"),
    path("shifts/", ShiftsView.as_view(), name="shifts"),
]
