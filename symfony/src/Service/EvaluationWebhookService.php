<?php

namespace App\Service;

use App\Entity\Submission;
use Psr\Log\LoggerInterface;
use Symfony\Contracts\HttpClient\HttpClientInterface;

final class EvaluationDispatchException extends \RuntimeException
{
}

class EvaluationWebhookService
{
    private const TIMEOUT_SECONDS = 10;
    private const HTTP_SUCCESS_MIN = 200;
    private const HTTP_SUCCESS_MAX = 299;

    private readonly EvaluationConfig $config;

    /**
     * Supports both new clean signature (config object) and legacy (3 strings) for backward compat.
     *
     * @param EvaluationConfig|string $configOrEvaluatorUrl
     */
    public function __construct(
        private readonly HttpClientInterface $httpClient,
        private readonly LoggerInterface $logger,
        EvaluationConfig|string $configOrEvaluatorUrl,
        string $callbackUrl = '',
        string $callbackToken = '',
    ) {
        if ($configOrEvaluatorUrl instanceof EvaluationConfig) {
            $this->config = $configOrEvaluatorUrl;
        } else {
            // Legacy: 3 strings provided
            $this->config = new EvaluationConfig(
                $configOrEvaluatorUrl,
                $callbackUrl,
                $callbackToken
            );
        }
    }

    public function dispatch(Submission $submission): void
    {
        $payload = $this->buildPayload($submission);
        $this->logDispatching($payload['submissionId']);
        $response = $this->sendEvaluationRequest($payload);
        $this->ensureSuccessfulResponse($response, $payload['submissionId']);
    }

    private function buildPayload(Submission $submission): array
    {
        return [
            'submissionId' => $submission->getIdAsString(),
            'githubRepoUrl' => $submission->getGithubRepoUrl(),
            'challengeText' => $submission->getChallengeSnapshot(),
            'callbackUrl' => $this->config->callbackUrl,
            'callbackToken' => $this->config->callbackToken,
        ];
    }

    private function logDispatching(string $submissionId): void
    {
        $this->logger->info('Dispatching evaluation webhook', [
            'submissionId' => $submissionId,
            'evaluatorUrl' => $this->config->evaluatorUrl,
        ]);
    }

    private function sendEvaluationRequest(array $payload)
    {
        return $this->httpClient->request('POST', $this->config->getEvaluatorEndpoint(), [
            'json' => $payload,
            'timeout' => self::TIMEOUT_SECONDS,
        ]);
    }

    private function ensureSuccessfulResponse($response, string $submissionId): void
    {
        $statusCode = $response->getStatusCode();

        $this->logger->info('Evaluation webhook sent', [
            'submissionId' => $submissionId,
            'statusCode' => $statusCode,
        ]);

        if (!$this->isSuccessStatus($statusCode)) {
            throw new EvaluationDispatchException(
                sprintf('Evaluator responded with status %d', $statusCode)
            );
        }
    }

    private function isSuccessStatus(int $statusCode): bool
    {
        return $statusCode >= self::HTTP_SUCCESS_MIN && $statusCode <= self::HTTP_SUCCESS_MAX;
    }
}
