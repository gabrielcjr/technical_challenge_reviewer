from rest_framework import serializers

from .models import Challenge


class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = ["id", "title", "description", "created_at"]

    def validate_title(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("title required")
        if len(value) < 3:
            raise serializers.ValidationError("title must be at least 3 characters")
        if len(value) > 255:
            raise serializers.ValidationError("title must be at most 255 characters")
        return value

    def validate_description(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("description required")
        if len(value) < 20:
            raise serializers.ValidationError("description must be at least 20 characters")
        return value


class SubmissionCreateSerializer(serializers.Serializer):
    userName = serializers.CharField(required=False, allow_blank=True)
    user_name = serializers.CharField(required=False, allow_blank=True)
    githubRepoUrl = serializers.CharField(required=False, allow_blank=True)
    github_repo_url = serializers.CharField(required=False, allow_blank=True)
    challengeId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    customChallengeText = serializers.CharField(required=False, allow_blank=True)
    challengeText = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        user_name = (data.get("userName") or data.get("user_name") or "").strip()
        github_url = (data.get("githubRepoUrl") or data.get("github_repo_url") or "").strip()

        errors = {}
        if not user_name:
            errors["userName"] = "userName and githubRepoUrl are required"
        if not github_url:
            errors["githubRepoUrl"] = "userName and githubRepoUrl are required"

        if errors:
            raise serializers.ValidationError(errors)

        if "github.com" not in github_url.lower():
            raise serializers.ValidationError({"githubRepoUrl": "Repository URL must be a github.com URL"})

        challenge_id = data.get("challengeId")
        custom_text = (data.get("customChallengeText") or data.get("challengeText") or "").strip()

        if not challenge_id and not custom_text:
            raise serializers.ValidationError("Either challengeId or customChallengeText must be provided")

        if not challenge_id and len(custom_text) < 20:
            raise serializers.ValidationError(
                {"customChallengeText": "customChallengeText must be at least 20 characters long"}
            )

        data["validated_user_name"] = user_name
        data["validated_github_url"] = github_url
        data["validated_challenge_id"] = challenge_id
        data["validated_custom_text"] = custom_text
        return data


class EvaluationCallbackSerializer(serializers.Serializer):
    submissionId = serializers.CharField()
    approved = serializers.BooleanField(default=False)
    summary = serializers.CharField(default="", allow_blank=True)
    improvements = serializers.ListField(child=serializers.CharField(), default=list)
    reasoning = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    rawOutput = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    failed = serializers.BooleanField(default=False)
