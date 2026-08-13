from django.contrib import admin
from .models import Challenge, Submission

@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_at")
    search_fields = ("title", "description")

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "user_name", "github_repo_url", "status", "approved", "created_at")
    list_filter = ("status", "approved", "created_at")
    search_fields = ("user_name", "github_repo_url")
