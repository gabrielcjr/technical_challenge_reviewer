<?php

namespace App\Controller;

use App\Enum\SubmissionStatus;
use App\Repository\SubmissionRepository;
use Doctrine\ORM\EntityManagerInterface;
use Psr\Log\LoggerInterface;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

class InternalCallbackController extends AbstractController
{
    #[Route('/api/internal/evaluation-result', name: 'internal_evaluation_result', methods: ['POST'])]
    public function evaluationResult(
        Request $request,
        SubmissionRepository $submissionRepo,
        EntityManagerInterface $em,
        LoggerInterface $logger,
    ): JsonResponse {
        $expectedToken = $this->getParameter('callback_token');

        $providedToken = $request->headers->get('X-Internal-Token') ?? $request->headers->get('X-Callback-Token') ?? ($request->toArray(false)['callbackToken'] ?? null);

        // Also check JSON body token
        $payload = [];
        $content = $request->getContent();
        if ($content) {
            $decoded = json_decode($content, true);
            if (is_array($decoded)) {
                $payload = $decoded;
                // Token could be in body as callbackToken
                if (!$providedToken && isset($decoded['callbackToken'])) {
                    $providedToken = $decoded['callbackToken'];
                }
                // Or token field might be inside? Use providedToken from body if header missing
                if (isset($decoded['token'])) {
                    $providedToken = $decoded['token'];
                }
            }
        }

        // Fallback to query param for simplicity in dev?
        if (!$providedToken) {
            $providedToken = $request->query->get('token') ?? $request->headers->get('Authorization');
            if ($providedToken && str_starts_with($providedToken, 'Bearer ')) {
                $providedToken = substr($providedToken, 7);
            }
        }

        // Token check - if expectedToken is set, enforce it
        if ($expectedToken && $expectedToken !== 'change_me' && $providedToken !== $expectedToken) {
            // For dev, allow if token is same as in body callbackToken? Already checked. Log warning but enforce?
            // Let's be lenient if token is empty in dev? No, enforce if expected is set and provided differs.
            // However, if providedToken is null, we check if request comes from internal docker network - allow in dev for easier testing
            if ($providedToken !== $expectedToken) {
                $logger->warning('Invalid callback token', [
                    'expected' => substr($expectedToken, 0, 5) . '...',
                    'provided' => $providedToken ? substr($providedToken, 0, 5) . '...' : 'null',
                ]);
                // In production you would return 401. For this challenge, we return 401
                return $this->json(['error' => 'Invalid token'], 401);
            }
        }

        $submissionId = $payload['submissionId'] ?? null;
        $approved = $payload['approved'] ?? null;
        $summary = $payload['summary'] ?? null;
        $improvements = $payload['improvements'] ?? [];
        $details = $payload['details'] ?? null;
        $rawOutput = $payload['rawOutput'] ?? $payload['raw'] ?? null;
        $reasoning = $payload['reasoning'] ?? null;

        if (!$submissionId) {
            return $this->json(['error' => 'submissionId required'], 400);
        }

        if ($approved === null) {
            return $this->json(['error' => 'approved field required'], 400);
        }

        $submission = $submissionRepo->find($submissionId);
        if (!$submission) {
            $logger->error('Submission not found for callback', ['id' => $submissionId]);
            return $this->json(['error' => 'Submission not found'], 404);
        }

        // Build evaluation result
        $evaluationResult = [
            'approved' => (bool) $approved,
            'summary' => $summary ?? ($approved ? 'Challenge approved' : 'Challenge not approved'),
            'improvements' => $improvements,
            'reasoning' => $reasoning ?? $rawOutput ?? $details ?? '',
            'raw' => $rawOutput ?? json_encode($payload),
            'evaluatedAt' => (new \DateTimeImmutable())->format(\DateTimeInterface::ATOM),
        ];

        $submission->setEvaluationResult($evaluationResult);
        $submission->setApproved((bool) $approved);
        $submission->setStatus($approved ? SubmissionStatus::APPROVED : SubmissionStatus::REJECTED);
        $submission->setProcessingLogs(
            ($submission->getProcessingLogs() ?? '') . "\n" . 'Evaluated at ' . (new \DateTimeImmutable())->format('c') . ' - approved: ' . ($approved ? 'yes' : 'no')
        );

        $em->flush();

        $logger->info('Submission evaluated', [
            'id' => $submissionId,
            'approved' => $approved,
        ]);

        return $this->json(['status' => 'ok', 'id' => $submissionId, 'approved' => $approved]);
    }

    #[Route('/api/internal/health', name: 'internal_health', methods: ['GET'])]
    public function health(): JsonResponse
    {
        return $this->json(['status' => 'ok', 'service' => 'symfony']);
    }
}
