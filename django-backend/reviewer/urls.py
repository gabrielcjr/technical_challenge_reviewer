from django.urls import path

from . import views

urlpatterns = [
    path("api/challenges", views.challenge_list_create, name="api_challenge_list_create"),
    path("api/submissions", views.submission_list_create, name="api_submission_list_create"),
    path("api/submissions/<str:pk>", views.submission_detail, name="api_submission_detail"),
    path("api/submissions/<str:pk>/retry", views.submission_retry, name="api_submission_retry"),
    path("api/internal/evaluation-result", views.internal_evaluation_result, name="internal_evaluation_result"),
    path("api/internal/health", views.internal_health, name="internal_health"),
]
