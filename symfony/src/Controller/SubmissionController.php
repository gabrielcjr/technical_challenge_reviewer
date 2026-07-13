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
    #[Route('/', name: 'home', methods: ['GET'])]
    public function home(ChallengeRepository $challengeRepo, SubmissionRepository $submissionRepo): Response
    {
        $challenges = $challengeRepo->findBy([], ['createdAt' => 'DESC']);
        $submissions = $submissionRepo->findRecent(20);

        return $this->render('submission/home.html.twig', [
            'challenges' => $challenges,
            'submissions' => $submissions,
        ]);
    }

    #[Route('/submissions/new', name: 'submission_new', methods: ['GET'])]
    public function newForm(ChallengeRepository $challengeRepo): Response
    {
        $challenges = $challengeRepo->findBy([], ['createdAt' => 'DESC']);

        return $this->render('submission/new.html.twig', [
            'challenges' => $challenges,
        ]);
    }

    #[Route('/submissions/{id}', name: 'submission_show', methods: ['GET'])]
    public function show(string $id, SubmissionRepository $repo): Response
    {
        $submission = $repo->find($id);

        if (!$submission) {
            throw $this->createNotFoundException('Submission not found');
        }

        // If request wants JSON, return JSON
        return $this->render('submission/show.html.twig', [
            'submission' => $submission,
        ]);
    }

    #[Route('/api/submissions', name: 'api_submission_list', methods: ['GET'])]
    public function apiList(SubmissionRepository $repo): JsonResponse
    {
        $submissions = $repo->findRecent(50);
        $data = array_map(fn(Submission $s) => $s->toArray(), $submissions);

        return $this->json($data);
    }

    #[Route('/api/submissions', name: 'api_submission_create', methods: ['POST'])]
    public function apiCreate(
        Request $request,
        ChallengeRepository $challengeRepo,
        EntityManagerInterface $em,
        MessageBusInterface $bus,
        ValidatorInterface $validator,
    ): Response {
        $isJson = str_contains($request->headers->get('Content-Type', ''), 'application/json') ||
                  $request->getContentTypeFormat() === 'json' ||
                  $request->isXmlHttpRequest() === false && $request->headers->get('Accept') === 'application/json' ||
                  $request->getContent() !== '' && json_validate($request->getContent());

        $data = [];
        if ($isJson || $request->getContent()) {
            $content = $request->getContent();
            if ($content && json_validate($content)) {
                $data = json_decode($content, true);
            } else {
                $data = $request->request->all();
                // fallback to POST params
                if (empty($data)) {
                    $data = $request->request->all();
                }
            }
        } else {
            $data = $request->request->all();
        }

        // Support form-encoded from Twig form
        $userName = $data['userName'] ?? $data['user_name'] ?? $request->request->get('userName');
        $githubRepoUrl = $data['githubRepoUrl'] ?? $data['github_repo_url'] ?? $request->request->get('githubRepoUrl');
        $challengeId = $data['challengeId'] ?? $request->request->get('challengeId') ?? null;
        $customChallengeText = $data['customChallengeText'] ?? $data['challengeText'] ?? $request->request->get('customChallengeText') ?? $request->request->get('challengeText') ?? null;

        if (!$userName) {
            $userName = $data['userName'] ?? null;
        }
        if (!$githubRepoUrl) {
            $githubRepoUrl = $data['githubRepoUrl'] ?? null;
        }

        // Validation for missing fields for API
        if (!$userName || !$githubRepoUrl) {
            // Try to handle form submission differently
            if ($request->request->has('userName') || $request->request->has('githubRepoUrl')) {
                $userName = $request->request->get('userName');
                $githubRepoUrl = $request->request->get('githubRepoUrl');
                $challengeId = $request->request->get('challengeId');
                $customChallengeText = $request->request->get('customChallengeText');
            } else {
                if ($isJson || str_starts_with($request->headers->get('Accept', ''), 'application/json')) {
                    return $this->json(['error' => 'userName and githubRepoUrl are required'], 400);
                }
            }
        }

        $submission = new Submission();
        $submission->setUserName((string) $userName);
        $submission->setGithubRepoUrl((string) $githubRepoUrl);

        if ($challengeId) {
            $challenge = $challengeRepo->find($challengeId);
            if (!$challenge) {
                return $this->json(['error' => 'Challenge not found'], 404);
            }
            $submission->setChallenge($challenge);
        } else {
            if (!$customChallengeText) {
                return $this->json(['error' => 'Either challengeId or customChallengeText must be provided'], 400);
            }
            $submission->setChallengeSnapshot((string) $customChallengeText);
        }

        // Validate
        $errors = $validator->validate($submission);
        if (count($errors) > 0) {
            $errorMessages = [];
            foreach ($errors as $error) {
                $errorMessages[$error->getPropertyPath()] = $error->getMessage();
            }

            if ($isJson || $request->headers->get('Accept') === 'application/json') {
                return $this->json(['errors' => $errorMessages], 400);
            }

            $this->addFlash('error', 'Validation failed: ' . implode(', ', $errorMessages));
            return $this->redirectToRoute('submission_new');
        }

        // Additional validation: github url must contain github.com
        if (!str_contains($submission->getGithubRepoUrl(), 'github.com')) {
            $msg = 'Repository URL must be a github.com URL';
            if ($isJson) {
                return $this->json(['error' => $msg], 400);
            }
            $this->addFlash('error', $msg);
            return $this->redirectToRoute('submission_new');
        }

        $em->persist($submission);
        $em->flush();

        // Dispatch async message
        $bus->dispatch(new EvaluateSubmissionMessage($submission->getId()->toRfc4122()));

        // If JSON request, return JSON
        if ($isJson || $request->headers->get('Accept') === 'application/json' || $request->getContentTypeFormat() === 'json' || $request->isXmlHttpRequest()) {
            // Check content-type specifically
            if (str_contains($request->headers->get('Content-Type', ''), 'application/json') || str_contains($request->headers->get('Accept', ''), 'application/json')) {
                return $this->json([
                    'id' => $submission->getId()->toRfc4122(),
                    'status' => $submission->getStatus()->value,
                    'checkUrl' => $this->generateUrl('api_submission_get', ['id' => $submission->getId()->toRfc4122()]),
                    'webUrl' => $this->generateUrl('submission_show', ['id' => $submission->getId()->toRfc4122()]),
                ], 201);
            }
        }

        // For form submission, handle both JSON and redirect
        if ($request->getContentTypeFormat() === 'json' || $request->headers->get('Content-Type') === 'application/json') {
            return $this->json([
                'id' => $submission->getId()->toRfc4122(),
                'status' => $submission->getStatus()->value,
            ], 201);
        }

        // Check if request is from browser form
        if ($request->request->count() > 0) {
            $this->addFlash('success', 'Submission created! Evaluation is pending.');
            return $this->redirectToRoute('submission_show', ['id' => $submission->getId()->toRfc4122()]);
        }

        return $this->json([
            'id' => $submission->getId()->toRfc4122(),
            'status' => $submission->getStatus()->value,
            'checkUrl' => $this->generateUrl('api_submission_get', ['id' => $submission->getId()->toRfc4122()]),
        ], 201);
    }

    #[Route('/api/submissions/{id}', name: 'api_submission_get', methods: ['GET'])]
    public function apiGet(string $id, SubmissionRepository $repo): JsonResponse
    {
        $submission = $repo->find($id);
        if (!$submission) {
            return $this->json(['error' => 'Not found'], 404);
        }

        return $this->json($submission->toArray());
    }

    #[Route('/api/submissions/{id}/retry', name: 'api_submission_retry', methods: ['POST'])]
    public function apiRetry(string $id, SubmissionRepository $repo, EntityManagerInterface $em, MessageBusInterface $bus): JsonResponse
    {
        $submission = $repo->find($id);
        if (!$submission) {
            return $this->json(['error' => 'Not found'], 404);
        }

        if ($submission->getStatus()->isFinal() && $submission->getStatus() !== SubmissionStatus::FAILED) {
            return $this->json(['error' => 'Submission already finalized, cannot retry'], 400);
        }

        $submission->setStatus(SubmissionStatus::PENDING);
        $submission->setProcessingLogs('Retry requested at ' . (new \DateTimeImmutable())->format('c'));
        $em->flush();

        $bus->dispatch(new EvaluateSubmissionMessage($submission->getId()->toRfc4122()));

        return $this->json(['status' => 'retry dispatched', 'id' => $submission->getId()->toRfc4122()]);
    }
}
