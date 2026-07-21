<?php

namespace App\Controller;

use App\Entity\Submission;
use App\Enum\SubmissionStatus;
use App\Message\EvaluateSubmissionMessage;
use App\Repository\ChallengeRepository;
use App\Repository\SubmissionRepository;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Messenger\MessageBusInterface;
use Symfony\Component\Routing\Attribute\Route;
use Symfony\Component\Validator\Validator\ValidatorInterface;

class SubmissionController extends AbstractController
{
    private const HOME_RECENT_LIMIT = 20;
    private const API_RECENT_LIMIT = 50;
    private const GITHUB_DOMAIN = 'github.com';

    public function __construct(
        private readonly ValidatorInterface $validator,
        private readonly EntityManagerInterface $entityManager,
        private readonly MessageBusInterface $messageBus,
        private readonly ChallengeRepository $challengeRepository,
        private readonly SubmissionRepository $submissionRepository,
    ) {
    }

    #[Route('/', name: 'home', methods: ['GET'])]
    public function home(): Response
    {
        $challenges = $this->challengeRepository->findBy([], ['createdAt' => 'DESC']);
        $submissions = $this->submissionRepository->findRecent(self::HOME_RECENT_LIMIT);

        return $this->render('submission/home.html.twig', [
            'challenges' => $challenges,
            'submissions' => $submissions,
        ]);
    }

    #[Route('/submissions/new', name: 'submission_new', methods: ['GET'])]
    public function newForm(): Response
    {
        $challenges = $this->challengeRepository->findBy([], ['createdAt' => 'DESC']);

        return $this->render('submission/new.html.twig', [
            'challenges' => $challenges,
        ]);
    }

    #[Route('/submissions/{id}', name: 'submission_show', methods: ['GET'])]
    public function show(string $id): Response
    {
        $submission = $this->submissionRepository->find($id);

        if (!$submission) {
            throw $this->createNotFoundException('Submission not found');
        }

        return $this->render('submission/show.html.twig', [
            'submission' => $submission,
        ]);
    }

    #[Route('/api/submissions', name: 'api_submission_list', methods: ['GET'])]
    public function apiList(): JsonResponse
    {
        $submissions = $this->submissionRepository->findRecent(self::API_RECENT_LIMIT);
        $data = array_map(fn(Submission $s) => $s->toArray(), $submissions);

        return $this->json($data);
    }

    #[Route('/api/submissions', name: 'api_submission_create', methods: ['POST'])]
    public function apiCreate(Request $request): Response
    {
        $requestData = $this->parseRequestData($request);
        $fields = $this->extractSubmissionFields($request, $requestData);

        if (!$this->hasRequiredFields($fields)) {
            return $this->handleMissingFields($request);
        }

        return $this->createAndPersistSubmission($request, $fields);
    }

    #[Route('/api/submissions/{id}', name: 'api_submission_get', methods: ['GET'])]
    public function apiGet(string $id): JsonResponse
    {
        $submission = $this->submissionRepository->find($id);
        if (!$submission) {
            return $this->json(['error' => 'Not found'], 404);
        }

        return $this->json($submission->toArray());
    }

    #[Route('/api/submissions/{id}/retry', name: 'api_submission_retry', methods: ['POST'])]
    public function apiRetry(string $id): JsonResponse
    {
        $submission = $this->submissionRepository->find($id);
        if (!$submission) {
            return $this->json(['error' => 'Not found'], 404);
        }

        if (!$this->isRetryAllowed($submission)) {
            return $this->json(['error' => 'Submission already finalized, cannot retry'], 400);
        }

        $this->markForRetry($submission);
        $this->dispatchEvaluation($submission);

        return $this->json([
            'status' => 'retry dispatched',
            'id' => $submission->getIdAsString(),
        ]);
    }

    // --- Private helpers - each does one thing ---

    private function parseRequestData(Request $request): array
    {
        $content = $request->getContent();
        if ($content !== '' && json_validate($content)) {
            $decoded = json_decode($content, true);
            return is_array($decoded) ? $decoded : [];
        }

        return $request->request->all();
    }

    /**
     * Canonical field extraction - supports legacy snake_case for backward compatibility
     */
    private function extractSubmissionFields(Request $request, array $data): array
    {
        return [
            'userName' => $data['userName'] ?? $data['user_name'] ?? $request->request->get('userName'),
            'githubRepoUrl' => $data['githubRepoUrl'] ?? $data['github_repo_url'] ?? $request->request->get('githubRepoUrl'),
            'challengeId' => $data['challengeId'] ?? $request->request->get('challengeId'),
            'customChallengeText' => $data['customChallengeText'] ?? $data['challengeText'] ?? $request->request->get('customChallengeText') ?? $request->request->get('challengeText'),
        ];
    }

    private function hasRequiredFields(array $fields): bool
    {
        return !empty($fields['userName']) && !empty($fields['githubRepoUrl']);
    }

    private function handleMissingFields(Request $request): Response
    {
        if ($this->isJsonRequest($request)) {
            return $this->json(['error' => 'userName and githubRepoUrl are required'], 400);
        }

        $this->addFlash('error', 'userName and githubRepoUrl are required');
        return $this->redirectToRoute('submission_new');
    }

    private function createAndPersistSubmission(Request $request, array $fields): Response
    {
        $submission = new Submission();
        $submission->setUserName((string) $fields['userName']);
        $submission->setGithubRepoUrl((string) $fields['githubRepoUrl']);

        $challengeResolution = $this->resolveChallengeForSubmission($submission, $fields);
        if ($challengeResolution instanceof Response) {
            return $challengeResolution;
        }

        $validationResponse = $this->validateSubmission($request, $submission);
        if ($validationResponse !== null) {
            return $validationResponse;
        }

        $this->entityManager->persist($submission);
        $this->entityManager->flush();

        $this->dispatchEvaluation($submission);

        return $this->createSuccessResponse($request, $submission);
    }

    private function resolveChallengeForSubmission(Submission $submission, array $fields): ?Response
    {
        if (!empty($fields['challengeId'])) {
            $challenge = $this->challengeRepository->find($fields['challengeId']);
            if (!$challenge) {
                return $this->json(['error' => 'Challenge not found'], 404);
            }
            $submission->associateWithChallenge($challenge);
            return null;
        }

        if (empty($fields['customChallengeText'])) {
            return $this->json(['error' => 'Either challengeId or customChallengeText must be provided'], 400);
        }

        $submission->setChallengeSnapshot((string) $fields['customChallengeText']);
        return null;
    }

    private function validateSubmission(Request $request, Submission $submission): ?Response
    {
        $errors = $this->validator->validate($submission);
        if (count($errors) > 0) {
            return $this->handleValidationErrors($request, $errors);
        }

        if (!$this->isGithubUrlValid($submission->getGithubRepoUrl())) {
            return $this->handleInvalidGithubUrl($request);
        }

        return null;
    }

    private function handleValidationErrors(Request $request, $errors): Response
    {
        $errorMessages = [];
        foreach ($errors as $error) {
            $errorMessages[$error->getPropertyPath()] = $error->getMessage();
        }

        if ($this->isJsonRequest($request)) {
            return $this->json(['errors' => $errorMessages], 400);
        }

        $this->addFlash('error', 'Validation failed: ' . implode(', ', $errorMessages));
        return $this->redirectToRoute('submission_new');
    }

    private function handleInvalidGithubUrl(Request $request): Response
    {
        $message = 'Repository URL must be a github.com URL';
        if ($this->isJsonRequest($request)) {
            return $this->json(['error' => $message], 400);
        }

        $this->addFlash('error', $message);
        return $this->redirectToRoute('submission_new');
    }

    private function isGithubUrlValid(string $url): bool
    {
        return str_contains($url, self::GITHUB_DOMAIN);
    }

    private function createSuccessResponse(Request $request, Submission $submission): Response
    {
        $submissionId = $submission->getIdAsString();

        if ($this->isJsonRequest($request)) {
            return $this->json([
                'id' => $submissionId,
                'status' => $submission->getStatus()->value,
                'checkUrl' => $this->generateUrl('api_submission_get', ['id' => $submissionId]),
                'webUrl' => $this->generateUrl('submission_show', ['id' => $submissionId]),
            ], 201);
        }

        if ($request->request->count() > 0) {
            $this->addFlash('success', 'Submission created! Evaluation is pending.');
            return $this->redirectToRoute('submission_show', ['id' => $submissionId]);
        }

        return $this->json([
            'id' => $submissionId,
            'status' => $submission->getStatus()->value,
            'checkUrl' => $this->generateUrl('api_submission_get', ['id' => $submissionId]),
        ], 201);
    }

    private function isJsonRequest(Request $request): bool
    {
        $contentType = $request->headers->get('Content-Type', '');
        $accept = $request->headers->get('Accept', '');

        return str_contains($contentType, 'application/json')
            || str_contains($accept, 'application/json')
            || $request->getContentTypeFormat() === 'json';
    }

    private function isRetryAllowed(Submission $submission): bool
    {
        return $submission->canBeRetried();
    }

    private function markForRetry(Submission $submission): void
    {
        $submission->setStatus(SubmissionStatus::PENDING);
        $submission->appendProcessingLog('Retry requested');
        $this->entityManager->flush();
    }

    private function dispatchEvaluation(Submission $submission): void
    {
        $this->messageBus->dispatch(
            new EvaluateSubmissionMessage($submission->getIdAsString())
        );
    }
}
