<?php

namespace App\Controller;

use App\Dto\EvaluationCallbackPayload;
use App\Repository\SubmissionRepository;
use App\Service\CallbackAuthenticator;
use App\Service\CallbackAuthenticationException;
use Doctrine\ORM\EntityManagerInterface;
use Psr\Log\LoggerInterface;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

class InternalCallbackController extends AbstractController
{
    public function __construct(
        private readonly SubmissionRepository $submissionRepository,
        private readonly EntityManagerInterface $entityManager,
        private readonly LoggerInterface $logger,
        private readonly string $callbackToken,
    ) {
    }

    #[Route('/api/internal/evaluation-result', name: 'internal_evaluation_result', methods: ['POST'])]
    public function evaluationResult(Request $request): JsonResponse
    {
        try {
            $payload = $this->parsePayload($request);
            $authenticator = new CallbackAuthenticator($this->callbackToken, $this->logger);
            $providedToken = $authenticator->extractToken($request, $payload);
            $authenticator->authenticate($providedToken);

            $callbackData = EvaluationCallbackPayload::fromArray($payload);
            return $this->processEvaluation($callbackData);
        } catch (CallbackAuthenticationException $authException) {
            return $this->json(['error' => $authException->getMessage()], 401);
        } catch (\InvalidArgumentException $validationException) {
            return $this->json(['error' => $validationException->getMessage()], 400);
        } catch (\Exception $unexpectedException) {
            $this->logger->error('Unexpected error in callback', ['error' => $unexpectedException->getMessage()]);
            return $this->json(['error' => 'Internal error'], 500);
        }
    }

    #[Route('/api/internal/health', name: 'internal_health', methods: ['GET'])]
    public function health(): JsonResponse
    {
        return $this->json(['status' => 'ok', 'service' => 'symfony']);
    }

    private function parsePayload(Request $request): array
    {
        $content = $request->getContent();
        if ($content === '') {
            return [];
        }

        try {
            $data = $request->toArray(false);
            return is_array($data) ? $data : [];
        } catch (\Exception) {
            $decoded = json_decode($content, true);
            return is_array($decoded) ? $decoded : [];
        }
    }

    private function processEvaluation(EvaluationCallbackPayload $callbackData): JsonResponse
    {
        $submission = $this->submissionRepository->find($callbackData->submissionId);
        if (!$submission) {
            $this->logger->error('Submission not found for callback', ['id' => $callbackData->submissionId]);
            return $this->json(['error' => 'Submission not found'], 404);
        }

        $evaluationResult = $this->buildEvaluationResult($callbackData);
        $submission->applyEvaluationResult(
            $evaluationResult,
            $callbackData->approved,
            $callbackData->failed,
        );
        $this->entityManager->flush();

        $this->logger->info('Submission evaluated', [
            'id' => $callbackData->submissionId,
            'approved' => $callbackData->approved,
            'failed' => $callbackData->failed,
            'status' => $submission->getStatus()->value,
        ]);

        return $this->json([
            'status' => 'ok',
            'id' => $callbackData->submissionId,
            'approved' => $callbackData->approved,
            'submissionStatus' => $submission->getStatus()->value,
        ]);
    }

    private function buildEvaluationResult(EvaluationCallbackPayload $data): array
    {
        return [
            'approved' => $data->approved,
            'summary' => $data->summary,
            'improvements' => $data->improvements,
            'reasoning' => $data->reasoning,
            'raw' => $data->rawOutput ?? '',
            'evaluatedAt' => (new \DateTimeImmutable())->format(\DateTimeInterface::ATOM),
        ];
    }
}
