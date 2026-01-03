from django.urls import path, include

urlpatterns = [
    path('benchmark/', include('benchmark.urls')),
]
