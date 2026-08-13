import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Challenge, Submission, SubmissionStatus
from .serializers import ChallengeSerializer, EvaluationCallbackSerializer, SubmissionCreateSerializer
from .utils import dispatch_evaluation

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
def challenge_list_create(request):
    if request.method == "GET":
        challenges = Challenge.objects.all()
        data = [c.to_dict() for c in challenges]
        return Response(data, status=status.HTTP_200_OK)

    elif request.method == "POST":
        serializer = ChallengeSerializer(data=request.data)
        if not serializer.is_valid():
            # Return custom error format matching legacy tests
            error_map = {}
            for field, errors in serializer.errors.items():
                error_map[field] = errors[0] if isinstance(errors, list) else str(errors)

            # If title or description missing completely, return flat error
            title = request.data.get("title")
            description = request.data.get("description")
            if not title or not description:
                return Response({"error": "title and description required"}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"errors": error_map}, status=status.HTTP_400_BAD_REQUEST)

        challenge = serializer.save()
        return Response({"id": str(challenge.id), "title": challenge.title}, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
def submission_list_create(request):
    if request.method == "GET":
        submissions = Submission.objects.all()[:50]
        data = [s.to_dict() for s in submissions]
        return Response(data, status=status.HTTP_200_OK)

    elif request.method == "POST":
        serializer = SubmissionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            if "non_field_errors" in errors:
                err_msg = errors["non_field_errors"][0]
                return Response({"error": err_msg}, status=status.HTTP_400_BAD_REQUEST)
            if "userName" in errors and "githubRepoUrl" in errors:
                return Response(
                    {"error": "userName and githubRepoUrl are required"}, status=status.HTTP_400_BAD_REQUEST
                )
            if "githubRepoUrl" in errors:
                return Response(
                    {
                        "error": (
                            errors["githubRepoUrl"][0]
                            if isinstance(errors["githubRepoUrl"], list)
                            else str(errors["githubRepoUrl"])
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if "customChallengeText" in errors:
                return Response(
                    {
                        "error": (
                            errors["customChallengeText"][0]
                            if isinstance(errors["customChallengeText"], list)
                            else str(errors["customChallengeText"])
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user_name = data["validated_user_name"]
        github_url = data["validated_github_url"]
        challenge_id = data["validated_challenge_id"]
        custom_text = data["validated_custom_text"]

        submission = Submission(user_name=user_name, github_repo_url=github_url)

        if challenge_id:
            try:
                challenge = Challenge.objects.get(id=challenge_id)
                submission.associate_with_challenge(challenge)
            except (Challenge.DoesNotExist, ValueError):
                return Response({"error": "Challenge not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            submission.challenge_snapshot = custom_text

        submission.save()
        dispatch_evaluation(submission)

        check_url = f"/api/submissions/{submission.id}"
        return Response(
            {
                "id": str(submission.id),
                "status": submission.status,
                "checkUrl": check_url,
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET"])
def submission_detail(request, pk):
    try:
        submission = Submission.objects.get(id=pk)
    except (Submission.DoesNotExist, ValueError):
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response(submission.to_dict(), status=status.HTTP_200_OK)


@api_view(["POST"])
def submission_retry(request, pk):
    try:
        submission = Submission.objects.get(id=pk)
    except (Submission.DoesNotExist, ValueError):
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    if not submission.can_be_retried():
        return Response({"error": "Submission already finalized, cannot retry"}, status=status.HTTP_400_BAD_REQUEST)

    submission.status = SubmissionStatus.PENDING
    submission.append_processing_log("Retry requested")
    submission.save()

    dispatch_evaluation(submission)

    return Response({"status": "retry dispatched", "id": str(submission.id)}, status=status.HTTP_200_OK)


@api_view(["POST"])
def internal_evaluation_result(request):
    token = request.headers.get("X-Internal-Token") or request.data.get("callbackToken")
    expected_token = getattr(settings, "CALLBACK_TOKEN", "default_secret_callback_token_123")

    if not token or token != expected_token:
        return Response({"error": "Invalid or missing token"}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = EvaluationCallbackSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    sub_id = data["submissionId"]

    try:
        submission = Submission.objects.get(id=sub_id)
    except (Submission.DoesNotExist, ValueError):
        return Response({"error": "Submission not found"}, status=status.HTTP_404_NOT_FOUND)

    evaluation_result = {
        "approved": data["approved"],
        "summary": data["summary"],
        "improvements": data["improvements"],
        "reasoning": data.get("reasoning"),
        "raw": data.get("rawOutput") or "",
        "evaluatedAt": timezone.now().isoformat(),
    }

    submission.apply_evaluation_result(
        evaluation_result=evaluation_result,
        approved=data["approved"],
        failed=data.get("failed", False),
    )
    submission.save()

    return Response(
        {
            "status": "ok",
            "id": str(submission.id),
            "approved": submission.approved,
            "submissionStatus": submission.status,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
def internal_health(request):
    return Response({"status": "ok", "service": "django"}, status=status.HTTP_200_OK)
